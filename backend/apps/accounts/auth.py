"""Custom JWT authentication (paper NFR04) — pure MongoDB, no ORM users.

Access tokens (60 min) and refresh tokens (7 days) are minted with PyJWT and
signed with Django's SECRET_KEY. The `sub` claim carries the StudentProfile
ObjectID; DRF sees the profile as `request.user`.
"""
import base64
import hashlib
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


# Marker distinguishing the pre-hashed scheme from pre-hardening raw-bcrypt
# hashes (`$2b$...`). Django uses the same idea for BCryptSHA256.
PREHASH_PREFIX = "sha256$"


def _pre_hash(plain: str) -> str:
    """SHA-256 digest, base64-encoded, as the bcrypt input.

    bcrypt silently truncates its input at 72 bytes, so two passwords sharing
    the first 72 bytes were interchangeable. Hashing first removes the limit
    entirely (the bcrypt input is always 44 ASCII chars); base64 keeps the
    digest away from NUL bytes, which would truncate bcrypt's C-string input.
    """
    digest = hashlib.sha256(plain.encode("utf-8")).digest()
    return base64.b64encode(digest).decode("ascii")


def hash_password(plain: str) -> str:
    import bcrypt

    hashed = bcrypt.hashpw(_pre_hash(plain).encode(), bcrypt.gensalt()).decode()
    return PREHASH_PREFIX + hashed


def verify_password(plain: str, hashed: str) -> bool:
    import bcrypt

    try:
        if hashed.startswith(PREHASH_PREFIX):
            return bcrypt.checkpw(
                _pre_hash(plain).encode(), hashed[len(PREHASH_PREFIX):].encode()
            )
        # pre-hardening account: raw bcrypt over the original password
        # (bcrypt truncates at 72 bytes, which is exactly what that hash saw)
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode())
    except ValueError:
        return False


def needs_rehash(hashed: str) -> bool:
    """True for legacy raw-bcrypt hashes; LoginView re-hashes on success."""
    return not hashed.startswith(PREHASH_PREFIX)


class CareermindJWTAuthentication(authentication.BaseAuthentication):
    """Bearer-token authentication resolving to a StudentProfile document."""

    keyword = "Bearer"

    def authenticate_header(self, request) -> str:
        """WWW-Authenticate value for failed authentication.

        Without this DRF treats the authenticator as providing no challenge
        and downgrades every AuthenticationFailed (expired / malformed /
        unknown-subject token) from 401 to 403 — which is exactly the status
        the frontend's silent-refresh interceptor keys on
        (frontend/src/lib/api/client.ts), so expired access tokens never
        triggered a refresh."""
        return self.keyword

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
        except DoesNotExist:
            # only an unknown/deleted subject is an auth failure; a Mongo
            # outage or timeout must surface as a 500, not "Profile not found"
            raise exceptions.AuthenticationFailed("Profile not found")
        return (profile, header[1].decode())
