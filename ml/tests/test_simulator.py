"""Simulator validation (Phase 1).

Checks the design goal of data/simulator: latent parameters must produce
behavioural aggregates whose sub-metric PROXIES genuinely correlate with
outcomes, so that Eq. 2 calibration (Phase 2) has signal to learn from.

Note: the proxies below are inline approximations (raw ratios), NOT the
Phase 2 sub-metric implementations in careermind_ml.fes.submetrics.
"""
import numpy as np
import pytest

from simulator import StudentSimulator


@pytest.fixture(scope="module")
def population():
    sim = StudentSimulator(seed=123)
    students = sim.generate_students(200)
    data = []
    for student in students:
        sessions = sim.generate_sessions(student, 12)
        outcome = sim.generate_outcomes(student, sessions)
        data.append((student, sessions, outcome))
    return data


def test_latent_parameters_in_bounds(population):
    for student, _, _ in population:
        assert 0.0 < student["ability"] < 1.0
        assert 0.0 < student["motivation"] < 1.0
        assert 0.0 < student["focus_tendency"] < 1.0
        assert abs(sum(student["domain_affinity"].values()) - 1.0) < 1e-6


def test_session_fields_valid(population):
    for _, sessions, _ in population:
        assert len(sessions) == 12
        for s in sessions:
            assert s["duration_minutes"] > 0
            assert 0 <= s["tasks_completed"] <= s["tasks_started"]
            assert 0 <= s["quiz_items_correct"] <= s["quiz_items"]
            assert 0 <= s["quiz_reattempts"] <= (s["quiz_items"] - s["quiz_items_correct"])
            assert 0 <= s["assessment_score"] <= 100
            assert s["interaction_count"] >= 0
            for visit in s["resource_visits"]:
                assert visit["type"] in ("video", "article", "exercise", "interactive")
                assert visit["dwell_seconds"] > 0


def _pearson(x, y):
    if np.std(x) < 1e-9 or np.std(y) < 1e-9:
        return 0.0
    return float(np.corrcoef(x, y)[0, 1])


def test_tcr_proxy_correlates_with_ability(population):
    """Completion behaviour should track ability (Liu et al. [16] grounding)."""
    ability, tcr = [], []
    for student, sessions, _ in population:
        started = sum(s["tasks_started"] for s in sessions)
        completed = sum(s["tasks_completed"] for s in sessions)
        if started > 0:
            ability.append(student["ability"])
            tcr.append(completed / started)
    r = _pearson(ability, tcr)
    assert r > 0.3, f"TCR-ability correlation too weak: {r}"


def test_qap_proxy_correlates_with_motivation(population):
    """Quiz re-attempt persistence should track motivation."""
    motivation, qap = [], []
    for student, sessions, _ in population:
        incorrect = sum(s["quiz_items"] - s["quiz_items_correct"] for s in sessions)
        reattempts = sum(s["quiz_reattempts"] for s in sessions)
        if incorrect > 0:
            motivation.append(student["motivation"])
            qap.append(reattempts / incorrect)
    r = _pearson(motivation, qap)
    assert r > 0.3, f"QAP-motivation correlation too weak: {r}"


def test_assessment_scores_correlate_with_ability(population):
    ability, scores = [], []
    for student, sessions, _ in population:
        ability.append(student["ability"])
        scores.append(np.mean([s["assessment_score"] for s in sessions]))
    r = _pearson(ability, scores)
    assert r > 0.5, f"outcome-ability correlation too weak: {r}"


def test_career_label_matches_dominant_affinity(population):
    for student, _, outcome in population:
        dominant = max(student["domain_affinity"], key=student["domain_affinity"].get)
        assert outcome["career_category"] == dominant
        assert outcome["career_pathway_id"] is None or outcome["career_pathway_id"].startswith("c")


def test_determinism_with_seed():
    a = StudentSimulator(seed=7)
    b = StudentSimulator(seed=7)
    sa = a.generate_students(3)
    sb = b.generate_students(3)
    assert [s["student_id"] for s in sa] == [s["student_id"] for s in sb]
    assert sa[0]["ability"] == sb[0]["ability"]
    assert a.generate_sessions(sa[0], 5)[0]["date"] == b.generate_sessions(sb[0], 5)[0]["date"]


def test_explode_events_structure():
    sim = StudentSimulator(seed=1)
    student = sim.generate_students(1)[0]
    session = sim.generate_sessions(student, 1)[0]
    events = StudentSimulator.explode_events(session)
    types = [e["type"] for e in events]
    assert types[0] == "session_start" and types[-1] == "session_end"
    assert types.count("resource_open") == types.count("resource_close") == len(session["resource_visits"])
    assert all("timestamp" in e and "student" in e for e in events)
