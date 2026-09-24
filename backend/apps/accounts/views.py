from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView


class RegisterView(APIView):
    """Phase 3: student registration (FR01)."""

    permission_classes = [AllowAny]

    def post(self, request):
        return Response({"detail": "Not implemented (Phase 3)"}, status=501)


class LoginView(APIView):
    """Phase 3: JWT token obtain/refresh pair (NFR04)."""

    permission_classes = [AllowAny]

    def post(self, request):
        return Response({"detail": "Not implemented (Phase 3)"}, status=501)


class MeView(APIView):
    """Phase 3: current student profile (academic records, skills, preferences)."""

    def get(self, request):
        return Response({"detail": "Not implemented (Phase 3)"}, status=501)

    def patch(self, request):
        return Response({"detail": "Not implemented (Phase 3)"}, status=501)
