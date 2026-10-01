"""Test settings: isolated careermind_test database + eager Celery."""
import mongoengine

from .dev import *  # noqa: F401,F403

MONGO_DB_NAME = "careermind_test"

# base.py already connected the default alias to the dev DB — repoint it
mongoengine.disconnect()
mongoengine.connect(db=MONGO_DB_NAME, host=MONGO_URI, alias="default")  # noqa: F405

CELERY_BROKER_URL = "memory://"
CELERY_TASK_ALWAYS_EAGER = True

# the repo-root .env may carry REDIS_URL (for the compose stack) — tests must
# never reach into it: force the in-process LocMem cache for determinism
CACHES = {
    "default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache", "LOCATION": "careermind-test"}
}
