"""Execute every recorded experiment again; validation stays independent."""
from runner import packet, run_simulation


def replay(original):
    if not isinstance(original, dict) or original.get("schema_version") != "stormpilot.evidence.v1":
        raise ValueError("Replay input must be a StormPilot evidence.v1 packet.")
    if not isinstance(original.get("runs"), list) or not 1 <= len(original["runs"]) <= 80:
        raise ValueError("Replay packet must contain 1 to 80 recorded runs.")
    request = original["request"]
    runs, cache = [], {}
    for old in original["runs"]:
        key = (old["controller"]["id"], tuple(sorted(old["active_fault_ids"])))
        if key not in cache:
            cache[key] = run_simulation(request, old["role"], key[0], key[1])
        run = {**cache[key], "role": old["role"], "run_id": old["run_id"]}
        runs.append(run)
    result = packet(request, runs)
    result["request"] = dict(request)
    for field in ["ablations", "witness", "fallback", "search"]:
        if field in original:
            result[field] = original[field]
    result["replay"] = {"execution_status": "completed", "original_experiment_id": original["experiment_id"],
                        "unique_simulator_calls": len(cache), "recorded_runs_replayed": len(runs),
                        "search_reexecuted": False,
                        "note": "Every recorded configuration was re-executed. Search/reduction declarations are retained for independent comparison; they are not a new search result."}
    return result
