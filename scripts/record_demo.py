#!/usr/bin/env python3
"""Record the bounded compound-fault discovery for the welcome screen."""
import gzip
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from service.common import ROOT, JOBS, read_json, write_json
from service.present import normalize_config
from service.worker import execute

envelope = read_json(ROOT / "engine" / "examples" / "discovery-request.json")
config = normalize_config({
    "mode": "discover", "controller_id": "constant_flow",
    "controller_parameters": envelope["controller_parameters"],
    "fallback_controller_id": envelope["fallback_controller_id"],
    "fallback_controller_parameters": envelope["fallback_controller_parameters"],
    "fault_asset": "P2", "fault_kind": "sensor_bias", "sensor_bias_m": 1,
    "start_hour": 3, "duration_hours": 3,
    "additional_faults": [{"asset": "2", "kind": "valve_stuck", "setting": 0.035,
                           "start_hour": 6, "duration_hours": 2}],
    "discovery": envelope["discovery"],
})
# A new recording may use revised sources even when its settings are unchanged.
# Never reuse an immutable cloud job id for that new result.
job_id = uuid.uuid4().hex[:16]
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
