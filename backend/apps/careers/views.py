"""Career pathway catalogue + ensemble prediction APIs (paper FR08, Sec. V-D)."""
from datetime import datetime

from mongoengine import connection
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

import functools

from .models import CareerPathway, CareerPrediction

_ensemble = None


@functools.lru_cache(maxsize=1)
def _skill_categories():
    from careermind_ml.career_prediction.features import load_skill_categories

    return load_skill_categories()


def _get_ensemble() -> dict:
    """Lazy singleton: trained stacking ensemble artifact (RF+GBT+MLP -> LR).
    Rebuilt on process restart (same refresh story as the cascade)."""
    global _ensemble
    if _ensemble is None:
        from careermind_ml.career_prediction.ensemble import load_artifact

        _ensemble = load_artifact()
    return _ensemble


def _prediction_features(profile) -> tuple[dict, bool]:
    """(student agg for feature_row, cold_start) for the requesting student."""
    from apps.fes.models import FESScore
    from careermind_ml.fes.trend import compute_fes_trend

    series = [(s.computed_at, s.fes) for s in FESScore.objects(student=profile.student_id).order_by("computed_at")]
    fes_current = series[-1][1] if series else None
    fes_trend = compute_fes_trend(series)

    db = connection.get_db("default")
    sessions = list(
        db.sessions.aggregate(
            [
                {"$match": {"student": profile.student_id}},
                {"$group": {"_id": None, "sessions": {"$sum": 1}, "mean_duration": {"$avg": "$duration_minutes"}}},
            ]
        )
    )
    interactions = list(
        db.interactions.aggregate(
            [
                {"$match": {"student": profile.student_id}},
                {"$group": {"_id": None, "interactions": {"$sum": 1}, "items": {"$addToSet": "$item_id"}}},
            ]
        )
    )
    participation = {
        "exp_sessions": sessions[0]["sessions"] if sessions else 0,
        "exp_interactions": interactions[0]["interactions"] if interactions else 0,
        "exp_distinct_items": len(interactions[0]["items"]) if interactions else 0,
        "exp_mean_duration": sessions[0]["mean_duration"] if sessions else None,
    }

    cold_start = not profile.skill_assessments and not profile.academic_records and fes_current is None

    agg = {
        "grades": {r.subject: r.grade for r in profile.academic_records},
        "skills": {
            s.skill: max(1, min(5, int(s.score // 20) + 1))
            for s in profile.skill_assessments
        },
        "participation": participation,
        "fes_current": fes_current,
        "fes_trend": fes_trend,
        "preferences": {p.category: p.weight for p in profile.career_preferences},
        "year_of_study": profile.year_of_study or 3,
    }
    return agg, cold_start


class PathwayListView(APIView):
    """Career pathway catalogue (knowledge-graph nodes), Phase 1.

    Public (AllowAny): the catalogue is non-personalised reference data used
    by the frontend and by Stage 1 of the recommendation cascade (Phase 4).
    """

    permission_classes = [AllowAny]

    def get(self, request):
        pathways = [
            {
                "id": p.external_id,
                "name": p.name,
                "category": p.category,
                "description": p.description,
                "prerequisites": [
                    {"skill": r.skill, "min_level": r.min_level} for r in p.prerequisites
                ],
                "typical_courses": p.typical_courses,
            }
            for p in CareerPathway.objects.order_by("external_id")
        ]
        return Response({"count": len(pathways), "pathways": pathways})


class CareerPredictionView(APIView):
    """GET /careers/predictions (JWT): ensemble prediction for the requesting
    student — confidence-ranked distribution over career categories plus
    top contributing features (transparency, Sec. V-D), persisted to the
    career_prediction collection."""

    def get(self, request):
        try:
            artifact = _get_ensemble()
        except FileNotFoundError:
            return Response(
                {"detail": "Ensemble artifact missing — run `make train-ensemble` first"},
                status=503,
            )

        import pandas as pd

        from careermind_ml.career_prediction.attribution import top_contributing_features
        from careermind_ml.career_prediction.features import feature_row

        profile = request.user
        agg, cold_start = _prediction_features(profile)
        row = feature_row(
            agg,
            _skill_categories(),
            include_preferences=any(c.startswith("pref_") for c in artifact["columns"]),
            population_defaults=artifact["population_defaults"],
        )
        x = pd.DataFrame([row], columns=artifact["columns"])
        model = artifact["model"]

        probabilities = model.predict_proba(x)[0]
        ranked = sorted(
            zip(model.classes_, probabilities), key=lambda pair: -pair[1]
        )
        prediction = ranked[0][0]
        distribution = [
            {"category": category, "probability": float(p)} for category, p in ranked
        ]
        top_features = top_contributing_features(
            model, x, prediction, k=5, baseline=artifact["population_defaults"]
        )

        doc = CareerPrediction.objects(student=profile.student_id).first()
        if doc is None:
            doc = CareerPrediction(student=profile.student_id)
        doc.distribution = distribution
        doc.top_features = top_features
        doc.model_version = artifact["version"]
        doc.predicted_at = datetime.utcnow()
        doc.save()

        return Response(
            {
                "prediction": prediction,
                "cold_start": cold_start,
                "distribution": distribution,
                "top_features": top_features,
                "model_version": artifact["version"],
                "predicted_at": doc.predicted_at.isoformat(),
            }
        )
