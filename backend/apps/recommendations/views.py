"""Recommendation API (Phase 4, FR05/FR11): 3-stage cascade + accept/reject."""
from datetime import datetime

from mongoengine import connection
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Recommendation

_cascade = None


def _get_cascade():
    """Lazy singleton: KG + FES-weighted CF + trained FM artifact.
    Rebuilt on process restart (documented refresh story for the prototype)."""
    global _cascade
    if _cascade is None:
        from django.conf import settings

        from careermind_ml.recommender.cascade import CascadeRecommender

        _cascade = CascadeRecommender.from_mongo(settings.MONGO_URI, settings.MONGO_DB_NAME)
    return _cascade


def _student_context(profile) -> tuple[dict, dict | None]:
    """(feature agg, skill levels) for the requesting student (JWT profile)."""
    import numpy as np

    from apps.fes.models import FESScore

    series = [(s.computed_at, s.fes) for s in FESScore.objects(student=profile.student_id).order_by("computed_at")]
    fes_current = series[-1][1] if series else None
    fes_trend = None
    if len(series) >= 2:
        recent = [f for _, f in series[-7:]]
        previous = [f for _, f in series[-14:-7]] or [f for _, f in series[:-7]]
        fes_trend = float(np.clip(0.5 + (np.mean(recent) - np.mean(previous)) / 2.0, 0.0, 1.0))

    grades = {r.subject: r.grade for r in profile.academic_records}
    preferences = {p.category: p.weight for p in profile.career_preferences}

    skills = {
        s.skill: max(1, min(5, int(s.score // 20) + 1))
        for s in profile.skill_assessments
    }

    agg = {
        "student": profile.student_id,
        "grades": grades,
        "fes_current": fes_current,
        "fes_trend": fes_trend,
        "preferences": preferences,
        "year_of_study": profile.year_of_study or 3,
    }
    return agg, (skills or None)


def _serialize(doc: Recommendation, result: dict) -> dict:
    return {
        "recommendation_id": str(doc.pk),
        "item_type": "pathway",
        "id": result["id"],
        "name": result["name"],
        "category": result["category"],
        "stage1_eligibility": result["stage1_eligibility"],
        "prerequisites_met": result["prerequisites_met"],
        "stage2_cf_score": result["stage2_cf_score"],
        "stage3_fm_score": result["stage3_fm_score"],
        "contributing_features": result["contributing_features"],
        "decision": doc.decision,
    }


class RecommendationListView(APIView):
    """GET /recommendations/ (JWT): run the cascade for the requesting
    student, persist pending Recommendation docs with per-stage provenance."""

    def get(self, request):
        agg, skills = _student_context(request.user)
        db = connection.get_db("default")
        student_items = list(
            db.interactions.find({"student": request.user.student_id}, {"item_id": 1})
        )
        student_items = [row["item_id"] for row in student_items]

        try:
            result = _get_cascade().recommend(agg, skills, student_items, top_k=10)
        except FileNotFoundError:
            return Response(
                {"detail": "FM artifact missing — run `make train-fm` first"}, status=503
            )

        payload = []
        for ranked in result["results"]:
            doc = Recommendation(
                student=request.user.student_id,
                item_type="pathway",
                item_id=ranked["id"],
                stage1_eligible=ranked["stage1_eligibility"],
                stage2_cf_score=ranked["stage2_cf_score"],
                stage3_fm_score=ranked["stage3_fm_score"],
                contributing_features=ranked["contributing_features"],
                decision="pending",
                created_at=datetime.utcnow(),
            ).save()
            payload.append(_serialize(doc, ranked))

        return Response(
            {
                "count": len(payload),
                "cold_start": result["cold_start"],
                "recommendations": payload,
            }
        )


class _DecisionView(APIView):
    """Shared accept/reject logic: logs the decision (feeds the RL state's
    acceptance ratio and future CF retraining data)."""

    decision = None

    def post(self, request, recommendation_id):
        doc = Recommendation.objects(pk=recommendation_id).first()
        if doc is None or doc.student != request.user.student_id:
            return Response({"detail": "Recommendation not found"}, status=404)
        if doc.decision != "pending":
            return Response({"detail": f"Already {doc.decision}"}, status=409)
        doc.decision = self.decision
        doc.save()
        return Response({"recommendation_id": str(doc.pk), "decision": doc.decision})


class AcceptView(_DecisionView):
    decision = "accepted"


class RejectView(_DecisionView):
    decision = "rejected"


class ExplainView(APIView):
    """Phase 7: plain-language explanation via llm_gateway (NFR07)."""

    def get(self, request, recommendation_id):
        return Response({"detail": "Not implemented (Phase 7)"}, status=501)
