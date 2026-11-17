"""AI-generated career roadmaps: Gemini generation + per-student persistence.

Conventions mirror apps/llm_proxy: unconfigured key -> 503, provider failure
-> 502 (the frontend degrades with a friendly message either way). Roadmaps
are always scoped to the authenticated student's PII-free id (NFR05).
"""
import os

from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.throttling import check_throttle

from .models import GeneratedRoadmap

MAX_CAREER_CHARS = 120
MAX_CONTEXT_CHARS = 500
MAX_LIST = 50


def _llm_error() -> str | None:
    """503 detail when the LLM is not configured, else None."""
    if not os.getenv("LLM_API_KEY"):
        return "LLM API key not configured — set LLM_API_KEY (and LLM_PROVIDER / LLM_MODEL)"
    return None


def _summary(doc: GeneratedRoadmap) -> dict:
    return {
        "slug": doc.slug,
        "title": doc.title,
        "description": doc.description,
        "generated_at": doc.generated_at.isoformat() if doc.generated_at else None,
    }


class GenerateRoadmapView(APIView):
    """POST /roadmaps/generate — build a roadmap for a career with Gemini.

    Regenerating an already-generated slug replaces the previous roadmap
    (progress statuses survive: they are keyed by node id and unrelated
    nodes keep their ids only by luck — the frontend sanitises on read).
    """

    def post(self, request):
        career = str(request.data.get("career") or "").strip()
        if not career:
            return Response({"detail": "career is required"}, status=400)
        if len(career) > MAX_CAREER_CHARS:
            return Response(
                {"detail": f"career must be {MAX_CAREER_CHARS} characters or fewer"},
                status=400,
            )
        context = str(request.data.get("context") or "").strip()[:MAX_CONTEXT_CHARS]

        error = _llm_error()
        if error:
            return Response({"detail": error}, status=503)

        throttled = check_throttle(request, "roadmap_generate")
        if throttled is not None:
            return throttled

        from careermind_llm.roadmapgen import generate_roadmap

        try:
            roadmap = generate_roadmap(career, context=context or None)
        except ValueError as exc:
            # unusable model output — surfaced so the user can retry
            return Response({"detail": str(exc)}, status=502)
        except Exception:
            return Response({"detail": "LLM provider request failed"}, status=502)

        GeneratedRoadmap.objects(student=request.user.student_id, slug=roadmap["slug"]).modify(
            upsert=True,
            new=True,
            set__title=roadmap["title"],
            set__description=roadmap["description"],
            set__roadmap=roadmap,
            set__generated_at=_now(),
        )
        return Response({"roadmap": roadmap})


class MyGeneratedRoadmapsView(APIView):
    """GET /roadmaps/mine — the student's generated roadmaps (newest first).

    Full roadmaps are returned so a fresh device can render them without a
    second round trip per slug.
    """

    def get(self, request):
        docs = list(
            GeneratedRoadmap.objects(student=request.user.student_id).order_by("-generated_at")[
                :MAX_LIST
            ]
        )
        return Response(
            {
                "roadmaps": [
                    {**_summary(doc), "roadmap": doc.roadmap} for doc in docs
                ]
            }
        )


class GeneratedRoadmapView(APIView):
    """GET /roadmaps/<slug> — one generated roadmap owned by the student.
    DELETE /roadmaps/<slug> — delete one generated roadmap owned by the student.
    """

    def get(self, request, slug: str):
        doc = GeneratedRoadmap.objects(
            student=request.user.student_id, slug=slug
        ).first()
        if doc is None:
            return Response({"detail": "not found"}, status=404)
        return Response({"roadmap": doc.roadmap})

    def delete(self, request, slug: str):
        doc = GeneratedRoadmap.objects(
            student=request.user.student_id, slug=slug
        ).first()
        if doc is None:
            return Response({"detail": "not found"}, status=404)
        doc.delete()
        return Response({"detail": "deleted", "slug": slug}, status=200)


def _now():
    from django.utils import timezone

    return timezone.now()
