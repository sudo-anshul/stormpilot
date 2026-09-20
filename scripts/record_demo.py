#!/usr/bin/env python3
"""Record a genuine two-condition investigation for the welcome screen."""
import gzip
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from service.common import ROOT, JOBS, digest, read_json, write_json
from service.present import normalize_config
from service.worker import execute

config = normalize_config({"additional_faults": [{"asset": "2", "start_hour": 30, "duration_hours": 1}]})
job_id = digest({"welcome_config": config})[:16]
request = {"id": job_id, "config": config, "created_at": datetime.now(timezone.utc).isoformat(), "replay_of": None}
folder = JOBS / job_id
write_json(folder / "request.json", request)
write_json(folder / "status.json", {"id": job_id, "status": "queued"})
if execute(job_id):
    raise SystemExit("The welcome experiment failed; no fixture was saved.")
report = read_json(folder / "validation.json")
if report["status"] != "passed":
    raise SystemExit("The welcome evidence did not pass; no fixture was saved.")
fixture = ROOT / "fixtures"
write_json(fixture / "demo-request.json", request)
(fixture / "demo-packet.json.gz").write_bytes(gzip.compress((folder / "packet.json").read_bytes(), mtime=0))
print(f"Recorded real welcome case {job_id}; validation passed.")
