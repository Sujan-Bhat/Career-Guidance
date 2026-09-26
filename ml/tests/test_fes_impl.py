"""FES engine tests (Phase 2): sub-metrics, EngagementSignal, Eq. 2 calibration."""
import math

import numpy as np
import pytest

from careermind_ml.fes.engagement import engagement_signal
from careermind_ml.fes.submetrics import (
    distraction_free_engagement_time,
    learning_resource_depth_score,
    quiz_attempt_persistence,
    session_consistency_index,
    task_completion_rate,
)
from careermind_ml.fes.weights import (
    SUBMETRICS,
    calibrate_population_weights,
    calibrate_student_weights,
    compute_fes,
    compute_submetric_correlations,
    normalise_weights,
)


# ------------------------------------------------------------- sub-metrics

class TestTCR:
    def test_basic_ratio(self):
        assert task_completion_rate(4, 3) == pytest.approx(0.75)

    def test_zero_started_is_missing(self):
        assert task_completion_rate(0, 0) is None

    def test_clipped_at_one(self):
        assert task_completion_rate(2, 2) == 1.0


class TestSCI:
    def test_perfectly_regular(self):
        logins = [9 * 60] * 5
        durations = [30.0] * 5
        assert session_consistency_index(logins, durations) == pytest.approx(1.0)

    def test_irregular_is_lower(self):
        regular = session_consistency_index([540] * 5, [30.0] * 5)
        chaotic = session_consistency_index([60, 400, 900, 1300, 200], [10.0, 90.0, 20.0, 120.0, 5.0])
        assert chaotic < regular
        assert 0.0 <= chaotic <= 1.0

    def test_circular_wraparound_counts_as_regular(self):
        # 23:00 vs 01:00 should be nearly as regular as identical times
        near = session_consistency_index([23 * 60, 23 * 60, 60, 60], [30.0] * 4)
        assert near > 0.5

    def test_single_session_is_missing(self):
        assert session_consistency_index([540], [30.0]) is None


class TestDFET:
    VISITS_SUSTAINED = [
        {"type": "video", "dwell_seconds": 400, "idle_gap_seconds": 10, "rapid_switch": False},
        {"type": "article", "dwell_seconds": 300, "idle_gap_seconds": 30, "rapid_switch": False},
    ]
    VISITS_BAD = [
        {"type": "video", "dwell_seconds": 400, "idle_gap_seconds": 300, "rapid_switch": False},  # idle
        {"type": "article", "dwell_seconds": 300, "idle_gap_seconds": 10, "rapid_switch": True},  # rapid
    ]

    def test_all_sustained(self):
        dfet = distraction_free_engagement_time(self.VISITS_SUSTAINED, 12.0)  # 700/720
        assert dfet == pytest.approx(700 / 720)

    def test_distracted_reduced(self):
        dfet = distraction_free_engagement_time(self.VISITS_BAD, 12.0)
        assert dfet == pytest.approx(0.0)

    def test_mixed(self):
        dfet = distraction_free_engagement_time(
            self.VISITS_SUSTAINED + self.VISITS_BAD, 24.0
        )
        assert dfet == pytest.approx(700 / 1440, rel=0.01)

    def test_no_visits_is_missing(self):
        assert distraction_free_engagement_time([], 30.0) is None


class TestQAP:
    def test_half_reattempted(self):
        assert quiz_attempt_persistence(10, 6, 2) == pytest.approx(0.5)

    def test_no_incorrect_items_is_missing(self):
        # confirmed design decision: nothing to re-attempt -> pairwise excluded
        assert quiz_attempt_persistence(5, 5, 0) is None

    def test_all_reattempted(self):
        assert quiz_attempt_persistence(4, 2, 2) == 1.0


class TestLRDS:
    VISITS = [
        {"type": "video", "dwell_seconds": 400, "idle_gap_seconds": 0, "rapid_switch": False},
        {"type": "article", "dwell_seconds": 100, "idle_gap_seconds": 0, "rapid_switch": False},
    ]

    def test_proportion_above_threshold(self):
        # video threshold 300s: 400 passes; article threshold 180s: 100 fails
        assert learning_resource_depth_score(self.VISITS) == pytest.approx(0.5)

    def test_all_deep(self):
        visits = [{"type": "video", "dwell_seconds": 500}] * 3
        assert learning_resource_depth_score(visits) == 1.0

    def test_no_visits_is_missing(self):
        assert learning_resource_depth_score([]) is None


# ------------------------------------------------------ EngagementSignal

class TestEngagementSignal:
    def test_all_thresholds_met_exactly(self):
        assert engagement_signal(15.0, interaction_count=45, quiz_attempt_rate=0.6) == 1

    def test_duration_below_threshold(self):
        assert engagement_signal(14.9, interaction_count=45, quiz_attempt_rate=0.6) == 0

    def test_interaction_rate_below_threshold(self):
        assert engagement_signal(20.0, interaction_count=50, quiz_attempt_rate=0.6) == 0  # 2.5/min

    def test_quiz_rate_below_threshold(self):
        assert engagement_signal(20.0, interaction_count=100, quiz_attempt_rate=0.5) == 0

    def test_explicit_interaction_rate(self):
        assert engagement_signal(20.0, interaction_rate=3.0, quiz_attempt_rate=0.9) == 1


# ------------------------------------------------------- Eq. 2 calibration

def _pair(tcr=0.5, sci=0.5, dfet=0.5, qap=0.5, lrds=0.5, outcome=70.0):
    return {"tcr": tcr, "sci": sci, "dfet": dfet, "qap": qap, "lrds": lrds, "outcome": outcome}


class TestCorrelations:
    def test_perfect_correlation(self):
        pairs = [_pair(tcr=i / 10, outcome=i / 10) for i in range(6)]
        corr = compute_submetric_correlations(pairs)
        assert corr["tcr"] == pytest.approx(1.0, abs=1e-6)

    def test_pairwise_exclusion_of_missing(self):
        # 5 pairs, 3 with tcr present -> still computed from the 3 non-missing
        pairs = [_pair(tcr=None, outcome=50 + i) for i in range(2)]
        pairs += [_pair(tcr=i / 5, outcome=i * 20) for i in range(3)]
        corr = compute_submetric_correlations(pairs)
        assert "tcr" in corr  # >= 3 non-missing
        # outcome series among the 3 kept pairs: [0, 20, 40] vs tcr [0, .2, .4]
        assert corr["tcr"] == pytest.approx(1.0, abs=1e-6)

    def test_below_nonmissing_gate_dropped(self):
        pairs = [_pair(tcr=0.5, outcome=60.0)] * 2 + [_pair(tcr=None) for _ in range(6)]
        corr = compute_submetric_correlations(pairs)
        assert "tcr" not in corr  # only 2 non-missing < min 3

    def test_zero_variance_gets_zero(self):
        pairs = [_pair(sci=0.5) for _ in range(5)]  # constant sci
        corr = compute_submetric_correlations(pairs)
        assert corr["sci"] == 0.0


class TestNormaliseWeights:
    def test_sums_to_one(self):
        w = normalise_weights({"tcr": 0.6, "sci": 0.2, "dfet": 0.1, "qap": 0.05, "lrds": 0.05})
        assert sum(w.values()) == pytest.approx(1.0)
        assert w["tcr"] == pytest.approx(0.6)

    def test_degenerate_uniform(self):
        w = normalise_weights({"tcr": 0.0, "sci": 0.0})
        assert w == {"tcr": 0.5, "sci": 0.5}


class TestCalibrateStudentWeights:
    def _informative_pairs(self, n=10):
        # TCR tracks the outcome; others carry no signal
        rng = np.random.default_rng(0)
        pairs = []
        for i in range(n):
            tcr = i / max(n - 1, 1)
            pairs.append(_pair(tcr=tcr, outcome=tcr * 100 + rng.normal(0, 0.01)))
        return pairs

    def test_weights_recover_dominant_metric(self):
        w = calibrate_student_weights(self._informative_pairs())
        assert w is not None
        assert sum(w.values()) == pytest.approx(1.0)
        assert w["tcr"] == max(w.values())
        assert w["tcr"] > 0.5

    def test_below_session_gate_falls_back(self):
        pairs = self._informative_pairs(n=7)  # < min_sessions 8
        assert calibrate_student_weights(pairs) is None

    def test_one_metric_below_nonmissing_gate_falls_back(self):
        pairs = self._informative_pairs(n=10)
        pairs[0]["dfet"] = None
        pairs[1]["dfet"] = None
        pairs[2]["dfet"] = None  # 7 non-missing left... keep 8 of 10 -> below gate needs < 3
        pairs[3]["dfet"] = None
        pairs[4]["dfet"] = None
        pairs[5]["dfet"] = None
        pairs[6]["dfet"] = None
        pairs[7]["dfet"] = None  # only 2 non-missing dfet left
        assert calibrate_student_weights(pairs) is None  # paper rule: whole-student fallback

    def test_outcome_gate(self):
        pairs = [{k: None for k in SUBMETRICS} for _ in range(2)]
        pairs += self._informative_pairs(8)  # 10 total but only 8 with outcomes
        # outcomes present in the 8 informative pairs -> gate passes
        w = calibrate_student_weights(pairs)
        assert w is not None


class TestPopulationWeights:
    def test_pooled_calibration(self):
        rng = np.random.default_rng(1)
        pairs = []
        for s in range(20):
            for i in range(5):
                tcr = i / 4
                pairs.append(_pair(tcr=tcr, outcome=tcr * 100 + rng.normal(0, 0.05)))
        w = calibrate_population_weights(pairs)
        assert w["tcr"] == max(w.values())
        assert sum(w.values()) == pytest.approx(1.0)

    def test_uniform_on_degenerate_pool(self):
        pairs = [_pair() for _ in range(10)]  # no variance anywhere
        w = calibrate_population_weights(pairs)
        assert w == {m: pytest.approx(0.2) for m in SUBMETRICS}


class TestComputeFES:
    W = {"tcr": 0.5, "sci": 0.2, "dfet": 0.1, "qap": 0.1, "lrds": 0.1}

    def test_weighted_sum(self):
        metrics = {m: 1.0 for m in SUBMETRICS}
        assert compute_fes(metrics, self.W) == pytest.approx(1.0)
        metrics = {m: 0.0 for m in SUBMETRICS}
        assert compute_fes(metrics, self.W) == pytest.approx(0.0)

    def test_missing_renormalised(self):
        # tcr missing -> remaining weights renormalised to 1.0
        metrics = {"sci": 1.0, "dfet": 1.0, "qap": 1.0, "lrds": 1.0}  # no tcr
        assert compute_fes(metrics, self.W) == pytest.approx(1.0)

    def test_all_missing_is_none(self):
        assert compute_fes({}, self.W) is None
        assert compute_fes({m: None for m in SUBMETRICS}, self.W) is None

    def test_partial_value(self):
        metrics = {"tcr": 0.8, "sci": 0.6, "dfet": 1.0, "qap": 0.0, "lrds": 1.0}
        fes = compute_fes(metrics, self.W)
        expected = 0.5 * 0.8 + 0.2 * 0.6 + 0.1 * 1.0 + 0.1 * 0.0 + 0.1 * 1.0
        assert fes == pytest.approx(expected)
        assert 0.0 <= fes <= 1.0
