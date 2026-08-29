from __future__ import annotations

from typing import Any, Iterable

import numpy as np


def _finite_values(values: Iterable[float]) -> np.ndarray:
    array = np.asarray(list(values), dtype=float)
    return array[np.isfinite(array)]


def detect_distribution_shift(
    current_values: Iterable[float],
    baseline_values: Iterable[float],
    *,
    ratio_threshold: float = 3.0,
) -> dict[str, Any]:
    """Detect robust distribution drift using quantiles normalized by IQR.

    The argument name is retained for compatibility with the starter API, but
    it is now a normalized quantile-shift threshold rather than a mean ratio.
    Comparing the 10th, 50th, and 90th percentiles catches both a location
    shift and many shape/spread changes that a mean-only detector misses.
    """
    current = _finite_values(current_values)
    baseline = _finite_values(baseline_values)
    if current.size == 0 or baseline.size == 0:
        return {
            "is_anomaly": False,
            "score": 0.0,
            "method": "robust_quantile_shift",
            "reason": "empty_or_non_finite_input",
        }

    quantiles = np.array([0.10, 0.50, 0.90])
    current_quantiles = np.quantile(current, quantiles)
    baseline_quantiles = np.quantile(baseline, quantiles)
    baseline_iqr = float(np.subtract(*np.quantile(baseline, [0.75, 0.25])))
    baseline_median = float(baseline_quantiles[1])

    # A constant baseline still needs a usable tolerance. Use 5% of the
    # baseline magnitude, with a tiny floor for a baseline centered at zero.
    scale = max(abs(baseline_iqr), abs(baseline_median) * 0.05, 1e-9)
    score = float(np.max(np.abs(current_quantiles - baseline_quantiles)) / scale)
    return {
        "is_anomaly": bool(score >= ratio_threshold),
        "score": score,
        "method": "robust_quantile_shift",
        "reason": (
            f"baseline_q10_q50_q90={baseline_quantiles.round(4).tolist()}; "
            f"current_q10_q50_q90={current_quantiles.round(4).tolist()}; "
            f"scale_iqr={scale:.4f}; threshold={ratio_threshold}"
        ),
    }
