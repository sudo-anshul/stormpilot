"""Causal depth-feedback baselines; no future rain or hidden fault access."""
import math

POLICIES = [
    {"id": "constant_flow", "label": "Constant-flow control", "description": "Throttle each bottom orifice from measured depth toward a fixed target discharge."},
    {"id": "equal_filling", "label": "Equal-filling control", "description": "Add measured relative storage imbalance to the constant-flow setting."},
    {"id": "uncontrolled", "label": "Outlets open", "description": "Command every outlet fully open; physical actuator faults still apply."},
]


def commands(controller_id, observations, assets, max_depths, parameters):
    if controller_id == "uncontrolled":
        return {a["id"]: 1.0 for a in assets}
    targets = parameters["targets_m3s"]
    filling = {node: max(0, depth) / max_depths[node] for node, depth in observations.items()}
    mean = sum(filling.values()) / len(filling)
    result = {}
    for i, asset in enumerate(assets):
        depth = observations[asset["node_id"]]
        setting = 1.0 if depth < 0.001 else targets[i] / (asset["discharge_coefficient"] * asset["area_m2"] * math.sqrt(2 * 9.81 * depth))
        if controller_id == "equal_filling":
            setting += parameters.get("equal_filling_gain", 1.0) * (filling[asset["node_id"]] - mean)
        result[asset["id"]] = max(0.0, min(1.0, setting))
    return result
