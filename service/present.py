"""Presentation values are derived from completed experiments, never fixtures invented for UI."""
from __future__ import annotations

import math

from engine.models import SCENARIOS, metadata
from engine.controllers import POLICIES, PARAMETER_SPECS, normalize_parameters
from service.common import ROOT, read_json
from service.models import imported_models, resolve_model

METRICS = {
    "flood_volume_m3": ("total overflow", "m³"),
    "peak_downstream_flow_m3s": ("peak downstream flow", "m³/s"),
    "downstream_excess_volume_m3": ("downstream excess volume", "m³"),
}
DEFAULTS = dict(model_id="theta", controller_id="constant_flow", fallback_controller_id="uncontrolled",
                metric="flood_volume_m3", threshold=100.0, fault_asset="1", fault_kind="stuck_closed",
                start_hour=1.0, duration_hours=5.0, budget=8, seed=42, mode="investigate", additional_faults=[],
                fault_setting=0.0, sensor_bias_m=1.0, rainfall_multiplier=1.0, noise_std_m=0.0,
                controller_parameters={}, fallback_controller_parameters={}, discovery=None)


def model_view(model):
    return {
        "id": model["id"], "name": model.get("label", model["id"]),
        "description": model.get("description", ""), "source": model.get("source_url", ""),
        "asset_ids": [a["id"] for a in model.get("assets", [])],
        "nodes": [{**n, "kind": n.get("type", "junction")} for n in model.get("nodes", [])],
        "links": [{**l, "from": l.get("source"), "to": l.get("target")} for l in model.get("links", [])],
        "duration_hours": model.get("horizon_s", 0) / 3600,
        "coordinates_kind": model.get("coordinates_kind", "Benchmark schematic"),
        "origin": model.get("origin", "published"), "flow_units": model.get("input_units"),
        "sha256": model.get("base_model_sha256"), "downstream_link": model.get("downstream_link"),
        "downstream_threshold_m3s": model.get("threshold_m3s"), "targets_m3s": model.get("targets_m3s"),
    }


def catalog():
    build = ROOT / "engine" / "build" / "build.json"
    details = read_json(build) if build.exists() else {}
    return {
        "models": [model_view(m) for m in [*[metadata(k) for k in SCENARIOS], *imported_models()]],
        "policies": [{**p, "name": p["label"], "parameters": [
            {"id": key, "default": spec[0], "min": spec[1], "max": spec[2]}
            for key, spec in PARAMETER_SPECS[p["id"]].items()]} for p in POLICIES],
        "defaults": DEFAULTS,
        "engine": {"status": "ready" if build.exists() else "build_required", "version": str(details.get("version", "EPA SWMM 5.2.4"))},
    }


def number(value, name, low, high):
    if isinstance(value, bool):
        raise ValueError(f"{name} must be a number.")
    result = float(value)
    if not math.isfinite(result) or not low <= result <= high:
        raise ValueError(f"{name} must be between {low:g} and {high:g}.")
    return result


def normalize_config(config):
    if not isinstance(config, dict):
        raise ValueError("Experiment settings must be an object.")
    c = {**DEFAULTS, **{k: v for k, v in config.items() if k in DEFAULTS}}
    custom = resolve_model(c["model_id"]) if c["model_id"] not in SCENARIOS else None
    model = metadata(c["model_id"], custom)
    policies = {p["id"] for p in POLICIES}
    if c["controller_id"] not in policies or c["fallback_controller_id"] not in policies:
        raise ValueError("Choose a supported control policy.")
    if c["metric"] not in METRICS:
        raise ValueError("Choose a supported performance check.")
    assets = {a["id"] for a in model["assets"]}
    sensors = {a["node_id"] for a in model["assets"]}
    kinds = {"stuck_closed", "valve_stuck", "sensor_bias", "sensor_dropout"}
    if c["fault_kind"] not in kinds:
        raise ValueError("Choose a supported outlet or sensor fault.")
    if str(c["fault_asset"]) not in (sensors if c["fault_kind"].startswith("sensor_") else assets):
        raise ValueError("Choose an asset compatible with the selected fault type.")
    c["fault_asset"] = str(c["fault_asset"])
    c["fault_setting"] = number(c["fault_setting"], "Valve opening", 0, 1)
    c["sensor_bias_m"] = number(c["sensor_bias_m"], "Sensor bias", -5, 5)
    c["rainfall_multiplier"] = number(c["rainfall_multiplier"], "Rainfall multiplier", 0.25, 2.5)
    c["noise_std_m"] = number(c["noise_std_m"], "Sensor noise", 0, 0.5)
    c["controller_parameters"] = normalize_parameters(c["controller_id"], c["controller_parameters"])
    c["fallback_controller_parameters"] = normalize_parameters(c["fallback_controller_id"], c["fallback_controller_parameters"])
    horizon = model["horizon_s"] / 3600
    c["start_hour"] = number(c["start_hour"], "Fault onset", 0, horizon - 0.01)
    c["duration_hours"] = number(c["duration_hours"], "Fault duration", 0.01, horizon)
    if c["start_hour"] + c["duration_hours"] > horizon + 1e-8:
        raise ValueError("The fault must end within the simulation horizon.")
    c["threshold"] = number(c["threshold"], "Test threshold", 0, 1e9)
    budget = number(c["budget"], "Search budget", 3, 24)
    if budget != int(budget):
        raise ValueError("Search budget must be a whole number.")
    c["budget"] = int(budget)
    seed = number(c["seed"], "Seed", 0, 2**31 - 1)
    if seed != int(seed):
        raise ValueError("Seed must be a whole number.")
    c["seed"] = int(seed)
    if not isinstance(c["additional_faults"], list) or len(c["additional_faults"]) > 3:
        raise ValueError("Use at most three additional faults.")
    extras = []
    for i, fault in enumerate(c["additional_faults"]):
        if not isinstance(fault, dict) or fault.get("kind", "stuck_closed") not in kinds:
            raise ValueError(f"Additional fault {i + 1} needs a supported fault type.")
        kind = fault.get("kind", "stuck_closed")
        if str(fault.get("asset")) not in (sensors if kind.startswith("sensor_") else assets):
            raise ValueError(f"Additional fault {i + 1} needs a compatible asset in this network.")
        start = number(fault.get("start_hour"), "Additional fault onset", 0, horizon - 0.01)
        duration = number(fault.get("duration_hours"), "Additional fault duration", 0.01, horizon)
        if start + duration > horizon + 1e-8:
            raise ValueError("An additional fault ends after the simulation horizon.")
        extras.append({"asset": str(fault["asset"]), "start_hour": start, "duration_hours": duration, "kind": kind,
                       "setting": number(fault.get("setting", 0), "Valve opening", 0, 1),
                       "bias_m": number(fault.get("bias_m", 1), "Sensor bias", -5, 5)})
    c["additional_faults"] = extras
    conditions = [{"asset": c["fault_asset"], "kind": c["fault_kind"], "start_hour": c["start_hour"], "duration_hours": c["duration_hours"]}, *extras]
    for i, fault in enumerate(conditions):
        for previous in conditions[:i]:
            if (fault["asset"] == previous["asset"]
                    and not fault["kind"].startswith("sensor_") and not previous["kind"].startswith("sensor_")
                    and fault["start_hour"] < previous["start_hour"] + previous["duration_hours"]
                    and previous["start_hour"] < fault["start_hour"] + fault["duration_hours"]):
                raise ValueError("Fault windows on the same outlet must not overlap.")
    if c["mode"] not in ("run", "investigate", "discover"):
        raise ValueError("Choose run, investigate or discover mode.")
    if c["mode"] == "discover":
        if not isinstance(c["discovery"], dict):
            raise ValueError("Declare the discovery envelope before starting a search.")
        # Full envelope validation is performed by the engine's discovery adapter.
        # Reject unbounded or unknown structures before queueing native work.
        allowed = {"sensor_asset", "valve_asset", "bias_values_m", "sensor_windows_s", "valve_settings", "valve_windows_s", "budget"}
        if set(c["discovery"]) - allowed:
            raise ValueError("Unknown discovery envelope field.")
        d = dict(c["discovery"])
        if str(d.get("sensor_asset")) not in sensors or str(d.get("valve_asset")) not in assets:
            raise ValueError("Choose compatible discovery sensor and valve assets.")
        for key, low, high in (("bias_values_m", -5, 5), ("valve_settings", 0, 1)):
            if not isinstance(d.get(key), list) or not 1 <= len(d[key]) <= 8:
                raise ValueError(f"{key} needs 1–8 declared values.")
            d[key] = [number(v, key, low, high) for v in d[key]]
        for key in ("sensor_windows_s", "valve_windows_s"):
            if not isinstance(d.get(key), list) or not 1 <= len(d[key]) <= 8:
                raise ValueError(f"{key} needs 1–8 declared windows.")
            windows = []
            for window in d[key]:
                if not isinstance(window, list) or len(window) != 2:
                    raise ValueError("Discovery windows must contain start and end seconds.")
                start, end = [number(v, "Discovery window", 0, model["horizon_s"]) for v in window]
                if end <= start:
                    raise ValueError("Discovery windows must end after they start.")
                if start % 300 or end % 300:
                    raise ValueError("Discovery windows must align to five-minute control intervals.")
                windows.append([start, end])
            d[key] = windows
        limit = number(d.get("budget", 40), "Discovery call budget", 9, 300)
        if limit != int(limit):
            raise ValueError("Discovery call budget must be a whole number.")
        d["budget"] = int(limit)
        c["discovery"] = d
    return c


def engine_request(config):
    conditions = [{"kind": config["fault_kind"], "asset": config["fault_asset"], "start_hour": config["start_hour"],
                   "duration_hours": config["duration_hours"], "setting": config.get("fault_setting", 0),
                   "bias_m": config.get("sensor_bias_m", 1)}, *config.get("additional_faults", [])]
    faults = []
    for i, condition in enumerate(conditions, 1):
        kind = condition.get("kind", "stuck_closed")
        entry = {"id": f"outlet-{i}", "type": "valve_stuck" if kind == "stuck_closed" else kind,
                 "asset": condition["asset"], "start_s": condition["start_hour"] * 3600,
                 "end_s": (condition["start_hour"] + condition["duration_hours"]) * 3600}
        if entry["type"] == "valve_stuck":
            entry["setting"] = 0 if kind == "stuck_closed" else condition.get("setting", 0)
        elif entry["type"] == "sensor_bias":
            entry["bias_m"] = condition.get("bias_m", 1)
        faults.append(entry)
    request = {
        "scenario_id": config["model_id"], "controller_id": config["controller_id"],
        "fallback_controller_id": config["fallback_controller_id"], "seed": config["seed"],
        "rainfall_multiplier": config.get("rainfall_multiplier", 1), "noise_std_m": config.get("noise_std_m", 0),
        "controller_parameters": config.get("controller_parameters", {}),
        "fallback_controller_parameters": config.get("fallback_controller_parameters", {}),
        "faults": faults,
        "test_contract": {"metric": config["metric"], "threshold": config["threshold"], "tolerance": 1e-6},
        "search_budget": config["budget"],
    }
    if config["model_id"] not in SCENARIOS:
        request["custom_model"] = resolve_model(config["model_id"])
    if config.get("mode") == "discover":
        request["discovery"] = config["discovery"]
    return request


def config_from_native(native, previous=None):
    """Present the policy and conditions actually recorded by a derived run."""
    config = {**DEFAULTS, **(previous or {})}
    config.update(model_id=native["scenario_id"], controller_id=native["controller_id"],
                  fallback_controller_id=native["fallback_controller_id"],
                  controller_parameters=native.get("controller_parameters", {}),
                  fallback_controller_parameters=native.get("fallback_controller_parameters", {}),
                  rainfall_multiplier=native["rainfall_multiplier"], noise_std_m=native["noise_std_m"],
                  threshold=native["test_contract"]["threshold"], metric=native["test_contract"]["metric"],
                  seed=native["seed"], mode="investigate", discovery=None)
    faults = native.get("faults", [])
    if faults:
        first = faults[0]
        config.update(fault_asset=first["asset"], fault_kind=first["type"],
                      fault_setting=first.get("setting") or 0, sensor_bias_m=first.get("bias_m", 1),
                      start_hour=first["start_s"] / 3600, duration_hours=(first["end_s"] - first["start_s"]) / 3600)
        config["additional_faults"] = [{"asset": f["asset"], "kind": f["type"], "setting": f.get("setting") or 0,
                                        "bias_m": f.get("bias_m", 1), "start_hour": f["start_s"] / 3600,
                                        "duration_hours": (f["end_s"] - f["start_s"]) / 3600} for f in faults[1:]]
    return config


def compact_trace(run, maximum=1000):
    trace = run.get("display_trace") or run.get("trace", [])
    if len(trace) <= maximum:
        selected = trace
    else:
        indices = {0, len(trace) - 1}
        stride = max(1, len(trace) // (maximum // 4))
        fields = ["total_flooding_m3s", "downstream_flow_m3s", "total_storage_m3"]
        for start in range(0, len(trace), stride):
            stop = min(len(trace), start + stride)
            indices.add(start)
            for field in fields:
                indices.add(max(range(start, stop), key=lambda i: trace[i].get(field, 0)))
        selected = [trace[i] for i in sorted(indices)]
    # Send only fields consumed by the workbench. Complete physical/observed
    # traces, commands and settings remain in the downloadable evidence packet.
    fields = ("time_s", "total_flooding_m3s", "total_storage_m3", "downstream_flow_m3s")
    return [{**{field: row[field] for field in fields},
             "node_depths_m": row.get("basin_depth_m", row.get("node_depths_m", {}))}
            for row in selected]


def make_view(packet, validation, request, *, recorded=False):
    config = request["config"]
    model = packet.get("model") or metadata(config["model_id"])
    if "id" not in model:
        model = {**metadata(config["model_id"]), **model}
    roles = {"nominal": "Nominal", "stress": "Declared stress case", "reduced": "Reduced witness", "fallback": "Alternative",
             "single_sensor": "Sensor only", "single_valve": "Valve only", "single_a": "Condition A only", "single_b": "Condition B only",
             "mitigation_empty": "Alternative · no faults", "mitigation_a": "Alternative · condition A", "mitigation_b": "Alternative · condition B"}
    fault_list = packet.get("experiment", {}).get("faults", packet.get("faults", []))
    fault_lookup = {f["id"]: f for f in fault_list if isinstance(f, dict)}
    runs = packet.get("runs", [])
    reduction = packet.get("witness") or {}
    original_stress = next((r for r in runs if r.get("role") == "original_stress"), None)
    witness_id = reduction.get("run_id")
    cases = []
    for run in runs:
        role = run.get("role")
        if role == "original_stress":
            role = "stress"
        elif original_stress and run.get("run_id") == witness_id:
            role = "reduced"
        if role not in roles:
            continue
        controller = run.get("controller", {})
        cases.append({"id": run["run_id"], "role": role, "label": roles[role],
                      "controller_id": controller.get("id", controller) if isinstance(controller, dict) else controller,
                      "controller_parameters": controller.get("parameters", {}) if isinstance(controller, dict) else {},
                      "faults": [fault_lookup.get(f, {"id": f}) for f in run.get("active_fault_ids", [])],
                      "metrics": run.get("metrics", {}), "trace": compact_trace(run)})
    stress = next((r for r in runs if r.get("run_id") == witness_id), None) or next((r for r in runs if r.get("role") == "stress"), None)
    nominal = next((r for r in runs if r.get("role") == "nominal"), None)
    metric, threshold = config["metric"], config["threshold"]
    label, unit = METRICS[metric]
    value = stress.get("metrics", {}).get(metric) if stress else None
    base = nominal.get("metrics", {}).get(metric) if nominal else None
    violated = value is not None and value > threshold + 1e-6
    nominal_failed = base is not None and base > threshold + 1e-6
    first = None
    if stress and violated:
        cumulative, previous = 0.0, 0.0
        flow_threshold = packet.get("experiment", {}).get("threshold_m3s", 0.5)
        for row in stress.get("trace", []):
            t = row["time_s"]
            if metric == "flood_volume_m3":
                cumulative += row["total_flooding_m3s"] * (t - previous)
                observed = cumulative
            elif metric == "downstream_excess_volume_m3":
                cumulative += max(0, row["downstream_flow_m3s"] - flow_threshold) * (t - previous)
                observed = cumulative
            else:
                observed = row["downstream_flow_m3s"]
            previous = t
            if observed > threshold + 1e-6:
                first = t
                break
    raw_search = packet.get("search") or {}
    if validation.get("status") == "failed":
        finding_status = "unverified"
        title = "Evidence checks need attention."
    elif value is None or base is None:
        finding_status = "incomplete"
        title = "The experiment is incomplete."
    elif nominal_failed:
        finding_status = "baseline_failure"
        title = "The nominal plan already exceeds this check."
    elif violated:
        finding_status = "violation"
        title = "A weak point in the plan."
    elif (raw_search.get("stopping_reason") == "budget_exhausted"
          or packet.get("discovery", {}).get("stopping_reason") == "screening_budget_exhausted"):
        finding_status = "incomplete"
        title = "The search reached its call budget."
    else:
        finding_status = "no_violation"
        title = "No violation found in the tested case."
    description = (f"The tested case produced {value:,.3f} {unit} of {label}, against a declared check of {threshold:,.3f} {unit}. "
                   f"The nominal case produced {base:,.3f} {unit}." if value is not None and base is not None else "The experiment did not provide the required metric.")
    if nominal_failed:
        description += " This is not a failure introduced only by the stress condition."
    if finding_status == "unverified":
        description += " Required evidence checks failed; inspect them before drawing a conclusion."
    elif finding_status == "incomplete":
        description += " No complete search conclusion is supported. The recorded cases remain available."
    original_run = next((r for r in runs if r.get("run_id") == reduction.get("original_run_id")), stress)
    witness_run = next((r for r in runs if r.get("run_id") == reduction.get("run_id")), stress)
    search = {
        "evaluated": raw_search.get("simulator_calls", len(runs)),
        "budget": raw_search.get("budget", config["budget"] if config["mode"] == "investigate" else len(runs)),
        "status": raw_search.get("status", "declared_cases_evaluated"),
        "stopping_reason": raw_search.get("stopping_reason", "declared_cases_evaluated"),
        "method": raw_search.get("method", "Declared stress case"),
        "reduced_from": len(original_run.get("active_fault_ids", [])) if original_run else 0,
        "reduced_to": len(witness_run.get("active_fault_ids", [])) if witness_run else 0,
        "claim": reduction.get("guarantee", "No reduction claim is available for this run."),
        "coverage": raw_search.get("coverage_note", "Only the recorded cases were evaluated; this is not a safety guarantee."),
        "metric": metric,
        "unit": unit,
        "conditions": [{"id": f["id"], "asset": f.get("asset", ""),
                        "start_hour": f.get("start_s", 0) / 3600,
                        "duration_hours": (f.get("end_s", 0) - f.get("start_s", 0)) / 3600,
                        "kind": f.get("type"), "setting": f.get("setting"), "bias_m": f.get("bias_m"),
                        "retained": (f["id"] in witness_run.get("active_fault_ids", [])) if reduction and witness_run else None}
                       for f in fault_list],
        "tests": [{"id": candidate["run_id"], "phase": candidate["phase"],
                   "active_fault_ids": candidate["active_fault_ids"], "value": candidate["value"],
                   "violated": candidate["violated"]}
                  for candidate in raw_search.get("candidates", [])],
    }
    provenance = packet.get("provenance", {})
    return {
        "id": request["id"], "created_at": request["created_at"], "recorded": recorded,
        "config": config, "model": model_view(model), "cases": cases,
        "finding": {"status": finding_status, "title": title, "description": description,
                    "metric": metric, "threshold": threshold, "unit": unit, "first_time_s": first},
        "search": search, "validation": validation,
        "discovery": packet.get("discovery"), "repair": packet.get("repair"),
        "provenance": {"engine_version": f"EPA SWMM {provenance.get('epa_version', '5.2.4')}",
                       "model_sha256": model.get("base_model_sha256", packet.get("experiment", {}).get("base_model_sha256", "")),
                       "source_url": model.get("source_url", ""), "model_name": model.get("label", model["id"]),
                       "units": "SI · seconds, metres, m³ and m³/s",
                       "run_seconds": sum(r.get("runtime_s", 0) for r in runs)},
    }
