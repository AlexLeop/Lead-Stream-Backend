from __future__ import annotations

import dj_database_url

from leadstream.common.env import env

from .base import *  # noqa: F403
from .base import REST_FRAMEWORK, SIMPLE_JWT

DEBUG = False
SECRET_KEY = "test-only-secret-key-that-is-at-least-64-bytes-long-for-hmac-sha256-compliance"
SIMPLE_JWT["SIGNING_KEY"] = SECRET_KEY
ALLOWED_HOSTS = ["testserver", "localhost"]
TEST_DATABASE_URL = env("TEST_DATABASE_URL")
DATABASES = (
    {
        "default": dj_database_url.parse(
            TEST_DATABASE_URL,
            conn_max_age=0,
            conn_health_checks=True,
        )
    }
    if TEST_DATABASE_URL
    else {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}}
)
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True
CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"] = {
    "auth": "5/min",
    "auth_refresh": "10/min",
    "tenant": "10000/min",
}
