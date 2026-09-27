"""Base Django settings for CAREERMIND (paper Sec. V: MongoDB persistence, JWT, Celery)."""
import os
from datetime import timedelta
from pathlib import Path

import mongoengine

BASE_DIR = Path(__file__).resolve().parent.parent.parent


def _load_env_file() -> None:
    """Load the repo-root .env (if present) so `cp .env.example .env`
    configures local dev. Existing environment variables always win."""
    env_path = BASE_DIR.parent / ".env"
    if not env_path.is_file():
        return
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


_load_env_file()

SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "insecure-dev-key-change-me")
DEBUG = False
ALLOWED_HOSTS = ["*"]

INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "corsheaders",
    "rest_framework",
    "apps.accounts",
    "apps.collector",
    "apps.fes",
    "apps.courses",
    "apps.careers",
    "apps.recommendations",
    "apps.rl_feedback",
    "apps.llm_proxy",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.common.CommonMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {"context_processors": []},
    }
]

WSGI_APPLICATION = "config.wsgi.application"

# --- MongoDB (no relational DB by design; MongoEngine documents only) ---
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
MONGO_DB_NAME = os.getenv("MONGO_DB_NAME", "careermind")
mongoengine.connect(db=MONGO_DB_NAME, host=MONGO_URI, alias="default")

# Intentionally empty: all persistence goes through MongoEngine (paper Sec. V).
DATABASES = {}

# --- DRF / JWT (NFR04) ---
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "apps.accounts.auth.CareermindJWTAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": ("rest_framework.permissions.IsAuthenticated",),
    "DEFAULT_RENDERER_CLASSES": ("rest_framework.renderers.JSONRenderer",),
}

# --- CORS ---
CORS_ALLOWED_ORIGINS = [os.getenv("FRONTEND_URL", "http://localhost:3000")]

# --- Celery (async jobs: session-end FES computation, weight recalibration) ---
CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/1")
CELERY_TASK_ALWAYS_EAGER = os.getenv("CELERY_TASK_ALWAYS_EAGER", "0") == "1"

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_TZ = True
