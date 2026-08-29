from __future__ import annotations

import math
from typing import Any


def calculate_slo(target: float, bad_events: int, total_events: int) -> dict[str, Any]:
    if not 0 < target < 1:
        raise ValueError("target must be between 0 and 1 (exclusive)")
    if bad_events < 0 or total_events < 0 or bad_events > total_events:
        raise ValueError("invalid event counts")
    allowed_bad_rate = 1.0 - target
    if total_events == 0:
        return {
            "target": target,
            "actual_bad_rate": 0.0,
            "allowed_bad_rate": allowed_bad_rate,
            "burn_rate": 0.0,
            "remaining_error_budget_fraction": 1.0,
            "breached": False,
        }
    actual_bad_rate = bad_events / total_events
    burn_rate = actual_bad_rate / allowed_bad_rate
    consumed_fraction = min(1.0, actual_bad_rate / allowed_bad_rate)
    return {
        "target": target,
        "actual_bad_rate": actual_bad_rate,
        "allowed_bad_rate": allowed_bad_rate,
        "burn_rate": burn_rate,
        "remaining_error_budget_fraction": max(0.0, 1.0 - consumed_fraction),
        "breached": bool(actual_bad_rate > allowed_bad_rate),
    }


def evaluate_multiwindow_burn(
    *,
    short_window_burn: float,
    long_window_burn: float,
    policy: str = "starter",
) -> dict[str, Any]:
    """Evaluate a two-window burn-rate alert policy.

    Both windows must be elevated before paging. This prevents a short-lived
    batch glitch from waking an operator while retaining fast alerts for a
    sustained error-budget burn. The thresholds are deliberately explicit so
    a service can later tune them to its SLO period and response capacity.
    """
    if policy != "starter":
        raise ValueError(f"Unsupported burn policy: {policy}")
    for name, value in {
        "short_window_burn": short_window_burn,
        "long_window_burn": long_window_burn,
    }.items():
        if not math.isfinite(value) or value < 0:
            raise ValueError(f"{name} must be a finite non-negative number")

    result = {
        "short_window_burn": float(short_window_burn),
        "long_window_burn": float(long_window_burn),
        "policy": "two_window_v1",
    }

    # Fast burn: consuming budget at >=14.4x in the recent window and >=6x
    # over the longer window deserves an immediate, high-severity page.
    if short_window_burn >= 14.4 and long_window_burn >= 6.0:
        return {
            **result,
            "page": True,
            "severity": "critical",
            "reason": "sustained_fast_burn: short>=14.4 and long>=6.0",
        }

    # Slower but still sustained burn is actionable during normal on-call.
    if short_window_burn >= 6.0 and long_window_burn >= 3.0:
        return {
            **result,
            "page": True,
            "severity": "warning",
            "reason": "sustained_burn: short>=6.0 and long>=3.0",
        }

    if short_window_burn >= 6.0 or long_window_burn >= 3.0:
        return {
            **result,
            "page": False,
            "severity": "warning",
            "reason": "single_window_elevated: investigate, but do_not_page",
        }

    return {
        **result,
        "page": False,
        "severity": "info",
        "reason": "burn_within_policy",
    }
