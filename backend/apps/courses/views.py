import re
from datetime import datetime
import os
import requests
from rest_framework.permissions import IsAuthenticated
from .models import CodingProblem, CodeSubmission
from mongoengine.errors import ValidationError as MongoValidationError
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from ..collector.models import BehaviourSession
from ..collector.services import get_active_session
from ..accounts.throttling import check_throttle
from .models import Course, Quiz, QuizAttempt

# Item ids are question indices: "q0", "q1", ... (bounded so a hand-crafted
# "q" + digits payload can't smuggle anything else through)
_ITEM_ID_PATTERN = re.compile(r"^q(\d{1,8})$")


def _get_quiz_or_404(quiz_id):
    """Fetch a quiz by id; malformed ObjectIds are 404, not an unhandled 500."""
    try:
        return Quiz.objects(pk=quiz_id).first()
    except MongoValidationError:
        return None


class CourseListView(APIView):
    """Course catalogue (supports the RL difficulty-adjustment action)."""

    permission_classes = [AllowAny]

    def get(self, request):
        # materialise first: QuerySet.count() ignores .limit() by default, so
        # it would report the total catalogue size while only 500 are returned
        courses = list(Course.objects.order_by("code").limit(500))
        return Response(
            {
                "count": len(courses),
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
    """Quiz questions with answers — JWT only. Answers are informational for
    the taker (review mode); attempts are scored SERVER-SIDE, so the client's
    belief about correctness is never trusted (see QuizAttemptView)."""

    def get(self, request, quiz_id):
        quiz = _get_quiz_or_404(quiz_id)
        if quiz is None:
            return Response({"detail": "Quiz not found"}, status=404)
        return Response(_serialize_quiz(quiz, include_questions=True))


class QuizAttemptView(APIView):
    """FR04: submit one quiz item attempt (JWT-authenticated).

    Persists a structured QuizAttempt (source of truth for the session's quiz
    aggregates -> QAP) and updates the student's active session counters,
    including re-attempt detection for previously-incorrect items.

    Hardened (security review): the client sends only WHAT it selected
    (`selected`: option index, or -1 for "no answer") — never whether it was
    right. `correct` is computed here from the stored question's answer, so a
    tampering client can only hurt its own score. `item_id` must be the exact
    `q<index>` of a question that exists in this quiz (no phantom items, no
    10k-char garbage rows).
    """

    def post(self, request, quiz_id):
        throttled = check_throttle(request, "quiz_attempt")
        if throttled is not None:
            return throttled

        quiz = _get_quiz_or_404(quiz_id)
        if quiz is None:
            return Response({"detail": "Quiz not found"}, status=404)

        item_id = request.data.get("item_id")
        selected = request.data.get("selected")
        if not isinstance(item_id, str) or not isinstance(selected, int) or isinstance(selected, bool):
            return Response(
                {"detail": "Requires item_id ('q<index>') and selected (option index int, -1 = unanswered)"},
                status=400,
            )

        questions = quiz.questions or []
        match = _ITEM_ID_PATTERN.fullmatch(item_id)
        if match is None or int(match.group(1)) >= len(questions):
            return Response({"detail": "Unknown item_id for this quiz"}, status=400)

        question = questions[int(match.group(1))]
        options = question.get("options") or []
        if not -1 <= selected < len(options):
            return Response({"detail": "selected out of range for this item"}, status=400)

        correct = selected == question.get("answer")

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
                "selected": selected,
                "correct": correct,
                "is_reattempt": is_reattempt,
            },
            status=status.HTTP_201_CREATED,
        )
DETAIL_QUERY = """
query questionData($titleSlug: String!) {
  question(titleSlug: $titleSlug) {
    content
    exampleTestcases
    codeSnippets { langSlug code }
  }
}
"""


class ProblemListView(APIView):
    """Paginated list of coding problems with user's solved status."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        search = (request.query_params.get("search") or "").strip()
        difficulty = (request.query_params.get("difficulty") or "").strip()
        page = max(1, int(request.query_params.get("page", 1)))
        limit = min(100, max(1, int(request.query_params.get("limit", 50))))

        qs = CodingProblem.objects
        if search:
            qs = qs.filter(title__icontains=search)
        if difficulty in ("Easy", "Medium", "Hard"):
            qs = qs.filter(difficulty=difficulty)

        total = qs.count()
        items = list(
            qs.skip((page - 1) * limit)
            .limit(limit)
            .only("slug", "question_id", "title", "difficulty", "topic_tags")
        )

        solved_slugs = set(
            CodeSubmission.objects(student=request.user.student_id, passed=True).distinct("problem_slug")
        )

        return Response({
            "total": total,
            "page": page,
            "problems": [
                {
                    "slug": p.slug,
                    "question_id": p.question_id,
                    "title": p.title,
                    "difficulty": p.difficulty,
                    "topic_tags": p.topic_tags,
                    "solved": p.slug in solved_slugs,
                }
                for p in items
            ],
        })


class ProblemDetailView(APIView):
    """Full problem details (lazy-loads from LeetCode on first click and caches in MongoDB)."""

    permission_classes = [IsAuthenticated]

    def get(self, request, slug):
        problem = CodingProblem.objects(slug=slug).first()
        if not problem:
            return Response({"detail": "Problem not found"}, status=404)

        if not problem.content:
            url = os.getenv("LEETCODE_GRAPHQL_URL", "https://leetcode.com/graphql")
            headers = {
                "Content-Type": "application/json",
                "User-Agent": "Mozilla/5.0",
                "Referer": "https://leetcode.com",
            }
            try:
                res = requests.post(
                    url,
                    json={"query": DETAIL_QUERY, "variables": {"titleSlug": slug}},
                    headers=headers,
                    timeout=10,
                )
                res.raise_for_status()
                detail = (res.json().get("data") or {}).get("question") or {}
                problem.content = detail.get("content") or ""
                problem.example_testcases = detail.get("exampleTestcases") or ""
                problem.starter_code = {
                    s["langSlug"]: s["code"] for s in (detail.get("codeSnippets") or [])
                }
                problem.save()
            except requests.RequestException:
                return Response({"detail": "Failed to fetch problem details from LeetCode"}, status=502)

        return Response({
            "slug": problem.slug,
            "question_id": problem.question_id,
            "title": problem.title,
            "difficulty": problem.difficulty,
            "topic_tags": problem.topic_tags,
            "content": problem.content,
            "starter_code": problem.starter_code,
            "example_testcases": problem.example_testcases,
        })
