"""Bounded subset search and honest one-condition-deletion reduction.

Every call, including nominal and fallback, consumes budget. Cached identical
experiments do not. We search only the explicitly supplied fault envelope.
"""
from itertools import combinations
from runner import METRICS, packet, prepare, run_simulation


def investigate(request):
    normalized, model, *_ = prepare(request)
    budget = request.get("search_budget", request.get("budget", 8))
    if isinstance(budget, bool) or not isinstance(budget, int) or not 3 <= budget <= 40:
        raise ValueError("search_budget must be an integer between 3 and 40, including baseline and fallback calls.")
    ids = tuple(f["id"] for f in normalized["faults"])
    cache, runs, candidates, ablations = {}, [], [], []
    calls = hits = 0

    def evaluate(active, role, controller=None):
        nonlocal calls, hits
        controller = controller or normalized["controller_id"]
        key = (controller, tuple(sorted(active)))
        if key in cache:
            hits += 1
            return cache[key]
        if calls >= budget:
            return None
        run = run_simulation(normalized, role, controller, active)
        calls += 1
        cache[key] = run
        runs.append(run)
        return run

    def record(run, phase):
        candidates.append({"run_id": run["run_id"], "active_fault_ids": run["active_fault_ids"],
                           "phase": phase, **run["contract_result"]})

    nominal = evaluate([], "nominal")
    record(nominal, "nominal")
    original = evaluate(ids, "stress")
    # Empty envelope legitimately reuses nominal; roles still need distinct rows.
    if original is nominal:
        original = {**nominal, "role": "stress", "run_id": "stress-" + nominal["run_id"]}
        runs.append(original)
    record(original, "supplied_stress")
    selected = original
    healthy_baseline = not nominal["contract_result"]["violated"]
    found = healthy_baseline and original["contract_result"]["violated"]
    stopping_reason = "supplied_stress_evaluated"

    if healthy_baseline and not found and ids:
        # Nonmonotonic hydraulics means a subset can fail even when the full set
        # does not. Enumerate smaller supplied subsets; keep one call for fallback.
        exhausted = True
        for size in range(1, len(ids)):
            for subset in combinations(ids, size):
                if calls >= budget - 1:
                    exhausted = False
                    break
                run = evaluate(subset, "search_candidate")
                record(run, "subset_sweep")
                if run["contract_result"]["violated"]:
                    selected, found = run, True
                    break
            if found or not exhausted:
                break
        stopping_reason = "witness_found" if found else ("envelope_exhausted" if exhausted else "budget_exhausted")

    if found:
        # Greedy deletion is followed by checking every single deletion of the
        # final set. Only that final complete neighborhood earns '1-minimal'.
        changed = True
        while changed:
            changed = False
            for fault_id in list(selected["active_fault_ids"]):
                subset = [i for i in selected["active_fault_ids"] if i != fault_id]
                key = (normalized["controller_id"], tuple(sorted(subset)))
                if key not in cache and calls >= budget - 1:
                    stopping_reason = "budget_exhausted"
                    break
                run = evaluate(subset, "ablation")
                ablations.append({"source_run_id": selected["run_id"], "run_id": run["run_id"], "removed_fault_ids": [fault_id]})
                record(run, "condition_removal")
                if run["contract_result"]["violated"]:
                    selected, changed = run, True
                    break
            if stopping_reason == "budget_exhausted":
                break

    if selected is not original:
        original["role"] = "original_stress"
        selected["role"] = "stress"
    single_removals = []
    if found:
        for fault_id in selected["active_fault_ids"]:
            subset = tuple(i for i in selected["active_fault_ids"] if i != fault_id)
            run = cache.get((normalized["controller_id"], tuple(sorted(subset))))
            if run is not None and not run["contract_result"]["violated"]:
                single_removals.append({"fault_id": fault_id, "run_id": run["run_id"]})
    one_minimal = found and len(single_removals) == len(selected["active_fault_ids"])
    fallback = evaluate(selected["active_fault_ids"], "fallback", normalized["fallback_controller_id"])
    if fallback is None:
        raise RuntimeError("Search budget accounting failed to reserve a fallback run.")
    if fallback in [nominal, original, selected] or fallback["role"] != "fallback":
        fallback = {**fallback, "role": "fallback", "run_id": "fallback-" + fallback["run_id"]}
        runs.append(fallback)
    result = packet(normalized, runs)
    result["ablations"] = ablations
    result["witness"] = ({"run_id": selected["run_id"], "original_run_id": original["run_id"],
                           "claim": "1-minimal" if one_minimal else "reduced",
                           "single_removals": single_removals,
                           "guarantee": "No single remaining condition can be removed while retaining this violation under the tested model." if one_minimal else "Reduction is incomplete within the declared budget; no minimality claim."} if found else None)
    result["fallback"] = {"stressed_run_id": selected["run_id"], "fallback_run_id": fallback["run_id"],
                          "primary_metric": normalized["test_contract"]["metric"], "minimum_improvement": 0.0,
                          "tolerance": 1e-6,
                          "maximum_increase": {metric: 0.0 for metric in METRICS if metric != normalized["test_contract"]["metric"]}}
    deltas = {metric: fallback["metrics"][metric]-selected["metrics"][metric] for metric in METRICS}
    status = "nominal_violation" if not healthy_baseline else ("witness_found" if found else "no_violation_found")
    result["search"] = {"status": status, "method": "declared-condition-subset-sweep-and-single-deletion-v1",
                        "budget": budget, "simulator_calls": calls, "cache_hits": hits,
                        "nominal_passes": healthy_baseline, "stopping_reason": "single_deletion_neighborhood_complete" if one_minimal else stopping_reason,
                        "envelope_fault_ids": list(ids), "candidates": candidates,
                        "global_minimality_claimed": False, "fallback_metric_deltas": deltas,
                        "coverage_note": "Only subsets of the supplied conditions were tested. Durations, severity, rainfall and unlisted faults were not globally searched."}
    result["request"]["search_budget"] = budget
    return result
