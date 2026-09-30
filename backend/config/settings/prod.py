"""Production settings (Phase 10: TLS 1.3 in transit, hardened cookies, etc.).

`DJANGO_ALLOWED_HOSTS` is REQUIRED here. The previous behaviour —
`"".split(",") == [""]` — silently rejected every request with DisallowedHost
whenever the variable was unset, so the failure now happens at import time
with an actionable message instead of at the first HTTP request.
"""
from django.core.exceptions import ImproperlyConfigured

from .base import *  # noqa: F401,F403

DEBUG = False

ALLOWED_HOSTS = [  # noqa: F405
    host.strip() for host in os.getenv("DJANGO_ALLOWED_HOSTS", "").split(",") if host.strip()
]
if not ALLOWED_HOSTS:
    raise ImproperlyConfigured(
        "DJANGO_ALLOWED_HOSTS must be a comma-separated list of hostnames when "
        "using config.settings.prod (set it in .env — see .env.example)."
    )
