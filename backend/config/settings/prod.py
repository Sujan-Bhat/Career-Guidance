"""Production settings (Phase 10: TLS 1.3 in transit, hardened cookies, etc.).

Both `DJANGO_SECRET_KEY` and `DJANGO_ALLOWED_HOSTS` are REQUIRED here — the
failure happens at import time with an actionable message instead of at the
first HTTP request (or, for the key, with a known default silently signing
tokens).
"""
from django.core.exceptions import ImproperlyConfigured

from .base import *  # noqa: F401,F403

DEBUG = False

if os.getenv("DJANGO_SECRET_KEY") is None:  # noqa: F405
    raise ImproperlyConfigured(
        "DJANGO_SECRET_KEY must be set when using config.settings.prod "
        "(set it in .env — see .env.example). Refusing to sign tokens with a "
        "fallback key."
    )

ALLOWED_HOSTS = [  # noqa: F405
    host.strip() for host in os.getenv("DJANGO_ALLOWED_HOSTS", "").split(",") if host.strip()
]
if not ALLOWED_HOSTS:
    raise ImproperlyConfigured(
        "DJANGO_ALLOWED_HOSTS must be a comma-separated list of hostnames when "
        "using config.settings.prod (set it in .env — see .env.example)."
    )
