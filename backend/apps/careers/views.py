from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView


class PathwayListView(APIView):
    """Phase 1/4: catalogue of career pathways (knowledge-graph nodes)."""

    permission_classes = [AllowAny]

    def get(self, request):
        return Response({"detail": "Not implemented (Phase 1/4)"}, status=501)


class CareerPredictionView(APIView):
    """Phase 5: ensemble prediction — probability distribution + top features."""

    def get(self, request):
        return Response({"detail": "Not implemented (Phase 5)"}, status=501)
