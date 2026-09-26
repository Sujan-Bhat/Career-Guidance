from datetime import datetime

from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .auth import hash_password, mint_tokens, verify_password, decode_token
from .models import StudentProfile
from .serializers import (
    LoginSerializer,
    ProfileSerializer,
    RefreshSerializer,
    RegisterSerializer,
)


def _auth_response(profile: StudentProfile, status_code: int) -> Response:
    tokens = mint_tokens(profile.student_id)
    return Response(
        {
            "access": tokens["access"],
            "refresh": tokens["refresh"],
            "student_id": profile.student_id,
            "email": profile.email,
        },
        status=status_code,
    )


class RegisterView(APIView):
    """FR01: student registration -> StudentProfile (source=careermind)."""

    permission_classes = [AllowAny]

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        if StudentProfile.objects(email=data["email"]).first():
            return Response({"detail": "Email already registered"}, status=400)
        profile = StudentProfile(
            email=data["email"],
            full_name=data["full_name"],
            password_hash=hash_password(data["password"]),
            programme=data.get("programme") or "",
            year_of_study=data.get("year_of_study"),
            source="careermind",
            created_at=datetime.utcnow(),
        ).save()
        return _auth_response(profile, status.HTTP_201_CREATED)


class LoginView(APIView):
    """NFR04: email + password -> access/refresh JWT pair."""

    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        profile = StudentProfile.objects(email=serializer.validated_data["email"]).first()
        if not profile or not verify_password(
            serializer.validated_data["password"], profile.password_hash
        ):
            return Response({"detail": "Invalid credentials"}, status=401)
        return _auth_response(profile, status.HTTP_200_OK)


class RefreshView(APIView):
    """Exchange a valid refresh token for a new access token."""

    permission_classes = [AllowAny]

    def post(self, request):
        serializer = RefreshSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payload = decode_token(serializer.validated_data["refresh"], expected_type="refresh")
        if not StudentProfile.objects(pk=payload["sub"]).first():
            return Response({"detail": "Profile not found"}, status=401)
        tokens = mint_tokens(payload["sub"])
        return Response({"access": tokens["access"]})


class MeView(APIView):
    """Current student profile (JWT-authenticated)."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(ProfileSerializer(request.user).data)

    def patch(self, request):
        serializer = ProfileSerializer(request.user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        for field in ("full_name", "programme", "year_of_study"):
            if field in serializer.validated_data:
                setattr(request.user, field, serializer.validated_data[field])
        request.user.save()
        return Response(ProfileSerializer(request.user).data)
