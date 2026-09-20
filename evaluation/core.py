"""Predeclared treatment generation and independent campaign criteria.

No simulator/controller implementation is imported here. Valid evidence and a
favorable policy outcome are separate fields throughout.
"""

from __future__ import annotations

import copy
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any, Mapping

from validation.metrics import EvidenceError, METRIC_UNITS, finite_number
from validation.validate_packet import canonical_sha256, validate_packet

SUBSETS = ("empty", "a", "b", "ab")
POLICIES = ("reference", "candidate")


def load_protocol(path: str | Path) -> tuple[dict, str]:
    path = Path(path)
    content = path.read_bytes()
    digest = hashlib.sha256(content).hexdigest()
    expected = path.with_suffix(".sha256").read_text().split()[0]
    if digest != expected:
        raise EvidenceError("frozen evaluation protocol no longer matches its digest")
    protocol = json.loads(content)
    if protocol.get("schema_version") != "stormpilot.evaluation-protocol.v1":
        raise EvidenceError("unsupported evaluation protocol")
    return protocol, digest


def subset_ids(faults: list[dict]) -> dict[str, list[str]]:
    if len(faults) != 2 or len({f.get("id") for f in faults}) != 2:
        raise EvidenceError("joint evaluation requires exactly two uniquely named conditions")
    ids = sorted(f["id"] for f in faults)
    return dict(empty=[], a=[ids[0]], b=[ids[1]], ab=ids)


def holdout_request(snapshot: Mapping, transform: Mapping, protocol: Mapping) -> dict:
    """Generate the exact predeclared case from a frozen pair; no result input."""
    request = copy.deepcopy(snapshot["request"])
    horizon = protocol["horizon_s"]
    request.update(scenario_id=protocol["scenario_id"], rainfall_multiplier=transform["rainfall_multiplier"],
                   seed=transform["seed"], noise_std_m=transform["noise_std_m"],
                   test_contract=copy.deepcopy(protocol["primary_contract"]))
    for fault in request["faults"]:
        duration = min((fault["end_s"] - fault["start_s"]) * transform["duration_scale"], horizon)
        if duration <= 0:
            raise EvidenceError("transformed fault has no positive duration")
        shift = transform.get("fault_time_shift_s", {}).get(fault["type"], transform["time_shift_s"])
        start = min(max(fault["start_s"] + shift, 0), horizon - duration)
        fault.update(start_s=start, end_s=start + duration)
        if fault["type"] == "valve_stuck" and fault.get("setting") is not None:
            fault["setting"] = min(1.0, max(0.0, fault["setting"] + transform["valve_setting_delta"]))
        elif fault["type"] == "sensor_bias":
            fault["bias_m"] *= transform["sensor_bias_scale"]
    request["faults"].sort(key=lambda f: f["id"])
    return request


def _difference(reference: Mapping, candidate: Mapping, protocol: Mapping) -> dict:
    rules = protocol["mitigation_acceptance"]
    tolerance = rules["guard_arithmetic_tolerance"]
    changes = {metric: finite_number(candidate.get(metric), metric) - finite_number(reference.get(metric), metric)
               for metric in METRIC_UNITS}
    before = reference["flood_volume_m3"]
    reduction = -changes["flood_volume_m3"]
    relative = reduction / before if before > 0 else None
    material = reduction + tolerance >= rules["stressed_minimum_absolute_flood_reduction_m3"] and (
        relative is not None and relative + 1e-12 >= rules["stressed_minimum_relative_flood_reduction"]
    )
    guards = {metric: changes[metric] <= maximum + tolerance
              for metric, maximum in rules["guard_maximum_increase"].items()}
    normalized = {metric: changes[metric] / maximum for metric, maximum in rules["guard_maximum_increase"].items()}
    return dict(reference=dict(reference), candidate=dict(candidate), changes=changes,
                flood_reduction_m3=reduction, relative_flood_reduction=relative,
                material_flood_improvement=material, guards=guards, all_guards_pass=all(guards.values()),
                largest_normalized_guard_increase=max(normalized.values()))


def assess_table(table: Mapping, protocol: Mapping) -> dict:
    """Recompute all criteria from eight metric rows, without trusting flags."""
    expected = {(p, s) for p in POLICIES for s in SUBSETS}
    if set(table) != {f"{p}:{s}" for p, s in expected}:
        raise EvidenceError("evaluation table must contain each policy and fault subset exactly once")
    limit = protocol["primary_contract"]["threshold"]
    tolerance = protocol["primary_contract"]["tolerance"]
    primary = {key: finite_number(metrics.get("flood_volume_m3"), "flood_volume_m3") > limit + tolerance
               for key, metrics in table.items()}
    secondary_limit = protocol["secondary_detection_contract"]["threshold"]
    secondary = {key: metrics["flood_volume_m3"] > secondary_limit + tolerance for key, metrics in table.items()}
    comparisons = {s: _difference(table[f"reference:{s}"], table[f"candidate:{s}"], protocol) for s in SUBSETS}
    joint = all(not primary[f"reference:{s}"] for s in ("empty", "a", "b")) and primary["reference:ab"]
    interaction = sum(sign * table[f"reference:{s}"]["flood_volume_m3"] for s, sign in (("ab", 1), ("a", -1), ("b", -1), ("empty", 1)))
    other_nonregression = all(comparisons[s]["changes"]["flood_volume_m3"] <= protocol["mitigation_acceptance"]["primary_nonregression_allowance_m3_other_subsets"] + tolerance
                              for s in ("empty", "a", "b"))
    guards_pass = all(c["all_guards_pass"] for c in comparisons.values())
    return dict(primary_violations=primary, secondary_violations=secondary,
                joint_failure=joint, interaction_excess_m3=interaction,
                material_superadditivity=interaction + tolerance >= protocol["joint_failure_acceptance"]["material_superadditivity_minimum_m3"],
                comparisons=comparisons, all_guards_pass=guards_pass,
                other_subsets_primary_nonregression=other_nonregression,
                mitigation_passes=comparisons["ab"]["material_flood_improvement"] and guards_pass and other_nonregression)


def assess_case(packet: Mapping, snapshot: Mapping, expected_request: Mapping, protocol: Mapping,
                root_path: str | Path | None = None) -> dict:
    """Validate actual full traces and then apply predeclared case criteria."""
    checked = validate_packet(packet, root_path)
    if checked["status"] != "passed":
        raise EvidenceError("case packet did not pass independent evidence checks: " + "; ".join(
            c["id"] + ": " + c["message"] for c in checked["checks"] if c["required"] and c["status"] != "passed"
        ))
    if "artifacts" in snapshot:
        frozen = {a["path"]: a["sha256"] for a in snapshot["artifacts"]}
        actual = {a["path"]: a["sha256"] for a in packet["artifacts"]}
        if actual != frozen:
            raise EvidenceError("case executable/model artifacts changed after candidate freeze")
    for key in ("scenario_id", "rainfall_multiplier", "seed", "noise_std_m", "faults", "test_contract"):
        if packet["request"].get(key) != expected_request.get(key):
            raise EvidenceError(f"evaluated request differs from its fixed case: {key}")
    if packet["experiment"]["horizon_s"] != protocol["horizon_s"]:
        raise EvidenceError("case changed the evaluation horizon")
    expected_boundary = protocol["information_boundary_id"]
    clarification = snapshot.get("information_boundary_clarification")
    if clarification is not None:
        content = clarification["content"]
        if content["protocol_sha256"] != snapshot["protocol_sha256"] or content["declared_information_boundary_id"] != expected_boundary:
            raise EvidenceError("information-boundary clarification belongs to a different protocol")
        expected_boundary = content["execution_information_boundary_id"]
    if packet["experiment"]["information_boundary_id"] != expected_boundary:
        raise EvidenceError("case information boundary differs from the protocol or disclosed clarification")
    expected_faults = subset_ids(expected_request["faults"])
    table, traces, treatments = {}, {}, {}
    for run in packet["runs"]:
        identity = run.get("evaluation_role")
        if not isinstance(identity, dict) or identity.get("policy") not in POLICIES or identity.get("subset") not in SUBSETS:
            raise EvidenceError("case runs require explicit policy/subset evaluation roles")
        policy, subset = identity["policy"], identity["subset"]
        key = f"{policy}:{subset}"
        if key in table:
            raise EvidenceError("duplicate policy/subset result cannot replace an unfavorable case")
        spec = snapshot[policy]
        if run["controller"]["id"] != spec["controller_id"]:
            raise EvidenceError("evaluated controller differs from the frozen candidate/reference")
        for parameter, value in spec["parameters"].items():
            if run["controller"]["parameters"].get(parameter) != value:
                raise EvidenceError(f"evaluated policy changed its frozen parameter: {parameter}")
        if run["active_fault_ids"] != expected_faults[subset]:
            raise EvidenceError("evaluated active faults differ from the declared subset")
        table[key] = checked["runs"][run["run_id"]]["computed_metrics"]
        traces[key] = dict(run_id=run["run_id"], rows=len(run["trace"]), sha256=canonical_sha256(run["trace"]))
        treatments[key] = dict(controller=run["controller"], context=run["context"], active_fault_ids=run["active_fault_ids"])
    outcome = assess_table(table, protocol)
    return dict(evidence_status="passed_at_execution", evidence_basis="Full routing traces independently checked in this execution.",
                validation_counts=dict(Counter(c["status"] for c in checked["checks"])), table=table,
                trace_records=traces, treatments=treatments, outcome=outcome)


def assess_campaign(cases: list[Mapping], snapshot: Mapping, protocol: Mapping) -> dict:
    """Reject missing/duplicate/transformed cases and recompute suite outcomes."""
    expected = {case["id"]: case for case in protocol["holdout_cases"]}
    seen = set()
    outcomes = {}
    failures = []
    for case in cases:
        identifier = case.get("case_id")
        if identifier not in expected or identifier in seen:
            raise EvidenceError("heldout campaign has an undeclared or duplicated case")
        seen.add(identifier)
        request = holdout_request(snapshot, expected[identifier], protocol)
        if case.get("request") != request:
            raise EvidenceError(f"heldout case {identifier} changed its frozen request")
        if case.get("status") != "completed":
            failures.append(identifier)
            continue
        outcomes[identifier] = assess_table(case.get("table", {}), protocol)
    if seen != set(expected):
        raise EvidenceError("heldout campaign omits declared cases; an incomplete table cannot support a success claim")
    rules = protocol["heldout_usefulness_acceptance"]
    joint_before = sum(c["comparisons"]["ab"]["reference"]["flood_volume_m3"] for c in outcomes.values())
    joint_after = sum(c["comparisons"]["ab"]["candidate"]["flood_volume_m3"] for c in outcomes.values())
    reduction = joint_before - joint_after
    relative = reduction / joint_before if joint_before > 0 else None
    material_cases = [key for key, case in outcomes.items() if case["comparisons"]["ab"]["material_flood_improvement"]]
    all_guards = not failures and all(case["all_guards_pass"] for case in outcomes.values())
    all_primary = not failures and all(comp["changes"]["flood_volume_m3"] <= rules["maximum_primary_increase_m3_each_case"] + 1e-6
                                     for case in outcomes.values() for comp in case["comparisons"].values())
    useful = not failures and all_guards and all_primary and reduction + 1e-6 >= rules["joint_case_aggregate_minimum_absolute_reduction_m3"] and (
        relative is not None and relative + 1e-12 >= rules["joint_case_aggregate_minimum_relative_reduction"]
    ) and len(material_cases) >= rules["minimum_joint_cases_with_10m3_and_10pct_individual_reduction"]
    return dict(completeness="complete_with_invalid_cases" if failures else "complete", invalid_cases=failures,
                case_outcomes=outcomes, all_case_guards_pass=all_guards, all_case_primary_nonregression=all_primary,
                joint_aggregate_reference_flood_m3=joint_before, joint_aggregate_candidate_flood_m3=joint_after,
                joint_aggregate_flood_reduction_m3=reduction, joint_aggregate_relative_flood_reduction=relative,
                individually_material_joint_cases=material_cases, heldout_usefulness_passes=useful,
                claim_scope=f"Only the {len(expected)} fixed simulated perturbations and declared guard allowances.")
