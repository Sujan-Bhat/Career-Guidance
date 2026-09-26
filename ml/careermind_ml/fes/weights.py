"""Per-student FES weight calibration (paper Eq. 2).

Closed-form statistical estimator — NOT a trained model: absolute Pearson
correlation between each sub-metric and academic performance outcomes,
followed by absolute-value normalisation to enforce sum(w_i) = 1.

Calibration rules (paper Sec. V-A):
  * per-student weights computed only when the student has >= 8 completed
    sessions AND >= 2 associated graded outcomes;
  * any sub-metric with < 3 non-missing observations -> the student falls
    back to the population-level weight vector;
  * missing sub-metric values are excluded pairwise per sub-metric, not
    by dropping the session;
  * students below the threshold use the population-level weight vector
    (identical computation, pooling all students) as cold-start.
"""
from typing import Optional

import numpy as np

SUBMETRICS = ("tcr", "sci", "dfet", "qap", "lrds")

DEFAULT_CONFIG = {
    "min_sessions": 8,
    "min_graded_outcomes": 2,
    "min_nonmissing_per_submetric": 3,
}


def compute_submetric_correlations(pairs: list[dict], config: dict | None = None) -> dict:
    """Absolute Pearson correlation |r| between each sub-metric and outcomes.

    Args:
        pairs: one dict per session, e.g. {"tcr": 0.8, "sci": None, ...,
            "outcome": 72.5}. None sub-metric values are excluded pairwise
            (per sub-metric only).
    Returns:
        {submetric: |r|} for sub-metrics with >= min_nonmissing non-missing
        pairs. Sub-metrics with zero variance get |r| = 0 (no signal).
    """
    cfg = {**DEFAULT_CONFIG, **(config or {})}
    result = {}
    for metric in SUBMETRICS:
        xs, ys = [], []
        for pair in pairs:
            value = pair.get(metric)
            outcome = pair.get("outcome")
            if value is not None and outcome is not None:
                xs.append(value)
                ys.append(outcome)
        if len(xs) < cfg["min_nonmissing_per_submetric"]:
            continue
        x, y = np.asarray(xs, dtype=float), np.asarray(ys, dtype=float)
        if x.std() < 1e-12 or y.std() < 1e-12:
            result[metric] = 0.0
            continue
        result[metric] = abs(float(np.corrcoef(x, y)[0, 1]))
    return result


def normalise_weights(correlations: dict) -> dict:
    """Eq. 2: w_i = a_i / sum(a_j) over the available sub-metrics.

    Degenerate case (all |r| = 0): uniform weights, so FES remains defined
    while carrying no per-metric signal.
    """
    if not correlations:
        return {}
    total = sum(correlations.values())
    if total <= 0:
        uniform = 1.0 / len(correlations)
        return {metric: uniform for metric in correlations}
    return {metric: value / total for metric, value in correlations.items()}


def calibrate_student_weights(pairs: list[dict], config: dict | None = None) -> Optional[dict]:
    """Full per-student Eq. 2 pipeline.

    Returns the weight dict, or None when the student must fall back to the
    population-level vector (below the session/outcome gates, or ANY
    sub-metric with < min_nonmissing non-missing observations — paper Sec. V-A).
    """
    cfg = {**DEFAULT_CONFIG, **(config or {})}

    completed = [p for p in pairs if p.get("outcome") is not None]
    if len(completed) < cfg["min_sessions"]:
        return None
    if sum(1 for p in completed if p.get("outcome") is not None) < cfg["min_graded_outcomes"]:
        return None

    correlations = compute_submetric_correlations(completed, cfg)
    if set(correlations) != set(SUBMETRICS):
        return None  # some sub-metric lacked >= 3 non-missing observations
    return normalise_weights(correlations)


def calibrate_population_weights(pairs: list[dict], config: dict | None = None) -> dict:
    """Population-level vector: identical Eq. 2 computation, pooling all
    (sub-metric, outcome) pairs across students. Serves as cold-start
    initialisation for students below the per-student gates."""
    cfg = {**DEFAULT_CONFIG, **(config or {})}
    correlations = compute_submetric_correlations(pairs, cfg)
    if set(correlations) != set(SUBMETRICS):
        # pooled data should always clear the gate; degrade to uniform if not
        return {m: 1.0 / len(SUBMETRICS) for m in SUBMETRICS}
    return normalise_weights(correlations)


def compute_fes(metrics: dict, weights: dict) -> Optional[float]:
    """Eq. 1: FES = sum(w_i * m_i), renormalised over the sub-metrics that
    are present in this session (missing sub-metrics are excluded rather
    than zero-filled, mirroring the pairwise-exclusion principle)."""
    available = [m for m in SUBMETRICS if m in weights and metrics.get(m) is not None]
    if not available:
        return None
    total_w = sum(weights[m] for m in available)
    if total_w <= 0:
        return None
    return sum(weights[m] * metrics[m] for m in available) / total_w
