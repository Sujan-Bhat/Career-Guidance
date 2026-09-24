from rest_framework.response import Response
from rest_framework.views import APIView


class CurrentFESView(APIView):
    """Phase 2/3: latest FES value for the requesting student."""

    def get(self, request):
        return Response({"detail": "Not implemented (Phase 2/3)"}, status=501)


class FESHistoryView(APIView):
    """Phase 2/3: FES time series (supports the 14-day trend feature)."""

    def get(self, request):
        return Response({"detail": "Not implemented (Phase 2/3)"}, status=501)


class FESSubmetricsView(APIView):
    """Phase 2/3: TCR, SCI, DFET, QAP, LRDS breakdown for the dashboard."""

    def get(self, request):
        return Response({"detail": "Not implemented (Phase 2/3)"}, status=501)
