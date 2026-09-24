"""Smoke tests for the FES sub-package stubs (real tests arrive in Phase 2)."""
import pytest

from careermind_ml.fes import engagement, submetrics, weights


def test_submetric_stubs_raise_with_phase_pointer():
    with pytest.raises(NotImplementedError, match="Phase 2"):
        submetrics.task_completion_rate(10, 7)


def test_weight_constants_match_paper():
    assert weights.SUBMETRICS == ("tcr", "sci", "dfet", "qap", "lrds")
    assert (engagement.MIN_SESSION_MINUTES, engagement.MIN_INTERACTIONS_PER_MIN, engagement.MIN_QUIZ_ATTEMPT_RATE) == (
        15,
        3,
        0.6,
    )
