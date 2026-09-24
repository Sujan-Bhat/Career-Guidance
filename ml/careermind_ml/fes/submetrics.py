"""FES sub-metrics (paper Sec. V-A).

Each function takes session-scoped behavioural aggregates (from the
Behavioural Data Collector) and returns a sub-metric in [0, 1].
"""
from typing import Optional


def task_completion_rate(tasks_started: int, tasks_completed: int) -> float:
    """TCR: ratio of tasks completed to tasks started within a session.

    Grounded in Liu et al. [16]: completion behaviour is the strongest single
    predictor of academic performance.
    """
    raise NotImplementedError("Phase 2")


def session_consistency_index(login_times: list, session_durations: list, window_days: int = 14) -> float:
    """SCI: regularity of daily login times and session durations over a
    14-day window (informed by [16] and the active-learner profile of
    Jo and Huh [17]).

    Phase 2 implementation: 1 - normalised dispersion (e.g., circular std of
    login times + coefficient of variation of durations).
    """
    raise NotImplementedError("Phase 2")


def distraction_free_engagement_time(
    total_seconds: int,
    sustained_segments: list[dict],
    rapid_switch_threshold_seconds: float = 30.0,
    idle_threshold_seconds: float = 120.0,
) -> float:
    """DFET: proportion of session time in sustained, single-resource engagement.

    Sustained engagement = segments with no rapid resource-switching (< 30 s
    per resource) and no extended idling (> 120 s without interaction).
    Adversarial gaming (leaving a resource open without engaging) is an open
    limitation (paper Sec. VII).
    """
    raise NotImplementedError("Phase 2")


def quiz_attempt_persistence(items_incorrect: list, items_reattempted: list) -> float:
    """QAP: proportion of incorrectly answered items re-attempted at least
    once — motivated, goal-directed learning."""
    raise NotImplementedError("Phase 2")


def learning_resource_depth_score(resource_dwell_seconds: dict, type_thresholds: Optional[dict] = None) -> float:
    """LRDS: proportion of accessed resources whose dwell time exceeds a
    type-specific engagement threshold (video/article/exercise/interactive)
    — depth rather than superficial access."""
    raise NotImplementedError("Phase 2")
