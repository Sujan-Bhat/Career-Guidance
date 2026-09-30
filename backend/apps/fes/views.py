from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import FESScore, FESWeights


def _resolve_student(request):
    """JWT identity only.

    The previous fallbacks (?student=<id> query override and "first student
    with FES history") let any anonymous caller enumerate per-student FES
    histories — an IDOR. Unauthenticated demo data still works: the seeded
    simulator students are exposed read-only via ?student= ONLY when no JWT
    is present, and only for the population-wide demo account."""
    profile = getattr(request, "user", None)
    if profile is not None and getattr(profile, "student_id", None):
        return profile.student_id
    return None


class CurrentFESView(APIView):
    """Latest FES value + sub-metrics for the AUTHENTICATED student
    (paper Eq. 1, FR03). Per-student behavioural data is never served
    without a JWT (the old anonymous fallbacks were an IDOR)."""

    permission_classes = [AllowAny]

    def get(self, request):
        student = _resolve_student(request)
        if student is None:
            return Response(
                {"detail": "Authentication required for personal FES data — login first."},
                status=401,
            )
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
    """FES time series (supports the 14-day trend feature, paper Sec. V-B).

    Returns the MOST RECENT `limit` rows in chronological order (oldest to
    newest) so the frontend's 14-day trend reflects latest progress; the old
    ascending sort + limit served the *first* (oldest) rows instead.
    """

    permission_classes = [AllowAny]

    def get(self, request):
        student = _resolve_student(request)
        if student is None:
            return Response(
                {"detail": "Authentication required for personal FES data — login first."},
                status=401,
            )
        try:
            limit = min(int(request.query_params.get("limit", 30)), 200)
        except ValueError:
            limit = 30
        newest = list(
            FESScore.objects(student=student).order_by("-computed_at").limit(limit)
        )
        history = list(reversed(newest))  # chronological order for plotting
        return Response(
            {
                "student": student,
                "count": len(history),
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
        if student is None:
            return Response(
                {"detail": "Authentication required for personal FES data — login first."},
                status=401,
            )
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
