"""Career prediction API tests (Phase 5): ensemble endpoint + persistence."""
from datetime import datetime

import pytest

import apps.careers.views as views
from apps.accounts.models import AcademicRecord, SkillAssessment, StudentProfile
from apps.fes.models import FESScore


@pytest.fixture(autouse=True)
def fresh_ensemble(clean_test_db):
    """Rebuild the lazy artifact/skill-mapping singletons per test."""
    views._ensemble = None
    views._skill_categories.cache_clear()
    yield
    views._ensemble = None
    views._skill_categories.cache_clear()


def test_predictions_cold_start_flow(registered):
    client, user = registered
    response = client.get("/api/v1/careers/predictions")
    assert response.status_code == 200

    assert response.data["cold_start"] is True  # brand-new user: no data
    distribution = response.data["distribution"]
    assert len(distribution) == 6  # all career categories
    assert sum(row["probability"] for row in distribution) == pytest.approx(1.0)
    probabilities = [row["probability"] for row in distribution]
    assert probabilities == sorted(probabilities, reverse=True)  # confidence-ranked
    assert response.data["prediction"] == distribution[0]["category"]

    top_features = response.data["top_features"]
    assert 0 < len(top_features) <= 5  # transparency, Sec. V-D
    assert {"feature", "importance"} == set(top_features[0])
    assert response.data["model_version"]

    from apps.careers.models import CareerPrediction

    assert CareerPrediction.objects(student=user["student_id"]).count() == 1


def test_prediction_upserts_single_document(registered):
    client, _ = registered
    assert client.get("/api/v1/careers/predictions").status_code == 200
    assert client.get("/api/v1/careers/predictions").status_code == 200

    from apps.careers.models import CareerPrediction

    assert CareerPrediction.objects().count() == 1  # updated, not duplicated


def test_prediction_personalized_after_profile_data(registered):
    client, user = registered
    assert client.get("/api/v1/careers/predictions").data["cold_start"] is True

    profile = StudentProfile.objects(email="student@test.local").first()
    profile.skill_assessments = [
        SkillAssessment(skill="programming_python", score=95),
        SkillAssessment(skill="statistics", score=92),
        SkillAssessment(skill="ml_fundamentals", score=90),
    ]
    profile.academic_records = [AcademicRecord(subject="CS201", grade=88.0)]
    profile.save()
    for i, fes in enumerate((0.55, 0.71)):
        FESScore(
            session=f"s{i}",
            student=user["student_id"],
            fes=fes,
            computed_at=datetime(2026, 9, 20 + i),
        ).save()

    response = client.get("/api/v1/careers/predictions")
    assert response.status_code == 200
    assert response.data["cold_start"] is False


def test_predictions_require_auth(api):
    assert api.get("/api/v1/careers/predictions").status_code in (401, 403)


def test_predictions_503_when_artifact_missing(registered, monkeypatch):
    def _missing():
        raise FileNotFoundError("ensemble.joblib")

    monkeypatch.setattr("careermind_ml.career_prediction.ensemble.load_artifact", _missing)
    views._ensemble = None
    client, _ = registered
    response = client.get("/api/v1/careers/predictions")
    assert response.status_code == 503
    assert "train-ensemble" in response.data["detail"]
