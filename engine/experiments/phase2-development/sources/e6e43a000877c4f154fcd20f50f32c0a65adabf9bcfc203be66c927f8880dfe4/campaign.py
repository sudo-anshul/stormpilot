"""Bounded, reproducible search for joint sensor/actuator contract failures.

Screening retains compact summaries. Only a selected clean/A/B/AB comparison and
its fallback retain full physical traces. Their independent validation must not
be presented as independent validation of the entire screening ledger.
"""
from itertools import product
import math

from models import digest
from runner import METRICS, packet, prepare, run_simulation


def normalize_discovery(request):
    base, model, *_ = prepare({**request, "faults": []})
    supplied = request.get("discovery", {})
    allowed = {"sensor_asset", "valve_asset", "bias_values_m", "sensor_windows_s", "valve_settings", "valve_windows_s", "budget"}
    if not isinstance(supplied, dict) or set(supplied)-allowed:
        raise ValueError("discovery must be an object using only the documented search-grid fields.")
    budget = supplied.get("budget", 40)
    if isinstance(budget, bool) or not isinstance(budget, int) or not 9 <= budget <= 300:
        raise ValueError("discovery.budget must be an integer from 9 to 300, including proof and fallback calls.")
    selected_asset = model["assets"][-1]
    sensor = str(supplied.get("sensor_asset", selected_asset["node_id"]))
    valve = str(supplied.get("valve_asset", selected_asset["id"]))
    if sensor not in {a["node_id"] for a in model["assets"]} or valve not in {a["id"] for a in model["assets"]}:
        raise ValueError("Discovery sensor/valve must exist in the selected model.")

    def numbers(name, defaults, lower, upper):
        values = supplied.get(name, defaults)
        if not isinstance(values, list) or not 1 <= len(values) <= 8:
            raise ValueError("discovery." + name + " must contain 1 to 8 numbers.")
        if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or not lower <= v <= upper for v in values):
            raise ValueError(f"discovery.{name} values must be finite and in [{lower}, {upper}].")
        if len(set(values)) != len(values):
            raise ValueError("Discovery grid values must be unique.")
        return sorted(float(v) for v in values)

    def windows(name, defaults):
        values = supplied.get(name, defaults)
        if not isinstance(values, list) or not 1 <= len(values) <= 8:
            raise ValueError("discovery." + name + " must contain 1 to 8 windows.")
        result = []
        for window in values:
            if not isinstance(window, list) or len(window) != 2:
                raise ValueError("Each discovery window must be [start_s, end_s].")
            if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) for v in window):
                raise ValueError("Discovery window endpoints must be finite numbers.")
            start, end = window
            if not 0 <= start < end <= model["horizon_s"] or any(abs(v/300-round(v/300)) > 1e-9 for v in window):
                raise ValueError("Discovery windows must be within the model horizon and aligned to the 300-second control grid.")
            result.append([float(start), float(end)])
        if len({tuple(w) for w in result}) != len(result):
            raise ValueError("Discovery windows must be unique.")
        return sorted(result)

    config = {"sensor_asset": sensor, "valve_asset": valve,
              "bias_values_m": numbers("bias_values_m", [0.25, 0.5, 1.0], -5, 5),
              "sensor_windows_s": windows("sensor_windows_s", [[10800, 21600]]),
              "valve_settings": numbers("valve_settings", [0.03, 0.035, 0.04], 0, 1),
              "valve_windows_s": windows("valve_windows_s", [[21600, 28800]]), "budget": budget}
    if len(config["bias_values_m"])*len(config["sensor_windows_s"]) > 32 or len(config["valve_settings"])*len(config["valve_windows_s"]) > 32:
        raise ValueError("Discovery supports at most 32 sensor variants and 32 valve variants per declared grid.")
    return base, model, config


def discover(request):
    base, model, config = normalize_discovery(request)
    sensors = [{"id": f"sensor-{i+1}", "type": "sensor_bias", "asset": config["sensor_asset"],
                "bias_m": bias, "start_s": window[0], "end_s": window[1]}
               for i, (bias, window) in enumerate(product(config["bias_values_m"], config["sensor_windows_s"]))]
    valves = [{"id": f"valve-{i+1}", "type": "valve_stuck", "asset": config["valve_asset"],
               "setting": setting, "start_s": window[0], "end_s": window[1]}
              for i, (setting, window) in enumerate(product(config["valve_settings"], config["valve_windows_s"]))]
    budget, ledger, singles, eligible = config["budget"], [], {}, []
    screening_limit = budget - 5  # Reserve all four paired proof runs and fallback.
    metric_name = base["test_contract"]["metric"]

    def execute(case, active, role, controller=None, parameters=None, retain=False):
        if len(ledger) >= budget:
            raise RuntimeError("Discovery exhausted its declared simulator-call budget.")
        run = run_simulation(case, role, controller, active, parameters)
        summary = {"call": len(ledger)+1, "phase": role, "run_id": run["run_id"],
                   "request_sha256": digest(prepare(case)[0]), "active_fault_ids": run["active_fault_ids"],
                   "faults": case["faults"], "context": run["context"], "controller": run["controller"],
                   "metrics": run["metrics"], "contract_result": run["contract_result"],
                   "continuity": run["continuity"], "trace_sha256": digest(run["trace"]),
                   "routing_steps": run["routing_steps"], "runtime_s": run["runtime_s"]}
        ledger.append(summary)
        return run if retain else summary

    empty_case = {**base, "faults": []}
    nominal_screen = execute(empty_case, [], "screen_nominal")
    baseline_passes = not nominal_screen["contract_result"]["violated"]
    tested_pairs = 0
    if baseline_passes:
        for fault in sensors + valves:
            if len(ledger) >= screening_limit:
                break
            singles[fault["id"]] = execute({**base, "faults": [fault]}, [fault["id"]], "screen_single")
        for sensor, valve in product(sensors, valves):
            if len(ledger) >= screening_limit:
                break
            a, b = singles.get(sensor["id"]), singles.get(valve["id"])
            if a is None or b is None or a["contract_result"]["violated"] or b["contract_result"]["violated"]:
                continue
            case = {**base, "faults": [sensor, valve]}
            joint = execute(case, [sensor["id"], valve["id"]], "screen_pair")
            tested_pairs += 1
            if joint["contract_result"]["violated"]:
                individual_sum = a["metrics"][metric_name] + b["metrics"][metric_name]
                interaction = joint["metrics"][metric_name] - individual_sum + nominal_screen["metrics"][metric_name]
                eligible.append((individual_sum, -interaction, sensor["id"], valve["id"], case))
    eligible.sort(key=lambda item: item[:4])
    selected_case = eligible[0][4] if eligible else empty_case
    ids = [fault["id"] for fault in selected_case["faults"]]
    runs, proof_cache, proof_calls, proof_hits = [], {}, 0, 0

    def proof(active, role, controller=None, parameters=None):
        nonlocal proof_calls, proof_hits
        controller = controller or base["controller_id"]
        parameters = parameters if parameters is not None else base["controller_parameters"]
        key = (controller, digest(parameters), tuple(sorted(active)))
        if key in proof_cache:
            proof_hits += 1
            run = {**proof_cache[key], "role": role, "run_id": role + "-" + proof_cache[key]["run_id"]}
        else:
            run = execute(selected_case, active, role, controller, parameters, retain=True)
            proof_cache[key] = run
            proof_calls += 1
        runs.append(run)
        return run

    nominal = proof([], "nominal")
    a = proof(ids[:1], "single_sensor") if ids else None
    b = proof(ids[1:], "single_valve") if ids else None
    stressed = proof(ids, "stress")
    fallback = proof(ids, "fallback", base["fallback_controller_id"], base["fallback_controller_parameters"])
    interaction_verified = bool(ids and not nominal["contract_result"]["violated"] and
                                not a["contract_result"]["violated"] and not b["contract_result"]["violated"] and
                                stressed["contract_result"]["violated"])
    result = packet(selected_case, runs)
    result["ablations"] = []
    result["witness"] = None
    if interaction_verified:
        result["ablations"] = [{"source_run_id": stressed["run_id"], "run_id": a["run_id"], "removed_fault_ids": ids[1:]},
                               {"source_run_id": stressed["run_id"], "run_id": b["run_id"], "removed_fault_ids": ids[:1]}]
        result["witness"] = {"run_id": stressed["run_id"], "original_run_id": stressed["run_id"], "claim": "1-minimal",
                             "single_removals": [{"fault_id": ids[1], "run_id": a["run_id"]}, {"fault_id": ids[0], "run_id": b["run_id"]}],
                             "guarantee": "Both conditions are necessary for this violation in the retained paired experiment; neither single condition violates the declared contract."}
    # These allowances were fixed before controller tuning in the independent
    # evaluation protocol. They permit small reported changes, not zero change.
    allowances = {"flood_volume_m3": 1.0, "peak_downstream_flow_m3s": 0.001,
                  "downstream_excess_volume_m3": 1.0, "terminal_storage_m3": 0.1}
    result["fallback"] = {"stressed_run_id": stressed["run_id"], "fallback_run_id": fallback["run_id"],
                          "primary_metric": metric_name, "minimum_improvement": 10.0 if metric_name == "flood_volume_m3" else 0.0,
                          "tolerance": 1e-6,
                          "maximum_increase": {metric: allowances[metric] for metric in METRICS if metric != metric_name}}
    proof_status = "nominal_violation" if nominal["contract_result"]["violated"] else ("witness_found" if interaction_verified else "no_violation_found")
    result["search"] = {"status": proof_status, "method": "retained-paired-proof-v1", "budget": proof_calls,
                        "simulator_calls": proof_calls, "cache_hits": proof_hits, "nominal_passes": not nominal["contract_result"]["violated"],
                        "stopping_reason": "single_deletion_neighborhood_complete" if interaction_verified else "retained_reference_evaluated",
                        "envelope_fault_ids": ids, "global_minimality_claimed": False,
                        "candidates": [{"run_id": run["run_id"], "phase": run["role"], "active_fault_ids": run["active_fault_ids"], **run["contract_result"]}
                                       for run in runs if run["role"] != "fallback"],
                        "coverage_note": "These full traces establish only the retained paired proof. The separate discovery ledger records all screening calls and its wider declared grid."}
    eligible_pairs = sum(not singles[s["id"]]["contract_result"]["violated"] and not singles[v["id"]]["contract_result"]["violated"]
                         for s, v in product(sensors, valves) if s["id"] in singles and v["id"] in singles)
    exhausted = baseline_passes and len(singles) == len(sensors)+len(valves) and tested_pairs == eligible_pairs
    interaction_values = None
    if ids:
        values = {"nominal": nominal["metrics"][metric_name], "sensor_only": a["metrics"][metric_name],
                  "valve_only": b["metrics"][metric_name], "joint": stressed["metrics"][metric_name]}
        interaction_values = {**values, "interaction_excess": values["joint"]-values["sensor_only"]-values["valve_only"]+values["nominal"]}
    result["discovery"] = {"schema_version": "stormpilot.discovery.v1", "method": "single-screen-then-pair-grid-v1",
                           "status": "baseline_failed" if not baseline_passes else ("interaction_found" if interaction_verified else "no_interaction_found"),
                           "budget": budget, "simulator_calls": len(ledger), "screening_calls": len(ledger)-proof_calls,
                           "proof_simulator_calls": proof_calls, "proof_cache_hits": proof_hits,
                           "declared_grid": config, "grid_sha256": digest(config), "contract_sha256": result["test_contract_sha256"],
                           "declared_sensor_variants": len(sensors), "declared_valve_variants": len(valves),
                           "declared_pairs": len(sensors)*len(valves), "screened_singles": len(singles), "screened_pairs": tested_pairs,
                           "eligible_interactions_found": len(eligible), "grid_exhausted": exhausted,
                           "stopping_reason": "baseline_failed" if not baseline_passes else ("declared_grid_exhausted" if exhausted else "screening_budget_exhausted"),
                           "selection_rule": "Among joint failures with passing singles, minimize summed single-condition metric, then maximize interaction excess; stable fault-ID tie-break.",
                           "joint_proof_verified_by_engine": interaction_verified, "interaction_values": interaction_values,
                           "ledger": ledger,
                           "coverage_note": "This bounded grid searches specified biases, partial valve settings and control-aligned time windows at the declared rainfall. It is not a global fault search. Supplied request.faults are replaced by the explicitly declared discovery grid.",
                           "verification_scope": "The retained full traces can be independently recomputed and replayed. Screening summaries and trace hashes are an audit ledger, not independently trace-validated evidence."}
    return result
