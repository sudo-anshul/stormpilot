"""Freeze a development candidate and execute the predeclared heldout suite once.

Outputs preserve all unfavorable and invalid outcomes. The worker executes SWMM;
this process independently audits every complete trace before compacting records.
"""
from __future__ import annotations

import argparse
import gc
import gzip
import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
import subprocess
import sys

from validation.metrics import EvidenceError
from validation.validate_packet import canonical_sha256
from .core import assess_campaign, assess_case, holdout_request, load_protocol, subset_ids

ROOT = Path(__file__).resolve().parents[1]


def read_json(path):
    path = Path(path)
    return json.loads(gzip.decompress(path.read_bytes()) if path.suffix == ".gz" else path.read_bytes())


def write_json(path, value, exclusive=False):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x" if exclusive else "w") as handle:
        json.dump(value, handle, indent=2, allow_nan=False)
        handle.write("\n")


def now():
    return datetime.now(timezone.utc).isoformat()


def check_sources(snapshot, root):
    for artifact in snapshot["artifacts"]:
        path = (root / artifact["path"]).resolve()
        if not path.is_relative_to(root.resolve()) or not path.is_file():
            raise EvidenceError("frozen source/model artifact is missing")
        if hashlib.sha256(path.read_bytes()).hexdigest() != artifact["sha256"]:
            raise EvidenceError(f"source changed after candidate freeze: {artifact['path']}")
    for name in ("development_search_ledger", "information_boundary_clarification"):
        record = snapshot.get(name)
        if record is None:
            continue
        path = (root / record["path"]).resolve()
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != record["sha256"]:
            raise EvidenceError(f"frozen supplementary evidence changed: {name}")


def freeze_candidate(packet_path, spec_path, output, protocol_path, development_ledger=None):
    if Path(output).exists() or Path(output).with_suffix(".sha256").exists():
        raise EvidenceError("candidate freeze already exists; it cannot be overwritten")
    protocol, protocol_hash = load_protocol(protocol_path)
    if protocol.get("prior_phase") and development_ledger is None:
        raise EvidenceError("phase 2 requires its complete development ledger before candidate freeze")
    packet, spec = read_json(packet_path), read_json(spec_path)
    request = packet["request"]
    for key in ("rainfall_multiplier", "noise_std_m", "seed"):
        if request[key] != protocol["development_context"][key]:
            raise EvidenceError(f"development case departed from the frozen context: {key}")
    if request["scenario_id"] != protocol["scenario_id"] or request["test_contract"] != protocol["primary_contract"]:
        raise EvidenceError("development scenario or primary contract differs from protocol")
    fixed_pair = protocol["development_context"].get("fixed_fault_pair")
    if fixed_pair is not None and request["faults"] != fixed_pair:
        raise EvidenceError("development fault pair differs from the pair fixed before policy development")
    if spec["reference"]["controller_id"] != protocol["development_context"]["reference_controller_id"]:
        raise EvidenceError("reference controller differs from the predeclared baseline")
    reference_parameters = protocol["development_context"].get("reference_controller_parameters", {})
    if not reference_parameters and spec["reference"]["controller_id"] == "constant_flow":
        reference_parameters = {"target_scale": 1.0}
    if spec["reference"]["parameters"] != reference_parameters:
        raise EvidenceError("reference parameters differ from the predeclared baseline")
    snapshot = dict(schema_version="stormpilot.candidate-freeze.v1", frozen_at_utc=now(), protocol_sha256=protocol_hash,
                    request=request, reference=spec["reference"], candidate=spec["candidate"],
                    artifacts=packet["artifacts"], provenance=packet["provenance"],
                    development_packet_sha256=hashlib.sha256(Path(packet_path).read_bytes()).hexdigest(),
                    development_request_sha256=canonical_sha256(request))
    clarification_path = Path(protocol_path).parent / "information-boundary-clarification.json"
    if clarification_path.exists():
        clarification_bytes = clarification_path.read_bytes()
        clarification_hash = hashlib.sha256(clarification_bytes).hexdigest()
        if clarification_hash != clarification_path.with_suffix(".sha256").read_text().split()[0]:
            raise EvidenceError("information-boundary clarification changed after recording")
        snapshot["information_boundary_clarification"] = dict(content=json.loads(clarification_bytes), sha256=clarification_hash,
            path=str(clarification_path.relative_to(ROOT)) if clarification_path.is_relative_to(ROOT) else str(clarification_path))
    checked = assess_case(packet, snapshot, request, protocol, ROOT)
    snapshot["development"] = checked
    if development_ledger is not None:
        ledger_path = Path(development_ledger)
        ledger_bytes = ledger_path.read_bytes()
        if not ledger_bytes:
            raise EvidenceError("development ledger is empty")
        ledger_copy = Path(output).parent / ("development-ledger" + "".join(ledger_path.suffixes))
        ledger_copy.parent.mkdir(parents=True, exist_ok=True)
        if ledger_path.resolve() != ledger_copy.resolve():
            shutil.copyfile(ledger_path, ledger_copy)
        ledger_hash = hashlib.sha256(ledger_bytes).hexdigest()
        if hashlib.sha256(ledger_copy.read_bytes()).hexdigest() != ledger_hash:
            raise EvidenceError("development ledger changed while being frozen")
        snapshot["development_search_ledger"] = dict(
            path=str(ledger_copy.relative_to(ROOT)) if ledger_copy.is_relative_to(ROOT) else str(ledger_copy),
            sha256=ledger_hash, source_filename=ledger_path.name,
            scope="Complete recorded development ledger, including rejected and failed attempts; no optimizer-superiority claim.")
    proof_copy = Path(output).parent / "development-packet.json.gz"
    proof_copy.parent.mkdir(parents=True, exist_ok=True)
    with proof_copy.open("wb") as handle:
        with gzip.GzipFile(fileobj=handle, mode="wb", mtime=0) as compressed:
            compressed.write(json.dumps(packet, separators=(",", ":"), allow_nan=False).encode())
    snapshot["development_packet"] = dict(path=str(proof_copy.relative_to(ROOT)) if proof_copy.is_relative_to(ROOT) else str(proof_copy),
                                           sha256=hashlib.sha256(proof_copy.read_bytes()).hexdigest())
    write_json(output, snapshot, exclusive=True)
    content = Path(output).read_bytes()
    digest = hashlib.sha256(content).hexdigest()
    Path(output).with_suffix(".sha256").write_text(digest + "  " + Path(output).name + "\n")
    return dict(snapshot_sha256=digest, development_joint_failure=checked["outcome"]["joint_failure"],
                development_mitigation_passes=checked["outcome"]["mitigation_passes"])


def _load_snapshot(path, protocol_hash):
    content = Path(path).read_bytes()
    digest = hashlib.sha256(content).hexdigest()
    if digest != Path(path).with_suffix(".sha256").read_text().split()[0]:
        raise EvidenceError("candidate snapshot changed after freezing")
    snapshot = json.loads(content)
    if snapshot["protocol_sha256"] != protocol_hash:
        raise EvidenceError("candidate snapshot belongs to a different protocol")
    return snapshot, digest


def make_report(cases, snapshot, protocol, protocol_hash, snapshot_hash, retained, suite_type="heldout_benchmark"):
    aggregate = assess_campaign(cases, snapshot, protocol)
    development = snapshot["development"]["outcome"]
    accepted = dict(development_joint_failure=development["joint_failure"],
                    development_mitigation=development["mitigation_passes"],
                    heldout_usefulness=aggregate["heldout_usefulness_passes"])
    accepted["overall"] = all(accepted.values())
    presentation = []
    for case in cases:
        entry = dict(case_id=case["case_id"], transform=next(t for t in protocol["holdout_cases"] if t["id"] == case["case_id"]),
                     status=case["status"], request=case["request"], subsets=[])
        if case["status"] == "completed":
            outcome = aggregate["case_outcomes"][case["case_id"]]
            ids = subset_ids(case["request"]["faults"])
            for subset, comp in outcome["comparisons"].items():
                entry["subsets"].append(dict(subset=subset, active_fault_ids=ids[subset],
                                              reference_metrics=comp["reference"], candidate_metrics=comp["candidate"],
                                              changes=comp["changes"], guards=comp["guards"], all_guards_pass=comp["all_guards_pass"],
                                              material_flood_improvement=comp["material_flood_improvement"],
                                              flood_reduction_m3=comp["flood_reduction_m3"], relative_flood_reduction=comp["relative_flood_reduction"]))
            entry["trace_records"] = case["trace_records"]
            entry["validation_counts"] = case["validation_counts"]
        else:
            entry["error"] = case.get("error", "Invalid case")
        presentation.append(entry)
    prov = snapshot["provenance"]
    controller_hash = next(a["sha256"] for a in snapshot["artifacts"] if a["path"] == "engine/controllers.py")
    result = dict(schema_version="stormpilot.evaluation-report.v1", suite_type=suite_type,
                status="completed_with_invalid_cases" if aggregate["invalid_cases"] else "completed",
                completed_at_utc=now(), protocol=dict(id=protocol["protocol_id"], sha256=protocol_hash, frozen_at_utc=protocol["frozen_at_utc"]),
                candidate_snapshot_sha256=snapshot_hash,
                matching_identity=dict(development_request_sha256=snapshot["development_request_sha256"],
                    base_model_sha256=prov["base_model_sha256"], controller_source_sha256=controller_hash,
                    engine_source_sha256=prov["engine_source_sha256"], runner_source_sha256=prov["runner_source_sha256"]),
                reference=snapshot["reference"], candidate=snapshot["candidate"], development=development,
                development_request=snapshot["request"], development_packet=snapshot.get("development_packet"),
                holdout=dict(case_count=len(cases), policy_run_count=sum(8 for c in cases if c["status"] == "completed"),
                             expected_policy_run_count=len(protocol["holdout_cases"]) * 8, criteria=protocol["heldout_usefulness_acceptance"],
                             guard_allowances=protocol["mitigation_acceptance"]["guard_maximum_increase"],
                             aggregate_metrics={k: v for k, v in aggregate.items() if k not in {"case_outcomes", "claim_scope"}}, cases=presentation),
                acceptance=accepted, conclusion=("The frozen candidate meets the predeclared development and heldout criteria." if accepted["overall"] else
                    "The frozen candidate does not meet every predeclared criterion; inspect the complete case table and guard failures."),
                retained_packets=retained,
                limitations=[f"Fixed Theta benchmark and {len(protocol['holdout_cases'])} simulated perturbations; no field calibration or general safety claim.",
                             "The heldout suite was executed once after candidate freeze; unfavorable and invalid cases are retained in the table.",
                             "All complete traces were independently checked during execution and retained in compressed case packets. Extra retention was authorized before outcomes without changing any criteria.",
                             "This is a fixed policy comparison. No algorithmic superiority is claimed without a complete equal-budget optimization baseline."])
    if suite_type == "declared_robustness":
        result["acceptance"]["suite_usefulness"] = result["acceptance"].pop("heldout_usefulness")
        result["conclusion"] = ("The recorded policies meet the declared base-case and robustness-suite criteria." if accepted["overall"] else
                                "The recorded policies do not meet every declared criterion; inspect all cases and guard failures.")
        result["limitations"] = [
            "This is a declared robustness suite. Its transforms are visible and may have been reused; it is not a heldout evaluation.",
            "The original model's full horizon is retained. Shifted fault windows are clipped using the formula declared before execution, preserving duration unless it exceeds the horizon.",
            "No field calibration, general safety or algorithmic-superiority claim follows from this policy comparison.",
            "All complete traces were checked during execution and retained in compressed case packets alongside the complete metric table and trace hashes.",
        ]
    if "information_boundary_clarification" in snapshot:
        result["information_boundary_clarification"] = snapshot["information_boundary_clarification"]
        result["limitations"].append(snapshot["information_boundary_clarification"]["content"]["required_report_statement"])
    if "development_search_ledger" in snapshot:
        result["development_search_ledger"] = snapshot["development_search_ledger"]
    return result


def run_holdout(snapshot_path, protocol_path, output_dir, report_path=None, suite_type="heldout_benchmark"):
    protocol, protocol_hash = load_protocol(protocol_path)
    snapshot, snapshot_hash = _load_snapshot(snapshot_path, protocol_hash)
    check_sources(snapshot, ROOT)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    lock = output_dir / "execution.json"
    state = dict(schema_version="stormpilot.heldout-execution.v1", started_at_utc=now(),
                 protocol_sha256=protocol_hash, candidate_snapshot_sha256=snapshot_hash, suite_type=suite_type,
                 status="running", completed_cases=[])
    write_json(lock, state, exclusive=True)
    spec_path = output_dir / "policy-spec.json"
    write_json(spec_path, {key: snapshot[key] for key in ("reference", "candidate")})
    cases, compressed = [], {}
    for transform in protocol["holdout_cases"]:
        identifier = transform["id"]
        request = holdout_request(snapshot, transform, protocol)
        case = dict(case_id=identifier, request=request, status="failed")
        request_path, packet_path = output_dir / f"{identifier}-request.json", output_dir / f"{identifier}-packet.json"
        progress_path = output_dir / f"{identifier}-execution.json"
        write_json(request_path, request)
        print(json.dumps(dict(phase="evaluating_fixed_case", case_id=identifier, completed_cases=len(cases))), flush=True)
        try:
            check_sources(snapshot, ROOT)
            completed = subprocess.run([sys.executable, str(ROOT / "evaluation/worker.py"), "--request", str(request_path),
                                        "--spec", str(spec_path), "--output", str(packet_path), "--progress", str(progress_path)],
                                       cwd=ROOT, capture_output=True, text=True, timeout=1200)
            if completed.returncode:
                raise EvidenceError("isolated engine worker failed: " + completed.stderr[-2000:])
            packet = read_json(packet_path)
            checked = assess_case(packet, snapshot, request, protocol, ROOT)
            case.update(checked, status="completed", full_packet_sha256=hashlib.sha256(packet_path.read_bytes()).hexdigest())
            del packet
        except (EvidenceError, OSError, ValueError, KeyError, TypeError, subprocess.TimeoutExpired) as exc:
            case["error"] = str(exc)
        finally:
            if progress_path.exists():
                case["execution"] = read_json(progress_path)
            if packet_path.exists():
                # Preserve rejected evidence too: an invalid full packet must
                # remain inspectable instead of disappearing after validation.
                gzip_path = output_dir / f"{identifier}-packet.json.gz"
                with packet_path.open("rb") as source, gzip_path.open("wb") as destination:
                    with gzip.GzipFile(fileobj=destination, mode="wb", mtime=0) as zipped:
                        for chunk in iter(lambda: source.read(65536), b""):
                            zipped.write(chunk)
                compressed[identifier] = gzip_path
                case["full_packet_sha256"] = hashlib.sha256(packet_path.read_bytes()).hexdigest()
                packet_path.unlink()
        cases.append(case)
        write_json(output_dir / "case-records.json", cases)
        state["completed_cases"].append(identifier)
        write_json(lock, state)
        gc.collect()
    successful = [c for c in cases if c["status"] == "completed"]
    retained_ids = set()
    if successful:
        retained_ids.add(max(successful, key=lambda c: (c["table"]["reference:ab"]["flood_volume_m3"], c["case_id"]))["case_id"])
        retained_ids.add(max(successful, key=lambda c: (max(v["largest_normalized_guard_increase"] for v in c["outcome"]["comparisons"].values()), c["case_id"]))["case_id"])
    retained = []
    for identifier, path in compressed.items():
        retained.append(dict(case_id=identifier, path=str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path),
                             sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                             validation_status=next(c["status"] for c in cases if c["case_id"] == identifier),
                             highlighted_by_predeclared_rule=identifier in retained_ids))
    report = make_report(cases, snapshot, protocol, protocol_hash, snapshot_hash, retained, suite_type)
    report_path = Path(report_path) if report_path is not None else output_dir.parent / "report.json"
    write_json(report_path, report)
    state.update(status="completed", completed_at_utc=now(), report_sha256=hashlib.sha256(report_path.read_bytes()).hexdigest())
    write_json(lock, state)
    return dict(status=report["status"], acceptance=report["acceptance"], retained_case_ids=sorted(compressed))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    freeze = sub.add_parser("freeze")
    freeze.add_argument("--packet", type=Path, required=True)
    freeze.add_argument("--spec", type=Path, required=True)
    freeze.add_argument("--output", type=Path, default=ROOT / "evaluation/candidate.json")
    freeze.add_argument("--protocol", type=Path, default=ROOT / "evaluation/protocol.json")
    freeze.add_argument("--development-ledger", type=Path, help="Complete development ledger, mandatory for phase 2")
    holdout = sub.add_parser("holdout")
    holdout.add_argument("--snapshot", type=Path, default=ROOT / "evaluation/candidate.json")
    holdout.add_argument("--protocol", type=Path, default=ROOT / "evaluation/protocol.json")
    holdout.add_argument("--output-dir", type=Path, default=ROOT / "evaluation/heldout")
    holdout.add_argument("--report", type=Path, help="Default: report.json beside the case output directory")
    args = parser.parse_args()
    result = freeze_candidate(args.packet, args.spec, args.output, args.protocol, args.development_ledger) if args.command == "freeze" else run_holdout(args.snapshot, args.protocol, args.output_dir, args.report)
    print(json.dumps(result), flush=True)


if __name__ == "__main__":
    main()
