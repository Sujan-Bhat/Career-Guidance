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


# ---- Phase 7: LLM explanation endpoint (NFR07) ---------------------------

@pytest.fixture
def recommendation_for_user(registered):
    from datetime import datetime

    from apps.recommendations.models import Recommendation

    _, user = registered
    doc = Recommendation(
        student=user["student_id"],
        item_type="pathway",
        item_id="c03",
        stage1_eligible=True,
        stage2_cf_score=0.41,
        stage3_fm_score=0.83,
        contributing_features={"fes_current": 0.72, "skill_databases_sql": 90},
        decision="pending",
        created_at=datetime.utcnow(),
    ).save()
    return str(doc.pk)


def test_explain_requires_auth(api, recommendation_for_user):
    response = api.get(f"/api/v1/recommendations/{recommendation_for_user}/explain")
    assert response.status_code in (401, 403)


def test_explain_404_unknown(registered, recommendation_for_user):
    client, _ = registered
    assert client.get("/api/v1/recommendations/000000000000000000000000/explain").status_code == 404


def test_explain_503_without_key(recommendation_for_user, registered, monkeypatch):
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    client, _ = registered
    response = client.get(f"/api/v1/recommendations/{recommendation_for_user}/explain")
    assert response.status_code == 503
    assert "LLM_API_KEY" in response.data["detail"]


def test_explain_generates_and_caches(recommendation_for_user, registered, monkeypatch):
    import careermind_llm.explain as explain_mod

    monkeypatch.setenv("LLM_API_KEY", "test-key")
    calls = []

    def _fake(recommendation, features, client=None):
        calls.append((recommendation, features))
        return "Your SQL skill and engagement match this pathway."

    monkeypatch.setattr(explain_mod, "generate_explanation", _fake)

    client, _ = registered
    first = client.get(f"/api/v1/recommendations/{recommendation_for_user}/explain")
    assert first.status_code == 200
    assert first.data["explanation"] == "Your SQL skill and engagement match this pathway."
    assert first.data["cached"] is False

    recommendation, features = calls[0]
    assert recommendation["stage3_fm_score"] == 0.83
    assert {"feature": "fes_current", "value": 0.72} in features

    # cached: no second LLM call even if the provider would now fail
    def _should_not_be_called(*_args, **_kwargs):
        raise AssertionError("second call must not hit the LLM")

    monkeypatch.setattr(explain_mod, "generate_explanation", _should_not_be_called)
    second = client.get(f"/api/v1/recommendations/{recommendation_for_user}/explain")
    assert second.status_code == 200
    assert second.data["cached"] is True
    assert len(calls) == 1


def test_explain_provider_failure_returns_502(recommendation_for_user, registered, monkeypatch):
    import careermind_llm.explain as explain_mod

    monkeypatch.setenv("LLM_API_KEY", "test-key")

    def _boom(recommendation, features, client=None):
        raise RuntimeError("provider down")

    monkeypatch.setattr(explain_mod, "generate_explanation", _boom)
    client, _ = registered
    response = client.get(f"/api/v1/recommendations/{recommendation_for_user}/explain")
    assert response.status_code == 502


@pytest.mark.usefixtures("seeded_population")
def test_accept_writes_an_interactions_document(registered):
    """`interactions` is what stage-2 CF and the ensemble's exp_* features
    read; live users must contribute to it on accept, not only the seeder."""
    client, user = registered
    recs = client.get("/api/v1/recommendations/").data["recommendations"]
    accepted, rejected = recs[0], recs[1]

    assert client.post(f"/api/v1/recommendations/{accepted['recommendation_id']}/accept").status_code == 200
    assert client.post(f"/api/v1/recommendations/{rejected['recommendation_id']}/reject").status_code == 200

    db = connection.get_db("default")
    row = db.interactions.find_one({"student": user["student_id"], "item_id": accepted["id"]})
    assert row is not None, "accepting a recommendation must record an interaction"
    assert row["decision"] == "accepted"
    assert row["created_at"] is not None

    # rejections are not positive feedback and must not be written
    assert db.interactions.find_one({"student": user["student_id"], "item_id": rejected["id"]}) is None


@pytest.mark.usefixtures("seeded_population")
def test_accepting_twice_upserts_rather_than_duplicates(registered):
    client, user = registered
    rec = client.get("/api/v1/recommendations/").data["recommendations"][0]
    client.post(f"/api/v1/recommendations/{rec['recommendation_id']}/accept")

    # force a second accept through the same code path (the view's 409 guard
    # normally blocks it) to prove the write is idempotent
    views._record_interaction(user["student_id"], rec["id"])
    views._record_interaction(user["student_id"], rec["id"])

    db = connection.get_db("default")
    assert db.interactions.count_documents({"student": user["student_id"], "item_id": rec["id"]}) == 1
