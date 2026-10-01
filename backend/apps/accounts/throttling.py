"""Cache-backed login throttling (auth hardening).

A fixed-window failure counter keyed by (normalized email, client IP): after
LOGIN_FAILURE_LIMIT failed attempts inside LOGIN_LOCKOUT_WINDOW_SECONDS, that
combination is locked out for the rest of the window — even with the correct
password. A successful login clears the counter so legitimate users recover
immediately.

The state lives in Django's cache (Redis in the stack, LocMem fallback), so it
is shared across all workers of the login process. Cache failures fail OPEN:
an outage of the cache backend must degrade to unlimited attempts, never lock
every user out of the platform.
"""
import logging

from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)

_PREFIX = "login-fail"


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
