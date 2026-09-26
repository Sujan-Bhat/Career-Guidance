from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import FESScore, FESWeights


def _resolve_student(request):
    """Phase 2 (review mode): the student comes from ?student= or defaults
    to the first student with FES history. Phase 3 replaces this with the
    JWT-derived identity."""
    student = request.query_params.get("student")
    if student:
        return student
    first = FESScore.objects.order_by("student").first()
    return first.student if first else "sim_0001"


class CurrentFESView(APIView):
    """Latest FES value + sub-metrics for the student (paper Eq. 1, FR03)."""

    permission_classes = [AllowAny]

    def get(self, request):
        student = _resolve_student(request)
        latest = (
            FESScore.objects(student=student).order_by("-computed_at").first()
        )
        if latest is None:
            return Response(
                {"detail": f"No FES history for student '{student}'. Run `make train-fes`."},
                status=404,
            )
        return Response(
            {
                "student": student,
                "fes": latest.fes,
                "tcr": latest.tcr,
                "sci": latest.sci,
                "dfet": latest.dfet,
                "qap": latest.qap,
                "lrds": latest.lrds,
                "weights": latest.weights,
                "computed_at": latest.computed_at,
            }
        )


class FESHistoryView(APIView):
    """FES time series (supports the 14-day trend feature, paper Sec. V-B)."""

    permission_classes = [AllowAny]

    def get(self, request):
        student = _resolve_student(request)
        try:
            limit = min(int(request.query_params.get("limit", 30)), 200)
        except ValueError:
            limit = 30
        history = (
            FESScore.objects(student=student).order_by("computed_at").limit(limit)
        )
        return Response(
            {
                "student": student,
                "count": history.count(),
                "history": [
                    {"date": s.computed_at, "fes": s.fes} for s in history
                ],
            }
        )


class FESSubmetricsView(APIView):
    """TCR, SCI, DFET, QAP, LRDS breakdown for the dashboard (paper Sec. V-A),
    plus the student's Eq. 2 weights vs the population vector."""

    permission_classes = [AllowAny]

    def get(self, request):
        student = _resolve_student(request)
        latest = FESScore.objects(student=student).order_by("-computed_at").first()
        if latest is None:
            return Response(
                {"detail": f"No FES history for student '{student}'. Run `make train-fes`."},
                status=404,
            )
        population = FESWeights.objects(student=None).first()
        return Response(
            {
                "student": student,
                "submetrics": {
                    "tcr": latest.tcr,
                    "sci": latest.sci,
                    "dfet": latest.dfet,
                    "qap": latest.qap,
                    "lrds": latest.lrds,
                },
                "student_weights": latest.weights,
                "population_weights": population.weights if population else None,
                "computed_at": latest.computed_at,
            }
        )
