"""Causal depth-feedback baselines; no future rain or hidden fault access."""
import math
from statistics import median

POLICIES = [
    {"id": "constant_flow", "label": "Constant-flow control", "description": "Throttle each bottom orifice from measured depth toward a fixed target discharge."},
    {"id": "equal_filling", "label": "Equal-filling control", "description": "Add measured relative storage imbalance to the constant-flow setting."},
    {"id": "balanced_flow", "label": "Balanced flow allocation", "description": "Redistribute a bounded total target discharge toward basins with greater measured relative filling; no forecast or hidden fault access."},
    {"id": "plausible_depth", "label": "Sensor plausibility control", "description": "Track abrupt sensor offsets from past measured depths, conservatively correct positive offsets, and cap aggregate commands using a recent measured-head estimate."},
    {"id": "uncontrolled", "label": "Outlets open", "description": "Command every outlet fully open; physical actuator faults still apply."},
]

PARAMETER_SPECS = {
    "constant_flow": {"target_scale": (1.0, 0.5, 1.5)},
    "equal_filling": {"target_scale": (1.0, 0.5, 1.5), "equal_filling_gain": (1.0, 0.0, 4.0)},
    "balanced_flow": {"target_scale": (1.0, 0.5, 1.5), "balance_gain": (1.0, 0.0, 8.0)},
    "plausible_depth": {"target_scale": (1.0, 0.5, 1.5), "jump_threshold_m": (0.65, 0.2, 2.0),
                        "correction_fraction": (0.75, 0.0, 1.0)},
    "uncontrolled": {},
}


def normalize_parameters(controller_id, supplied=None):
    """Small explicit search space; reject misspellings instead of ignoring them."""
    if controller_id not in PARAMETER_SPECS:
        raise ValueError("Unsupported controller.")
    supplied = {} if supplied is None else supplied
    if not isinstance(supplied, dict):
        raise ValueError("Controller parameters must be an object.")
    specs = PARAMETER_SPECS[controller_id]
    if set(supplied) - set(specs):
        raise ValueError("Unsupported parameter for " + controller_id + ": " + ", ".join(sorted(set(supplied)-set(specs))))
    result = {}
    for name, (default, lower, upper) in specs.items():
        value = supplied.get(name, default)
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not lower <= value <= upper:
            raise ValueError(f"{name} must be finite and between {lower} and {upper}.")
        result[name] = float(value)
    return result


def plausible_observations(observations, parameters, state):
    """Causal step-offset hypothesis, never a claim to know the true depth.

    Smooth physical depth changes are estimated from three prior increments.
    A jump beyond the declared threshold updates an offset estimate. Opposite
    jumps cancel an existing estimate. Negative offsets are tracked but do not
    change the control input, avoiding additional throttling under a low sensor
    reading. Each simulation supplies an isolated state dictionary.
    """
    trusted = {}
    for node, measured in observations.items():
        memory = state.setdefault(node, {"previous": measured, "increments": [], "offset": 0.0, "events": 0})
        step = measured - memory["previous"]
        expected = median(memory["increments"]) if memory["increments"] else 0.0
        innovation = step - expected
        if abs(innovation) >= parameters["jump_threshold_m"]:
            previous_offset = memory["offset"]
            updated = previous_offset + innovation
            if previous_offset * innovation < 0 and abs(updated) < parameters["jump_threshold_m"]:
                updated = 0.0
            memory["offset"] = updated
            memory["events"] += 1
        else:
            memory["increments"] = (memory["increments"] + [step])[-3:]
        memory["previous"] = measured
        trusted[node] = measured - parameters["correction_fraction"] * max(0.0, memory["offset"])
        memory["control_depth_m"] = trusted[node]
        memory["control_depth_history"] = (memory.get("control_depth_history", []) + [trusted[node]])[-3:]
        memory["aggregate_cap_scale"] = 1.0
    return trusted


def commands(controller_id, observations, assets, max_depths, parameters, state=None):
    if controller_id == "uncontrolled":
        return {a["id"]: 1.0 for a in assets}
    if controller_id == "plausible_depth":
        if state is None:
            raise ValueError("Sensor plausibility control requires isolated per-run state.")
        observations = plausible_observations(observations, parameters, state)
    targets = parameters["targets_m3s"]
    filling = {node: max(0, depth) / max_depths[node] for node, depth in observations.items()}
    mean = sum(filling.values()) / len(filling)
    if controller_id == "balanced_flow":
        # Preserve the configured total discharge target. This controller sees
        # only current possibly corrupted measurements, never the active faults,
        # true simulator depth, rainfall, or future state.
        gain = parameters["balance_gain"]
        weights = [target * max(0.05, 1.0 + gain * (min(1.0, filling[asset["node_id"]]) -
                   sum(min(1.0, f) for f in filling.values()) / len(filling)))
                   for target, asset in zip(targets, assets)]
        total = sum(targets)
        targets = [total * weight / sum(weights) for weight in weights]
    result = {}
    for i, asset in enumerate(assets):
        depth = observations[asset["node_id"]]
        setting = 1.0 if depth < 0.001 else targets[i] / (asset["discharge_coefficient"] * asset["area_m2"] * math.sqrt(2 * 9.81 * depth))
        if controller_id == "equal_filling":
            setting += parameters.get("equal_filling_gain", 1.0) * (filling[asset["node_id"]] - mean)
        result[asset["id"]] = max(0.0, min(1.0, setting))
    if controller_id == "plausible_depth" and any(memory["offset"] > 0 for memory in state.values()):
        # Correcting one biased sensor must not add unrestricted discharge when
        # another noisy sensor briefly reads low. Estimate conservative heads
        # from the current and two past control depths, then cap aggregate
        # requested flow at the original configured total. This is an estimate,
        # not hidden hydraulic feedback or a guarantee on actual downstream flow.
        estimated_flow = sum(asset["discharge_coefficient"] * asset["area_m2"] *
            math.sqrt(2 * 9.81 * max(0.0, observations[asset["node_id"]],
                median(state[asset["node_id"]]["control_depth_history"]))) * result[asset["id"]]
            for asset in assets)
        cap_scale = min(1.0, sum(targets) / estimated_flow) if estimated_flow > 0 else 1.0
        result = {asset: setting * cap_scale for asset, setting in result.items()}
        for memory in state.values():
            memory["aggregate_cap_scale"] = cap_scale
    return result
