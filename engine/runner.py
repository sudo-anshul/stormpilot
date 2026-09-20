"""Reproducible closed-loop experiments on the real EPA SWMM solver.

Each run has its own hydraulic trajectory. Only the exogenous rainfall, faults
and asset/time-indexed sensor noise are paired across policies and ablations.
"""
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import math
import tempfile
import time

from build import source_hash
from controllers import POLICIES, commands, normalize_parameters
from models import ROOT, EPA_COMMIT, PYSTORMS_COMMIT, digest, metadata, rainfall_model, sections, normalize_custom_model, custom_model_id
from swmm import Simulation

INFORMATION_BOUNDARY = "causal-depth-feedback-v1"
METRIC_PROTOCOL = "routing-step-right-rectangle-v1"
FAULT_TYPES = ["valve_stuck", "sensor_dropout", "sensor_bias"]
METRICS = {"flood_volume_m3": "m3", "peak_downstream_flow_m3s": "m3/s",
           "downstream_excess_volume_m3": "m3", "terminal_storage_m3": "m3"}


def finite(value, name, lower, upper):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not lower <= value <= upper:
        raise ValueError(f"{name} must be finite and between {lower} and {upper}.")
    return float(value)


def prepare(request):
    if not isinstance(request, dict):
        raise ValueError("Request must be a JSON object.")
    custom_model = normalize_custom_model(request["custom_model"]) if request.get("custom_model") is not None else None
    scenario_id = request.get("scenario_id", custom_model_id(custom_model) if custom_model is not None else "theta")
    model = metadata(scenario_id, custom_model)
    policies = {p["id"] for p in POLICIES}
    controller = request.get("controller_id", "constant_flow")
    fallback = request.get("fallback_controller_id", "uncontrolled")
    if controller not in policies or fallback not in policies:
        raise ValueError("Unsupported controller_id or fallback_controller_id.")
    controller_parameters = normalize_parameters(controller, request.get("controller_parameters"))
    fallback_parameters = normalize_parameters(fallback, request.get("fallback_controller_parameters"))
    seed = request.get("seed", 42)
    if isinstance(seed, bool) or not isinstance(seed, int) or not 0 <= seed <= 2**32-1:
        raise ValueError("seed must be an integer in [0, 4294967295].")
    multiplier = finite(request.get("rainfall_multiplier", 1.0), "rainfall_multiplier", 0.25, 2.5)
    noise = finite(request.get("noise_std_m", 0.0), "noise_std_m", 0, 0.5)
    faults = request.get("faults", [])
    if not isinstance(faults, list) or len(faults) > 12:
        raise ValueError("faults must be an array with at most 12 conditions.")
    basin_ids = {a["node_id"] for a in model["assets"]}
    valve_ids = {a["id"] for a in model["assets"]}
    normalized_faults, ids = [], set()
    for i, fault in enumerate(faults):
        if not isinstance(fault, dict):
            raise ValueError("Each fault must be an object.")
        kind, asset = fault.get("type"), str(fault.get("asset", ""))
        if kind not in FAULT_TYPES or asset not in (valve_ids if kind == "valve_stuck" else basin_ids):
            raise ValueError("Fault type/asset does not exist in the selected model.")
        fault_id = str(fault.get("id", f"f{i+1}"))
        if not fault_id or len(fault_id) > 80 or fault_id in ids:
            raise ValueError("Fault ids must be unique nonempty strings of at most 80 characters.")
        ids.add(fault_id)
        start = finite(fault.get("start_s", 3600), "fault.start_s", 0, model["horizon_s"])
        end = finite(fault.get("end_s", 21600), "fault.end_s", 0, model["horizon_s"])
        if end <= start:
            raise ValueError("Fault end_s must exceed start_s.")
        entry = {"id": fault_id, "type": kind, "asset": asset, "start_s": start, "end_s": end}
        if kind == "valve_stuck":
            # Omitted setting freezes this run's actual position at fault onset.
            entry["setting"] = None if fault.get("setting") is None else finite(fault["setting"], "fault.setting", 0, 1)
        if kind == "sensor_bias":
            entry["bias_m"] = finite(fault.get("bias_m", 0.5), "fault.bias_m", -5, 5)
        normalized_faults.append(entry)
    normalized_faults.sort(key=lambda f: f["id"])
    # Overlapping actuator faults on one asset are ambiguous and rejected.
    for i, a in enumerate(normalized_faults):
        for b in normalized_faults[i+1:]:
            if a["type"] == b["type"] == "valve_stuck" and a["asset"] == b["asset"] and max(a["start_s"],b["start_s"]) < min(a["end_s"],b["end_s"]):
                raise ValueError("Overlapping stuck-valve conditions on one asset are unsupported.")
    contract = request.get("test_contract", {})
    if not isinstance(contract, dict):
        raise ValueError("test_contract must be an object.")
    metric = contract.get("metric", "flood_volume_m3")
    if metric not in METRICS:
        raise ValueError("Unsupported test-contract metric.")
    test_contract = {"mode": "absolute", "direction": "above", "metric": metric,
                     "threshold": finite(contract.get("threshold", 100), "test threshold", 0, 1e9),
                     "tolerance": finite(contract.get("tolerance", 1e-6), "test tolerance", 0, 1e3),
                     "units": METRICS[metric], "horizon_s": model["horizon_s"]}
    normalized = {"scenario_id": scenario_id, "controller_id": controller, "fallback_controller_id": fallback,
                  "controller_parameters": controller_parameters, "fallback_controller_parameters": fallback_parameters,
                  "seed": seed, "rainfall_multiplier": multiplier, "noise_std_m": noise,
                  "faults": normalized_faults, "test_contract": test_contract}
    if custom_model is not None:
        normalized["custom_model"] = custom_model
    model_text, rain_hash = rainfall_model(scenario_id, multiplier, custom_model)
    options = sections(model_text)["[OPTIONS]"]
    solver_settings = {"input_options": options, "control_interval_s": 300,
                       "routing_boundary_protocol": "preserve-adaptive-routing-clip-max-and-min-step-at-control-and-fault-boundaries-v2",
                       "output_conversion": "internal-ft3-to-m3-exact-0.028316846592-v1"}
    exogenous = {"seed": seed, "noise_std_m": noise, "noise_protocol": "sha256-box-muller-asset-control-time-v1",
                 "faults": normalized_faults, "rainfall_sha256": rain_hash}
    context = {"base_model_sha256": model["base_model_sha256"], "effective_model_sha256": digest(model_text.encode()),
               "rainfall_sha256": rain_hash, "exogenous_sha256": digest(exogenous),
               "solver_settings_sha256": digest(solver_settings), "horizon_s": model["horizon_s"],
               "information_boundary_id": INFORMATION_BOUNDARY}
    return normalized, model, model_text, context, solver_settings, exogenous


def normal_draw(seed, asset, time_s):
    data = hashlib.sha256(f"stormpilot-noise-v1:{seed}:{asset}:{time_s:.6f}".encode()).digest()
    u1 = (int.from_bytes(data[:8], "big") + 0.5) / 2**64
    u2 = (int.from_bytes(data[8:16], "big") + 0.5) / 2**64
    return math.sqrt(-2 * math.log(u1)) * math.cos(2 * math.pi * u2)


def evaluate_contract(metrics, contract):
    value = metrics[contract["metric"]]
    return {"violated": value > contract["threshold"] + contract["tolerance"],
            "metric": contract["metric"], "value": value, "threshold": contract["threshold"],
            "tolerance": contract["tolerance"], "units": contract["units"]}


def run_simulation(request, role="stress", controller_id=None, active_fault_ids=None, controller_parameters=None):
    started = time.monotonic()
    normalized, model, model_text, context, solver_settings, exogenous = prepare(request)
    controller_id = controller_id or normalized["controller_id"]
    if controller_id not in {p["id"] for p in POLICIES}:
        raise ValueError("Unsupported controller.")
    if controller_parameters is None:
        if controller_id == normalized["controller_id"]:
            controller_parameters = normalized["controller_parameters"]
        elif controller_id == normalized["fallback_controller_id"]:
            controller_parameters = normalized["fallback_controller_parameters"]
    configuration = normalize_parameters(controller_id, controller_parameters)
    all_ids = {f["id"] for f in normalized["faults"]}
    active_ids = all_ids if active_fault_ids is None else set(active_fault_ids)
    if not active_ids <= all_ids:
        raise ValueError("active_fault_ids must be present in the exogenous fault envelope.")
    faults = [f for f in normalized["faults"] if f["id"] in active_ids]
    parameters = {"targets_m3s": [target * configuration.get("target_scale", 1.0) for target in model["targets_m3s"]],
                  "control_interval_s": 300, **configuration}
    run_id = role + "-" + digest({"request": normalized, "controller": controller_id, "parameters": configuration,
                               "active_fault_ids": sorted(active_ids)})[:12]
    trace, display, observations, held_commands, frozen = [], [], {}, {}, {}
    extrema, peak_values = {}, {"flow": -1.0, "flood": -1.0, "storage": -1.0}
    max_depths = {n["id"]: n["max_depth_m"] for n in model["nodes"] if n["type"] == "basin"}
    peak_depths = {node: 0.0 for node in max_depths}
    metric = {"flood_volume_m3": 0.0, "peak_downstream_flow_m3s": 0.0,
              "downstream_excess_volume_m3": 0.0, "downstream_exceedance_duration_s": 0.0,
              "terminal_storage_m3": 0.0}
    runs_dir = ROOT / "runs"
    runs_dir.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="swmm-", dir=runs_dir) as directory:
        folder = Path(directory)
        input_path = folder / "model.inp"
        input_path.write_text(model_text)
        sim = Simulation(input_path, folder / "model.rpt", folder / "model.out")
        try:
            length_factor = 0.3048 if model["input_units"].upper() in {"CFS", "GPM", "MGD"} else 1.0
            def sample():
                signed_flow = sim.lib.stormpilot_link_flow_m3s(sim.links[model["downstream_link"]])
                return {"time_s": sim.time_s,
                        "total_flooding_m3s": sum(max(0.0, sim.lib.stormpilot_node_overflow_m3s(i)) for i in sim.nodes.values()),
                        "total_storage_m3": sum(sim.lib.stormpilot_node_volume_m3(i) for i in sim.nodes.values()) + sum(sim.lib.stormpilot_link_volume_m3(i) for i in sim.links.values()),
                        "downstream_flow_m3s": max(0.0, signed_flow), "signed_downstream_flow_m3s": signed_flow}
            def depths():
                return {n: sim.get(303, sim.nodes[n]) * length_factor for n in max_depths}
            def display_sample():
                return {**sample(), "basin_depth_m": depths(), "observed_depth_m": dict(observations),
                        "observation_time_s": last_control, "valve_commands": dict(held_commands),
                        "valve_settings": {a["id"]: sim.get(407, sim.links[a["id"]]) for a in model["assets"]}}
            current = sample()
            trace.append(current)
            next_control, last_control = 0.0, 0.0
            boundaries = sorted({f[k] for f in faults for k in ["start_s", "end_s"]})
            # Clip routing at the union of all envelope boundaries even for ablations;
            # removing a fault must not silently change the numerical step protocol.
            envelope_boundaries = sorted({f[k] for f in normalized["faults"] for k in ["start_s", "end_s"]})
            max_step = 30.0 if model["id"] == "theta" else 60.0
            running = True
            while running:
                now = sim.time_s
                if now + 1e-7 >= next_control:
                    last_control = next_control
                    observations = depths()
                    for node in observations:
                        observations[node] += normalized["noise_std_m"] * normal_draw(normalized["seed"], node, next_control)
                    for fault in faults:
                        if fault["start_s"] <= now < fault["end_s"]:
                            if fault["type"] == "sensor_bias":
                                observations[fault["asset"]] += fault["bias_m"]
                    # A zero-reading failure overrides bias and noise regardless
                    # of fault-id ordering; simultaneous biases are additive.
                    for fault in faults:
                        if fault["type"] == "sensor_dropout" and fault["start_s"] <= now < fault["end_s"]:
                            observations[fault["asset"]] = 0.0
                    held_commands = commands(controller_id, observations, model["assets"], max_depths, parameters)
                    next_control += 300.0
                # Apply every actuator command; a physical fault overrides only that asset.
                for asset in model["assets"]:
                    asset_id = asset["id"]
                    setting = held_commands[asset_id]
                    for fault in faults:
                        if fault["type"] == "valve_stuck" and fault["asset"] == asset_id and fault["start_s"] <= now < fault["end_s"]:
                            if fault["id"] not in frozen:
                                frozen[fault["id"]] = sim.get(407, sim.links[asset_id]) if fault["setting"] is None else fault["setting"]
                            setting = frozen[fault["id"]]
                    sim.set(407, sim.links[asset_id], setting)
                if not display or now - display[-1]["time_s"] >= 300 - 1e-6:
                    display.append(display_sample())
                if any(abs(now-b) < 1e-6 for b in envelope_boundaries):
                    extrema["boundary:" + str(now)] = display_sample()
                upcoming = [b for b in envelope_boundaries if b > now + 1e-7]
                boundary = min(next_control, sim.duration_s, upcoming[0] if upcoming else sim.duration_s)
                sim.lib.stormpilot_set_max_step_s(min(max_step, max(0.001, boundary - now)))
                previous = current
                running = sim.step()
                current = sample()
                dt = current["time_s"] - previous["time_s"]
                if dt <= 0:
                    raise RuntimeError("SWMM returned a non-increasing routing timestamp.")
                trace.append(current)
                metric["flood_volume_m3"] += current["total_flooding_m3s"] * dt
                metric["peak_downstream_flow_m3s"] = max(metric["peak_downstream_flow_m3s"], current["downstream_flow_m3s"])
                excess = max(0.0, current["downstream_flow_m3s"] - model["threshold_m3s"])
                metric["downstream_excess_volume_m3"] += excess * dt
                if excess > 0:
                    metric["downstream_exceedance_duration_s"] += dt
                for key, field in [("flow", "downstream_flow_m3s"), ("flood", "total_flooding_m3s"), ("storage", "total_storage_m3")]:
                    if current[field] > peak_values[key]:
                        peak_values[key] = current[field]
                        extrema["global_peak_" + key] = display_sample()
                if current["total_flooding_m3s"] > 1e-9 and "first_overflow" not in extrema:
                    extrema["first_overflow"] = display_sample()
                for node, depth in depths().items():
                    if depth > peak_depths[node]:
                        peak_depths[node] = depth
                        extrema["peak_depth:" + node] = display_sample()
            if display[-1]["time_s"] != current["time_s"]:
                display.append(display_sample())
            display = list({row["time_s"]: row for row in display + list(extrema.values())}.values())
            display.sort(key=lambda row: row["time_s"])
            metric["terminal_storage_m3"] = current["total_storage_m3"]
            node_volumes = sim.native_flood_volumes()
            metric["native_flood_volume_m3"] = sum(node_volumes.values())
            continuity = sim.finish()
            report = (folder / "model.rpt").read_text(errors="replace")
        finally:
            sim.close()
    return {"run_id": run_id, "role": role, "context": context,
            "controller": {"id": controller_id, "source_sha256": digest((ROOT / "controllers.py").read_bytes()),
                           "parameters": parameters, "description": next(p["description"] for p in POLICIES if p["id"] == controller_id)},
            "active_fault_ids": sorted(active_ids), "trace": trace, "display_trace": display,
            "metrics": metric, "continuity": continuity, "node_flood_volume_m3": node_volumes,
            "peak_basin_depth_m": peak_depths, "contract_result": evaluate_contract(metric, normalized["test_contract"]),
            "routing_steps": len(trace)-1, "runtime_s": time.monotonic()-started,
            "units": {"time": "s", "flow": "m3/s", "volume": "m3", "depth": "m"},
            "metric_protocol": METRIC_PROTOCOL, "report_sha256": digest(report.encode()), "swmm_report": report}


def packet(request, runs=None):
    normalized, model, model_text, context, settings, exogenous = prepare(request)
    if runs is None:
        runs = [run_simulation(normalized, "nominal", active_fault_ids=[]),
                run_simulation(normalized, "stress"),
                run_simulation(normalized, "fallback", controller_id=normalized["fallback_controller_id"],
                               controller_parameters=normalized["fallback_controller_parameters"])]
    experiment = {"scenario_id": model["id"], **context, "threshold_m3s": model["threshold_m3s"],
                  "metric_protocol": METRIC_PROTOCOL, "test_contract": normalized["test_contract"],
                  "faults": normalized["faults"], "exogenous": exogenous, "solver_settings": settings}
    result = {"schema_version": "stormpilot.evidence.v1", "experiment_id": digest(normalized)[:20],
              "created_at": datetime.now(timezone.utc).isoformat(), "request": normalized,
              "provenance": {"base_model_sha256": model["base_model_sha256"], "engine_source_sha256": source_hash(),
                             "runner_source_sha256": digest((ROOT / "runner.py").read_bytes()),
                             "source_url": model["source_url"], "model_path": model["model_path"],
                             "epa_version": "5.2.4", "epa_commit": EPA_COMMIT, "pystorms_commit": PYSTORMS_COMMIT,
                             "epa_source_url": f"https://github.com/USEPA/Stormwater-Management-Model/tree/{EPA_COMMIT}",
                             "conversion": "All flow/volume outputs converted from SWMM internal feet units with exact 0.028316846592; solver equations unchanged."},
              "model": model, "experiment": experiment, "runs": runs,
              "claims": {"scope": "Public benchmark simulation only", "field_validated": False,
                         "notes": ["Existing SWMM hydraulics and published benchmark inputs; StormPilot implements the experiment workflow.",
                                   "Policies share exogenous forcing, not hydraulic state or identical resulting observations.",
                                   "No repair costs, residents protected, or real-city flood predictions are inferred."]}}
    result["test_contract_sha256"] = digest(normalized["test_contract"])
    source_files = sorted(p for p in (ROOT / "vendor/epa-swmm/src/solver").rglob("*") if p.is_file())
    source_files += sorted(ROOT.glob("*.py")) + [ROOT / "native_bridge.c", ROOT.parent / model["model_path"]]
    result["artifacts"] = [{"path": "engine/" + str(path.relative_to(ROOT)), "sha256": digest(path.read_bytes())} for path in source_files]
    return result
