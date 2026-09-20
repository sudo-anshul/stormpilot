"""Causal depth-feedback baselines; no future rain or hidden fault access."""
import math

POLICIES = [
    {"id": "constant_flow", "label": "Constant-flow control", "description": "Throttle each bottom orifice from measured depth toward a fixed target discharge."},
    {"id": "equal_filling", "label": "Equal-filling control", "description": "Add measured relative storage imbalance to the constant-flow setting."},
    {"id": "balanced_flow", "label": "Balanced flow allocation", "description": "Redistribute a bounded total target discharge toward basins with greater measured relative filling; no forecast or hidden fault access."},
    {"id": "uncontrolled", "label": "Outlets open", "description": "Command every outlet fully open; physical actuator faults still apply."},
]

PARAMETER_SPECS = {
    "constant_flow": {"target_scale": (1.0, 0.5, 1.5)},
    "equal_filling": {"target_scale": (1.0, 0.5, 1.5), "equal_filling_gain": (1.0, 0.0, 4.0)},
    "balanced_flow": {"target_scale": (1.0, 0.5, 1.5), "balance_gain": (1.0, 0.0, 8.0)},
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


def commands(controller_id, observations, assets, max_depths, parameters):
    if controller_id == "uncontrolled":
        return {a["id"]: 1.0 for a in assets}
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
    return result
