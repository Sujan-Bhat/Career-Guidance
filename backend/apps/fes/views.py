from mongoengine.queryset.visitor import Q
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from careermind_ml.fes.weights import SESSION_LOCAL_SUBMETRICS, SUBMETRICS

from .models import FESScore, FESWeights

# Rows carrying at least one session-local sub-metric. Legacy rows written
# before the compute_session_fes skip guard (phantom StrictMode sessions,
# page_view-only browses — FES collapsed onto SCI alone) are skipped at read
# time so they can never shadow a real reading as "the latest".
_HAS_SESSION_SIGNAL = (
    Q(tcr__ne=None) | Q(dfet__ne=None) | Q(qap__ne=None) | Q(lrds__ne=None)
)


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


def _latest_score(student: str):
    """Newest FES row that actually carries session-local signal."""
    return (
        FESScore.objects(_HAS_SESSION_SIGNAL, student=student)
        .order_by("-computed_at")
        .first()
    )


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
        latest = _latest_score(student)
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
    Signal-less legacy rows are excluded so the chart never plots points
    where FES merely mirrors SCI.

    Each row carries the five SUB-METRICS alongside the composite (paper
    Eq. 1) so the metrics page can chart the sub-metric history from the
    database rather than only the composite: a sub-metric legitimately has no
    value in a session that never recorded that activity, so it is served as
    null and the chart leaves a gap instead of plotting a zero.
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
            FESScore.objects(_HAS_SESSION_SIGNAL, student=student)
            .order_by("-computed_at")
            .limit(limit)
        )
        history = list(reversed(newest))  # chronological order for plotting
        return Response(
            {
                "student": student,
                "count": len(history),
                "history": [
                    {
                        "session": s.session,
                        "date": s.computed_at,
                        "fes": s.fes,
                        **{m: getattr(s, m) for m in SUBMETRICS},
                        "weights": s.weights,
                    }
                    for s in history
                ],
            }
        )


class FESSubmetricsView(APIView):
    """TCR, SCI, DFET, QAP, LRDS breakdown for the dashboard (paper Sec. V-A),
    plus the student's Eq. 2 weights vs the population vector.

    Each sub-metric is served as the MOST RECENT non-null reading with its
    `as_of` timestamp: a session with no quizzes legitimately has no QAP, and
    hiding every other metric because the newest row is sparse was the bug —
    the dashboard can now show the last real reading per metric. `latest`
    reports the newest row's availability so the UI can explain the gap."""

    permission_classes = [AllowAny]

    def get(self, request):
        student = _resolve_student(request)
        if student is None:
            return Response(
                {"detail": "Authentication required for personal FES data — login first."},
                status=401,
            )
        rows = list(FESScore.objects(student=student).order_by("-computed_at").limit(100))
        if not rows:
            return Response(
                {"detail": f"No FES history for student '{student}'. Run `make train-fes`."},
                status=404,
            )

        submetrics = {}
        for metric in SUBMETRICS:
            reading = next((r for r in rows if getattr(r, metric, None) is not None), None)
            submetrics[metric] = (
                {"value": getattr(reading, metric), "as_of": reading.computed_at}
                if reading is not None
                else None
            )

        newest = rows[0]
        with_signal = next(
            (
                r
                for r in rows
                if any(getattr(r, m, None) is not None for m in SESSION_LOCAL_SUBMETRICS)
            ),
            newest,
        )
        population = FESWeights.objects(student=None).first()
        return Response(
            {
                "student": student,
                "latest": {
                    "computed_at": newest.computed_at,
                    "fes": newest.fes,
                    "available": [m for m in SUBMETRICS if getattr(newest, m, None) is not None],
                    "missing": [m for m in SUBMETRICS if getattr(newest, m, None) is None],
                },
                "submetrics": submetrics,
                "student_weights": with_signal.weights,
                "population_weights": population.weights if population else None,
                "computed_at": with_signal.computed_at,
            }
        )
