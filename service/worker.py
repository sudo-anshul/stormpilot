"""One isolated job lifecycle. The native solver lives in a subprocess."""
from __future__ import annotations

import subprocess
import sys
import traceback

from service.common import JOBS, ROOT, read_json, write_json
from service.present import engine_request, make_view
from service.archive import build_archive
from validation.validate_packet import validate_packet
from validation.replay import compare_replay


def execute(job_id):
    folder = JOBS / job_id
    request = read_json(folder / "request.json")
    state = read_json(folder / "status.json")
    def progress(phase, message):
        state.update(status="running", phase=phase, message=message)
        write_json(folder / "status.json", state)
    try:
        progress("Preparing experiment", "Freezing the model, policy, fault and performance check.")
        config = request["config"]
        native_request = engine_request(config)
        write_json(folder / "engine-request.json", native_request)
        command = "investigate" if config["mode"] == "investigate" else "run"
        input_path = folder / "engine-request.json"
        if request.get("replay_of"):
            command = "replay"
            input_path = JOBS / request["replay_of"] / "packet.json"
        progress("Running simulations", "Computing nominal, stressed and alternative policies with the EPA SWMM engine.")
        completed = subprocess.run(
            [sys.executable, str(ROOT / "engine" / "cli.py"), command,
             "--request", str(input_path), "--output", str(folder / "packet.json")],
            cwd=ROOT, capture_output=True, text=True, timeout=210,
        )
        if completed.returncode:
            raise RuntimeError((completed.stderr or completed.stdout or "Simulation failed without a result.")[-1800:])
        packet = read_json(folder / "packet.json")
        progress("Checking evidence", "Independently recomputing metrics and checking paired inputs and provenance.")
        validation = validate_packet(packet, root_path=ROOT)
        if request.get("replay_of"):
            original = read_json(JOBS / request["replay_of"] / "packet.json")
            replay = compare_replay(original, packet, root_path=ROOT)
            replay["original_run_id"] = request["replay_of"]
            write_json(folder / "replay.json", replay)
            validation["checks"].extend(replay["checks"])
            validation["replay_status"] = replay["replay_status"]
            if replay["status"] == "failed":
                validation["status"] = "failed"
            elif replay["status"] != "passed" and validation["status"] == "passed":
                validation["status"] = "partial"
        write_json(folder / "validation.json", validation)
        write_json(folder / "view.json", make_view(packet, validation, request))
        progress("Packaging evidence", "Bundling the recorded cases, exact source files and independent replay tools.")
        build_archive(folder)
        state.update(status="completed", phase="Complete", message="Simulation results and evidence checks are ready.")
        write_json(folder / "status.json", state)
    except Exception as exc:
        traceback.print_exc()
        state.update(status="failed", phase="Experiment stopped", error=str(exc)[-1200:])
        write_json(folder / "status.json", state)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(execute(sys.argv[1]))
