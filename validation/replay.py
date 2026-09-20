"""Compare an original evidence packet with a newly executed recorded replay.

The caller executes the simulator; this module independently compares its output.
Runtime, creation dates and report CPU timing are deliberately not compared.
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Mapping
from pathlib import Path

from .metrics import EvidenceError, TRACE_UNITS, close_enough
from .validate_packet import _tolerances, canonical_sha256, validate_packet


def compare_replay(original: Mapping, replayed: Mapping, root_path: str | Path | None = None) -> dict:
    checks: list[dict] = []

    def record(identifier, passed, message, **details):
        item = dict(id=identifier, status="passed" if passed else "failed", message=message)
        if details:
            item["details"] = details
        checks.append(item)

    reports = {"original": validate_packet(original, root_path),
               "replayed": validate_packet(replayed, root_path)}
    for label, report in reports.items():
        checks.append(dict(id=f"{label}_evidence", status=report["status"],
                           message=f"{label.capitalize()} packet recorded-evidence status is {report['status']}."))
    try:
        if any(r["status"] == "failed" for r in reports.values()):
            raise EvidenceError("cannot accept replay equality for a packet with failed evidence checks")
        if canonical_sha256(original["experiment"]) != canonical_sha256(replayed["experiment"]):
            raise EvidenceError("replay changed the declared experiment, property, exogenous stream or solver settings")
        if canonical_sha256(original["request"]) != canonical_sha256(replayed["request"]):
            raise EvidenceError("replay request differs from the original")
        for key in ("base_model_sha256", "engine_source_sha256", "runner_source_sha256"):
            if original["provenance"].get(key) != replayed["provenance"].get(key):
                raise EvidenceError(f"replay changed provenance: {key}")
        record("experiment_identity", True, "Experiment, request and executable source identities match.")
        originals = {r["run_id"]: r for r in original["runs"]}
        reruns = {r["run_id"]: r for r in replayed["runs"]}
        if set(originals) != set(reruns):
            raise EvidenceError("replay must include exactly the original logical run IDs")
        tolerance = _tolerances(original["experiment"])
        for identifier, old in originals.items():
            new = reruns[identifier]
            for field in ("role", "context", "active_fault_ids"):
                if old[field] != new[field]:
                    raise EvidenceError(f"{identifier}: replay changed {field}")
            for field in ("id", "source_sha256", "parameters"):
                if old["controller"][field] != new["controller"][field]:
                    raise EvidenceError(f"{identifier}: replay changed controller {field}")
            before = reports["original"]["runs"][identifier]["computed_metrics"]
            after = reports["replayed"]["runs"][identifier]["computed_metrics"]
            if not before or not after:
                raise EvidenceError(f"{identifier}: replay lacks independently recomputed metrics")
            differences = {}
            for metric, value in before.items():
                differences[metric] = after[metric] - value
                if not close_enough(value, after[metric], absolute=tolerance["absolute"], relative=tolerance["relative"]):
                    raise EvidenceError(f"{identifier}: replayed {metric} differs beyond tolerance")
            if len(old["trace"]) != len(new["trace"]):
                raise EvidenceError(f"{identifier}: replay changed the routing sample grid")
            max_deltas = {key: 0.0 for key in TRACE_UNITS}
            for index, (a, b) in enumerate(zip(old["trace"], new["trace"])):
                for key in TRACE_UNITS:
                    absolute = tolerance["time_s"] if key == "time_s" else tolerance["absolute"]
                    relative = 0 if key == "time_s" else tolerance["relative"]
                    if not close_enough(a[key], b[key], absolute=absolute, relative=relative):
                        raise EvidenceError(f"{identifier}: trace[{index}].{key} differs beyond tolerance")
                    max_deltas[key] = max(max_deltas[key], abs(a[key] - b[key]))
            for field in ("node_flood_volume_m3", "peak_basin_depth_m"):
                if field not in old and field not in new:
                    continue
                a, b = old.get(field), new.get(field)
                if not isinstance(a, Mapping) or not isinstance(b, Mapping) or set(a) != set(b):
                    raise EvidenceError(f"{identifier}: replay changed {field} coverage")
                if any(not close_enough(a[k], b[k], absolute=tolerance["absolute"], relative=tolerance["relative"]) for k in a):
                    raise EvidenceError(f"{identifier}: replayed {field} differs beyond tolerance")
            record(f"run:{identifier}", True, "Controller treatment, complete trace and physical metrics match within tolerance.",
                   metric_differences=differences, maximum_trace_differences=max_deltas,
                   trace_rows=len(old["trace"]))
    except (EvidenceError, KeyError, TypeError, ValueError) as exc:
        record("replay_comparison", False, str(exc))

    statuses = {c["status"] for c in checks}
    status = "failed" if "failed" in statuses else ("partial" if "partial" in statuses else "passed")
    return dict(status=status, replay_status="matched" if status == "passed" else status,
                scope="recorded_replay_comparison", checks=checks,
                evidence_status={name: report["status"] for name, report in reports.items()},
                limitations=[
                    "The caller must actually run the simulator to produce the replayed packet; comparing a copied packet does not establish execution.",
                    "Recorded cases are replayed; this comparison does not repeat or validate exhaustive search coverage.",
                    "Matched simulation output does not establish field calibration or a safety certificate.",
                ])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("original", type=Path)
    parser.add_argument("replayed", type=Path)
    parser.add_argument("--root", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        report = compare_replay(json.loads(args.original.read_text()), json.loads(args.replayed.read_text()), args.root)
    except (OSError, ValueError) as exc:
        report = dict(status="failed", replay_status="failed", checks=[dict(id="packet_read", status="failed", message=str(exc))])
    rendered = json.dumps(report, indent=2, allow_nan=False) + "\n"
    if args.output:
        args.output.write_text(rendered)
    else:
        print(rendered, end="")
    return 0 if report["status"] == "passed" else (2 if report["status"] == "partial" else 1)


if __name__ == "__main__":
    raise SystemExit(main())
