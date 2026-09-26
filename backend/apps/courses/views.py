from datetime import datetime

from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from ..collector.models import BehaviourSession
from ..collector.services import get_active_session
from .models import Course, Quiz, QuizAttempt


class CourseListView(APIView):
    """Phase 4/8: course catalogue (supports RL difficulty-adjustment action)."""

    permission_classes = [AllowAny]

    def get(self, request):
        return Response({"detail": "Not implemented (Phase 4/8)"}, status=501)


class QuizAttemptView(APIView):
    """FR04: submit one quiz item attempt (JWT-authenticated).

    Persists a structured QuizAttempt (source of truth for the session's quiz
    aggregates -> QAP) and updates the student's active session counters,
    including re-attempt detection for previously-incorrect items.
    """

    def post(self, request, quiz_id):
        quiz = Quiz.objects(pk=quiz_id).first()
        item_id = request.data.get("item_id")
        correct = request.data.get("correct")
        if quiz is None or not item_id or not isinstance(correct, bool):
            return Response(
                {"detail": "Requires quiz_id (path), item_id, correct (bool)"}, status=400
            )

        session = get_active_session(request.user.student_id)
        if session is None:
            return Response({"detail": "No active session — call /sessions/start first"}, status=400)

        is_reattempt = QuizAttempt.objects(
            quiz=str(quiz.pk), student=request.user.student_id, item_id=item_id, correct=False
        ).first() is not None

        QuizAttempt(
            quiz=str(quiz.pk),
            student=request.user.student_id,
            item_id=item_id,
            correct=correct,
            is_reattempt=is_reattempt,
            attempted_at=datetime.utcnow(),
        ).save()

        session.quiz_items = (session.quiz_items or 0) + 1
        session.quiz_items_correct = (session.quiz_items_correct or 0) + (1 if correct else 0)
        session.quiz_reattempts = (session.quiz_reattempts or 0) + (1 if is_reattempt else 0)
        session.save()

        return Response(
            {
                "quiz": str(quiz.pk),
                "item_id": item_id,
                "correct": correct,
                "is_reattempt": is_reattempt,
            },
            status=status.HTTP_201_CREATED,
        )
