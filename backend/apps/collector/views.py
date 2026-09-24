from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView


class SessionStartView(APIView):
    """Phase 3: open a behavioural session; returns session id."""

    permission_classes = [AllowAny]

    def post(self, request):
        return Response({"detail": "Not implemented (Phase 3)"}, status=501)


class SessionEndView(APIView):
    """Phase 3: close a session; enqueues Celery FES computation task."""

    permission_classes = [AllowAny]

    def post(self, request, session_id):
        return Response({"detail": "Not implemented (Phase 3)"}, status=501)


class EventBatchView(APIView):
    """Phase 3: ingest batched events from the frontend tracking SDK
    (flushed every 20 events or 10 seconds)."""

    permission_classes = [AllowAny]

    def post(self, request):
        return Response({"detail": "Not implemented (Phase 3)"}, status=501)
