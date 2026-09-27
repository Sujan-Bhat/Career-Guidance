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
    min_session_minutes: float | None = None,
    min_interactions_per_min: float | None = None,
    min_quiz_attempt_rate: float | None = None,
) -> int:
    """Return 1 if all three paper thresholds are met, else 0.

    `interaction_rate` (actions/min) may be supplied directly; otherwise it
    is derived as interaction_count / duration. `quiz_attempt_rate` is the
    fraction of presented quiz items attempted (paper Sec. V-A). Threshold
    overrides exist for the sensitivity sweep (paper Sec. VIII #4) and
    default to the paper's constants."""
    if not duration_minutes or duration_minutes <= 0:
        return 0
    if interaction_rate is None:
        interaction_rate = (interaction_count or 0) / duration_minutes
    return int(
        duration_minutes >= (min_session_minutes if min_session_minutes is not None else MIN_SESSION_MINUTES)
        and interaction_rate
        >= (min_interactions_per_min if min_interactions_per_min is not None else MIN_INTERACTIONS_PER_MIN)
        and (quiz_attempt_rate or 0.0)
        >= (min_quiz_attempt_rate if min_quiz_attempt_rate is not None else MIN_QUIZ_ATTEMPT_RATE)
    )
