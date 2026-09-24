"""QNetwork shape tests (torch required — skipped if torch is absent)."""
import numpy as np
import pytest

torch = pytest.importorskip("torch", reason="torch not installed")

from careermind_ml.rl.dqn import DQNAgent, QNetwork  # noqa: E402


def test_qnetwork_forward_shape():
    net = QNetwork()
    out = net(torch.zeros(4, 17))
    assert out.shape == (4, 8)


def test_agent_epsilon_greedy_bounds():
    agent = DQNAgent(config={})
    state = np.zeros(17, dtype=np.float32)
    assert agent.select_action(state, epsilon=1.0) in range(8)
    assert agent.select_action(state, epsilon=0.0) in range(8)
