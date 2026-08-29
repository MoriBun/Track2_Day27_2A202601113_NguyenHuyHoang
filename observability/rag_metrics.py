from __future__ import annotations

from typing import Any, Iterable

import numpy as np

from observability.anomaly import zscore_detector
from observability.distribution import detect_distribution_shift


def approximate_token_lengths(texts: Iterable[str]) -> list[int]:
    # Deliberately simple proxy; no tokenizer/model download needed.
    return [len(str(t).split()) for t in texts]


def detect_text_length_shift(
    current_texts: Iterable[str],
    baseline_batch_means: Iterable[float],
    *,
    threshold: float = 3.0,
) -> dict[str, Any]:
    lengths = approximate_token_lengths(current_texts)
    current_mean = float(np.mean(lengths)) if lengths else 0.0
    result = zscore_detector(current_mean, baseline_batch_means, threshold=threshold)
    result["metric"] = "mean_text_length"
    result["current_mean"] = current_mean
    return result


def detect_embedding_norm_shift(
    current_norms: Iterable[float], baseline_norms: Iterable[float]
) -> dict[str, Any]:
    """Detect embedding-norm drift without downloading an embedding model.

    Norms are a compact proxy for an embedding pipeline's output geometry.
    This is not a semantic retrieval-quality metric, but it can expose model,
    normalization, or indexing regressions before they affect every query.
    """
    result = detect_distribution_shift(current_norms, baseline_norms)
    result["method"] = f"embedding_norm:{result['method']}"
    result["metric"] = "embedding_norm"
    return result
