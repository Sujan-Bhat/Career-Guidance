"""DQN environment + pre-training loop tests (Phase 6)."""
import numpy as np
import pytest

torch = pytest.importorskip("torch", reason="torch not installed")
gym = pytest.importorskip("gymnasium", reason="gymnasium not installed")

from simulator import StudentSimulator  # noqa: E402  (conftest adds data/simulator)

from careermind_ml.rl.dqn import DQNAgent  # noqa: E402
from careermind_ml.rl.environment import ACTION_NAMES, CareerGuidanceEnv  # noqa: E402
from careermind_ml.rl.train import train_dqn  # noqa: E402

FAST_CONFIG = {
    "state_dim": 17,
    "n_actions": 8,
    "steps_per_episode": 12,
    "max_episodes": 3,
    "batch_size": 4,
    "replay_buffer_size": 200,
    "target_update_steps": 5,
    "epsilon_start": 1.0,
    "epsilon_end": 0.1,
    "epsilon_decay_steps": 50,
    "learning_rate": 0.001,
    "random_state": 7,
    "log_every": 0,
    "reward_weights": {"alpha": 0.4, "beta": 0.3, "gamma": 0.1, "delta": 0.2},
}


@pytest.fixture()
def env():
    return CareerGuidanceEnv(StudentSimulator(seed=FAST_CONFIG["random_state"]), FAST_CONFIG)


def test_action_space_and_names():
    env = CareerGuidanceEnv(StudentSimulator(seed=0), FAST_CONFIG)
    assert env.action_space.n == 8
    assert len(ACTION_NAMES) == 8
    assert env.observation_space.shape == (17,)


def test_reset_returns_normalised_state(env):
    state, info = env.reset(seed=3)
    assert state.shape == (17,)
    assert state.dtype == np.float32
    assert np.isfinite(state).all()
    assert state.min() >= 0.0 and state.max() <= 1.0
    assert 0.0 <= state[16] <= 1.0  # acceptance ratio neutral 0.5
    assert isinstance(info, dict)


def test_step_shapes_reward_finite_and_truncation(env):
    env.reset(seed=3)
    for step in range(1, FAST_CONFIG["steps_per_episode"] + 1):
        state, reward, terminated, truncated, info = env.step(env.action_space.sample())
        assert state.shape == (17,)
        assert np.isfinite(reward)
        assert not terminated  # episodes end by truncation (fixed horizon)
        assert truncated == (step == FAST_CONFIG["steps_per_episode"])
        assert {"fes", "engagement", "ca"} <= set(info)
    # a fresh reset starts a new trajectory with a fresh seed history
    state, _ = env.reset(seed=4)
    assert state.shape == (17,)


def test_introduce_new_domain_shifts_affinity_mass(env):
    env.reset(seed=3)
    active_cat = env._pathway_category[env._active_pathway]
    before = env._affinity[active_cat]
    env.step(2)  # introduce_new_domain
    assert env._affinity[active_cat] == pytest.approx(before - 0.10, abs=1e-6) or env._affinity[active_cat] < before
    assert sum(env._affinity.values()) == pytest.approx(1.0, abs=1e-6)


def test_quiz_action_boosts_active_domain_skills(env):
    env.reset(seed=3)
    skills = env._pathway_skills[env._active_pathway]
    tracked = [s for s in skills if s in env._skill_scores]
    if not tracked:
        pytest.skip("active pathway skills not assessed for this student")
    before = {s: env._skill_scores[s] for s in tracked}
    env.step(7)  # request_self_assessment_quiz
    gained = [s for s in tracked if env._skill_scores[s] > before[s]]
    assert gained, "quiz action must raise active-domain skill scores"


def test_dqn_agent_train_step_and_target_sync():
    agent = DQNAgent({"target_update_steps": 1, "learning_rate": 0.001})
    rng = np.random.default_rng(0)
    batch = (
        rng.normal(size=(8, 17)).astype(np.float32),
        rng.integers(0, 8, size=8),
        rng.normal(size=8).astype(np.float32),
        rng.normal(size=(8, 17)).astype(np.float32),
        np.zeros(8, dtype=np.float32),
    )
    out = agent.train_step(batch)
    assert np.isfinite(out["loss"]) and np.isfinite(out["td_error"])
    # target_update_steps=1 -> target synced after the first gradient step
    for qp, tp in zip(agent.q_net.parameters(), agent.target_net.parameters()):
        assert np.allclose(qp.detach().numpy(), tp.detach().numpy())


def test_q_values_shape():
    agent = DQNAgent({})
    q = agent.q_values(np.zeros(17, dtype=np.float32))
    assert q.shape == (8,)
    assert agent.select_action(np.zeros(17, dtype=np.float32), epsilon=0.0) == int(q.argmax())


def test_train_dqn_smoke_saves_artifact(env, tmp_path):
    config = {**FAST_CONFIG, "artifact_path": str(tmp_path / "dqn.pt")}
    agent = DQNAgent(config)
    metrics = train_dqn(env, agent, config)

    assert metrics["episodes"] == FAST_CONFIG["max_episodes"]
    assert metrics["total_steps"] > 0
    assert np.isfinite(metrics["mean_reward_last50"])
    assert (tmp_path / "dqn.pt").exists()

    # artifact round-trips
    from careermind_ml.rl.train import load_agent

    loaded = load_agent(config, path=tmp_path / "dqn.pt")
    q = loaded.q_values(np.zeros(17, dtype=np.float32))
    assert q.shape == (8,)
