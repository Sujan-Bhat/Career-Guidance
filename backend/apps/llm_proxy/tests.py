"""LLM proxy tests (Phase 7) — provider faked, no network."""
import pytest

import apps.llm_proxy.views as views


@pytest.fixture(autouse=True)
def reset_chat(clean_test_db):
    # clear at setup only: tests may monkeypatch views._chat with a plain
    # lambda that has no cache_clear, and fixture teardown order is not ours
    views._chat.cache_clear()


class FakeGuidanceChat:
    def __init__(self, reply="Explore both options.", error=None):
        self.reply = reply
        self.error = error
        self.calls = []

    def chat(self, student_id, message, context=None):
        self.calls.append({"student": student_id, "message": message, "context": context})
        if self.error:
            raise self.error
        return self.reply


def test_chat_requires_auth(api):
    assert api.post("/api/v1/llm/chat", {"message": "hi"}).status_code in (401, 403)


def test_chat_503_without_api_key(registered, monkeypatch):
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    client, _ = registered
    response = client.post("/api/v1/llm/chat", {"message": "hi"})
    assert response.status_code == 503
    assert "LLM_API_KEY" in response.data["detail"]


def test_chat_rejects_empty_message(registered, monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "test-key")
    client, _ = registered
    assert client.post("/api/v1/llm/chat", {"message": "   "}).status_code == 400


def test_chat_returns_grounded_reply(registered, monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "test-key")
    fake = FakeGuidanceChat()
    monkeypatch.setattr(views, "_chat", lambda: fake)
    client, user = registered

    response = client.post("/api/v1/llm/chat", {"message": "Which pathway fits me?"})
    assert response.status_code == 200
    assert response.data["reply"] == "Explore both options."

    call = fake.calls[0]
    assert call["student"] == user["student_id"]
    assert call["message"] == "Which pathway fits me?"
    assert isinstance(call["context"], str)  # profile/FES/recs grounding block


def test_chat_provider_failure_returns_502(registered, monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "test-key")
    monkeypatch.setattr(views, "_chat", lambda: FakeGuidanceChat(error=RuntimeError("boom")))
    client, _ = registered
    response = client.post("/api/v1/llm/chat", {"message": "hi"})
    assert response.status_code == 502


def test_quiz_requires_auth(api):
    assert api.post("/api/v1/llm/quiz/generate", {"skill": "python"}).status_code in (401, 403)


def test_quiz_503_without_api_key(registered, monkeypatch):
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    client, _ = registered
    response = client.post("/api/v1/llm/quiz/generate", {"skill": "python"})
    assert response.status_code == 503


def test_quiz_validation(registered, monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "test-key")
    client, _ = registered
    assert client.post("/api/v1/llm/quiz/generate", {}).status_code == 400
    assert (
        client.post("/api/v1/llm/quiz/generate", {"skill": "python", "difficulty": "high"}).status_code
        == 400
    )


def test_quiz_returns_items_with_clamped_difficulty(registered, monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "test-key")
    captured = {}

    def _fake_generate(skill, difficulty, n_items):
        captured.update(skill=skill, difficulty=difficulty, n_items=n_items)
        return [{"question": "Q?", "options": ["a", "b"], "answer": 1, "difficulty": difficulty}]

    import careermind_llm.quizgen as quizgen

    monkeypatch.setattr(quizgen, "generate_quiz_items", _fake_generate)
    client, _ = registered
    response = client.post(
        "/api/v1/llm/quiz/generate", {"skill": "python", "difficulty": 7, "n_items": 3}
    )
    assert response.status_code == 200
    assert captured == {"skill": "python", "difficulty": 3, "n_items": 3, }
    assert len(response.data["items"]) == 1
    assert response.data["skill"] == "python"


def test_quiz_model_failure_returns_502(registered, monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "test-key")
    import careermind_llm.quizgen as quizgen

    def _boom(skill, difficulty, n_items):
        raise ValueError("LLM did not return a JSON array of quiz items")

    monkeypatch.setattr(quizgen, "generate_quiz_items", _boom)
    client, _ = registered
    response = client.post("/api/v1/llm/quiz/generate", {"skill": "python"})
    assert response.status_code == 502
    assert "JSON array" in response.data["detail"]
