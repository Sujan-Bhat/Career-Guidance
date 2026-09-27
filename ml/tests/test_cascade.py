"""Cascade orchestrator tests (Phase 4): provenance, cold start, personalization."""
import pytest

torch = pytest.importorskip("torch")

from careermind_ml.recommender.cascade import CascadeRecommender
from careermind_ml.recommender.features import GRADE_SUBJECTS, build_spec
from careermind_ml.recommender.fm import FactorizationMachine
from careermind_ml.recommender.knowledge_graph import load_knowledge_graph

STRONG_DATA_SKILLS = {
    "dsa": 5, "programming_python": 5, "programming_java": 4, "statistics": 5,
    "ml_fundamentals": 4, "databases_sql": 4, "web_backend": 3, "softeng_practices": 4,
    "operating_systems": 3, "javascript_ts": 3, "web_frontend": 3, "cloud_platforms": 2,
}
STRONG_HARDWARE_SKILLS = {
    "programming_c_cpp": 5, "electronics_digital": 5, "embedded_systems": 4,
    "control_systems": 4, "operating_systems": 3, "discrete_math": 3,
}


def _agg(student="test", pref="data"):
    return {
        "student": student,
        "grades": {s: 75 for s in GRADE_SUBJECTS},
        "fes_current": 0.7,
        "fes_trend": 0.6,
        "preferences": {pref: 1.0},
        "year_of_study": 3,
    }


@pytest.fixture()
def recommender():
    spec = build_spec([], ["c01", "c03", "c10", "c11"])
    model = FactorizationMachine(spec.dim, k=8)  # untrained: mechanics only
    # population profile broad enough that several careers clear the 60% gate
    population = {skill: 3.0 for skill in (
        "dsa", "programming_python", "programming_java", "statistics",
        "ml_fundamentals", "databases_sql", "web_backend", "softeng_practices",
        "operating_systems", "javascript_ts", "web_frontend", "programming_c_cpp",
        "electronics_digital", "embedded_systems", "control_systems",
        "discrete_math", "communication", "cloud_platforms",
    )}
    population.update({"dsa": 4.2, "statistics": 3.9, "programming_c_cpp": 4.0})
    return CascadeRecommender(
        graph=load_knowledge_graph(),
        cooc={},  # no CF history: all scores 0
        fm_model=model,
        fm_spec=spec,
        population_skills=population,
    )


def test_cascade_provenance_fields(recommender):
    result = recommender.recommend(_agg(), STRONG_DATA_SKILLS, ["c03"], top_k=5)
    assert result["cold_start"] is False
    assert result["results"], "strong student must match some careers"
    for r in result["results"]:
        assert 0.0 <= r["stage1_eligibility"] <= 1.0
        assert r["stage2_cf_score"] == 0.0  # empty cooc
        assert isinstance(r["stage3_fm_score"], float)
        assert "prerequisites_met" in r and "/" in r["prerequisites_met"]
        assert r["contributing_features"]["fes_current"] == 0.7


def test_cold_start_uses_population_profile(recommender):
    result = recommender.recommend(_agg(), None, [], top_k=10)
    assert result["cold_start"] is True
    assert result["results"], "population profile must yield candidates (FR11)"


def test_stage1_filters_below_threshold(recommender):
    weak_skills = {"communication": 2}  # only Tech Product Manager prereq-ish
    result = recommender.recommend(_agg(), weak_skills, [], top_k=20)
    for r in result["results"]:
        assert r["stage1_eligibility"] >= 0.60


def test_personalization_differs_by_profile(recommender):
    data_ranking = recommender.recommend(_agg(pref="data"), STRONG_DATA_SKILLS, [])
    hardware_ranking = recommender.recommend(_agg(pref="hardware"), STRONG_HARDWARE_SKILLS, [])
    data_top = {r["id"] for r in data_ranking["results"][:3]}
    hardware_top = {r["id"] for r in hardware_ranking["results"][:3]}
    assert data_top != hardware_top
