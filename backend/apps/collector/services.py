"""Collector aggregate services (Phase 3).

Materialises the raw event stream of a live session into the session-level
aggregates the FES engine reads (the same schema the simulator seeds).
"""
from datetime import datetime

from .models import BehaviourEvent, BehaviourSession

RAPID_SWITCH_SECONDS = 30.0  # resource opened < 30s after the previous open


def get_active_session(student_id: str):
    return (
        BehaviourSession.objects(student=student_id, status="active")
        .order_by("-started_at")
        .first()
    )


def parse_timestamp(value) -> datetime:
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(str(value))
    except ValueError:
        return datetime.utcnow()


def recompute_session_aggregates(session: BehaviourSession) -> BehaviourSession:
    """One pass over the session's events -> FES-ready aggregates.

    Quiz aggregates come from QuizAttempt documents (the structured FR04
    endpoint is the source of truth); raw quiz_attempt *events* are stored but
    not double-counted here.
    """
    events = list(
        BehaviourEvent.objects(session=str(session.pk)).order_by("timestamp")
    )
    started = session.started_at
    last = events[-1].timestamp if events else (session.ended_at or started)

    tasks_started = sum(1 for e in events if e.type == "task_start")
    tasks_completed = sum(1 for e in events if e.type == "task_complete")
    interaction_count = max(len(events) - 1, 0)  # exclude the synthetic session_end event

    resource_visits = []
    open_at = None
    prev_open = None
    for event in events:
        if event.type == "resource_open":
            if open_at is not None:  # never closed -> close at the last known point
                resource_visits.append(
                    {
                        "type": (event.metadata or {}).get("resource_type", "article"),
                        "dwell_seconds": max(0.0, (event.timestamp - open_at).total_seconds()),
                        "idle_gap_seconds": 0.0,
                        "rapid_switch": prev_open is not None
                        and (event.timestamp - prev_open).total_seconds() < RAPID_SWITCH_SECONDS,
                    }
                )
            prev_open = event.timestamp
            open_at = event.timestamp
        elif event.type == "resource_close" and open_at is not None:
            resource_visits.append(
                {
                    "type": (event.metadata or {}).get("resource_type", "article"),
                    "dwell_seconds": max(0.0, (event.timestamp - open_at).total_seconds()),
                    "idle_gap_seconds": 0.0,
                    "rapid_switch": prev_open is not None
                    and prev_open != open_at
                    and (open_at - prev_open).total_seconds() < RAPID_SWITCH_SECONDS,
                }
            )
            open_at = None

    # quiz aggregates from structured attempts (FR04)
    from apps.courses.models import QuizAttempt

    attempts = list(QuizAttempt.objects(student=session.student).order_by("attempted_at"))
    session_attempts = []
    for attempt in attempts:
        ts = attempt.attempted_at
        if ts and started <= ts <= (session.ended_at or last):
            session_attempts.append(attempt)
    quiz_items = len(session_attempts)
    quiz_correct = sum(1 for a in session_attempts if a.correct)
    quiz_reattempts = sum(1 for a in session_attempts if a.is_reattempt)

    session.duration_minutes = max((last - started).total_seconds() / 60.0, 0.0)
    session.duration_seconds = int(session.duration_minutes * 60)
    session.date = started.date().isoformat()
    session.login_minute_of_day = started.hour * 60 + started.minute
    session.tasks_started = tasks_started
    session.tasks_completed = tasks_completed
    session.interaction_count = interaction_count
    session.resource_visits = resource_visits
    session.quiz_items = quiz_items
    session.quiz_items_correct = quiz_correct
    session.quiz_reattempts = quiz_reattempts
    session.ended_at = session.ended_at or last
    session.status = "completed"
    session.save()
    return session
