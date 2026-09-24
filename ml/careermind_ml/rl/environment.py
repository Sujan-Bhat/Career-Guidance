"""Student-simulator MDP environment (paper Sec. V-C).

Gymnasium-style environment wrapping the synthetic student simulator
(data/simulator) — used for DQN pre-training before online deployment.

State (17-dim):
    [0:5]   last five session FES values
    [5:10]  five key subject grades
    [10:15] top five skill-assessment scores
    [15]    active career-pathway identifier (scalar)
    [16]    recommendation acceptance/rejection ratio over last ten sessions

Actions (8):
    0 maintain_current_pathway
    1 escalate_current_pathway
    2 introduce_new_domain
    3 trigger_productivity_intervention
    4 adjust_difficulty_up
    5 adjust_difficulty_down
    6 provide_peer_comparison
    7 request_self_assessment_quiz

Reward (Eq. 3): R = alpha*dFES + beta*dSkill + gamma*E + delta*CA
    dFES: weekly change in average FES
    dSkill: change in skill-assessment scores within the recommended domain
    E: binary EngagementSignal (see careermind_ml.fes.engagement)
    CA: CareerAlignment — consistency of recent course completions with the
        recommended pathway
"""
import gymnasium as gym
import numpy as np
from gymnasium import spaces

ACTION_NAMES = [
    "maintain_current_pathway",
    "escalate_current_pathway",
    "introduce_new_domain",
    "trigger_productivity_intervention",
    "adjust_difficulty_up",
    "adjust_difficulty_down",
    "provide_peer_comparison",
    "request_self_assessment_quiz",
]


class CareerGuidanceEnv(gym.Env):
    """One environment instance = one (simulated) student trajectory."""

    def __init__(self, simulator, config: dict):
        super().__init__()
        self.simulator = simulator
        self.config = config
        self.observation_space = spaces.Box(low=0.0, high=np.inf, shape=(17,), dtype=np.float32)
        self.action_space = spaces.Discrete(8)

    def _build_state(self) -> np.ndarray:
        """Assemble the 17-dim state vector from simulator state."""
        raise NotImplementedError("Phase 6")

    def _compute_reward(self, prev_state, action, next_state) -> float:
        """Eq. 3 with weights alpha/beta/gamma/delta from config (ml/configs/dqn.yaml)."""
        raise NotImplementedError("Phase 6")

    def reset(self, *, seed=None, options=None):
        raise NotImplementedError("Phase 6")

    def step(self, action):
        raise NotImplementedError("Phase 6")
