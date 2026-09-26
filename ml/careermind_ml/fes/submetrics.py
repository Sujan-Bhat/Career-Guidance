"""FES sub-metrics (paper Sec. V-A). Concrete implementations (Phase 2).

Each function takes session-scoped behavioural aggregates (from the
Behavioural Data Collector / seeded simulator data) and returns a sub-metric
in [0, 1], or None when the metric is undefined for that session.

Missing-value convention (paper Sec. V-A): a sub-metric with a zero
denominator is treated as missing for that session and excluded PAIRWISE
from the Eq. 2 correlation computation — the session is not dropped.
"""
import math
from typing import Optional

# LRDS: type-specific dwell-time thresholds (seconds) — mirrored in ml/configs/fes.yaml
DEFAULT_LRDS_THRESHOLDS = {"video": 300, "article": 180, "exercise": 240, "interactive": 240}

# DFET heuristics (paper Sec. V-A): rapid resource-switching / extended idling
DFET_RAPID_SWITCH_SECONDS = 30.0
DFET_IDLE_SECONDS = 120.0


def task_completion_rate(tasks_started: int, tasks_completed: int) -> Optional[float]:
    """TCR: ratio of tasks completed to tasks started within a session.

    Grounded in Liu et al. [16]: completion behaviour is the strongest single
    predictor of academic performance.
    """
    if tasks_started is None or tasks_started <= 0:
        return None
    return min(1.0, tasks_completed / tasks_started)


def session_consistency_index(
    login_minutes: list[int],
    session_durations: list[float],
) -> Optional[float]:
    """SCI: regularity of daily login times and session durations (14-day window).

    SCI = 1 - 0.5 * (circular_std(login_times) + CV(durations)), both terms
    normalised to [0, 1]. Login regularity uses the circular standard
    deviation on the 24h clock (so 23:00 vs 01:00 counts as regular).
    Informed by [16] and the active-learner profile of Jo and Huh [17].

    Args:
        login_minutes: minute-of-day login times over the window.
        session_durations: minutes, same window.
    Returns:
        None if fewer than 2 sessions in the window.
    """
    if login_minutes is None or session_durations is None:
        return None
    if len(login_minutes) < 2 or len(session_durations) < 2:
        return None

    # circular dispersion of login times (24h circle)
    angles = [2.0 * math.pi * m / 1440.0 for m in login_minutes]
    sin_sum = sum(math.sin(a) for a in angles)
    cos_sum = sum(math.cos(a) for a in angles)
    resultant = math.sqrt(sin_sum**2 + cos_sum**2) / len(angles)
    resultant = max(resultant, 1e-12)
    circ_std = math.sqrt(max(0.0, -2.0 * math.log(resultant)))  # radians
    login_norm = min(1.0, circ_std / math.pi)

    # coefficient of variation of durations
    mean_d = sum(session_durations) / len(session_durations)
    if mean_d <= 0:
        return None
    variance = sum((d - mean_d) ** 2 for d in session_durations) / len(session_durations)
    cv = math.sqrt(variance) / mean_d
    duration_norm = min(1.0, cv)

    return 1.0 - 0.5 * (login_norm + duration_norm)


def distraction_free_engagement_time(
    resource_visits: list[dict],
    duration_minutes: float,
    rapid_switch_threshold_seconds: float = DFET_RAPID_SWITCH_SECONDS,
    idle_threshold_seconds: float = DFET_IDLE_SECONDS,
) -> Optional[float]:
    """DFET: proportion of session time in sustained, single-resource engagement.

    Sustained time = dwell of visits with no rapid resource-switching and no
    extended idling (idle gap <= 120s). Rapid switches (gaps < 30s) break
    sustained engagement. Note: adversarial gaming (resource open but not
    engaged) is a documented limitation (paper Sec. VII #2).
    """
    if not resource_visits or not duration_minutes or duration_minutes <= 0:
        return None
    total_seconds = duration_minutes * 60.0
    sustained = sum(
        v["dwell_seconds"]
        for v in resource_visits
        if not v.get("rapid_switch") and v.get("idle_gap_seconds", 0.0) <= idle_threshold_seconds
    )
    return min(1.0, sustained / total_seconds)


def quiz_attempt_persistence(
    quiz_items: int, quiz_items_correct: int, quiz_reattempts: int
) -> Optional[float]:
    """QAP: proportion of incorrectly answered items re-attempted at least
    once — motivated, goal-directed learning.

    Missing when there are no incorrect items: the student had nothing to
    re-attempt, so persistence is undefined for that session (excluded
    pairwise, per the paper's missing-data rule).
    """
    if quiz_items is None:
        return None
    incorrect = quiz_items - (quiz_items_correct or 0)
    if incorrect <= 0:
        return None
    return min(1.0, quiz_reattempts / incorrect)


def learning_resource_depth_score(
    resource_visits: list[dict],
    thresholds: Optional[dict] = None,
) -> Optional[float]:
    """LRDS: proportion of accessed resources whose dwell time exceeds a
    type-specific engagement threshold — depth rather than superficial access."""
    if not resource_visits:
        return None
    th = thresholds or DEFAULT_LRDS_THRESHOLDS
    deep = sum(1 for v in resource_visits if v["dwell_seconds"] >= th.get(v["type"], 180))
    return deep / len(resource_visits)
