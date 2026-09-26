from datetime import datetime

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import BehaviourEvent, BehaviourSession
from .services import get_active_session, parse_timestamp

MAX_BATCH_SIZE = 200


class SessionStartView(APIView):
    """Open a behavioural session for the authenticated student (FR02)."""

    def post(self, request):
        session = BehaviourSession(
            student=request.user.student_id,
            status="active",
            started_at=datetime.utcnow(),
            source="collector",
        ).save()
        return Response(
            {"session_id": str(session.pk), "started_at": session.started_at},
            status=status.HTTP_201_CREATED,
        )


class EventBatchView(APIView):
    """Ingest a batch of behavioural events from the frontend tracking SDK
    (flushed every 20 events or 10 seconds). The server stamps ownership and
    resolves the student's active session."""

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

        docs = []
        for event in events:
            if not isinstance(event, dict) or not event.get("type"):
                continue
            docs.append(
                BehaviourEvent(
                    session=str(session.pk),
                    student=request.user.student_id,
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

        return Response({"stored": len(docs), "session_id": str(session.pk)})


class SessionEndView(APIView):
    """Close a session; enqueues the Celery FES computation task (FR03)."""

    def post(self, request, session_id):
        session = BehaviourSession.objects(pk=session_id).first()
        if session is None or session.student != request.user.student_id:
            return Response({"detail": "Session not found"}, status=404)
        if session.status == "completed":
            return Response({"detail": "Session already completed"}, status=409)

        session.status = "completed"
        session.ended_at = datetime.utcnow()
        session.save()

        from apps.fes.tasks import compute_session_fes

        compute_session_fes.delay(str(session.pk))
        return Response(
            {"session_id": str(session.pk), "ended_at": session.ended_at, "fes_queued": True}
        )
