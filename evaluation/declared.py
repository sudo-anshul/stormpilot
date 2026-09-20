"""Run a declared robustness suite from a recorded model and two recorded policies.

These transforms are visible/reusable. This interface makes no heldout claim.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys

from validation.metrics import EvidenceError
from validation.validate_packet import canonical_sha256, validate_packet
from .core import load_protocol
from .run_campaign import ROOT, freeze_candidate, now, read_json, run_holdout, write_json


def _policy_spec(run):
    parameters = run["controller"]["parameters"]
    return dict(controller_id=run["controller"]["id"], parameters={
        key: value for key, value in parameters.items() if key not in {"targets_m3s", "control_interval_s"}
    })


def prepare_declared_suite(packet, reference_run_id, candidate_run_id, pair_ids, template):
    """Pure derivation used by API validation and tests; no solver execution."""
    if packet["experiment"]["test_contract"]["metric"] != "flood_volume_m3":
        raise EvidenceError("Robustness suites currently require a flood-volume test contract.")
    if len(pair_ids) != 2 or len(set(pair_ids)) != 2:
        raise EvidenceError("Select exactly two distinct recorded conditions.")
    runs = {run["run_id"]: run for run in packet["runs"]}
    if reference_run_id not in runs or candidate_run_id not in runs:
        raise EvidenceError("Both policies must come from completed recorded runs.")
    catalog = {f["id"]: f for f in packet["request"]["faults"]}
    if any(identifier not in catalog for identifier in pair_ids):
        raise EvidenceError("Selected conditions must belong to the recorded fault catalog.")
    pair = [copy.deepcopy(catalog[identifier]) for identifier in sorted(pair_ids)]
    types = [fault["type"] for fault in pair]
    if types.count("valve_stuck") != 1 or sum(t in {"sensor_bias", "sensor_dropout"} for t in types) != 1:
        raise EvidenceError("Select one recorded sensor condition and one recorded valve condition.")
    model = packet["model"]
    valves = {asset["id"] for asset in model["assets"]}
    basins = {node["id"] for node in model["nodes"] if node["type"] == "basin"}
    if any(fault["asset"] not in (valves if fault["type"] == "valve_stuck" else basins) for fault in pair):
        raise EvidenceError("Selected condition assets do not belong to the recorded model.")
    spec = dict(reference=_policy_spec(runs[reference_run_id]), candidate=_policy_spec(runs[candidate_run_id]))
    request = copy.deepcopy(packet["request"])
    request.pop("search_budget", None)
    request.update(faults=pair, controller_id=spec["reference"]["controller_id"],
                   controller_parameters=spec["reference"]["parameters"],
                   fallback_controller_id=spec["candidate"]["controller_id"],
                   fallback_controller_parameters=spec["candidate"]["parameters"])
    protocol = copy.deepcopy(template)
    protocol.update(protocol_id="declared-robustness-" + canonical_sha256(dict(request=request, spec=spec))[:20],
                    frozen_at_utc=now(), status="declared_before_this_execution_not_heldout",
                    scope="Recorded supplied model and visible robustness transforms; no calibration or heldout claim.",
                    scenario_id=request["scenario_id"], horizon_s=packet["experiment"]["horizon_s"],
                    information_boundary_id=packet["experiment"]["information_boundary_id"],
                    primary_contract=copy.deepcopy(packet["experiment"]["test_contract"]))
    protocol["primary_contract"]["horizon_s"] = protocol["horizon_s"]
    request["test_contract"] = copy.deepcopy(protocol["primary_contract"])
    protocol["development_context"].update(rainfall_multiplier=request["rainfall_multiplier"], noise_std_m=request["noise_std_m"],
                                           seed=request["seed"], reference_controller_id=spec["reference"]["controller_id"],
                                           reference_controller_parameters=spec["reference"]["parameters"])
    protocol["holdout_transform_protocol"]["results_access"] = "Transforms are visible and reusable; this invocation is a declared suite, never described as held out."
    return request, spec, protocol


def evaluate_declared_suite(packet_path, reference_run_id, candidate_run_id, pair_ids, output_dir, report_path):
    packet = read_json(packet_path)
    checked = validate_packet(packet, ROOT)
    if checked["status"] != "passed":
        raise EvidenceError("Recorded evidence or source identity is invalid. Run a fresh experiment before evaluating this suite.")
    template, template_hash = load_protocol(ROOT / "evaluation/protocol.json")
    request, spec, protocol = prepare_declared_suite(packet, reference_run_id, candidate_run_id, pair_ids, template)
    protocol["template_protocol_sha256"] = template_hash
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=False)
    protocol_path = output_dir / "protocol.json"
    request_path, spec_path, proof_path = output_dir / "base-request.json", output_dir / "policy-spec.json", output_dir / "base-proof.json"
    write_json(protocol_path, protocol)
    protocol_path.with_suffix(".sha256").write_text(hashlib.sha256(protocol_path.read_bytes()).hexdigest() + "  protocol.json\n")
    write_json(request_path, request)
    write_json(spec_path, spec)
    completed = subprocess.run([sys.executable, str(ROOT / "evaluation/worker.py"), "--request", str(request_path),
                                "--spec", str(spec_path), "--output", str(proof_path)], cwd=ROOT,
                               capture_output=True, text=True, timeout=1200)
    if completed.returncode:
        raise EvidenceError("Base-case execution failed: " + completed.stderr[-2000:])
    snapshot_path = output_dir / "candidate.json"
    freeze_candidate(proof_path, spec_path, snapshot_path, protocol_path)
    # freeze_candidate retained a complete compressed development proof.
    proof_path.unlink()
    return run_holdout(snapshot_path, protocol_path, output_dir / "cases", report_path, suite_type="declared_robustness")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--packet", type=Path, required=True)
    parser.add_argument("--reference-run-id", required=True)
    parser.add_argument("--candidate-run-id", required=True)
    parser.add_argument("--pair-id", action="append", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(evaluate_declared_suite(args.packet, args.reference_run_id, args.candidate_run_id,
                                             args.pair_id, args.output_dir, args.report)))


if __name__ == "__main__":
    main()
