"""EngagementSignal (paper Sec. V-A).

Binary indicator used in the RL reward (Eq. 3):
    E = 1  iff  (session duration >= 15 min)
             AND (interaction rate >= 3 actions/min)
             AND (quiz attempt rate >= 0.6)
"""

MIN_SESSION_MINUTES = 15
MIN_INTERACTIONS_PER_MIN = 3
MIN_QUIZ_ATTEMPT_RATE = 0.6


def engagement_signal(
    duration_minutes: float,
    interaction_count: int | None = None,
    quiz_attempt_rate: float | None = None,
    interaction_rate: float | None = None,
) -> int:
    """Return 1 if all three paper thresholds are met, else 0.

    `interaction_rate` (actions/min) may be supplied directly; otherwise it
    is derived as interaction_count / duration. `quiz_attempt_rate` is the
    fraction of presented quiz items attempted (paper Sec. V-A).
    """
    if not duration_minutes or duration_minutes <= 0:
        return 0
    if interaction_rate is None:
        interaction_rate = (interaction_count or 0) / duration_minutes
    return int(
        duration_minutes >= MIN_SESSION_MINUTES
        and interaction_rate >= MIN_INTERACTIONS_PER_MIN
        and (quiz_attempt_rate or 0.0) >= MIN_QUIZ_ATTEMPT_RATE
    )
