"""ReplayBuffer tests (numpy-only — no torch required)."""
import numpy as np

from careermind_ml.rl.buffer import ReplayBuffer


def test_push_and_sample():
    buf = ReplayBuffer(capacity=100)
    for i in range(10):
        buf.push(np.full(17, i, dtype=np.float32), action=i % 8, reward=float(i),
                 next_state=np.full(17, i + 1, dtype=np.float32), done=(i == 9))
    assert len(buf) == 10
    states, actions, rewards, next_states, dones = buf.sample(batch_size=4)
    assert states.shape == (4, 17)
    assert actions.shape == (4,)
    assert dones.max() <= 1.0


def test_capacity_wraparound():
    buf = ReplayBuffer(capacity=5)
    for i in range(8):
        buf.push(np.zeros(17, dtype=np.float32), 0, float(i), np.zeros(17, dtype=np.float32), False)
    assert len(buf) == 5
    assert buf.pos == 3
