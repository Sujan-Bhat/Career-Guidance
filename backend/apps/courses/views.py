from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView


class CourseListView(APIView):
    """Phase 3: course catalogue (supports RL difficulty-adjustment action)."""

    permission_classes = [AllowAny]

    def get(self, request):
        return Response({"detail": "Not implemented (Phase 3)"}, status=501)


class QuizAttemptView(APIView):
    """Phase 3: submit a quiz attempt (feeds QAP + skill assessments)."""

    permission_classes = [AllowAny]

    def post(self, request, quiz_id):
        return Response({"detail": "Not implemented (Phase 3)"}, status=501)
