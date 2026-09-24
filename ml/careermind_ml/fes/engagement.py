"""EngagementSignal (paper Sec. V-A).

Binary indicator used in the RL reward (Eq. 3):
    E = 1  iff  (session duration >= 15 min)
             AND (interaction rate >= 3 actions/min)
             AND (quiz attempt rate >= 0.6)
"""

MIN_SESSION_MINUTES = 15
MIN_INTERACTIONS_PER_MIN = 3
MIN_QUIZ_ATTEMPT_RATE = 0.6


def engagement_signal(duration_minutes: float, interaction_count: int, quiz_attempt_rate: float) -> int:
    """Return 1 if all three thresholds are met, else 0."""
    raise NotImplementedError("Phase 2")
