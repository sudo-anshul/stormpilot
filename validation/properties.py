"""Declared numerical properties and guarded comparisons of recorded metrics."""

from __future__ import annotations

import math
from collections.abc import Mapping
from typing import Any

from .metrics import EvidenceError, METRIC_UNITS, finite_number


def evaluate_property(
    declaration: Mapping[str, Any],
    candidate: Mapping[str, Any],
    reference: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """A violation exceeds a declared absolute bound by more than tolerance.

    ``mode=absolute`` tests the candidate metric itself; ``mode=increase`` tests
    candidate minus reference. ``direction=above`` is a maximum allowed bound,
    while ``below`` is a minimum allowed bound. No default property is invented.
    """
    metric = declaration.get("metric")
    if metric not in METRIC_UNITS:
        raise EvidenceError("property names an unsupported physical metric")
    if declaration.get("unit") != METRIC_UNITS[metric]:
        raise EvidenceError("property unit does not match its metric")
    mode = declaration.get("mode")
    direction = declaration.get("direction")
    if mode not in {"absolute", "increase"} or direction not in {"above", "below"}:
        raise EvidenceError("property requires mode absolute/increase and direction above/below")
    bound = finite_number(declaration.get("bound"), "property bound")
    tolerance = finite_number(declaration.get("tolerance"), "property tolerance")
    if tolerance < 0:
        raise EvidenceError("property tolerance must be nonnegative")
    value = finite_number(candidate.get(metric), f"candidate {metric}")
    reference_value = None
    if mode == "increase":
        if reference is None:
            raise EvidenceError("increase property requires a reference run")
        reference_value = finite_number(reference.get(metric), f"reference {metric}")
        value -= reference_value
    margin = value - bound if direction == "above" else bound - value
    return {
        "metric": metric,
        "unit": METRIC_UNITS[metric],
        "value": value,
        "reference_value": reference_value,
        "bound": bound,
        "tolerance": tolerance,
        "margin": margin,
        # Do not turn roundoff at the declared boundary into a violation.
        "violated": margin > tolerance and not math.isclose(
            value, bound + tolerance if direction == "above" else bound - tolerance,
            rel_tol=1e-12, abs_tol=1e-12,
        ),
    }


def compare_fallback(
    stressed: Mapping[str, Any],
    fallback: Mapping[str, Any],
    declaration: Mapping[str, Any],
) -> dict[str, Any]:
    """Check a primary improvement and every explicitly declared guard.

    All supported metrics are reported even when a guard was not declared. A
    missing guard withholds the aggregate non-regression claim.
    """
    primary = declaration.get("primary_metric")
    if primary not in METRIC_UNITS:
        raise EvidenceError("fallback primary metric is unsupported")
    minimum = finite_number(declaration.get("minimum_improvement"), "minimum improvement")
    tolerance = finite_number(declaration.get("tolerance"), "fallback tolerance")
    if minimum < 0 or tolerance < 0:
        raise EvidenceError("fallback improvement and tolerance must be nonnegative")
    guards = declaration.get("maximum_increase")
    if not isinstance(guards, Mapping):
        raise EvidenceError("fallback requires explicit maximum-increase guards")
    unknown = set(guards) - set(METRIC_UNITS)
    if unknown:
        raise EvidenceError(f"unsupported fallback guard: {sorted(unknown)}")
    changes: dict[str, Any] = {}
    for metric, unit in METRIC_UNITS.items():
        before = finite_number(stressed.get(metric), f"stressed {metric}")
        after = finite_number(fallback.get(metric), f"fallback {metric}")
        allowed = None
        passed = None
        if metric in guards:
            allowed = finite_number(guards[metric], f"maximum increase for {metric}")
            if allowed < 0:
                raise EvidenceError("guard maximum increase must be nonnegative")
            passed = after - before <= allowed + tolerance
        changes[metric] = {
            "unit": unit,
            "stressed": before,
            "fallback": after,
            "change": after - before,
            "maximum_increase": allowed,
            "guard_passed": passed,
        }
    improvement = -changes[primary]["change"]
    improved = improvement > minimum + tolerance
    missing = sorted(set(METRIC_UNITS) - set(guards) - {primary})
    guards_pass = not missing and all(
        c["guard_passed"] is not False for c in changes.values()
    )
    return {
        "primary_metric": primary,
        "primary_improvement": improvement,
        "primary_improved": improved,
        "changes": changes,
        "missing_guards": missing,
        "all_specified_guards_pass": all(c["guard_passed"] is not False for c in changes.values()),
        "guarded_improvement": improved and guards_pass,
        "conclusion": "guarded_improvement" if improved and guards_pass else (
            "tradeoff_or_incomplete_guards" if improved else "no_material_primary_improvement"
        ),
    }
