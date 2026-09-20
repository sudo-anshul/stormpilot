#!/usr/bin/env python3
"""Serve the workbench and isolate native experiments in worker processes."""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import gzip
import json
import mimetypes
import os
from pathlib import Path
import re
import signal
import shutil
import subprocess
import sys
import threading
from urllib.parse import urlparse
import uuid

from service.common import JOBS, ROOT, read_json, write_json
from service.present import catalog, normalize_config, model_view, config_from_native, number
from service.models import inspect_model, register_model
from service.archive import build_archive, build_evaluation_archive
from service.demo import install_demo

EXECUTOR = ThreadPoolExecutor(max_workers=2, thread_name_prefix="experiment")
PENDING: set[str] = set()
LOCK = threading.Lock()
ID = re.compile(r"^[a-f0-9]{16}$")
DEMO = None


def now():
    return datetime.now(timezone.utc).isoformat()


def run_worker(job_id, timeout_s=240):
    try:
        job_dir = JOBS / job_id
        request = read_json(job_dir / "request.json")
        worker_module = "service.evaluation_worker" if request.get("action") == "evaluate" else "service.worker"
        with (job_dir / "worker.log").open("w") as log:
            process = subprocess.Popen(
                [sys.executable, "-m", worker_module, job_id],
                cwd=ROOT, stdout=log, stderr=log, start_new_session=True,
            )
            try:
                returncode = process.wait(timeout=timeout_s)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait()
                raise
        state = read_json(job_dir / "status.json")
        if returncode and state["status"] != "failed":
            state.update(status="failed", phase="Engine stopped", error="The experiment worker stopped before completing its result. Retry the run.")
            write_json(job_dir / "status.json", state)
    except subprocess.TimeoutExpired:
        write_json(JOBS / job_id / "status.json", {"id": job_id, "status": "failed", "phase": "Time limit reached", "error": "The experiment exceeded its execution limit. Reduce the search budget and retry."})
    except Exception:
        write_json(JOBS / job_id / "status.json", {"id": job_id, "status": "failed", "phase": "Experiment failed", "error": "The experiment could not complete. Check local worker logs and retry."})
    finally:
        with LOCK:
            PENDING.discard(job_id)


def launch_job(job_id, request, state):
    """Initialize all job kinds without retaining a failed queue reservation."""
    folder = JOBS / job_id
    created = False
    try:
        if shutil.disk_usage(ROOT).free < 128 * 1024 * 1024:
            raise RuntimeError("The server needs at least 128 MiB free space for a new evidence packet.")
        folder.mkdir(parents=True)
        created = True
        write_json(folder / "request.json", request)
        write_json(folder / "status.json", state)
    except Exception:
        with LOCK:
            PENDING.discard(job_id)
        if created:
            shutil.rmtree(folder, ignore_errors=True)
        raise
    try:
        EXECUTOR.submit(run_worker, job_id)
    except Exception:
        with LOCK:
            PENDING.discard(job_id)
        # Cloud submission can fail after real computation while persisting its
        # result. Preserve completed evidence; only unstarted jobs are relabeled.
        try:
            recorded = read_json(folder / "status.json")
            if recorded.get("status") == "queued":
                recorded.update(status="failed", phase="Not started", error="The experiment could not be started. Retry shortly.")
                write_json(folder / "status.json", recorded)
        except (OSError, ValueError):
            pass
        raise
    return state


def create_job(config, replay_of=None):
    normalized = normalize_config(config)
    if shutil.disk_usage(ROOT).free < 128 * 1024 * 1024:
        raise RuntimeError("The server needs at least 128 MiB free space for a new evidence packet.")
    with LOCK:
        if len(PENDING) >= 4:
            raise RuntimeError("Four experiments are already queued. Wait for one to finish.")
        job_id = uuid.uuid4().hex[:16]
        PENDING.add(job_id)
    request = {"id": job_id, "config": normalized, "created_at": now(), "replay_of": replay_of}
    state = {"id": job_id, "status": "queued", "phase": "Queued", "message": "Waiting for an isolated simulation worker.", "created_at": now()}
    return launch_job(job_id, request, state)


def create_evaluation(job_id):
    folder = JOBS / job_id
    if not (folder / "packet.json").is_file() or read_json(folder / "status.json")["status"] != "completed":
        raise ValueError("Complete the investigation before evaluating its alternative.")
    packet = read_json(folder / "packet.json")
    pair_ids = packet.get("witness", {}).get("run_id") if packet.get("witness") else None
    reference = next((r for r in packet["runs"] if r["run_id"] == pair_ids), None)
    reference = reference or next((r for r in packet["runs"] if r["role"] == "stress"), None)
    candidate = next((r for r in packet["runs"] if r["role"] == "fallback"), None)
    if not reference or not candidate or len(reference["active_fault_ids"]) != 2:
        raise ValueError("Robustness evaluation requires a recorded two-condition case and an alternative policy.")
    selected = [f for f in packet["request"]["faults"] if f["id"] in reference["active_fault_ids"]]
    if len(selected) != 2 or sorted(f["type"] for f in selected) not in (["sensor_bias", "valve_stuck"], ["sensor_dropout", "valve_stuck"]):
        raise ValueError("Select one recorded sensor fault and one valve fault for this robustness suite.")
    if packet["request"]["test_contract"]["metric"] != "flood_volume_m3":
        raise ValueError("This robustness suite currently evaluates overflow-volume contracts.")
    original = read_json(folder / "request.json")
    with LOCK:
        if len(PENDING) >= 4:
            raise RuntimeError("Four experiments are already queued. Wait for one to finish.")
        child_id = uuid.uuid4().hex[:16]
        PENDING.add(child_id)
    request = {"id": child_id, "action": "evaluate", "source_job_id": job_id,
               "created_at": now(), "config": original["config"], "reference_run_id": reference["run_id"],
               "candidate_run_id": candidate["run_id"], "pair_ids": reference["active_fault_ids"]}
    state = {"id": child_id, "kind": "evaluation", "status": "queued", "phase": "Queued",
             "created_at": now(), "message": "The recorded model, fault pair and policies are fixed for this robustness suite."}
    return launch_job(child_id, request, state)


def create_repair(job_id, settings):
    folder = JOBS / job_id
    if not (folder / "packet.json").is_file() or read_json(folder / "status.json")["status"] != "completed":
        raise ValueError("Complete the investigation before searching for an alternative.")
    packet = read_json(folder / "packet.json")
    witness = packet.get("witness") or {}
    stress = next((r for r in packet["runs"] if r["run_id"] == witness.get("run_id")), None)
    stress = stress or next((r for r in packet["runs"] if r["role"] == "stress"), None)
    if not stress or len(stress["active_fault_ids"]) != 2 or packet["request"]["test_contract"]["metric"] != "flood_volume_m3":
        raise ValueError("Repair search currently requires a recorded two-condition overflow-volume case.")
    if set(settings) - {"controller_id", "target_scales", "balance_gains", "jump_thresholds_m", "correction_fractions", "budget"}:
        raise ValueError("Unknown repair search field.")
    declared = dict(settings)
    if declared.get("controller_id", "plausible_depth") not in ("plausible_depth", "balanced_flow"):
        raise ValueError("Choose a supported repair controller family.")
    for field, low, high in (("target_scales", 0.5, 1.5), ("balance_gains", 0, 8),
                             ("jump_thresholds_m", 0.1, 2), ("correction_fractions", 0, 1)):
        if field not in declared:
            continue
        if not isinstance(declared[field], list) or not 1 <= len(declared[field]) <= 8:
            raise ValueError(f"{field} needs 1–8 candidate values.")
        declared[field] = [number(v, field, low, high) for v in declared[field]]
        if len(set(declared[field])) != len(declared[field]):
            raise ValueError("Repair candidate values must be unique.")
    budget = number(declared.get("budget", 120), "Repair call budget", 8, 300)
    if budget != int(budget):
        raise ValueError("Repair call budget must be a whole number.")
    declared["budget"] = int(budget)
    native = {**packet["request"], "faults": [f for f in packet["request"]["faults"] if f["id"] in stress["active_fault_ids"]], "repair": declared}
    child_config = config_from_native(native)
    with LOCK:
        if len(PENDING) >= 4:
            raise RuntimeError("Four experiments are already queued. Wait for one to finish.")
        child_id = uuid.uuid4().hex[:16]
        PENDING.add(child_id)
    request = {"id": child_id, "action": "repair", "source_job_id": job_id,
               "created_at": now(), "config": child_config, "native_request": native}
    state = {"id": child_id, "status": "queued", "phase": "Queued", "created_at": now(),
             "message": "The fault pair is fixed; candidate controls will be tested against the declared guard limits."}
    return launch_job(child_id, request, state)


class Handler(BaseHTTPRequestHandler):
    server_version = "StormPilot"

    def log_message(self, fmt, *args):
        if "/api/jobs/" not in str(args[0]):
            super().log_message(fmt, *args)

    def send_json(self, value, status=200):
        body = json.dumps(value, separators=(",", ":"), allow_nan=False).encode()
        compressed = len(body) > 1024 and "gzip" in self.headers.get("Accept-Encoding", "")
        if compressed:
            body = gzip.compress(body, compresslevel=4, mtime=0)
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Vary", "Accept-Encoding")
        if compressed:
            self.send_header("Content-Encoding", "gzip")
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def error(self, message, status=400):
        self.send_json({"error": message}, status)

    def send_file(self, path, content_type=None, download=None):
        self.send_response(200)
        self.send_header("Content-Type", content_type or mimetypes.guess_type(path.name)[0] or "application/octet-stream")
        self.send_header("Content-Length", str(path.stat().st_size))
        self.send_header("X-Content-Type-Options", "nosniff")
        if download:
            self.send_header("Content-Disposition", f'attachment; filename="{download}"')
        self.end_headers()
        with path.open("rb") as f:
            while chunk := f.read(65536):
                self.wfile.write(chunk)

    def do_GET(self):
        path = urlparse(self.path).path
        try:
            if path == "/api/health":
                return self.send_json({"status": "ok", "engine_ready": (ROOT / "engine" / "build" / "build.json").exists(), "version": "0.1.0"})
            if path == "/api/catalog":
                return self.send_json(catalog())
            if path == "/api/demo":
                if DEMO is None:
                    return self.error("No recorded investigation is available yet. Run a fresh experiment.", 404)
                return self.send_json(DEMO)
            if path in ("/api/evaluation", "/api/evaluation/phase2"):
                report = ROOT / "evaluation" / "report.json" if path == "/api/evaluation" else ROOT / "evaluation" / "phase2" / "report.json"
                if not report.is_file():
                    return self.error("The recorded benchmark evaluation is not available yet.", 404)
                return self.send_json(read_json(report))
            if path in ("/api/evaluation/export", "/api/evaluation/phase2/export"):
                phase = "phase2" if path == "/api/evaluation/phase2/export" else "phase1"
                archive = ROOT / "evaluation" / f"{phase}-evidence.zip"
                if not archive.is_file():
                    return self.error("This frozen evaluation archive is not available yet.", 404)
                return self.send_file(archive, "application/zip", f"stormpilot-{phase}-evidence.zip")
            if path == "/api/jobs":
                records = []
                for p in sorted(JOBS.glob("*/status.json"), key=lambda p: p.stat().st_mtime, reverse=True)[:20]:
                    records.append(read_json(p))
                return self.send_json({"jobs": records})
            parts = path.strip("/").split("/")
            if len(parts) >= 3 and parts[0] == "api" and parts[1] in ("jobs", "evaluations") and ID.fullmatch(parts[2]):
                folder = JOBS / parts[2]
                if not folder.exists():
                    return self.error("This run is not available on this server.", 404)
                if len(parts) == 3:
                    return self.send_json(read_json(folder / "status.json"))
                if len(parts) == 4 and parts[3] == "result":
                    result = folder / ("report.json" if parts[1] == "evaluations" else "view.json")
                    if not result.exists():
                        return self.error("This run has not produced a result yet.", 409)
                    return self.send_json(read_json(result))
                if len(parts) == 4 and parts[3] == "export":
                    if parts[1] == "evaluations":
                        if not (folder / "report.json").exists() or read_json(folder / "status.json")["status"] != "completed":
                            return self.error("Finish the robustness evaluation before exporting it.", 409)
                        archive = folder / "evidence.zip"
                        if not archive.exists():
                            source_id = read_json(folder / "request.json")["source_job_id"]
                            archive = build_evaluation_archive(folder, JOBS / source_id)
                        return self.send_file(archive, "application/zip", f"stormpilot-robustness-{parts[2]}.zip")
                    if not (folder / "packet.json").exists() or read_json(folder / "status.json")["status"] != "completed":
                        return self.error("Finish the experiment before exporting its evidence.", 409)
                    archive = folder / "evidence.zip"
                    if not archive.exists():
                        archive = build_archive(folder)
                    return self.send_file(archive, "application/zip", f"stormpilot-{parts[2]}.zip")
            if path.startswith("/api/"):
                return self.error("Unknown API endpoint.", 404)
            dist = (ROOT / "web" / "dist").resolve()
            asset = (dist / path.lstrip("/")).resolve()
            if not asset.is_relative_to(dist):
                return self.error("Invalid path.", 403)
            if asset.is_file():
                return self.send_file(asset)
            if (dist / "index.html").exists():
                return self.send_file(dist / "index.html", "text/html; charset=utf-8")
            return self.error("Frontend has not been built. Run npm run build, or use the Vite development server.", 503)
        except (BrokenPipeError, ConnectionResetError):
            return
        except Exception as exc:
            self.error(f"The server could not complete this request: {str(exc)[:180]}", 500)

    def do_POST(self):
        path = urlparse(self.path).path
        origin = self.headers.get("Origin")
        if origin:
            origin_host = urlparse(origin).netloc
            allowed = {self.headers.get("Host"), "127.0.0.1:5173", "localhost:5173"}
            if origin_host not in allowed:
                return self.error("Cross-origin requests are not accepted.", 403)
        try:
            length = int(self.headers.get("Content-Length", "0"))
            limit = 300000 if path == "/api/models/inspect" else 16384
            if length > limit or length < 0:
                return self.error("The request is too large.", 413)
            data = json.loads(self.rfile.read(length) or b"{}")
            if not isinstance(data, dict):
                return self.error("An experiment must be a JSON object.")
            if path == "/api/models/inspect":
                return self.send_json(inspect_model(data))
            if path == "/api/models":
                return self.send_json({"model": model_view(register_model(data))}, 201)
            if path == "/api/jobs":
                return self.send_json(create_job(data), 202)
            parts = path.strip("/").split("/")
            if len(parts) == 4 and parts[:2] == ["api", "jobs"] and ID.fullmatch(parts[2]) and parts[3] == "evaluate":
                return self.send_json(create_evaluation(parts[2]), 202)
            if len(parts) == 4 and parts[:2] == ["api", "jobs"] and ID.fullmatch(parts[2]) and parts[3] == "repair":
                return self.send_json(create_repair(parts[2], data), 202)
            if len(parts) == 4 and parts[:2] == ["api", "jobs"] and ID.fullmatch(parts[2]) and parts[3] == "replay":
                folder = JOBS / parts[2]
                if not (folder / "view.json").exists():
                    return self.error("Complete this run before replaying it.", 409)
                original = read_json(folder / "request.json")
                return self.send_json(create_job(original["config"], replay_of=parts[2]), 202)
            return self.error("Unknown API endpoint.", 404)
        except (ValueError, KeyError, TypeError) as exc:
            return self.error(str(exc)[:200], 400)
        except RuntimeError as exc:
            return self.error(str(exc), 429)


def main():
    global DEMO
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=int(os.environ.get("PORT", 8787)))
    args = parser.parse_args()
    JOBS.mkdir(parents=True, exist_ok=True)
    # Runs interrupted by a previous server shutdown must not remain falsely active.
    for path in JOBS.glob("*/status.json"):
        state = read_json(path)
        if state.get("status") in ("queued", "running"):
            state.update(status="failed", phase="Interrupted", error="The server restarted before this run completed. Start a new run.")
            write_json(path, state)
    DEMO = install_demo()
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"StormPilot running at http://{args.host}:{args.port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.shutdown()


if __name__ == "__main__":
    main()
