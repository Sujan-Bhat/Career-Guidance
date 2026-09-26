"""Custom JWT authentication (paper NFR04) — pure MongoDB, no ORM users.

Access tokens (60 min) and refresh tokens (7 days) are minted with PyJWT and
signed with Django's SECRET_KEY. The `sub` claim carries the StudentProfile
ObjectID; DRF sees the profile as `request.user`.
"""
from datetime import datetime, timedelta, timezone

import jwt
from django.conf import settings
from mongoengine import DoesNotExist
from rest_framework import authentication, exceptions

ACCESS_TTL_MINUTES = 60
REFRESH_TTL_DAYS = 7
ALGORITHM = "HS256"


def _mint(token_type: str, student_id: str, ttl: timedelta) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": student_id,
        "type": token_type,
        "iat": int(now.timestamp()),
        "exp": int((now + ttl).timestamp()),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=ALGORITHM)


def mint_tokens(student_id: str) -> dict:
    return {
        "access": _mint("access", student_id, timedelta(minutes=ACCESS_TTL_MINUTES)),
        "refresh": _mint("refresh", student_id, timedelta(days=REFRESH_TTL_DAYS)),
    }


def decode_token(token: str, expected_type: str) -> dict:
    """Decode + validate; raises DRF AuthenticationFailed on any problem."""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
    except jwt.ExpiredSignatureError as exc:
        raise exceptions.AuthenticationFailed("Token expired") from exc
    except jwt.InvalidTokenError as exc:
        raise exceptions.AuthenticationFailed("Invalid token") from exc
    if payload.get("type") != expected_type:
        raise exceptions.AuthenticationFailed(f"Expected a {expected_type} token")
    return payload


def hash_password(plain: str) -> str:
    import bcrypt

    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    import bcrypt

    try:
        return bcrypt.checkpw(plain.encode(), hashed.encode())
    except ValueError:
        return False


class CareermindJWTAuthentication(authentication.BaseAuthentication):
    """Bearer-token authentication resolving to a StudentProfile document."""

    keyword = "Bearer"

    def authenticate(self, request):
        header = authentication.get_authorization_header(request).split()
        if not header or header[0].lower() != self.keyword.lower().encode():
            return None  # anonymous — permission classes decide
        if len(header) != 2:
            raise exceptions.AuthenticationFailed("Invalid Authorization header")
        payload = decode_token(header[1].decode(), expected_type="access")
        from .models import StudentProfile

        try:
            profile = StudentProfile.objects.get(pk=payload["sub"])
        except (DoesNotExist, Exception):
            raise exceptions.AuthenticationFailed("Profile not found")
        return (profile, header[1].decode())
