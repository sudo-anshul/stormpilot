"""Trace arithmetic without importing simulator or controller implementation.

The result is an integral of the recorded samples under the stated convention,
not an independent solution of the hydraulic equations.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from typing import Any


class EvidenceError(ValueError):
    """Evidence is incomplete, internally inconsistent, or numerically invalid."""


TRACE_UNITS = {
    "time_s": "s",
    "total_flooding_m3s": "m3/s",
    "downstream_flow_m3s": "m3/s",
    "total_storage_m3": "m3",
}
METRIC_UNITS = {
    "flood_volume_m3": "m3",
    "downstream_excess_volume_m3": "m3",
    "peak_downstream_flow_m3s": "m3/s",
    "terminal_storage_m3": "m3",
}


def finite_number(value: Any, label: str) -> float:
    """Accept real JSON numbers, excluding booleans and nonfinite values."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise EvidenceError(f"{label} must be a finite number")
    try:
        value = float(value)
    except (OverflowError, ValueError):
        raise EvidenceError(f"{label} must be a finite number") from None
    if not math.isfinite(value):
        raise EvidenceError(f"{label} must be a finite number")
    return value


def close_enough(actual: Any, expected: Any, *, absolute: float, relative: float) -> bool:
    a = finite_number(actual, "actual")
    b = finite_number(expected, "expected")
    if absolute < 0 or relative < 0:
        raise EvidenceError("metric tolerances must be nonnegative")
    return abs(a - b) <= absolute + relative * max(abs(a), abs(b))


def _positive_linear_integral(a: float, b: float, dt: float) -> float:
    """Integrate max(linear(a,b),0), including a crossing within the interval."""
    if a >= 0 and b >= 0:
        return (a + b) * dt / 2
    if a <= 0 and b <= 0:
        return 0.0
    positive = max(a, b)
    return positive * positive * dt / (2 * abs(b - a))


def compute_metrics(
    trace: Sequence[Mapping[str, Any]],
    *,
    integration: str,
    downstream_threshold_m3s: float,
    start_s: float | None = None,
    end_s: float | None = None,
    time_tolerance_s: float = 1e-6,
    negative_tolerance: float = 1e-9,
) -> dict[str, float]:
    """Recompute physical metrics from complete, explicitly sampled SI traces.

    ``right_rectangle`` treats each right-end rate as the preceding interval's
    rate; ``left_rectangle`` uses the left end. ``linear`` integrates the linear
    interpolation, resolving threshold crossings exactly within that model.
    All conventions require an initial and a terminal sample. Reverse downstream
    flow is retained; it contributes no positive threshold exceedance.
    """
    if integration not in {"right_rectangle", "left_rectangle", "linear"}:
        raise EvidenceError("unsupported or absent trace integration convention")
    if isinstance(trace, (str, bytes)) or not isinstance(trace, Sequence) or len(trace) < 2:
        raise EvidenceError("trace requires an initial and terminal sample")
    threshold = finite_number(downstream_threshold_m3s, "downstream threshold")
    if threshold < 0:
        raise EvidenceError("downstream threshold must be nonnegative")
    time_tol = finite_number(time_tolerance_s, "time tolerance")
    neg_tol = finite_number(negative_tolerance, "negative tolerance")
    if time_tol < 0 or neg_tol < 0:
        raise EvidenceError("numerical tolerances must be nonnegative")

    rows: list[dict[str, float]] = []
    for i, sample in enumerate(trace):
        if not isinstance(sample, Mapping):
            raise EvidenceError(f"trace[{i}] must be an object")
        row = {key: finite_number(sample.get(key), f"trace[{i}].{key}") for key in TRACE_UNITS}
        if row["time_s"] < -time_tol:
            raise EvidenceError(f"trace[{i}] has a negative timestamp")
        for key in ("total_flooding_m3s", "total_storage_m3"):
            if row[key] < -neg_tol:
                raise EvidenceError(f"trace[{i}].{key} is materially negative")
            row[key] = max(0.0, row[key])
        if rows and row["time_s"] <= rows[-1]["time_s"]:
            raise EvidenceError("trace times must be strictly increasing")
        rows.append(row)
    for declared, actual, label in (
        (start_s, rows[0]["time_s"], "start"),
        (end_s, rows[-1]["time_s"], "end"),
    ):
        if declared is not None and abs(finite_number(declared, label) - actual) > time_tol:
            raise EvidenceError(f"trace does not cover the declared {label} time")

    flood_parts: list[float] = []
    excess_parts: list[float] = []
    for left, right in zip(rows, rows[1:]):
        dt = right["time_s"] - left["time_s"]
        if integration == "linear":
            flood_parts.append(dt * (left["total_flooding_m3s"] + right["total_flooding_m3s"]) / 2)
            excess_parts.append(_positive_linear_integral(
                left["downstream_flow_m3s"] - threshold,
                right["downstream_flow_m3s"] - threshold,
                dt,
            ))
        else:
            row = right if integration == "right_rectangle" else left
            flood_parts.append(dt * row["total_flooding_m3s"])
            excess_parts.append(dt * max(row["downstream_flow_m3s"] - threshold, 0))
    result = {
        "flood_volume_m3": math.fsum(flood_parts),
        "downstream_excess_volume_m3": math.fsum(excess_parts),
        "peak_downstream_flow_m3s": max(row["downstream_flow_m3s"] for row in rows),
        "terminal_storage_m3": rows[-1]["total_storage_m3"],
    }
    for name, value in result.items():
        finite_number(value, name)
    return result
