"""RL feedback API tests (Phase 6): status, action selection, transition log."""
import pytest

import apps.rl_feedback.views as views
from apps.rl_feedback.models import RLTransition


@pytest.fixture(autouse=True)
def fresh_agent(clean_test_db):
    views._agent = None
    yield
    views._agent = None


def test_status_requires_auth(api):
    assert api.get("/api/v1/rl/status").status_code in (401, 403)


def test_status_returns_action_catalogue(registered):
    client, _ = registered
    response = client.get("/api/v1/rl/status")
    assert response.status_code == 200
    assert len(response.data["action_names"]) == 8
    assert response.data["transition_count"] == 0
    assert response.data["last_action"] is None
    assert response.data["pending_transition"] is False
    assert isinstance(response.data["model_available"], bool)


def test_action_selects_logs_and_closes_previous(registered, monkeypatch):
    from careermind_ml.rl.dqn import DQNAgent

    monkeypatch.setattr(views, "_agent", DQNAgent({}))  # random-init policy
    client, user = registered

    first = client.post("/api/v1/rl/action")
    assert first.status_code == 200
    assert first.data["action"] in range(8)
    assert len(first.data["state"]) == 17
    assert len(first.data["q_values"]) == 8
    assert 0.0 <= first.data["state"][16] <= 1.0  # acceptance ratio
    assert RLTransition.objects(student=user["student_id"]).count() == 1
    assert RLTransition.objects(done=False).count() == 1  # pending

    second = client.post("/api/v1/rl/action")
    assert second.status_code == 200
    assert RLTransition.objects(student=user["student_id"]).count() == 2

    closed = RLTransition.objects(done=True).first()
    assert closed is not None
    assert closed.reward == closed.reward  # finite (no NaN)
    assert RLTransition.objects(done=False).count() == 1  # new pending


def test_action_503_without_artifact(registered, monkeypatch):
    def _missing(_config=None, _path=None):
        raise FileNotFoundError("dqn.pt")

    monkeypatch.setattr("careermind_ml.rl.train.load_agent", _missing)
    views._agent = None
    client, _ = registered
    response = client.post("/api/v1/rl/action")
    assert response.status_code == 503
    assert "train-dqn" in response.data["detail"]
