from concurrent.futures import ThreadPoolExecutor
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
import io
import hashlib
import json
from pathlib import Path
import sys
import subprocess
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
import zipfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
import server
from service import worker
from service.common import read_json, write_json


class QuietHandler(server.Handler):
    def log_message(self,*args):
        pass


class HttpBoundaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix="stormpilot-service-tests-")
        cls.jobs = Path(cls.temp.name)/"jobs"
        cls.jobs.mkdir()
        cls.executor = ThreadPoolExecutor(max_workers=1)
        def actual_worker(job_id):
            try:
                return worker.execute(job_id)
            finally:
                with server.LOCK:
                    server.PENDING.discard(job_id)
        cls.patches = [patch.object(server,"JOBS",cls.jobs), patch.object(worker,"JOBS",cls.jobs),
                       patch.object(server,"PENDING",set()), patch.object(server,"EXECUTOR",cls.executor),
                       patch.object(server,"run_worker",actual_worker)]
        for item in cls.patches:
            item.start()
        cls.http = ThreadingHTTPServer(("127.0.0.1",0),QuietHandler)
        cls.thread = threading.Thread(target=cls.http.serve_forever,daemon=True)
        cls.thread.start()
        cls.port = cls.http.server_address[1]

    @classmethod
    def tearDownClass(cls):
        cls.http.shutdown()
        cls.http.server_close()
        cls.thread.join(timeout=5)
        cls.executor.shutdown(wait=True)
        for item in reversed(cls.patches):
            item.stop()
        cls.temp.cleanup()

    def request(self,method,path,body=None,headers=None):
        connection = HTTPConnection("127.0.0.1",self.port,timeout=20)
        try:
            connection.request(method,path,body=body,headers=headers or {})
            response = connection.getresponse()
            return response.status,dict(response.getheaders()),response.read()
        finally:
            connection.close()

    def post(self,path,body):
        status,headers,data = self.request("POST",path,json.dumps(body),{"Content-Type":"application/json"})
        return status,json.loads(data)

    def wait_complete(self,job_id):
        deadline = time.monotonic()+100
        while time.monotonic()<deadline:
            status,_,body = self.request("GET",f"/api/jobs/{job_id}")
            self.assertEqual(status,200)
            state = json.loads(body)
            if state["status"] in ("completed","failed"):
                self.assertEqual(state["status"],"completed",state)
                return state
            time.sleep(0.1)
        self.fail("The real isolated engine worker did not finish within the test deadline.")

    def test_invalid_json_shape_size_and_origin_are_rejected(self):
        cases = [
            ("{",{},400),
            ("[]",{},400),
            (json.dumps({"budget":2}),{},400),
            (json.dumps({"seed":0.5}),{},400),
            ('{"threshold":NaN}',{},400),
            ("{}",{"Origin":"https://untrusted.example"},403),
            ("",{"Content-Length":"16385"},413),
        ]
        for body,headers,expected in cases:
            with self.subTest(body=body,headers=headers):
                status,_,result = self.request("POST","/api/jobs",body,headers)
                self.assertEqual(status,expected,result)
                self.assertIn("error",json.loads(result))

    def test_unknown_jobs_api_paths_and_static_traversal_do_not_expose_files(self):
        for path in ["/api/unknown", "/api/jobs/ffffffffffffffff", "/api/jobs/../../engine/cli.py"]:
            with self.subTest(path=path):
                status,_,result = self.request("GET",path)
                self.assertEqual(status,404,result)
        status,_,result = self.request("GET","/../../engine/cli.py")
        self.assertEqual(status,403,result)

    def test_unfinished_jobs_cannot_export_or_replay(self):
        job_id = "aabbccddeeff0011"
        folder = self.jobs/job_id
        folder.mkdir(exist_ok=True)
        write_json(folder/"status.json",{"id":job_id,"status":"running"})
        status,_,_ = self.request("GET",f"/api/jobs/{job_id}/export")
        self.assertEqual(status,409)
        status,_ = self.post(f"/api/jobs/{job_id}/replay",{})
        self.assertEqual(status,409)

    def test_real_completed_investigation_exports_source_and_replays_all_cases(self):
        config = {"budget":8,"additional_faults":[{"asset":"2","start_hour":30,"duration_hours":1}]}
        status,state = self.post("/api/jobs",config)
        self.assertEqual(status,202,state)
        job_id = state["id"]
        self.wait_complete(job_id)
        status,_,body = self.request("GET",f"/api/jobs/{job_id}/result")
        self.assertEqual(status,200)
        view = json.loads(body)
        self.assertEqual(view["validation"]["status"],"passed")
        self.assertEqual(view["finding"]["status"],"violation")
        self.assertEqual({c["role"] for c in view["cases"]},{"nominal","stress","reduced","fallback"})
        status,headers,body = self.request("GET",f"/api/jobs/{job_id}/export")
        self.assertEqual(status,200)
        self.assertEqual(headers["Content-Type"],"application/zip")
        with zipfile.ZipFile(io.BytesIO(body)) as archive:
            names=set(archive.namelist())
            for name in ["packet.json","REPLAY.md","engine/cli.py","engine/data/theta.inp",
                         "engine/vendor/epa-swmm/src/solver/swmm5.c","validation/validate_packet.py"]:
                self.assertIn(name,names)
            self.assertFalse(any(name.startswith("/") or ".." in Path(name).parts for name in names))
            packet=json.loads(archive.read("packet.json"))
            self.assertEqual(packet["witness"]["claim"],"1-minimal")
            for artifact in packet["artifacts"]:
                self.assertIn(artifact["path"],names)
                self.assertEqual(hashlib.sha256(archive.read(artifact["path"])).hexdigest(),artifact["sha256"])
            replay_help=archive.read("REPLAY.md").decode()
            self.assertIn("engine/cli.py replay",replay_help)
            self.assertIn("validation.replay",replay_help)
            with tempfile.TemporaryDirectory(prefix="stormpilot-extracted-replay-") as extracted:
                exported_root=Path(extracted)
                archive.extractall(exported_root)
                # This starts with source only: the exported project must build
                # its native engine and replay without the original checkout.
                completed=subprocess.run([sys.executable,"engine/cli.py","replay","--request","packet.json",
                                          "--output","fresh-replay.json"],cwd=exported_root,
                                         capture_output=True,text=True,timeout=90)
                self.assertEqual(completed.returncode,0,completed.stderr)
                checked=subprocess.run([sys.executable,"-m","validation.replay","packet.json","fresh-replay.json",
                                        "--root",".","--output","fresh-replay-check.json"],cwd=exported_root,
                                       capture_output=True,text=True,timeout=60)
                self.assertEqual(checked.returncode,0,checked.stderr or checked.stdout)
                clean_report=read_json(exported_root/"fresh-replay-check.json")
                self.assertEqual(clean_report["status"],"passed")
                self.assertEqual(clean_report["replay_status"],"matched")
        status,replay_state=self.post(f"/api/jobs/{job_id}/replay",{})
        self.assertEqual(status,202,replay_state)
        self.wait_complete(replay_state["id"])
        status,_,body=self.request("GET",f"/api/jobs/{replay_state['id']}/result")
        self.assertEqual(status,200)
        replay_view=json.loads(body)
        self.assertEqual(replay_view["validation"]["status"],"passed")
        self.assertEqual(replay_view["validation"]["replay_status"],"matched")
        original=read_json(self.jobs/job_id/"packet.json")
        replayed=read_json(self.jobs/replay_state["id"]/"packet.json")
        self.assertEqual({r["run_id"] for r in original["runs"]},{r["run_id"] for r in replayed["runs"]})
        self.assertEqual(len(original["runs"]),5)


if __name__ == "__main__":
    unittest.main()
