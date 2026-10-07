"""Cache-backed throttling (auth hardening + generic request caps).

Two fixed-window mechanisms share the Django cache (Redis in the stack,
LocMem fallback), so state is shared across all workers:

- Login lockout: a FAILURE counter keyed by (normalized email, client IP).
  After LOGIN_FAILURE_LIMIT failed attempts inside the window that pair is
  locked out — even with the correct password. A successful login clears
  the counter so legitimate users recover immediately.
- Request caps (`check_throttle`): a REQUEST counter keyed by identity
  (JWT subject when authenticated, else client IP) and scope. Used for
  state-changing POSTs that accept no failure semantics (register,
  RL action, quiz attempt). Returns a ready-made 429 response once the
  scope's limit is exceeded inside the window.

Both fail OPEN on cache outages: a Redis hiccup must degrade to unlimited
requests, never lock every user out of the platform.
"""
import logging

from django.conf import settings
from django.core.cache import cache
from rest_framework.response import Response

logger = logging.getLogger(__name__)

_PREFIX = "login-fail"

# scope -> (settings attribute for the limit, fallback when unset)
_SCOPE_LIMITS = {
    "register": ("REGISTER_THROTTLE_LIMIT", 10),
}
_REQUEST_LIMIT_ATTR = "REQUEST_THROTTLE_LIMIT"
_REQUEST_LIMIT_DEFAULT = 60


def _limit() -> int:
    return int(getattr(settings, "LOGIN_FAILURE_LIMIT", 10))


def _window() -> int:
    return int(getattr(settings, "LOGIN_LOCKOUT_WINDOW_SECONDS", 900))


def client_ip(request) -> str:
    return request.META.get("REMOTE_ADDR", "unknown")


def _key(email: str, ip: str) -> str:
    return f"{_PREFIX}:{email.strip().lower()}:{ip}"


def is_locked_out(email: str, ip: str) -> bool:
    try:
        return cache.get(_key(email, ip), 0) >= _limit()
    except Exception:  # noqa: BLE001 — fail open on cache outage
        logger.warning("login throttle read failed — failing open", exc_info=True)
        return False


def register_failure(email: str, ip: str) -> None:
    key = _key(email, ip)
    try:
        try:
            cache.incr(key)  # incr keeps the window's original TTL
        except ValueError:
            # first failure inside this window — opens it
            cache.set(key, 1, _window())
    except Exception:  # noqa: BLE001 — fail open on cache outage
        logger.warning("login throttle write failed — failing open", exc_info=True)


def reset_failures(email: str, ip: str) -> None:
    try:
        cache.delete(_key(email, ip))
    except Exception:  # noqa: BLE001 — fail open on cache outage
        logger.warning("login throttle reset failed — failing open", exc_info=True)


# --- Generic fixed-window request caps -------------------------------------


def _request_key(request, scope: str) -> str:
    """One bucket per (scope, identity): the verified JWT subject when the
    request reached authentication, else the client IP (anonymous endpoints
    such as register). """
    student_id = getattr(getattr(request, "user", None), "student_id", None)
    identity = student_id or client_ip(request)
    return f"request-rate:{scope}:{identity}"


def _scope_limit(scope: str) -> int:
    attr, default = _SCOPE_LIMITS.get(scope, (_REQUEST_LIMIT_ATTR, _REQUEST_LIMIT_DEFAULT))
    return int(getattr(settings, attr, default))


def check_throttle(request, scope: str, window_seconds: int | None = None) -> Response | None:
    """Count this request against the scope's fixed window; return a 429
    response when the caller is over the limit, else None to proceed.

    The counter includes the current request: the first `limit` requests in a
    window pass, everything after is rejected until the window expires.
    Failures of the cache backend fail open (no throttling) by design.
    """
    window = int(window_seconds if window_seconds is not None else getattr(settings, "REQUEST_THROTTLE_WINDOW_SECONDS", 60))
    key = _request_key(request, scope)
    try:
        try:
            count = cache.incr(key)  # incr keeps the window's original TTL
        except ValueError:
            cache.set(key, 1, window)  # first request opens the window
            count = 1
    except Exception:  # noqa: BLE001 — fail open on cache outage
        logger.warning("%s throttle write failed — failing open", scope, exc_info=True)
        return None
    if count > _scope_limit(scope):
        logger.info("%s throttled for %s", scope, _request_key(request, scope))
        return Response(
            {"detail": "Too many requests — slow down and try again shortly."},
            status=429,
        )
    return None
