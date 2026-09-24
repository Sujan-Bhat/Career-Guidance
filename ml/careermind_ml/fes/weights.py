"""Per-student FES weight calibration (paper Eq. 2).

Closed-form statistical estimator — NOT a trained model: absolute Pearson
correlation between each sub-metric and academic performance outcomes,
followed by absolute-value normalisation to enforce sum(w_i) = 1.

Calibration rules (paper Sec. V-A):
  * per-student weights computed only when the student has >= 8 completed
    sessions AND >= 2 associated graded outcomes;
  * any sub-metric with < 3 non-missing observations falls back;
  * missing sub-metric values are excluded pairwise per sub-metric, not
    by dropping the session;
  * students below the threshold use the population-level weight vector
    (identical computation, pooling all students) as cold-start.
"""
import numpy as np

SUBMETRICS = ("tcr", "sci", "dfet", "qap", "lrds")


def compute_submetric_correlations(submetric_series: dict, outcome_series) -> dict:
    """Absolute Pearson correlation |r| between each sub-metric and outcomes.

    Args:
        submetric_series: {submetric_name: list of per-session values (may
            contain None for missing observations — excluded pairwise)}.
        outcome_series: per-session academic performance outcome aligned
            with the sub-metric lists.
    Returns:
        {submetric_name: |r|} for sub-metrics with >= 3 non-missing pairs.
    """
    raise NotImplementedError("Phase 2")


def normalise_weights(correlations: dict) -> dict:
    """Eq. 2: w_i = a_i / sum(a_j) over available sub-metrics."""
    a = np.array([correlations[m] for m in SUBMETRICS if m in correlations], dtype=float)
    total = a.sum()
    if total <= 0:
        raise NotImplementedError("Phase 2: zero-correlation fallback policy")
    raise NotImplementedError("Phase 2")


def calibrate_student_weights(session_records, outcome_records, config) -> dict:
    """Full per-student calibration pipeline; returns the Eq. 2 weight dict
    or the population-level fallback vector."""
    raise NotImplementedError("Phase 2")
