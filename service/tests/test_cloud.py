"""Cloud boundary failure injection; no native runs or remote storage writes."""
from concurrent.futures import ThreadPoolExecutor
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
import json
import os
from pathlib import Path
import tempfile
import subprocess
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import server
import cloud_server
from service import cloud_storage
from service.common import read_json, write_json

REAL_STORAGE_CALL = cloud_storage.call


class FakeBlob:
    def __init__(self):
        self.objects = {}
        self.fail_once = None
        self.operations = []

    def __call__(self, action, **args):
        key = args.get("key", "")
        self.operations.append((action, key))
        if action == "get_json":
            return json.loads(self.objects[key]) if key in self.objects else None
        if action == "get_file":
            if key not in self.objects:
                return None
            Path(args["path"]).write_bytes(self.objects[key])
            return {"path": args["path"]}
        if action in ("put_file", "put_json"):
            if self.fail_once and key.endswith(self.fail_once):
                self.fail_once = None
                raise RuntimeError("Injected transient upload failure")
            content = Path(args["path"]).read_bytes() if action == "put_file" else json.dumps(args["value"]).encode()
            if key in self.objects and self.objects[key] != content:
                raise RuntimeError("Immutable stored bytes differ")
            self.objects[key] = content
            return {"pathname": key}
        if action == "signed_download":
            return {"url": "https://download.example/" + key}
        if action == "list":
            paths = sorted(key for key in self.objects if key.startswith(args["prefix"]))
            start = int(args.get("cursor") or 0)
            end = start + args.get("limit", 25)
            more = end < len(paths)
            return {"paths": paths[start:end], "has_more": more, "cursor": str(end) if more else None}
        raise AssertionError(action)


class CloudStorageTests(unittest.TestCase):
    def setUp(self):
        work = Path(__file__).resolve().parents[2] / "work"
        work.mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(prefix="cloud-tests-", dir=work)
        self.jobs = Path(self.temp.name) / "jobs"
        self.jobs.mkdir()
        self.job_id = "00000000000000ab"
        self.folder = self.jobs / self.job_id
        self.folder.mkdir()
        self.blob = FakeBlob()
        self.registry = Path(self.temp.name) / "models"
        self.patches = [patch.object(cloud_storage, "JOBS", self.jobs), patch.object(cloud_storage, "call", self.blob),
                        patch.object(cloud_storage, "REGISTRY", self.registry),
                        patch.object(cloud_server, "JOBS", self.jobs), patch.object(server, "PENDING", set())]
        for item in self.patches:
            item.start()
        write_json(self.folder / "status.json", {"id": self.job_id, "status": "completed"})
        write_json(self.folder / "request.json", {"id": self.job_id, "config": {}})
        write_json(self.folder / "view.json", {"id": self.job_id, "finding": "recorded"})
        write_json(self.folder / "packet.json", {"proof": "exact recorded source"})
        (self.folder / "evidence.zip").write_bytes(b"recorded export bytes")

    def tearDown(self):
        for item in reversed(self.patches):
            item.stop()
        self.temp.cleanup()

    def test_retry_after_each_publication_stage_preserves_the_complete_result(self):
        for stage in ("-workspace.zip", "-evidence.zip", "complete.json"):
            with self.subTest(stage=stage):
                self.blob.objects.clear()
                self.blob.fail_once = stage
                with self.assertRaisesRegex(RuntimeError, "Injected"):
                    cloud_storage.save_job(self.job_id, prune=False)
                manifest = cloud_storage.save_job(self.job_id, prune=False)
                self.assertEqual(manifest["schema_version"], "stormpilot.cloud-completion.v2")
                for artifact in manifest["artifacts"].values():
                    self.assertIn(artifact["key"], self.blob.objects)
                self.assertEqual(len(self.blob.objects), 3)

    def test_active_request_retries_persistence_without_repeating_compute(self):
        for failure in (RuntimeError("transient"), subprocess.TimeoutExpired("storage", 90)):
            with self.subTest(failure=type(failure).__name__):
                computed = []
                with patch.object(cloud_storage, "save_job", side_effect=[failure, {}]) as save:
                    cloud_server.ActiveRequestExecutor().submit(lambda job, **kwargs: computed.append(job), self.job_id)
                self.assertEqual(computed, [self.job_id])
                self.assertEqual(save.call_count, 2)

    def test_overload_starts_no_compute_and_clears_queued_job(self):
        executor = cloud_server.ActiveRequestExecutor()
        executor.slots = threading.Semaphore(0)
        server.PENDING.add(self.job_id)
        write_json(self.folder / "status.json", {"id": self.job_id, "status": "queued"})
        with patch.object(cloud_storage, "save_job") as save:
            called = []
            with self.assertRaisesRegex(RuntimeError, "Two experiments"):
                executor.submit(lambda *args, **kwargs: called.append(args), self.job_id)
            self.assertEqual(called, [])
            save.assert_not_called()
        self.assertNotIn(self.job_id, server.PENDING)
        self.assertEqual(read_json(self.folder / "status.json")["status"], "failed")

    def test_reserved_capacity_is_reused_by_submit_and_released(self):
        executor = cloud_server.ActiveRequestExecutor()
        executor.slots = threading.Semaphore(1)
        called = []
        with patch.object(cloud_storage, "save_job", return_value={}):
            with executor.reserve():
                executor.submit(lambda job, **kwargs: called.append(job), self.job_id)
                self.assertFalse(executor.slots.acquire(blocking=False))
        self.assertEqual(called, [self.job_id])
        self.assertTrue(executor.slots.acquire(blocking=False))
        executor.slots.release()

    def test_initialization_failure_releases_pending_reservation(self):
        identifier = "00000000000000dd"
        for failure_point in ("mkdir", "write"):
            with self.subTest(failure_point=failure_point):
                server.PENDING.clear()
                server.PENDING.add("unrelated")
                target = "pathlib.Path.mkdir" if failure_point == "mkdir" else "server.write_json"
                with patch.object(server, "JOBS", self.jobs), \
                     patch.object(server, "normalize_config", return_value={}), \
                     patch("server.uuid.uuid4", return_value=SimpleNamespace(hex=identifier + "0" * 16)), \
                     patch("server.shutil.disk_usage", return_value=SimpleNamespace(free=1024 ** 3)), \
                     patch.object(server, "EXECUTOR", SimpleNamespace(submit=Mock())) as executor, \
                     patch(target, side_effect=OSError("injected disk error")):
                    with self.assertRaisesRegex(OSError, "injected disk"):
                        server.create_job({})
                    executor.submit.assert_not_called()
                self.assertEqual(server.PENDING, {"unrelated"})
                self.assertFalse((self.jobs / identifier).exists())

    def test_frozen_archive_is_published_once_per_hash(self):
        archive = Path(self.temp.name) / "phase1-evidence.zip"
        archive.write_bytes(b"frozen complete proof")
        first = cloud_storage.publish_frozen_archive(archive, "phase1")
        second = cloud_storage.publish_frozen_archive(archive, "phase1")
        self.assertEqual(first, second)
        self.assertIn(first["sha256"], first["key"])
        self.assertEqual(sum(action == "put_file" for action, _ in self.blob.operations), 1)
        self.assertEqual(sum(action == "signed_download" for action, _ in self.blob.operations), 2)

    def test_frozen_archive_recovers_from_pointer_publication_failure(self):
        archive = Path(self.temp.name) / "phase2-evidence.zip"
        archive.write_bytes(b"second frozen proof")
        self.blob.fail_once = "complete.json"
        with self.assertRaisesRegex(RuntimeError, "Injected"):
            cloud_storage.publish_frozen_archive(archive, "phase2")
        published = cloud_storage.publish_frozen_archive(archive, "phase2")
        self.assertIn(published["key"], self.blob.objects)
        self.assertEqual(len(self.blob.objects), 2)

    def test_storage_timeout_uses_remaining_shared_request_budget(self):
        clock = [1000.0]
        response = SimpleNamespace(returncode=0, stdout="{}", stderr="")
        with patch("service.cloud_storage.time.monotonic", side_effect=lambda: clock[0]), \
             patch("service.cloud_storage.subprocess.run", return_value=response) as run:
            with cloud_storage.request_budget(270):
                clock[0] += 250
                REAL_STORAGE_CALL("get_json", key="test")
                self.assertEqual(run.call_args.kwargs["timeout"], 20)
                clock[0] += 21
                with self.assertRaisesRegex(RuntimeError, "cloud time limit"):
                    REAL_STORAGE_CALL("get_json", key="test")
                self.assertEqual(run.call_count, 1)
        self.assertIsNone(cloud_storage.remaining_seconds())

    def test_compute_cap_reserves_storage_time_and_rejects_expired_requests(self):
        executor = cloud_server.ActiveRequestExecutor()
        limits = []
        with patch.object(cloud_storage, "save_job", return_value={}):
            with cloud_storage.request_budget(270):
                executor.submit(lambda job, timeout_s: limits.append(timeout_s), self.job_id)
            with cloud_storage.request_budget(100):
                executor.submit(lambda job, timeout_s: limits.append(timeout_s), self.job_id)
            server.PENDING.add(self.job_id)
            with cloud_storage.request_budget(20):
                with self.assertRaisesRegex(RuntimeError, "cloud time limit"):
                    executor.submit(lambda job, timeout_s: limits.append(timeout_s), self.job_id)
        self.assertEqual(limits[0], 180)
        self.assertLessEqual(limits[1], 70)
        self.assertGreater(limits[1], 69)
        self.assertEqual(len(limits), 2)
        self.assertNotIn(self.job_id, server.PENDING)

    def test_worker_timeout_is_cloud_overridable_and_local_default_remains_240(self):
        waits = []
        process = SimpleNamespace(wait=lambda **kwargs: waits.append(kwargs["timeout"]) or 0)
        with patch.object(server, "JOBS", self.jobs), patch("server.subprocess.Popen", return_value=process):
            server.run_worker(self.job_id, timeout_s=180)
            server.run_worker(self.job_id)
        self.assertEqual(waits, [180, 240])

    def test_source_lease_serializes_dependents_and_prunes_only_after_use(self):
        cloud_storage.save_job(self.job_id)
        first_inside, release_first, second_attempting, second_inside = (threading.Event() for _ in range(4))
        events = []
        def first():
            with cloud_storage.source_lease(self.job_id):
                self.assertTrue(cloud_storage.load_job(self.job_id, full=True))
                events.append("first-enter")
                first_inside.set()
                self.assertTrue(release_first.wait(timeout=3))
                self.assertTrue((self.folder / "packet.json").is_file())
                events.append("first-exit")
        def second():
            second_attempting.set()
            with cloud_storage.source_lease(self.job_id):
                second_inside.set()
                self.assertTrue(cloud_storage.load_job(self.job_id, full=True))
                self.assertTrue((self.folder / "packet.json").is_file())
                events.extend(["second-enter", "second-exit"])
        with ThreadPoolExecutor(max_workers=2) as executor:
            a = executor.submit(first)
            self.assertTrue(first_inside.wait(timeout=3))
            b = executor.submit(second)
            self.assertTrue(second_attempting.wait(timeout=3))
            self.assertFalse(second_inside.is_set())
            release_first.set()
            a.result(timeout=3)
            b.result(timeout=3)
        self.assertEqual(events, ["first-enter", "first-exit", "second-enter", "second-exit"])
        self.assertFalse((self.folder / "packet.json").exists())
        self.assertFalse((self.folder / ".hydrated").exists())
        self.assertEqual(sum(action == "get_file" for action, _ in self.blob.operations), 2)

    def test_different_sources_can_be_leased_concurrently(self):
        other_id = "00000000000000ef"
        other = self.jobs / other_id
        other.mkdir()
        write_json(other / "status.json", {"id": other_id, "status": "completed"})
        write_json(other / "request.json", {"id": other_id, "config": {}})
        write_json(other / "packet.json", {"proof": "second source"})
        (other / "evidence.zip").write_bytes(b"second export")
        for job_id in (self.job_id, other_id):
            cloud_storage.save_job(job_id)
        barrier = threading.Barrier(2)
        def dependent(job_id):
            with cloud_storage.source_lease(job_id):
                self.assertTrue(cloud_storage.load_job(job_id, full=True))
                barrier.wait(timeout=3)
                self.assertTrue((self.jobs / job_id / "packet.json").exists())
        with ThreadPoolExecutor(max_workers=2) as executor:
            list(executor.map(dependent, (self.job_id, other_id)))
        self.assertFalse((self.folder / "packet.json").exists())
        self.assertFalse((other / "packet.json").exists())

    def test_concurrent_atomic_json_writers_use_distinct_temporary_files(self):
        destination = Path(self.temp.name) / "shared.json"
        barrier = threading.Barrier(6)
        replace = os.replace
        def simultaneous_replace(source, target):
            if Path(target) == destination:
                barrier.wait(timeout=5)
            return replace(source, target)
        with patch("service.common.os.replace", simultaneous_replace):
            with ThreadPoolExecutor(max_workers=6) as executor:
                list(executor.map(lambda index: write_json(destination, {"writer": index}), range(6)))
        self.assertIn(read_json(destination)["writer"], range(6))
        self.assertFalse(list(destination.parent.glob("*.tmp")))

    def test_model_beyond_first_page_is_resolved_directly_and_listed(self):
        for index in range(26):
            model_id = "custom_" + f"{index:024x}"
            self.blob.objects[cloud_storage.PREFIX + f"models/{model_id}.json"] = json.dumps({"name": f"model {index}"}).encode()
        selected = "custom_" + f"{25:024x}"
        self.assertTrue(cloud_storage.load_model(selected))
        self.assertEqual(read_json(self.registry / f"{selected}.json"), {"name": "model 25"})
        self.assertFalse(any(action == "list" for action, _ in self.blob.operations))
        cloud_storage.load_models()
        self.assertEqual(len(list(self.registry.glob("custom_*.json"))), 26)
        self.assertEqual(sum(action == "list" for action, _ in self.blob.operations), 2)

    def test_completed_job_is_idempotent_after_cache_pruning_and_can_hydrate(self):
        first = cloud_storage.save_job(self.job_id)
        self.assertFalse((self.folder / "packet.json").exists())
        self.assertEqual(cloud_storage.save_job(self.job_id), first)
        self.assertTrue(cloud_storage.load_job(self.job_id, full=True))
        self.assertEqual(read_json(self.folder / "packet.json"), {"proof": "exact recorded source"})
        self.assertIn(first["artifacts"]["evidence"]["key"], cloud_storage.download_url(self.job_id))

    def test_same_job_concurrent_hydration_runs_once_and_metadata_reads_do_not_collide(self):
        cloud_storage.save_job(self.job_id)
        barrier = threading.Barrier(6)
        def load(index):
            barrier.wait(timeout=5)
            return cloud_storage.load_job(self.job_id, full=index % 2 == 0)
        with ThreadPoolExecutor(max_workers=6) as executor:
            self.assertEqual(list(executor.map(load, range(6))), [True] * 6)
        self.assertEqual(sum(action == "get_file" for action, _ in self.blob.operations), 1)
        self.assertTrue((self.folder / ".hydrated").is_file())
        self.assertFalse(list(self.folder.glob("*.tmp")))

    def test_corrupted_download_never_becomes_a_trusted_partial_cache(self):
        manifest = cloud_storage.save_job(self.job_id)
        self.blob.objects[manifest["artifacts"]["workspace"]["key"]] = b"truncated upload"
        with self.assertRaisesRegex(RuntimeError, "SHA-256"):
            cloud_storage.load_job(self.job_id, full=True)
        self.assertFalse((self.folder / ".hydrated").exists())
        self.assertFalse(list(self.jobs.glob("hydrate-*")))

    def test_existing_job_identity_cannot_be_replaced_by_different_results(self):
        first = cloud_storage.save_job(self.job_id, prune=False)
        write_json(self.folder / "view.json", {"id": self.job_id, "finding": "different"})
        with self.assertRaisesRegex(RuntimeError, "different result"):
            cloud_storage.save_job(self.job_id)
        key = cloud_storage.PREFIX + f"jobs/{self.job_id}/complete.json"
        self.assertEqual(json.loads(self.blob.objects[key]), first)

    def test_legacy_completion_and_archive_paths_remain_readable(self):
        manifest = cloud_storage.save_job(self.job_id)
        old_workspace = cloud_storage.PREFIX + f"jobs/{self.job_id}/workspace.zip"
        self.blob.objects[old_workspace] = self.blob.objects[manifest["artifacts"]["workspace"]["key"]]
        manifest.pop("artifacts")
        manifest["schema_version"] = "stormpilot.cloud-completion.v1"
        self.blob.objects[cloud_storage.PREFIX + f"jobs/{self.job_id}/complete.json"] = json.dumps(manifest).encode()
        self.assertTrue(cloud_storage.load_job(self.job_id, full=True))
        self.assertTrue(cloud_storage.download_url(self.job_id).endswith(f"jobs/{self.job_id}/evidence.zip"))

    def test_demo_export_then_followup_preserves_source_and_recovers_legacy_pruning(self):
        class QuietHandler(cloud_server.Handler):
            def log_message(self, *args):
                pass
        def source_required(*args, **kwargs):
            self.assertTrue((self.folder / "packet.json").is_file())
            return {"id": "00000000000000cd", "status": "queued"}
        patches = [patch.object(server, "JOBS", self.jobs), patch.object(cloud_server, "JOBS", self.jobs),
                   patch.object(server, "DEMO", {"id": self.job_id}),
                   patch.object(server, "create_repair", source_required),
                   patch.object(server, "create_evaluation", source_required), patch.object(server, "create_job", source_required)]
        for item in patches:
            item.start()
        http = ThreadingHTTPServer(("127.0.0.1", 0), QuietHandler)
        thread = threading.Thread(target=http.serve_forever, daemon=True)
        thread.start()
        def request(method, suffix):
            client = HTTPConnection("127.0.0.1", http.server_address[1], timeout=5)
            try:
                path = suffix if suffix.startswith("/") else f"/api/jobs/{self.job_id}/{suffix}"
                client.request(method, path, body="{}" if method == "POST" else None)
                response = client.getresponse()
                result = response.status, response.read()
                return result
            finally:
                client.close()
        try:
            busy = cloud_server.ActiveRequestExecutor()
            busy.slots = threading.Semaphore(0)
            with patch.object(server, "EXECUTOR", busy), patch.object(server, "DEMO", None), \
                 patch.object(cloud_storage, "load_job") as hydrate:
                self.assertEqual(request("POST", "repair")[0], 429)
                self.assertEqual(request("POST", "/api/jobs")[0], 429)
                hydrate.assert_not_called()
            self.assertEqual(request("GET", "export")[0], 302)
            self.assertTrue((self.folder / "packet.json").is_file())
            for suffix in ("repair", "evaluate", "replay"):
                self.assertEqual(request("POST", suffix)[0], 202)
            (self.folder / "packet.json").unlink()
            self.assertEqual(request("POST", "repair")[0], 202)
            with patch.object(cloud_storage, "download_url", side_effect=RuntimeError("signing unavailable")):
                status, body = request("GET", "export")
                self.assertEqual(status, 503)
                self.assertIn("signing unavailable", json.loads(body)["error"])
            with patch.object(server, "DEMO", None):
                self.assertEqual(request("POST", "repair")[0], 202)
                with cloud_storage.locked_job(self.job_id):
                    self.assertFalse((self.folder / "packet.json").exists())
                self.assertEqual(request("POST", "evaluate")[0], 202)
                with cloud_storage.locked_job(self.job_id):
                    self.assertFalse((self.folder / "packet.json").exists())
            archive_root = Path(self.temp.name) / "frozen-app"
            (archive_root / "evaluation").mkdir(parents=True)
            for phase in ("phase1", "phase2"):
                (archive_root / "evaluation" / f"{phase}-evidence.zip").write_bytes(phase.encode())
            with patch.object(cloud_server, "ROOT", archive_root):
                self.assertEqual(request("GET", "/api/evaluation/export")[0], 302)
                self.assertEqual(request("GET", "/api/evaluation/phase2/export")[0], 302)
                with patch.object(cloud_storage, "publish_frozen_archive", side_effect=RuntimeError("storage unavailable")):
                    status, body = request("GET", "/api/evaluation/export")
                    self.assertEqual(status, 503)
                    self.assertIn("storage unavailable", json.loads(body)["error"])
                (archive_root / "evaluation" / "phase2-evidence.zip").unlink()
                self.assertEqual(request("GET", "/api/evaluation/phase2/export")[0], 404)
        finally:
            http.shutdown()
            http.server_close()
            thread.join(timeout=5)
            for item in reversed(patches):
                item.stop()


if __name__ == "__main__":
    unittest.main()
