from rest_framework.response import Response
from rest_framework.views import APIView


class RecommendationListView(APIView):
    """Phase 4: run the 3-stage cascade (KG → CF → FM) for the requesting student."""

    def get(self, request):
        return Response({"detail": "Not implemented (Phase 4)"}, status=501)


class AcceptView(APIView):
    """Phase 4: log acceptance (feeds the RL state's acceptance ratio)."""

    def post(self, request, recommendation_id):
        return Response({"detail": "Not implemented (Phase 4)"}, status=501)


class RejectView(APIView):
    """Phase 4: log rejection (feeds the RL state's acceptance ratio)."""

    def post(self, request, recommendation_id):
        return Response({"detail": "Not implemented (Phase 4)"}, status=501)


class ExplainView(APIView):
    """Phase 7: plain-language explanation via llm_gateway (NFR07)."""

    def get(self, request, recommendation_id):
        return Response({"detail": "Not implemented (Phase 7)"}, status=501)
