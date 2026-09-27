"""Student-simulator MDP environment (paper Sec. V-C).

Gymnasium-style environment wrapping the synthetic student simulator
(data/simulator) — used for DQN pre-training before online deployment.

State (17-dim, all components normalised to ~[0, 1]):
    [0:5]   last five session FES values (padded with 0)
    [5:10]  five key subject grades / 100 (padded with population 0.7)
    [10:15] top five skill-assessment scores / 100 (padded with 0)
    [15]    active career-pathway identifier (index / 17)
    [16]    recommendation acceptance/rejection ratio over last ten
            sessions (0.5 neutral before any decisions)

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
    dFES: change in mean of last-five-session FES window
    dSkill: change in mean skill score of the active pathway's prerequisite
        skills
    E: binary EngagementSignal (see careermind_ml.fes.engagement)
    CA: CareerAlignment — affinity mass on the active pathway's category

One `step` = one simulated session under the post-intervention latents.
Session FES uses the paper's five sub-metrics with uniform population
weights (per-student Eq. 2 calibration needs >= 8 sessions, which the
short pre-training episodes do not reach).
"""
import gymnasium as gym
import numpy as np
from gymnasium import spaces

from careermind_ml.fes.engagement import engagement_signal
from careermind_ml.fes.submetrics import (
    distraction_free_engagement_time,
    learning_resource_depth_score,
    quiz_attempt_persistence,
    session_consistency_index,
    task_completion_rate,
)
from careermind_ml.recommender.features import CAREER_CATEGORIES, GRADE_SUBJECTS

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

_LATENT_CLIP = (0.05, 0.98)
_MAX_PATHWAY_INDEX = 17  # 18 pathways -> index / 17 in [0, 1]


class CareerGuidanceEnv(gym.Env):
    """One environment instance = one (simulated) student trajectory."""

    metadata = {"render_modes": []}

    def __init__(self, simulator, config: dict):
        super().__init__()
        self.simulator = simulator
        self.config = config or {}
        self.rng = np.random.default_rng(self.config.get("random_state"))
        self.steps_per_episode = int(self.config.get("steps_per_episode", 60))
        self.weights = {k: float(v) for k, v in (self.config.get("reward_weights") or {}).items()}
        self.observation_space = spaces.Box(low=0.0, high=1.0, shape=(17,), dtype=np.float32)
        self.action_space = spaces.Discrete(8)

        careers = getattr(simulator, "_careers", []) or []
        self._pathway_ids = sorted(c["id"] for c in careers)
        self._pathway_index = {pid: i for i, pid in enumerate(self._pathway_ids)}
        self._pathway_category = {c["id"]: c["category"] for c in careers}
        self._pathway_skills = {c["id"]: [p["skill"] for p in c.get("prerequisites", [])] for c in careers}

        # episode state
        self._student = None
        self._affinity: dict = {}
        self._fes_history: list[float] = []
        self._login_minutes: list[int] = []
        self._durations: list[float] = []
        self._grades: dict = {}
        self._skill_scores: dict = {}
        self._active_pathway = self._pathway_ids[0] if self._pathway_ids else "c01"
        self._acceptances: list[float] = []
        self._step_count = 0

    # ------------------------------------------------------------------ helpers

    def _session_fes(self, session: dict) -> float:
        """Uniform-weight mean of the available paper sub-metrics ([0, 1])."""
        parts = [
            m
            for m in (
                task_completion_rate(session.get("tasks_started"), session.get("tasks_completed")),
                session_consistency_index(self._login_minutes, self._durations),
                distraction_free_engagement_time(session.get("resource_visits"), session.get("duration_minutes")),
                quiz_attempt_persistence(
                    session.get("quiz_items"), session.get("quiz_items_correct"), session.get("quiz_reattempts")
                ),
                learning_resource_depth_score(session.get("resource_visits")),
            )
            if m is not None
        ]
        return float(np.mean(parts)) if parts else 0.5

    def _apply_action(self, action: int) -> bool:
        """Policy action -> latent/affinity intervention. Returns True for
        the self-assessment quiz (which also boosts skill scores)."""
        student = self._student
        if action == 1:  # escalate
            student["motivation"] = float(np.clip(student["motivation"] + 0.04, *_LATENT_CLIP))
        elif action == 2:  # introduce_new_domain: dilute active category mass
            active_cat = self._pathway_category.get(self._active_pathway, CAREER_CATEGORIES[0])
            others = [c for c in CAREER_CATEGORIES if c != active_cat]
            target = others[int(self.rng.integers(0, len(others)))]
            self._affinity[active_cat] = max(0.01, self._affinity.get(active_cat, 0.0) - 0.10)
            self._affinity[target] = self._affinity.get(target, 0.0) + 0.10
            total = sum(self._affinity.values()) or 1.0
            self._affinity = {k: v / total for k, v in self._affinity.items()}
        elif action == 3:  # productivity intervention
            student["focus_tendency"] = float(np.clip(student["focus_tendency"] + 0.05, *_LATENT_CLIP))
        elif action == 4:  # difficulty up (growth)
            student["ability"] = float(np.clip(student["ability"] + 0.03, *_LATENT_CLIP))
        elif action == 5:  # difficulty down (relief)
            student["motivation"] = float(np.clip(student["motivation"] + 0.03, *_LATENT_CLIP))
            student["focus_tendency"] = float(np.clip(student["focus_tendency"] + 0.02, *_LATENT_CLIP))
        elif action == 6:  # peer comparison
            student["motivation"] = float(np.clip(student["motivation"] + 0.04, *_LATENT_CLIP))
            student["focus_tendency"] = float(np.clip(student["focus_tendency"] - 0.01, *_LATENT_CLIP))
        elif action == 7:  # self-assessment quiz
            student["focus_tendency"] = float(np.clip(student["focus_tendency"] + 0.02, *_LATENT_CLIP))
            return True
        return False

    def _build_state(self) -> np.ndarray:
        """Assemble the 17-dim state vector from simulator state."""
        recent = self._fes_history[-5:]
        fes_part = (recent + [0.0] * (5 - len(recent)))  # already [0, 1]

        grade_part = [
            (self._grades.get(subject) or 70.0) / 100.0 for subject in GRADE_SUBJECTS
        ]

        top_skills = sorted(self._skill_scores.values(), reverse=True)[:5]
        skill_part = [s / 100.0 for s in top_skills] + [0.0] * (5 - len(top_skills))

        pathway_index = self._pathway_index.get(self._active_pathway, 0)
        acceptance = float(np.mean(self._acceptances)) if self._acceptances else 0.5

        state = np.asarray(
            fes_part + grade_part + skill_part + [pathway_index / _MAX_PATHWAY_INDEX, acceptance],
            dtype=np.float32,
        )
        assert state.shape == (17,)
        return state

    def _career_alignment(self) -> float:
        active_cat = self._pathway_category.get(self._active_pathway, CAREER_CATEGORIES[0])
        return float(np.clip(self._affinity.get(active_cat, 0.0), 0.0, 1.0))

    # ------------------------------------------------------------------ gym API

    def reset(self, *, seed=None, options=None):
        if seed is not None:
            self.rng = np.random.default_rng(seed)
        super().reset(seed=seed)

        self._student = self.simulator.generate_students(1)[0]
        self._affinity = dict(self._student["domain_affinity"])

        seed_sessions = self.simulator.generate_sessions(self._student, n_sessions=5)
        outcomes = self.simulator.generate_outcomes(self._student, seed_sessions)
        self._grades = dict(outcomes.get("grades") or {})
        self._skill_scores = dict(outcomes.get("skill_scores") or {})
        self._active_pathway = outcomes.get("career_pathway_id") or (self._pathway_ids[0] if self._pathway_ids else "c01")

        self._login_minutes = [int(s["login_minute_of_day"]) for s in seed_sessions]
        self._durations = [float(s["duration_minutes"]) for s in seed_sessions]
        self._fes_history = [self._session_fes(s) for s in seed_sessions]
        self._acceptances = []
        self._step_count = 0

        return self._build_state(), {}

    def step(self, action):
        action = int(action)
        quiz_action = self._apply_action(action)
        active_skills = self._pathway_skills.get(self._active_pathway, [])

        def domain_skill_mean() -> float:
            tracked = [self._skill_scores[s] for s in active_skills if s in self._skill_scores]
            return float(np.mean(tracked)) if tracked else 0.0

        prev_fes_window = self._fes_history[-5:]
        prev_skill_mean = domain_skill_mean()

        # advance one session under the post-intervention latents
        session = self.simulator.generate_sessions(self._student, n_sessions=1)[0]
        self._login_minutes.append(int(session["login_minute_of_day"]))
        self._durations.append(float(session["duration_minutes"]))
        session_fes = self._session_fes(session)
        self._fes_history.append(session_fes)

        # skill/grade drift (the quiz action accelerates skill growth)
        ability = self._student["ability"]
        for skill in self._skill_scores:
            boost = 2.5 if (quiz_action and skill in active_skills) else 0.0
            self._skill_scores[skill] = float(
                np.clip(self._skill_scores[skill] + 0.4 + 1.5 * ability + boost + self.rng.normal(0, 0.8), 0, 100)
            )
        for subject in self._grades:
            self._grades[subject] = float(np.clip(self._grades[subject] + 0.3 * ability + self.rng.normal(0, 1.0), 0, 100))

        new_fes_window = self._fes_history[-5:]
        new_skill_mean = domain_skill_mean()

        # Eq. 3 components
        dfes = float(np.mean(new_fes_window) - np.mean(prev_fes_window))
        dskill = (new_skill_mean - prev_skill_mean) / 100.0
        duration = float(session.get("duration_minutes") or 0.0)
        interactions = int(session.get("interaction_count") or 0)
        engagement = engagement_signal(
            duration,
            interaction_count=interactions,
            quiz_attempt_rate=min(1.0, (session.get("quiz_items") or 0) / 5.0),
            interaction_rate=(interactions / duration) if duration > 0 else None,
        )
        ca = self._career_alignment()

        # simulated acceptance of the current guidance (drives state[16])
        p_accept = float(np.clip(0.15 + 0.6 * session_fes + 0.6 * (ca - 1.0 / len(CAREER_CATEGORIES)), 0.0, 1.0))
        self._acceptances.append(1.0 if self.rng.random() < p_accept else 0.0)

        reward = (
            self.weights.get("alpha", 0.4) * dfes
            + self.weights.get("beta", 0.3) * dskill
            + self.weights.get("gamma", 0.1) * engagement
            + self.weights.get("delta", 0.2) * ca
        )

        self._step_count += 1
        truncated = self._step_count >= self.steps_per_episode
        info = {"fes": session_fes, "engagement": engagement, "ca": ca, "d_fes": dfes, "d_skill": dskill}
        return self._build_state(), float(reward), False, truncated, info
