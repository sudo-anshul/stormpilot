"""Isolated native execution only; independent checks live in evaluation.core."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / "engine"))
from runner import packet, prepare, run_simulation  # noqa: E402


def execute(request, spec, progress_path=None):
    request = dict(request, controller_id=spec["reference"]["controller_id"],
                   controller_parameters=spec["reference"]["parameters"],
                   fallback_controller_id=spec["candidate"]["controller_id"],
                   fallback_controller_parameters=spec["candidate"]["parameters"])
    normalized, *_ = prepare(request)
    ids = sorted(f["id"] for f in normalized["faults"])
    if len(ids) != 2:
        raise ValueError("Evaluation requires exactly two frozen fault conditions.")
    subsets = dict(empty=[], a=[ids[0]], b=[ids[1]], ab=ids)
    runs = []
    execution = dict(started_runs=0, completed_runs=0, treatments=[])
    for policy in ("reference", "candidate"):
        for subset, active in subsets.items():
            selected = spec[policy]
            execution["started_runs"] += 1
            execution["treatments"].append(dict(policy=policy, subset=subset, status="running"))
            if progress_path:
                Path(progress_path).write_text(json.dumps(execution))
            run = run_simulation(normalized, role=f"{policy}_{subset}", controller_id=selected["controller_id"],
                                 active_fault_ids=active, controller_parameters=selected["parameters"])
            run["evaluation_role"] = dict(policy=policy, subset=subset)
            runs.append(run)
            execution["completed_runs"] += 1
            execution["treatments"][-1].update(status="completed", run_id=run["run_id"])
            if progress_path:
                Path(progress_path).write_text(json.dumps(execution))
    return packet(normalized, runs)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--request", type=Path, required=True)
    parser.add_argument("--spec", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--progress", type=Path)
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    if args.progress:
        args.progress.parent.mkdir(parents=True, exist_ok=True)
    result = execute(json.loads(args.request.read_text()), json.loads(args.spec.read_text()), args.progress)
    args.output.write_text(json.dumps(result, separators=(",", ":"), allow_nan=False) + "\n")


if __name__ == "__main__":
    main()
