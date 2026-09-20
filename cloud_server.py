#!/usr/bin/env python3
"""Vercel container entrypoint with active-request compute and durable evidence."""
from http.server import ThreadingHTTPServer
from contextlib import contextmanager
import io
import json
import os
import subprocess
import threading
from urllib.parse import urlparse

import server
from service import cloud_storage
from service.common import JOBS, ROOT, read_json, write_json
from service.demo import install_demo
from service.models import TOKEN, MODEL_ID


class CapacityUnavailable(RuntimeError):
    pass


class ActiveRequestExecutor:
    slots = threading.Semaphore(2)

    def __init__(self):
        self.admission = threading.local()

    @contextmanager
    def reserve(self):
        if getattr(self.admission, "reserved", False):
            yield
            return
        if not self.slots.acquire(blocking=False):
            raise CapacityUnavailable("Two experiments are already active. This run was not started; retry after one finishes.")
        self.admission.reserved = True
        try:
            yield
        finally:
            self.admission.reserved = False
            self.slots.release()

    @staticmethod
    def reject(job_id, message):
        try:
            path = JOBS / job_id / "status.json"
            state = read_json(path) if path.exists() else {"id": job_id}
            state.update(status="failed", phase="Not started", error=message, message=message)
            write_json(path, state)
        finally:
            with server.LOCK:
                server.PENDING.discard(job_id)
        raise RuntimeError(message)

    def submit(self, function, job_id):
        acquired_here = not getattr(self.admission, "reserved", False)
        if acquired_here and not self.slots.acquire(blocking=False):
            return self.reject(job_id, "Two experiments are already active. This run was not started; retry after one finishes.")
        try:
            try:
                compute_timeout = cloud_storage.bounded_timeout(180, reserve=30)
            except RuntimeError as exc:
                return self.reject(job_id, str(exc))
            function(job_id, timeout_s=compute_timeout)
            # Retry persistence once without rerunning the native experiment.
            # Immutable uploads verify/reuse bytes from the first attempt.
            for attempt in range(2):
                try:
                    cloud_storage.save_job(job_id)
                    break
                except (RuntimeError, subprocess.TimeoutExpired):
                    if attempt:
                        raise
        finally:
            with server.LOCK:
                server.PENDING.discard(job_id)
            if acquired_here:
                self.slots.release()


server.EXECUTOR.shutdown(wait=False)
server.EXECUTOR = ActiveRequestExecutor()


class Handler(server.Handler):
    def do_GET(self):
        with cloud_storage.request_budget(270):
            return self._cloud_get()

    def _cloud_get(self):
        path = urlparse(self.path).path
        parts = path.strip("/").split("/")
        try:
            if path in ("/api/evaluation/export", "/api/evaluation/phase2/export"):
                phase = "phase2" if path == "/api/evaluation/phase2/export" else "phase1"
                archive = ROOT / "evaluation" / f"{phase}-evidence.zip"
                if not archive.is_file():
                    return self.error("The fixed evaluation archive is not available yet.", 404)
                published = cloud_storage.publish_frozen_archive(archive, phase)
                self.send_response(302)
                self.send_header("Location", published["url"])
                self.send_header("X-Artifact-SHA256", published["sha256"])
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                return
            if path == "/api/catalog":
                cloud_storage.load_models()
            if len(parts) >= 3 and parts[0] == "api" and parts[1] in ("jobs", "evaluations") and server.ID.fullmatch(parts[2]):
                job_id = parts[2]
                local_demo = server.DEMO and job_id == server.DEMO["id"]
                if not local_demo and not cloud_storage.load_job(job_id):
                    return self.error("This recorded run is not available.", 404)
                if len(parts) == 4 and parts[3] == "export":
                    status = read_json(JOBS / job_id / "status.json")
                    if status["status"] != "completed":
                        return self.error("Complete this run before exporting its evidence.", 409)
                    if local_demo:
                        # The fixture is immutable and must be published once
                        # before its direct signed Blob download is available.
                        manifest = cloud_storage.call("get_json", key=cloud_storage.PREFIX + f"jobs/{job_id}/complete.json")
                        if manifest is None:
                            cloud_storage.save_job(job_id, prune=False)
                    download = cloud_storage.download_url(job_id)
                    self.send_response(302)
                    self.send_header("Location", download)
                    self.send_header("Cache-Control", "no-store")
                    self.end_headers()
                    return
            return super().do_GET()
        except Exception as exc:
            return self.error(str(exc)[:300], 503)

    def do_POST(self):
        with cloud_storage.request_budget(270):
            return self._cloud_post()

    def _cloud_post(self):
        path = urlparse(self.path).path
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            return self.error("Invalid request length.", 400)
        if not 0 <= length <= 300000:
            return self.error("The request is too large.", 413)
        body = self.rfile.read(length)
        self.rfile = io.BytesIO(body)
        try:
            payload = json.loads(body or b"{}")
            if not isinstance(payload, dict):
                return self.error("The request must be a JSON object.")
            parts = path.strip("/").split("/")
            dependent = len(parts) == 4 and parts[:2] == ["api", "jobs"] and server.ID.fullmatch(parts[2]) and parts[3] in ("repair", "evaluate", "replay")
            if path == "/api/jobs" or dependent:
                # Reserve before downloading a source or waiting for its lease.
                with server.EXECUTOR.reserve():
                    return self._dispatch_post(path, parts, payload, dependent)
            return self._dispatch_post(path, parts, payload, False)
        except CapacityUnavailable as exc:
            return self.error(str(exc), 429)
        except (ValueError, TypeError) as exc:
            return self.error(str(exc)[:200], 400)
        except Exception as exc:
            return self.error(str(exc)[:300], 503)

    def _dispatch_post(self, path, parts, payload, dependent):
        if path == "/api/jobs":
            model_id = payload.get("model_id", "")
            if isinstance(model_id, str) and MODEL_ID.fullmatch(model_id):
                cloud_storage.load_model(model_id)
        if path == "/api/models":
            token = payload.get("token", "")
            if isinstance(token, str) and TOKEN.fullmatch(token):
                cloud_storage.load_draft(token)
        if dependent:
            local_demo = server.DEMO and parts[2] == server.DEMO["id"]
            with cloud_storage.source_lease(parts[2], preserve=bool(local_demo)):
                installed_source = local_demo and (JOBS / parts[2] / "packet.json").is_file()
                if not installed_source and not cloud_storage.load_job(parts[2], full=True):
                    return self.error("The source investigation is not available.", 404)
                source_request = read_json(JOBS / parts[2] / "request.json")
                model_id = source_request.get("config", {}).get("model_id", "")
                if isinstance(model_id, str) and MODEL_ID.fullmatch(model_id):
                    cloud_storage.load_model(model_id)
                return super().do_POST()
        return super().do_POST()

    def send_json(self, value, status=200):
        path = urlparse(self.path).path
        if self.command == "POST" and status < 300 and isinstance(value, dict):
            if path == "/api/models/inspect" and "token" in value:
                cloud_storage.save_draft(value["token"])
            elif path == "/api/models" and "model" in value:
                cloud_storage.save_model(value["model"]["id"])
        return super().send_json(value, status)


def main():
    JOBS.mkdir(parents=True, exist_ok=True)
    server.DEMO = install_demo()
    port = int(os.environ.get("PORT", "8000"))
    http = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    print(f"StormPilot cloud runtime listening on {port}", flush=True)
    http.serve_forever()


if __name__ == "__main__":
    main()
