from rest_framework.response import Response
from rest_framework.views import APIView


class RLStatusView(APIView):
    """Phase 6: current policy status for the student (active pathway, last action)."""

    def get(self, request):
        return Response({"detail": "Not implemented (Phase 6)"}, status=501)


class RLActionView(APIView):
    """Phase 6: select a recommendation-policy adjustment (one of 8 actions)
    with the pre-trained DQN over the 17-dim state."""

    def post(self, request):
        return Response({"detail": "Not implemented (Phase 6)"}, status=501)
