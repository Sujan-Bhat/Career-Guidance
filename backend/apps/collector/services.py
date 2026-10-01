"""Collector aggregate services (Phase 3).

Materialises the raw event stream of a live session into the session-level
aggregates the FES engine reads (the same schema the simulator seeds).
"""
from datetime import datetime

from .models import BehaviourEvent, BehaviourSession

RAPID_SWITCH_SECONDS = 30.0  # resource opened < 30s after the previous close


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
        text = str(value)
        # Python < 3.11 rejects the ISO "Z" suffix; normalise before parsing
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        return datetime.fromisoformat(text)
    except ValueError:
        return datetime.utcnow()


def _gap_seconds(from_ts: datetime, to_ts: datetime) -> float:
    return max(0.0, (to_ts - from_ts).total_seconds())


def recompute_session_aggregates(session: BehaviourSession) -> BehaviourSession:
    """One pass over the session's events -> FES-ready aggregates.

    Quiz aggregates come from QuizAttempt documents (the structured FR04
    endpoint is the source of truth); raw quiz_attempt *events* are stored but
    not double-counted here.

    Visit signals (fixes over the previous version, which hardcoded
    idle_gap_seconds=0.0 and measured open->open gaps so neither DFET
    heuristic could ever fire on live data):
      * idle_gap_seconds — seconds the student spent idle (idle_start..idle_end
        pairs) WITHIN the visit, from the SDK's visibility-change events. Idle
        intervals are clamped to the visit window so an idle_start that fired
        before the resource was opened (or before it closed) can never make
        the gap exceed dwell_seconds;
      * rapid_switch     — the visit was opened < 30s after the previous
        resource_close (genuine switching, not dwell-contaminated).

    interaction_count excludes session_start/session_end lifecycle markers so
    it stays comparable between simulator streams (which emit them) and live
    SDK streams (which do not).
    """
    events = list(
        BehaviourEvent.objects(session=str(session.pk)).order_by("timestamp")
    )
    started = session.started_at
    last = events[-1].timestamp if events else (session.ended_at or started)

    tasks_started = sum(1 for e in events if e.type == "task_start")
    tasks_completed = sum(1 for e in events if e.type == "task_complete")
    # session_start/session_end are stream bookkeeping, not student behaviour:
    # count neither (the old trailing-only discount missed session_start, so
    # every simulator session overcounted interactions by one)
    lifecycle = {"session_start", "session_end"}
    interaction_count = sum(1 for e in events if e.type not in lifecycle)

    resource_visits: list[dict] = []
    open_at: datetime | None = None
    visit_type = "article"
    visit_rapid = False
    visit_idle_seconds = 0.0
    idle_since: datetime | None = None
    prev_close: datetime | None = None

    for event in events:
        etype = event.type
        if etype == "resource_open":
            if open_at is not None:  # never closed -> close at the new open
                if idle_since is not None:
                    # pending idle belongs to the visit that is closing
                    visit_idle_seconds += _gap_seconds(idle_since, event.timestamp)
                    idle_since = None
                resource_visits.append(
                    {
                        "type": visit_type,
                        "dwell_seconds": _gap_seconds(open_at, event.timestamp),
                        "idle_gap_seconds": min(visit_idle_seconds, _gap_seconds(open_at, event.timestamp)),
                        "rapid_switch": visit_rapid,
                    }
                )
            visit_rapid = (
                prev_close is not None
                and _gap_seconds(prev_close, event.timestamp) < RAPID_SWITCH_SECONDS
            )
            open_at = event.timestamp
            visit_type = (event.metadata or {}).get("resource_type", "article")
            visit_idle_seconds = 0.0
            # an idle interval started before this visit is not part of it
            idle_since = None
        elif etype == "resource_close" and open_at is not None:
            if idle_since is not None:
                # unclosed idle: count only the part inside the visit window
                visit_idle_seconds += _gap_seconds(max(idle_since, open_at), event.timestamp)
                idle_since = None
            dwell = _gap_seconds(open_at, event.timestamp)
            resource_visits.append(
                {
                    "type": visit_type,
                    "dwell_seconds": dwell,
                    "idle_gap_seconds": min(visit_idle_seconds, dwell),
                    "rapid_switch": visit_rapid,
                }
            )
            open_at = None
            idle_since = None
            prev_close = event.timestamp
        elif etype == "idle_start" and idle_since is None:
            idle_since = event.timestamp
        elif etype == "idle_end" and idle_since is not None:
            visit_idle_seconds += _gap_seconds(idle_since, event.timestamp)
            idle_since = None

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
