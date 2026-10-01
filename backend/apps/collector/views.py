from datetime import datetime

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import BehaviourEvent, BehaviourSession
from .services import get_active_session, parse_timestamp


def _fes_task():
    """Lazy import: avoids a circular import with apps.fes at module load."""
    from apps.fes.tasks import compute_session_fes

    return compute_session_fes

MAX_BATCH_SIZE = 200


def _ingest_events(session: BehaviourSession, student_id: str, events) -> list[BehaviourEvent]:
    """Validate + insert an event batch for an ACTIVE session; returns the
    inserted docs. Raises ValueError when the session is already completed —
    late writes would mutate aggregates that FES has already computed."""
    if session.status != "active":
        raise ValueError("completed")
    docs = []
    for event in events:
        if not isinstance(event, dict) or not event.get("type"):
            continue
        docs.append(
            BehaviourEvent(
                session=str(session.pk),
                student=student_id,
                type=event["type"],
                resource_id=event.get("resource_id"),
                metadata=event.get("metadata") or {},
                timestamp=parse_timestamp(event.get("timestamp")),
            )
        )
    if docs:
        BehaviourEvent.objects.insert(docs)
        session.interaction_count = (session.interaction_count or 0) + len(docs)
        session.save()
    return docs


class SessionStartView(APIView):
    """Open a behavioural session for the authenticated student (FR02).

    Single-session invariant: a new start force-completes the student's
    previous active session(s) first. Duplicate client starts (React
    StrictMode double-mount, retried requests, two tabs) previously left the
    losers open forever as orphans: event batches resolve to the newest
    active session, so the orphan's events were lost to FES and the student's
    dashboard stayed empty (no completed session -> no FESScore row).
    """

    def post(self, request):
        now = datetime.utcnow()
        for stale in BehaviourSession.objects(student=request.user.student_id, status="active"):
            stale.status = "completed"
            stale.ended_at = now
            stale.save()
            _fes_task().delay(str(stale.pk))  # late aggregates from its events

        session = BehaviourSession(
            student=request.user.student_id,
            status="active",
            started_at=now,
            source="collector",
        ).save()
        return Response(
            {"session_id": str(session.pk), "started_at": session.started_at},
            status=status.HTTP_201_CREATED,
        )


class EventBatchView(APIView):
    """Ingest a batch of behavioural events from the frontend tracking SDK
    (flushed every 20 events or 10 seconds). The server stamps ownership and
    resolves the student's active session. Batches for completed sessions are
    rejected with 409 so late unload writes cannot corrupt FES aggregates."""

    def post(self, request):
        events = request.data.get("events")
        if not isinstance(events, list) or not events:
            return Response({"detail": "Body must be {events: [...]}"}, status=400)
        if len(events) > MAX_BATCH_SIZE:
            return Response({"detail": f"Max {MAX_BATCH_SIZE} events per batch"}, status=400)

        session = (
            BehaviourSession.objects(pk=request.data.get("session_id")).first()
            if request.data.get("session_id")
            else get_active_session(request.user.student_id)
        )
        if session is None or session.student != request.user.student_id:
            return Response({"detail": "No active session — call /sessions/start first"}, status=400)

        try:
            docs = _ingest_events(session, request.user.student_id, events)
        except ValueError:
            return Response(
                {"detail": "Session already completed — events not accepted"}, status=409
            )

        return Response({"stored": len(docs), "session_id": str(session.pk)})


class SessionEndView(APIView):
    """Close a session; enqueues the Celery FES computation task (FR03).

    Accepts an optional final event batch in the body ({events: [...]}) — the
    tracking SDK sends its tail events together with the session end in one
    keepalive request so they survive page unload."""

    def post(self, request, session_id):
        session = BehaviourSession.objects(pk=session_id).first()
        if session is None or session.student != request.user.student_id:
            return Response({"detail": "Session not found"}, status=404)
        if session.status == "completed":
            return Response({"detail": "Session already completed"}, status=409)

        # final batch first, so recompute_session_aggregates sees it
        events = request.data.get("events")
        if isinstance(events, list) and events:
            if len(events) > MAX_BATCH_SIZE:
                return Response(
                    {"detail": f"Max {MAX_BATCH_SIZE} events per batch"}, status=400
                )
            _ingest_events(session, request.user.student_id, events)
            session.reload()

        session.status = "completed"
        session.ended_at = datetime.utcnow()
        session.save()

        _fes_task().delay(str(session.pk))
        return Response(
            {"session_id": str(session.pk), "ended_at": session.ended_at, "fes_queued": True}
        )
