"""Guard-first bounded tuning of a causal controller on a fixed witness.

This is development-set optimization, not held-out validation. Every rejected
candidate stays in the compact ledger; full traces are retained for the four
reference treatments and four selected candidate treatments.
"""
from itertools import product

from controllers import normalize_parameters
from models import digest
from runner import packet, prepare, run_simulation

GUARDS = {"peak_downstream_flow_m3s": 0.001, "downstream_excess_volume_m3": 1.0, "terminal_storage_m3": 0.1}
MINIMUM_ABSOLUTE_REDUCTION = 10.0
MINIMUM_RELATIVE_REDUCTION = 0.10
OTHER_FLOOD_ALLOWANCE = 1.0
TOLERANCE = 1e-6


def normalize_repair(request):
    base, model, *_ = prepare(request)
    if len(base["faults"]) != 2:
        raise ValueError("Repair requires the immutable two-condition witness request.")
    if base["test_contract"]["metric"] != "flood_volume_m3":
        raise ValueError("Repair currently supports flood-volume contracts only.")
    config = request.get("repair", {})
    if not isinstance(config, dict) or set(config)-{"target_scales", "balance_gains", "budget"}:
        raise ValueError("repair must contain only target_scales, balance_gains and budget.")
    budget = config.get("budget", 120)
    if isinstance(budget, bool) or not isinstance(budget, int) or not 8 <= budget <= 300:
        raise ValueError("repair.budget must be an integer from 8 to 300, including all reference and candidate calls.")

    def values(name, default, parameter):
        items = config.get(name, default)
        if not isinstance(items, list) or not 1 <= len(items) <= 8:
            raise ValueError("repair." + name + " must contain 1 to 8 unique numbers.")
        normalized = [normalize_parameters("balanced_flow", {parameter: item})[parameter] for item in items]
        if len(set(normalized)) != len(normalized):
            raise ValueError("Repair grid values must be unique.")
        return sorted(normalized)

    return base, model, {"target_scales": values("target_scales", [0.90, 0.94, 0.96, 0.98, 1.0], "target_scale"),
                         "balance_gains": values("balance_gains", [0.5, 1.0, 2.0, 4.0, 8.0], "balance_gain"),
                         "budget": budget}


def assess_candidate(reference, candidate):
    """Fixed guard criteria, evaluated before primary-metric ranking."""
    comparisons, failures = {}, []
    for subset in ("empty", "a", "b", "ab"):
        before, after = reference[subset]["metrics"], candidate[subset]["metrics"]
        deltas = {metric: after[metric]-before[metric] for metric in ("flood_volume_m3", *GUARDS)}
        passed = {metric: deltas[metric] <= allowance + TOLERANCE for metric, allowance in GUARDS.items()}
        for metric, ok in passed.items():
            if not ok:
                failures.append({"subset": subset, "criterion": metric, "increase": deltas[metric], "allowance": GUARDS[metric]})
        if subset != "ab" and deltas["flood_volume_m3"] > OTHER_FLOOD_ALLOWANCE + TOLERANCE:
            failures.append({"subset": subset, "criterion": "flood_volume_m3", "increase": deltas["flood_volume_m3"], "allowance": OTHER_FLOOD_ALLOWANCE})
        comparisons[subset] = {"reference": before, "candidate": after, "changes": deltas, "guards": passed}
    before = reference["ab"]["metrics"]["flood_volume_m3"]
    reduction = before-candidate["ab"]["metrics"]["flood_volume_m3"]
    relative = reduction/before if before > 0 else None
    material = reduction+TOLERANCE >= MINIMUM_ABSOLUTE_REDUCTION and relative is not None and relative+1e-12 >= MINIMUM_RELATIVE_REDUCTION
    if not material:
        failures.append({"subset": "ab", "criterion": "material_flood_reduction", "absolute_reduction_m3": reduction,
                         "relative_reduction": relative, "minimum_absolute_m3": MINIMUM_ABSOLUTE_REDUCTION,
                         "minimum_relative": MINIMUM_RELATIVE_REDUCTION})
    return {"eligible": not failures, "failures": failures, "comparisons": comparisons,
            "flood_reduction_m3": reduction, "relative_flood_reduction": relative}


def repair(request):
    base, model, config = normalize_repair(request)
    ids = [fault["id"] for fault in base["faults"]]
    subsets = {"empty": [], "a": ids[:1], "b": ids[1:], "ab": ids}
    ledger, candidates, reference = [], [], {}
    best = None
    selected_runs = None
    selected_parameters = None
    budget = config["budget"]
    cache, cache_hits = {}, 0

    def execute(controller, parameters, subset, policy, candidate_id=None):
        nonlocal cache_hits
        role = ({"empty": "nominal", "a": "single_a", "b": "single_b", "ab": "stress"}[subset]
                if policy == "reference" else ("fallback" if subset == "ab" else "mitigation_"+subset))
        key = (controller, digest(parameters), subset)
        if key in cache:
            cache_hits += 1
            return {**cache[key], "role": role, "run_id": role + "-" + cache[key]["run_id"],
                    "evaluation_role": {"policy": policy, "subset": subset}}
        if len(ledger) >= budget:
            raise RuntimeError("Repair exceeded its declared simulator-call budget.")
        run = run_simulation(base, role, controller, subsets[subset], parameters)
        run["evaluation_role"] = {"policy": policy, "subset": subset}
        cache[key] = run
        ledger.append({"call": len(ledger)+1, "policy": policy, "subset": subset, "candidate_id": candidate_id,
                       "run_id": run["run_id"], "controller": run["controller"], "active_fault_ids": run["active_fault_ids"],
                       "metrics": run["metrics"], "contract_result": run["contract_result"], "continuity": run["continuity"],
                       "trace_sha256": digest(run["trace"]), "routing_steps": run["routing_steps"], "runtime_s": run["runtime_s"]})
        return run

    for subset in subsets:
        reference[subset] = execute(base["controller_id"], base["controller_parameters"], subset, "reference")
    valid_reference = (all(not reference[s]["contract_result"]["violated"] for s in ("empty", "a", "b")) and
                       reference["ab"]["contract_result"]["violated"])
    if valid_reference:
        for scale, gain in product(config["target_scales"], config["balance_gains"]):
            if len(ledger)+4 > budget:
                break
            parameters = {"target_scale": scale, "balance_gain": gain}
            candidate_id = "policy-" + digest(parameters)[:12]
            first_call = len(ledger)
            runs = {subset: execute("balanced_flow", parameters, subset, "candidate", candidate_id) for subset in subsets}
            outcome = assess_candidate(reference, runs)
            entry = {"candidate_id": candidate_id, "controller_id": "balanced_flow", "parameters": parameters,
                     "call_numbers": list(range(first_call+1, len(ledger)+1)), **outcome}
            candidates.append(entry)
            # Feasibility dominates flood reduction: a larger spill reduction
            # cannot compensate for violating an independently declared guard.
            rank = (not outcome["eligible"], len(outcome["failures"]), runs["ab"]["metrics"]["flood_volume_m3"], scale, gain)
            if best is None or rank < best:
                best, selected_runs, selected_parameters = rank, runs, parameters

    effective = dict(base)
    if selected_parameters is not None:
        effective["fallback_controller_id"] = "balanced_flow"
        effective["fallback_controller_parameters"] = selected_parameters
    retained = list(reference.values()) + (list(selected_runs.values()) if selected_runs else [])
    result = packet(effective, retained)
    stressed = reference["ab"]
    result["ablations"] = [{"source_run_id": stressed["run_id"], "run_id": reference["a"]["run_id"], "removed_fault_ids": ids[1:]},
                           {"source_run_id": stressed["run_id"], "run_id": reference["b"]["run_id"], "removed_fault_ids": ids[:1]}]
    result["witness"] = ({"run_id": stressed["run_id"], "original_run_id": stressed["run_id"], "claim": "1-minimal",
                          "single_removals": [{"fault_id": ids[1], "run_id": reference["a"]["run_id"]},
                                              {"fault_id": ids[0], "run_id": reference["b"]["run_id"]}],
                          "guarantee": "Both declared conditions are necessary for this reference-policy violation in the retained paired experiment."}
                         if valid_reference else None)
    if selected_runs:
        result["fallback"] = {"stressed_run_id": stressed["run_id"], "fallback_run_id": selected_runs["ab"]["run_id"],
                              "primary_metric": "flood_volume_m3", "minimum_improvement": MINIMUM_ABSOLUTE_REDUCTION,
                              "tolerance": TOLERANCE, "maximum_increase": dict(GUARDS)}
    # Proof accounting is separate from the complete development search ledger.
    proof_calls = len({(r["controller"]["id"], digest(r["controller"]["parameters"]), tuple(r["active_fault_ids"])) for r in retained})
    result["search"] = {"status": "witness_found" if valid_reference else ("nominal_violation" if reference["empty"]["contract_result"]["violated"] else "no_violation_found"),
                        "method": "retained-reference-and-policy-proof-v1", "budget": proof_calls, "simulator_calls": proof_calls,
                        "cache_hits": 0, "nominal_passes": not reference["empty"]["contract_result"]["violated"],
                        "stopping_reason": "single_deletion_neighborhood_complete" if valid_reference else "reference_not_joint_failure",
                        "envelope_fault_ids": ids, "global_minimality_claimed": False,
                        "candidates": [{"run_id": r["run_id"], "phase": r["role"], "active_fault_ids": r["active_fault_ids"], **r["contract_result"]}
                                       for r in reference.values()],
                        "coverage_note": "Full traces cover the reference and selected policy on the same four condition subsets. All other tuning evaluations are recorded separately as compact summaries."}
    if not valid_reference:
        # A failing single can invalidate the joint-interaction premise while
        # still establishing an ordinary violation. Do not mislabel that state
        # as either a valid joint witness or a no-violation search result.
        result.pop("search")
    selected_entry = next((c for c in candidates if c["parameters"] == selected_parameters), None)
    grid_size = len(config["target_scales"])*len(config["balance_gains"])
    result["repair"] = {"schema_version": "stormpilot.repair.v1", "method": "guard-first-causal-parameter-grid-v1",
                        "status": "reference_not_joint_failure" if not valid_reference else ("candidate_found" if selected_entry and selected_entry["eligible"] else "no_qualifying_candidate"),
                        "budget": budget, "simulator_calls": len(ledger), "proof_simulator_calls": proof_calls, "cache_hits": cache_hits,
                        "declared_grid": config, "grid_sha256": digest(config), "reference_request_sha256": digest(base),
                        "declared_candidates": grid_size, "evaluated_candidates": len(candidates),
                        "grid_exhausted": valid_reference and len(candidates) == grid_size,
                        "stopping_reason": "reference_not_joint_failure" if not valid_reference else ("declared_grid_exhausted" if len(candidates) == grid_size else "candidate_budget_exhausted"),
                        "selected": selected_entry, "candidates": candidates, "ledger": ledger,
                        "acceptance": {"minimum_absolute_flood_reduction_m3": MINIMUM_ABSOLUTE_REDUCTION,
                                       "minimum_relative_flood_reduction": MINIMUM_RELATIVE_REDUCTION,
                                       "guard_maximum_increase": dict(GUARDS), "other_subsets_flood_increase_allowance_m3": OTHER_FLOOD_ALLOWANCE,
                                       "arithmetic_tolerance": TOLERANCE},
                        "selection_rule": "Reject any guard/nonregression/material-improvement failure before ranking qualifying candidates by joint flood volume. If none qualify, retain the candidate with fewest failed criteria for inspection, explicitly marked unqualified.",
                        "information_boundary": "Current measured depths and declared model geometry only; no rainfall forecast, true simulator depth, active-fault flag or heldout result reaches the controller.",
                        "verification_scope": "This is optimization on the selected development witness. Full retained traces can be independently checked. The compact ledger preserves rejected candidates. Generalization requires a separately frozen held-out campaign."}
    return result
