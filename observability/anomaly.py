"""Metric anomaly detection with robust and seasonality-aware auto mode."""
from __future__ import annotations

from typing import Any, Iterable

import numpy as np


def _finite_values(history: Iterable[float]) -> np.ndarray:
    """Convert an input history into usable numeric observations."""
    values = np.asarray(list(history), dtype=float)
    return values[np.isfinite(values)]


def zscore_detector(current: float, history: Iterable[float], threshold: float = 3.0) -> dict[str, Any]:
    values = _finite_values(history)
    if not np.isfinite(float(current)):
        return {"is_anomaly": True, "score": float("inf"), "method": "zscore", "reason": "invalid_current_value"}
    if values.size < 3:
        return {"is_anomaly": False, "score": 0.0, "method": "zscore", "reason": "insufficient_history"}
    mean = float(np.mean(values))
    std = float(np.std(values))
    if std == 0:
        score = float("inf") if float(current) != mean else 0.0
    else:
        score = abs(float(current) - mean) / std
    return {
        "is_anomaly": bool(score > threshold),
        "score": float(score),
        "method": "zscore",
        "reason": f"mean={mean:.3f}, std={std:.3f}, threshold={threshold}",
    }


def mad_detector(current: float, history: Iterable[float], threshold: float = 3.5) -> dict[str, Any]:
    """Detect an outlier using median absolute deviation (MAD).

    MAD is resistant to a small number of extreme historical observations,
    unlike a mean/std baseline whose standard deviation can be inflated by the
    very incident it needs to detect.
    """
    values = _finite_values(history)
    if not np.isfinite(float(current)):
        return {"is_anomaly": True, "score": float("inf"), "method": "mad", "reason": "invalid_current_value"}
    if values.size < 5:
        return {"is_anomaly": False, "score": 0.0, "method": "mad", "reason": "insufficient_history"}
    median = float(np.median(values))
    mad = float(np.median(np.abs(values - median)))
    if mad == 0:
        score = float("inf") if float(current) != median else 0.0
        return {
            "is_anomaly": bool(score > threshold),
            "score": score,
            "method": "mad",
            "reason": f"median={median:.3f}, mad=0.000; constant_baseline=true",
        }
    modified_z = 0.6745 * abs(float(current) - median) / mad
    return {
        "is_anomaly": bool(modified_z > threshold),
        "score": float(modified_z),
        "method": "mad",
        "reason": f"median={median:.3f}, mad={mad:.3f}, threshold={threshold}",
    }


def detect_anomaly(
    current: float,
    history: Iterable[float],
    *,
    method: str = "auto",
    threshold: float = 3.0,
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Stable lab API.

    `auto` prefers a supplied same-segment history (for example, observations
    from the same weekday) and uses MAD once it has enough observations. It
    falls back to a robust full-history MAD baseline, then to z-score when the
    sample is too small. A caller can mark a planned event in `known_event` to
    suppress an expected, explained deviation.
    """
    if method == "mad":
        return mad_detector(current, history)
    if method == "zscore":
        return zscore_detector(current, history, threshold=threshold)
    if method == "auto":
        context = context or {}
        known_event = context.get("known_event")
        if known_event:
            return {
                "is_anomaly": False,
                "score": 0.0,
                "method": "auto:known_event",
                "reason": f"suppressed_by_known_event={known_event}",
            }

        segment_history = context.get("same_segment_history")
        if segment_history is not None:
            segment_values = _finite_values(segment_history)
            if segment_values.size >= 5:
                result = mad_detector(current, segment_values)
                result["method"] = "auto:mad_same_segment"
                result["reason"] += f"; segment_size={segment_values.size}"
                return result

        values = _finite_values(history)
        if values.size >= 5:
            result = mad_detector(current, values)
            result["method"] = "auto:mad"
            return result
        result = zscore_detector(current, values, threshold=threshold)
        result["method"] = "auto:zscore_fallback"
        return result
    raise ValueError(f"Unsupported method: {method}")
