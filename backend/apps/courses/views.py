from datetime import datetime

from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from ..collector.models import BehaviourSession
from ..collector.services import get_active_session
from .models import Course, Quiz, QuizAttempt


class CourseListView(APIView):
    """Course catalogue (supports the RL difficulty-adjustment action)."""

    permission_classes = [AllowAny]

    def get(self, request):
        courses = Course.objects.order_by("code").limit(500)
        return Response(
            {
                "count": courses.count(),
                "courses": [
                    {
                        "code": course.code,
                        "title": course.title,
                        "difficulty": course.difficulty,
                        "skill_tags": course.skill_tags,
                        "pathway": course.pathway,
                    }
                    for course in courses
                ],
            }
        )


def _serialize_quiz(quiz: Quiz, include_questions: bool) -> dict:
    payload = {
        "quiz_id": str(quiz.pk),
        "title": quiz.title,
        "skill": quiz.skill,
        "course": quiz.course,
        "item_count": len(quiz.questions),
    }
    if include_questions:
        payload["questions"] = quiz.questions  # answers included for the taker (JWT)
    return payload


class QuizListView(APIView):
    """Self-assessment quizzes (seeded demos + LLM-generated). Public list
    without answers; detail below hands questions+answers to JWT users."""

    permission_classes = [AllowAny]

    def get(self, request):
        quizzes = Quiz.objects.order_by("skill", "title").limit(100)
        return Response(
            {"count": len(quizzes), "quizzes": [_serialize_quiz(q, include_questions=False) for q in quizzes]}
        )


class QuizDetailView(APIView):
    """Quiz questions with answers — JWT only (the client scores each item
    and posts attempts, which require an active tracked session)."""

    def get(self, request, quiz_id):
        quiz = Quiz.objects(pk=quiz_id).first()
        if quiz is None:
            return Response({"detail": "Quiz not found"}, status=404)
        return Response(_serialize_quiz(quiz, include_questions=True))


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
