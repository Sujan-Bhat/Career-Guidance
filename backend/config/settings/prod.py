"""Production settings (Phase 10: TLS 1.3 in transit, hardened cookies, etc.)."""
from .base import *  # noqa: F401,F403

DEBUG = False

ALLOWED_HOSTS = os.getenv("DJANGO_ALLOWED_HOSTS", "").split(",")  # noqa: F405
