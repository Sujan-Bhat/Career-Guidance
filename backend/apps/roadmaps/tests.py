"""AI roadmap endpoint tests — provider faked, no network (mirrors llm_proxy)."""
import pytest


def _roadmap(career="Data Scientist", slug="data-scientist"):
    return {
        "slug": slug,
        "title": career,
        "description": f"Path into {career}.",
        "nodes": [
            {"id": "sec-1", "kind": "section", "label": "Basics", "lane": "spine"},
            {"id": "python", "kind": "topic", "lane": "spine", "label": "Python"},
        ],
        "edges": [],
        "version": 1,
    }


@pytest.fixture
def fake_generate(monkeypatch):
    """Patch roadmapgen.generate_roadmap (imported lazily inside the view)."""
    import careermind_llm.roadmapgen as roadmapgen

    calls = []

    def _fake(career, context=None, client=None):
        calls.append({"career": career, "context": context})
        return _roadmap(career)

    monkeypatch.setattr(roadmapgen, "generate_roadmap", _fake)
    return calls


def test_generate_requires_auth(api):
    assert api.post("/api/v1/roadmaps/generate", {"career": "x"}).status_code in (401, 403)


def test_list_requires_auth(api):
    assert api.get("/api/v1/roadmaps/mine").status_code in (401, 403)


def test_detail_requires_auth(api):
    assert api.get("/api/v1/roadmaps/data-scientist").status_code in (401, 403)


def test_generate_503_without_api_key(registered, monkeypatch):
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    client, _ = registered
    response = client.post("/api/v1/roadmaps/generate", {"career": "Data Scientist"})
    assert response.status_code == 503
    assert "LLM_API_KEY" in response.data["detail"]


def test_generate_validation(registered, monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "test-key")
    client, _ = registered
    assert client.post("/api/v1/roadmaps/generate", {}).status_code == 400
    assert client.post("/api/v1/roadmaps/generate", {"career": "   "}).status_code == 400
    assert (
        client.post("/api/v1/roadmaps/generate", {"career": "x" * 200}).status_code == 400
    )


def test_generate_returns_and_persists_roadmap(registered, monkeypatch, fake_generate):
    monkeypatch.setenv("LLM_API_KEY", "test-key")
    client, user = registered

    response = client.post(
        "/api/v1/roadmaps/generate", {"career": "Data Scientist", "context": "year 2"}
    )
    assert response.status_code == 200
    assert response.data["roadmap"]["slug"] == "data-scientist"
    assert fake_generate[0] == {"career": "Data Scientist", "context": "year 2"}

    from .models import GeneratedRoadmap

    doc = GeneratedRoadmap.objects(slug="data-scientist").first()
    assert doc is not None
    assert doc.student == user["student_id"]
    assert doc.roadmap["nodes"][1]["label"] == "Python"


def test_generate_regenerates_same_slug(registered, monkeypatch, fake_generate):
    monkeypatch.setenv("LLM_API_KEY", "test-key")
    client, _ = registered
    client.post("/api/v1/roadmaps/generate", {"career": "Data Scientist"})
    client.post("/api/v1/roadmaps/generate", {"career": "Data Scientist"})

    from .models import GeneratedRoadmap

    assert GeneratedRoadmap.objects(slug="data-scientist").count() == 1


def test_list_returns_only_own_roadmaps(registered, monkeypatch, fake_generate):
    monkeypatch.setenv("LLM_API_KEY", "test-key")
    client, user = registered
    client.post("/api/v1/roadmaps/generate", {"career": "Data Scientist"})

    # another student's roadmap must never leak into this student's list
    from rest_framework.test import APIClient

    from .models import GeneratedRoadmap

    GeneratedRoadmap(
        student="someone-else",
        slug="devops-engineer",
        title="DevOps Engineer",
        description="",
        roadmap=_roadmap("DevOps Engineer", "devops-engineer"),
        generated_at="2026-01-01T00:00:00Z",
    ).save()

    response = client.get("/api/v1/roadmaps/mine")
    assert response.status_code == 200
    slugs = [r["slug"] for r in response.data["roadmaps"]]
    assert slugs == ["data-scientist"]
    assert response.data["roadmaps"][0]["roadmap"]["nodes"]  # full payload for rendering
    assert APIClient().get("/api/v1/roadmaps/mine").status_code in (401, 403)


def test_detail_scoped_to_owner(registered, monkeypatch, fake_generate):
    monkeypatch.setenv("LLM_API_KEY", "test-key")
    client, _ = registered
    client.post("/api/v1/roadmaps/generate", {"career": "Data Scientist"})

    ok = client.get("/api/v1/roadmaps/data-scientist")
    assert ok.status_code == 200
    assert ok.data["roadmap"]["slug"] == "data-scientist"

    # unowned slug -> 404 (not 403: existence of another student's roadmap
    # must not be observable)
    from .models import GeneratedRoadmap

    GeneratedRoadmap(
        student="someone-else",
        slug="private-roadmap",
        title="Private",
        description="",
        roadmap=_roadmap("Private", "private-roadmap"),
        generated_at="2026-01-01T00:00:00Z",
    ).save()
    assert client.get("/api/v1/roadmaps/private-roadmap").status_code == 404
    assert client.get("/api/v1/roadmaps/never-generated").status_code == 404


def test_delete_scoped_to_owner(registered, monkeypatch, fake_generate):
    monkeypatch.setenv("LLM_API_KEY", "test-key")
    client, _ = registered
    client.post("/api/v1/roadmaps/generate", {"career": "Data Scientist"})

    from .models import GeneratedRoadmap

    assert GeneratedRoadmap.objects(slug="data-scientist").count() == 1

    # Unowned slug deletion -> 404
    assert client.delete("/api/v1/roadmaps/never-generated").status_code == 404

    # Own slug deletion -> 200
    res = client.delete("/api/v1/roadmaps/data-scientist")
    assert res.status_code == 200
    assert GeneratedRoadmap.objects(slug="data-scientist").count() == 0


def test_generate_provider_failure_returns_502(registered, monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "test-key")
    import careermind_llm.roadmapgen as roadmapgen

    def _boom(career, context=None, client=None):
        raise ValueError("LLM returned invalid roadmap JSON")

    monkeypatch.setattr(roadmapgen, "generate_roadmap", _boom)
    client, _ = registered
    response = client.post("/api/v1/roadmaps/generate", {"career": "Data Scientist"})
    assert response.status_code == 502
    assert "invalid roadmap JSON" in response.data["detail"]


def test_generate_generic_provider_error_returns_502(registered, monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "test-key")
    import careermind_llm.roadmapgen as roadmapgen

    def _boom(career, context=None, client=None):
        raise RuntimeError("quota exceeded")

    monkeypatch.setattr(roadmapgen, "generate_roadmap", _boom)
    client, _ = registered
    response = client.post("/api/v1/roadmaps/generate", {"career": "Data Scientist"})
    assert response.status_code == 502
