"""Thin proxy endpoints delegating to the careermind_llm package (Part A, NFR07).

Configured entirely from env: LLM_PROVIDER / LLM_API_KEY / LLM_MODEL.
Unconfigured key -> 503; provider failure -> 502 (the frontend shows a
friendly degradation either way).
"""
import os
from functools import lru_cache

from rest_framework.response import Response
from rest_framework.views import APIView


def _llm_error() -> str | None:
    """503 detail when the LLM is not configured, else None."""
    if not os.getenv("LLM_API_KEY"):
        return "LLM API key not configured — set LLM_API_KEY (and LLM_PROVIDER / LLM_MODEL)"
    return None


@lru_cache(maxsize=1)
def _chat():
    from careermind_llm.chat import GuidanceChat
    from careermind_llm.client import get_client

    return GuidanceChat(get_client())


def _chat_context(profile) -> str:
    from careermind_llm.chat import build_context
    from careermind_ml.fes.trend import compute_fes_trend

    from apps.fes.models import FESScore
    from apps.recommendations.models import Recommendation

    series = [
        (s.computed_at, s.fes) for s in FESScore.objects(student=profile.student_id).order_by("computed_at")
    ]
    fes = None
    if series:
        fes = {"score": series[-1][1], "trend": compute_fes_trend(series)}

    profile_dict = {
        "programme": profile.programme,
        "year_of_study": profile.year_of_study,
        "grades": {r.subject: r.grade for r in profile.academic_records},
        "skills": {s.skill: s.score for s in profile.skill_assessments},
    }

    from apps.careers.models import CareerPathway

    recent = list(Recommendation.objects(student=profile.student_id).order_by("-created_at")[:5])
    names = {
        p.external_id: p.name
        for p in CareerPathway.objects(external_id__in=[r.item_id for r in recent]).only("external_id", "name")
    } if recent else {}
    recommendations = [
        {"name": names.get(r.item_id, r.item_id), "decision": r.decision} for r in recent
    ]

    return build_context(profile_dict, fes, recommendations)


class ChatView(APIView):
    """Conversational career guidance (FR15): grounded multi-turn chat."""

    def post(self, request):
        message = str(request.data.get("message") or "").strip()
        if not message:
            return Response({"detail": "message is required"}, status=400)

        error = _llm_error()
        if error:
            return Response({"detail": error}, status=503)

        try:
            reply = _chat().chat(
                request.user.student_id, message, context=_chat_context(request.user)
            )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=502)
        except Exception:
            return Response({"detail": "LLM provider request failed"}, status=502)
        return Response({"reply": reply})


class QuizGenerateView(APIView):
    """LLM-generated self-assessment quiz items per skill domain (FR04)."""

    def post(self, request):
        skill = str(request.data.get("skill") or "").strip()
        if not skill:
            return Response({"detail": "skill is required"}, status=400)
        try:
            difficulty = int(request.data.get("difficulty", 2))
        except (TypeError, ValueError):
            return Response({"detail": "difficulty must be an integer 1-3"}, status=400)
        difficulty = min(3, max(1, difficulty))
        try:
            n_items = min(10, max(1, int(request.data.get("n_items", 5))))
        except (TypeError, ValueError):
            return Response({"detail": "n_items must be an integer"}, status=400)

        error = _llm_error()
        if error:
            return Response({"detail": error}, status=503)

        from careermind_llm.quizgen import generate_quiz_items

        try:
            items = generate_quiz_items(skill, difficulty, n_items)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=502)
        except Exception:
            return Response({"detail": "LLM provider request failed"}, status=502)

        # persist so attempts can be recorded against a real quiz id (FR04/QAP)
        from apps.courses.models import Quiz

        quiz = Quiz(
            skill=skill,
            title=f"AI quiz: {skill} (d{difficulty})",
            questions=items,
        ).save()
        return Response(
            {
                "quiz_id": str(quiz.pk),
                "items": items,
                "skill": skill,
                "difficulty": difficulty,
            }
        )
