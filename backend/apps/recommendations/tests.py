"""Recommendation API tests (Phase 4): cascade endpoint + accept/reject."""
import pytest
from mongoengine import connection

import apps.recommendations.views as views
from apps.accounts.models import SkillAssessment, StudentProfile


@pytest.fixture
def seeded_population(clean_test_db):
    """Minimal population so cold-start (population skill profile) yields
    candidates above the 60% gate, plus a little CF history. Uses the real
    FM artifact on disk (make train-fm)."""
    views._cascade = None  # rebuild against this test DB's data
    profiles = [
        ("pop1@test.local", {"dsa": 100, "programming_java": 90, "softeng_practices": 85, "operating_systems": 80}),
        ("pop2@test.local", {"programming_python": 100, "statistics": 95, "ml_fundamentals": 85, "databases_sql": 80}),
        ("pop3@test.local", {"programming_c_cpp": 100, "electronics_digital": 90, "embedded_systems": 85}),
    ]
    for i, (email, skills) in enumerate(profiles):
        StudentProfile(
            email=email,
            full_name=f"Population {i}",
            password_hash="x",
            source="simulator",
            skill_assessments=[SkillAssessment(skill=s, score=v) for s, v in skills.items()],
        ).save()
    db = connection.get_db("default")
    db.interactions.insert_many(
        [
            {"student": "pop_x", "item_id": "c03", "session": "pop_x:0", "date": "2025-03-01", "source": "simulator"},
            {"student": "pop_x", "item_id": "c01", "session": "pop_x:0", "date": "2025-03-01", "source": "simulator"},
        ]
    )
    return db


@pytest.mark.usefixtures("seeded_population")
def test_recommendations_cold_start_flow(registered):
    client, user = registered
    response = client.get("/api/v1/recommendations/")
    assert response.status_code == 200
    assert response.data["cold_start"] is True  # new user: no skills yet
    assert response.data["count"] > 0, "population profile must yield candidates (FR11)"
    rec = response.data["recommendations"][0]
    for key in ("recommendation_id", "id", "name", "stage1_eligibility", "stage2_cf_score", "stage3_fm_score", "decision"):
        assert key in rec
    assert rec["decision"] == "pending"

    # persisted with provenance
    from apps.recommendations.models import Recommendation

    assert Recommendation.objects(student=user["student_id"], decision="pending").count() > 0


@pytest.mark.usefixtures("seeded_population")
def test_accept_and_reject_decision_flow(registered):
    client, _ = registered
    rec_id = client.get("/api/v1/recommendations/").data["recommendations"][0]["recommendation_id"]

    accepted = client.post(f"/api/v1/recommendations/{rec_id}/accept")
    assert accepted.status_code == 200
    assert accepted.data["decision"] == "accepted"

    duplicate = client.post(f"/api/v1/recommendations/{rec_id}/accept")
    assert duplicate.status_code == 409

    rejected = client.post(f"/api/v1/recommendations/{rec_id}/reject")
    assert rejected.status_code == 409  # already accepted


@pytest.mark.usefixtures("seeded_population")
def test_recommendations_require_auth(api):
    assert api.get("/api/v1/recommendations/").status_code in (401, 403)
