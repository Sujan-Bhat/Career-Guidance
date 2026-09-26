"""Phase 2: constants and imports for the FES sub-package.

The behavioural implementations are tested in test_fes_impl.py.
"""
from careermind_ml.fes import engagement, submetrics, weights


def test_paper_constants_are_locked():
    # EngagementSignal thresholds (paper Sec. V-A)
    assert (engagement.MIN_SESSION_MINUTES, engagement.MIN_INTERACTIONS_PER_MIN, engagement.MIN_QUIZ_ATTEMPT_RATE) == (15, 3, 0.6)
    # Eq. 2 calibration gates (paper Sec. V-A)
    assert weights.DEFAULT_CONFIG["min_sessions"] == 8
    assert weights.DEFAULT_CONFIG["min_graded_outcomes"] == 2
    assert weights.DEFAULT_CONFIG["min_nonmissing_per_submetric"] == 3
    assert weights.SUBMETRICS == ("tcr", "sci", "dfet", "qap", "lrds")
    # LRDS type-specific dwell thresholds (fes.yaml mirror)
    assert submetrics.DEFAULT_LRDS_THRESHOLDS["video"] == 300
