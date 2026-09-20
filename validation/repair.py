"""Independent accounting and selection checks for compact policy-search records.

Nonselected runs have metrics and trace digests, not full traces. This auditor
checks their internal accounting but only independently integrates retained runs.
It never imports the producer's policy, simulator, or ranking implementation.
"""
from __future__ import annotations

import hashlib
import json
import re
from itertools import product

from .metrics import EvidenceError, METRIC_UNITS, close_enough, finite_number
from .properties import evaluate_property

SUBSETS = ("empty", "a", "b", "ab")
GUARDS = {"peak_downstream_flow_m3s": 0.001, "downstream_excess_volume_m3": 1.0, "terminal_storage_m3": 0.1}
ACCEPTANCE = dict(minimum_absolute_flood_reduction_m3=10.0, minimum_relative_flood_reduction=0.1,
                  guard_maximum_increase=GUARDS, other_subsets_flood_increase_allowance_m3=1.0,
                  arithmetic_tolerance=1e-6)


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def require(condition, message):
    if not condition:
        raise EvidenceError(message)


def integer(value, label):
    require(type(value) is int and value >= 0, label + " must be a nonnegative integer")
    return value


def matching(actual, expected, label):
    """Keep structure/Booleans exact and tolerate only small arithmetic roundoff."""
    if isinstance(expected, bool) or expected is None or isinstance(expected, str):
        require(type(actual) is type(expected) and actual == expected, label + " differs")
    elif isinstance(expected, (float, int)):
        require(close_enough(actual, expected, absolute=1e-8, relative=1e-10), label + " differs")
    elif isinstance(expected, dict):
        require(isinstance(actual, dict) and actual.keys() == expected.keys(), label + " fields differ")
        for key, value in expected.items():
            matching(actual[key], value, label + "." + key)
    elif isinstance(expected, list):
        require(isinstance(actual, list) and len(actual) == len(expected), label + " length differs")
        for i, (a, b) in enumerate(zip(actual, expected)):
            matching(a, b, f"{label}[{i}]")
    else:
        raise EvidenceError(label + " has unsupported comparison data")


def assess(reference, candidate):
    comparisons, failures = {}, []
    for subset in SUBSETS:
        before, after = reference[subset]["metrics"], candidate[subset]["metrics"]
        changes = {metric: after[metric] - before[metric] for metric in ("flood_volume_m3", *GUARDS)}
        guards = {metric: changes[metric] <= allowance + 1e-6 for metric, allowance in GUARDS.items()}
        for metric, passed in guards.items():
            if not passed:
                failures.append(dict(subset=subset, criterion=metric, increase=changes[metric], allowance=GUARDS[metric]))
        if subset != "ab" and changes["flood_volume_m3"] > 1.0 + 1e-6:
            failures.append(dict(subset=subset, criterion="flood_volume_m3", increase=changes["flood_volume_m3"], allowance=1.0))
        comparisons[subset] = dict(reference=before, candidate=after, changes=changes, guards=guards)
    flood = reference["ab"]["metrics"]["flood_volume_m3"]
    reduction = flood - candidate["ab"]["metrics"]["flood_volume_m3"]
    relative = reduction / flood if flood > 0 else None
    if reduction + 1e-6 < 10 or relative is None or relative + 1e-12 < 0.1:
        failures.append(dict(subset="ab", criterion="material_flood_reduction", absolute_reduction_m3=reduction,
                             relative_reduction=relative, minimum_absolute_m3=10.0, minimum_relative=0.1))
    return dict(eligible=not failures, failures=failures, comparisons=comparisons,
                flood_reduction_m3=reduction, relative_flood_reduction=relative)


def audit_repair(packet, validated_runs):
    repair, request = packet["repair"], packet["request"]
    require(isinstance(repair, dict), "repair must be an object")
    require(repair.get("schema_version") == "stormpilot.repair.v1", "unsupported repair schema")
    require(repair.get("method") == "guard-first-causal-parameter-grid-v1", "unsupported repair method")
    matching(repair.get("acceptance"), ACCEPTANCE, "fixed repair acceptance")
    config = repair["declared_grid"]
    require(isinstance(config, dict), "repair grid must be an object")
    family = config.get("controller_id", "balanced_flow")
    require(family in {"balanced_flow", "plausible_depth"}, "unsupported repair controller family")
    fields = {"target_scales", "balance_gains", "budget"} if family == "balanced_flow" else {
        "target_scales", "jump_thresholds_m", "correction_fractions", "budget", "controller_id"}
    require(set(config) - {"controller_id"} == fields - {"controller_id"}, "repair grid fields differ")
    require(repair["grid_sha256"] == digest(config), "repair grid digest differs")
    require(isinstance(repair["reference_request_sha256"], str) and re.fullmatch(r"[0-9a-f]{64}", repair["reference_request_sha256"]) is not None,
            "reference request digest is malformed")
    original_request_checked = "reference_request" in repair
    if original_request_checked:
        original_request = repair["reference_request"]
        require(isinstance(original_request, dict) and digest(original_request) == repair["reference_request_sha256"],
                "original repair request digest differs from its embedded content")
        excluded = {"fallback_controller_id", "fallback_controller_parameters"}
        require({k:v for k,v in original_request.items() if k not in excluded} ==
                {k:v for k,v in request.items() if k not in excluded},
                "repair changed model, forcing, reference policy or conditions from its original request")
    budget = integer(repair["budget"], "repair budget")
    require(8 <= budget <= 300 and config["budget"] == budget, "repair budget differs from declared grid")
    parameters_and_bounds = [("target_scales", "target_scale", (0.5, 1.5))]
    parameters_and_bounds += ([("balance_gains", "balance_gain", (0.0, 8.0))] if family == "balanced_flow" else
                              [("jump_thresholds_m", "jump_threshold_m", (0.2, 2.0)),
                               ("correction_fractions", "correction_fraction", (0.0, 1.0))])
    for name, parameter, bounds in parameters_and_bounds:
        values = config[name]
        require(isinstance(values, list) and 1 <= len(values) <= 8, "repair grid has invalid size")
        values = [finite_number(v, name) for v in values]
        require(values == sorted(set(values)) and all(bounds[0] <= v <= bounds[1] for v in values), "repair grid values are invalid or duplicated")
    expected_parameters = [dict(zip((p for _,p,_ in parameters_and_bounds), values))
                           for values in product(*(config[name] for name,_,_ in parameters_and_bounds))]
    candidates, ledger = repair["candidates"], repair["ledger"]
    require(isinstance(candidates, list) and isinstance(ledger, list), "repair candidates and ledger must be lists")
    require(integer(repair["simulator_calls"], "simulator calls") == len(ledger) <= budget, "repair hydraulic-call accounting differs")
    require(integer(repair["declared_candidates"], "declared candidates") == len(expected_parameters), "declared grid size differs")
    require(integer(repair["evaluated_candidates"], "evaluated candidates") == len(candidates) <= len(expected_parameters), "evaluated candidate count differs")
    faults = request["faults"]
    require(isinstance(faults, list) and len(faults) == 2, "repair must use exactly two conditions")
    ids = [f["id"] for f in faults]
    require(len(set(ids)) == 2, "repair condition IDs are duplicated")
    subsets = dict(empty=[], a=ids[:1], b=ids[1:], ab=ids)
    contract = request["test_contract"]
    require(contract["metric"] == "flood_volume_m3", "repair requires a flood-volume contract")
    declaration = dict(metric=contract["metric"], unit=contract["units"], mode=contract["mode"],
                       direction=contract["direction"], bound=contract["threshold"], tolerance=contract["tolerance"])
    controller_hashes = [a["sha256"] for a in packet["artifacts"] if a["path"] == "engine/controllers.py"]
    require(len(controller_hashes) == 1, "repair controller source identity is missing")
    continuation_limit = packet["experiment"].get("numerical_tolerances", {}).get("continuity_pct", 1.0)
    cache, consumed, hits, run_ids = {}, 0, 0, set()

    def take(controller_id, parameters, subset, policy, candidate_id):
        nonlocal consumed, hits
        key = (controller_id, digest(parameters), subset)
        if key in cache:
            hits += 1
            return cache[key]
        require(consumed < len(ledger), "repair ledger omits a declared treatment")
        row = ledger[consumed]
        consumed += 1
        require(type(row["call"]) is int and row["call"] == consumed, "repair call numbers are missing or duplicated")
        require(row["policy"] == policy and row["subset"] == subset and row["candidate_id"] == candidate_id,
                "repair ledger treatment or candidate identity differs")
        require(row["active_fault_ids"] == subsets[subset], "repair ledger changes the declared fault subset")
        controller = row["controller"]
        require(controller["id"] == controller_id and controller["source_sha256"] == controller_hashes[0], "repair policy/source identity differs")
        expected_parameters = dict(targets_m3s=[value * parameters.get("target_scale", 1.0) for value in packet["model"]["targets_m3s"]],
                                   control_interval_s=packet["experiment"]["solver_settings"]["control_interval_s"], **parameters)
        matching(controller["parameters"], expected_parameters, "repair effective controller parameters")
        require(isinstance(row["run_id"], str) and row["run_id"], "repair ledger run ID is missing")
        require(row["run_id"] not in run_ids, "repair ledger duplicates a run ID across actual calls")
        run_ids.add(row["run_id"])
        require(isinstance(row["trace_sha256"], str) and re.fullmatch(r"[0-9a-f]{64}", row["trace_sha256"]) is not None, "repair trace digest is malformed")
        require(integer(row["routing_steps"], "routing steps") > 0, "repair ledger has no routing steps")
        require(finite_number(row["runtime_s"], "runtime") >= 0, "repair runtime is negative")
        for metric in METRIC_UNITS:
            finite_number(row["metrics"][metric], metric)
        for metric, value in row["metrics"].items():
            require(finite_number(value, metric) >= -1e-9, "repair ledger has a negative metric")
        if "native_flood_volume_m3" in row["metrics"]:
            matching(row["metrics"]["native_flood_volume_m3"], row["metrics"]["flood_volume_m3"], "repair native flood total")
        for metric in ("runoff_error_pct", "routing_error_pct"):
            require(abs(finite_number(row["continuity"][metric], metric)) <= continuation_limit, "repair ledger continuity exceeds its declared bound")
        result = evaluate_property(declaration, row["metrics"])
        matching(row["contract_result"], dict(violated=result["violated"], metric=contract["metric"], value=result["value"],
                    threshold=contract["threshold"], tolerance=contract["tolerance"], units=contract["units"]), "repair contract result")
        cache[key] = row
        return row

    reference = {s: take(request["controller_id"], request["controller_parameters"], s, "reference", None) for s in SUBSETS}
    joint = all(not reference[s]["contract_result"]["violated"] for s in SUBSETS[:3]) and reference["ab"]["contract_result"]["violated"]
    require(joint or not candidates, "repair tuned a reference that is not a joint failure")
    checked, candidate_rows = [], {}
    for entry, parameters in zip(candidates, expected_parameters):
        require(consumed + 4 <= budget, "repair candidate began without declared call budget")
        identifier = "policy-" + digest(parameters)[:12]
        require(entry["candidate_id"] == identifier and entry["controller_id"] == family and entry["parameters"] == parameters,
                "repair candidates omit, reorder or replace declared grid entries")
        first = consumed
        rows = {s: take(family, parameters, s, "candidate", identifier) for s in SUBSETS}
        require(entry["call_numbers"] == list(range(first + 1, consumed + 1)), "repair candidate call list differs from ledger")
        outcome = assess(reference, rows)
        for name, value in outcome.items():
            matching(entry[name], value, "repair candidate " + name)
        checked.append(entry)
        candidate_rows[identifier] = rows
        if "controller_id" in config:
            # The newer producer releases candidate traces after each grid row.
            # Later identical reference/candidate treatments are actual calls.
            cache.clear()
    require(consumed == len(ledger), "repair ledger includes unaccounted calls")
    require(integer(repair["cache_hits"], "cache hits") == hits, "repair cache accounting differs")
    exhausted = joint and len(candidates) == len(expected_parameters)
    require(type(repair["grid_exhausted"]) is bool and repair["grid_exhausted"] == exhausted, "repair grid exhaustion claim differs")
    require(not joint or exhausted or consumed + 4 > budget, "repair stopped while declared candidates and budget remained")
    reason = "reference_not_joint_failure" if not joint else ("declared_grid_exhausted" if exhausted else "candidate_budget_exhausted")
    require(repair["stopping_reason"] == reason, "repair stopping reason differs")
    selected = min(checked, key=lambda c: (not c["eligible"], len(c["failures"]), c["comparisons"]["ab"]["candidate"]["flood_volume_m3"],
                                           tuple(c["parameters"][p] for _,p,_ in parameters_and_bounds))) if checked else None
    matching(repair["selected"], selected, "repair selected candidate")
    expected_status = "reference_not_joint_failure" if not joint else ("candidate_found" if selected and selected["eligible"] else "no_qualifying_candidate")
    require(repair["status"] == expected_status, "repair status overstates qualifying candidate")
    expected_retained = {("reference", s): row for s, row in reference.items()}
    if selected:
        require(request["fallback_controller_id"] == family and request["fallback_controller_parameters"] == selected["parameters"],
                "repair replay request differs from selected candidate")
        expected_retained.update({("candidate", s): row for s, row in candidate_rows[selected["candidate_id"]].items()})
    seen, full_trace_calls = set(), set()
    require(len(packet["runs"]) == len(expected_retained), "repair retained proof is incomplete")
    for run in packet["runs"]:
        tag = run.get("evaluation_role")
        if tag is None:
            # Generic replay preserves logical roles but need not copy optional
            # evaluation labels. Treatment identity is still checked below
            # against the actual controller, parameters, faults and trace hash.
            replay_roles = {"nominal": ("reference", "empty"), "single_a": ("reference", "a"),
                            "single_b": ("reference", "b"), "stress": ("reference", "ab"),
                            "mitigation_empty": ("candidate", "empty"), "mitigation_a": ("candidate", "a"),
                            "mitigation_b": ("candidate", "b"), "fallback": ("candidate", "ab")}
            require(run.get("role") in replay_roles, "repair proof lacks an explicit or replayable treatment role")
            policy, subset = replay_roles[run["role"]]
            tag = dict(policy=policy, subset=subset)
        key = (tag["policy"], tag["subset"])
        require(key in expected_retained and key not in seen, "repair retained proof has a missing or duplicate treatment")
        seen.add(key)
        row = expected_retained[key]
        validation = validated_runs[run["run_id"]]
        require(validation["status"] == "passed", "repair retained proof failed independent trace checks")
        require(run["controller"] == row["controller"] and run["active_fault_ids"] == row["active_fault_ids"], "repair retained treatment differs from ledger")
        require(digest(run["trace"]) == row["trace_sha256"], "repair retained trace digest differs from ledger")
        matching(run["metrics"], row["metrics"], "repair retained metrics")
        for metric, value in validation["computed_metrics"].items():
            matching(row["metrics"][metric], value, "repair integrated proof " + metric)
        require(run["routing_steps"] == row["routing_steps"], "repair retained routing steps differ")
        full_trace_calls.add(row["call"])
    unique_proof_treatments = {(r["controller"]["id"], digest(r["controller"]["parameters"]), tuple(r["active_fault_ids"])) for r in packet["runs"]}
    require(integer(repair["proof_simulator_calls"], "proof simulator calls") == len(unique_proof_treatments), "repair proof accounting differs")
    limits = ["Nonselected candidate metrics are checked for internal ledger consistency; their full traces are not retained in this repair packet.",
              "This development policy search does not establish heldout usefulness or optimizer superiority."]
    if not original_request_checked:
        limits.append("The original preselection request is not embedded, so its digest is syntactically checked but cannot be independently recomputed from the selected-policy request.")
    return dict(scope="recorded_repair_ledger", simulator_calls=len(ledger), candidate_count=len(candidates),
                rejected_candidate_count=sum(not c["eligible"] for c in candidates), grid_exhausted=exhausted,
                selected_candidate_id=selected["candidate_id"] if selected else None, selected_eligible=selected["eligible"] if selected else False,
                full_trace_audited_calls=len(full_trace_calls), compact_only_calls=len(ledger) - len(full_trace_calls),
                original_reference_request_digest_recomputed=original_request_checked, limitations=limits)
