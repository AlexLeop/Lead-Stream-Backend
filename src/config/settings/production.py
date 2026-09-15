from __future__ import annotations

import dj_database_url
from django.core.exceptions import ImproperlyConfigured

from leadstream.common.encrypted_fields import validate_encryption_keys
from leadstream.common.env import env_bool, env_int, env_list, required_env

from .base import *  # noqa: F403

DEBUG = False
SECRET_KEY = required_env("DJANGO_SECRET_KEY")
configured_hosts = env_list("DJANGO_ALLOWED_HOSTS", required=True)
if "*" in configured_hosts:
    ALLOWED_HOSTS = ["*"]
else:
    # Garante 127.0.0.1 e localhost para as sondagens de saúde internas do EasyPanel/Docker
    ALLOWED_HOSTS = list(dict.fromkeys(["127.0.0.1", "localhost", "testserver", *configured_hosts]))

CSRF_TRUSTED_ORIGINS = env_list(
    "DJANGO_CSRF_TRUSTED_ORIGINS",
    default=[f"https://{h}" for h in configured_hosts if h not in ("*", "127.0.0.1", "localhost")],
)
CORS_ALLOWED_ORIGINS = env_list(
    "CORS_ALLOWED_ORIGINS",
    default=CSRF_TRUSTED_ORIGINS,
)

production_database_url = required_env("DATABASE_URL")
CELERY_BROKER_URL = required_env("CELERY_BROKER_URL")
REDIS_URL = required_env("REDIS_URL")
DATA_HASH_KEY = required_env("DATA_HASH_KEY")
DATA_HASH_KEY_VERSION = required_env("DATA_HASH_KEY_VERSION")
FIELD_ENCRYPTION_KEYS = env_list("FIELD_ENCRYPTION_KEYS", required=True)
validate_encryption_keys(FIELD_ENCRYPTION_KEYS)
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": REDIS_URL,
    }
}
DATABASES = {
    "default": dj_database_url.parse(
        production_database_url,
        conn_max_age=env_int("DATABASE_CONN_MAX_AGE", default=60),
        conn_health_checks=True,
        ssl_require=env_bool("DATABASE_SSL_REQUIRED", default=False),
    )
}

if DATABASES["default"]["ENGINE"] != "django.db.backends.postgresql":
    raise ImproperlyConfigured("DATABASE_URL deve apontar para PostgreSQL em produção.")

appwrite_ep = APPWRITE_ENDPOINT or ""  # noqa: F405
if appwrite_ep and not (
    appwrite_ep.startswith("https://")
    or appwrite_ep.startswith("http://lead_stream_")
    or appwrite_ep.startswith("http://appwrite")
):
    raise ImproperlyConfigured(
        "APPWRITE_ENDPOINT deve usar HTTPS em produção ou apontar para a rede interna privada."
    )

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = env_bool("DJANGO_SECURE_SSL_REDIRECT", default=True)
SECURE_REDIRECT_EXEMPT = [r"^health/"]
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
AUTH_COOKIE_SECURE = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
SECURE_HSTS_SECONDS = env_int("DJANGO_SECURE_HSTS_SECONDS", default=3600)
SECURE_HSTS_INCLUDE_SUBDOMAINS = env_bool("DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS", default=False)
SECURE_HSTS_PRELOAD = env_bool("DJANGO_SECURE_HSTS_PRELOAD", default=False)
X_FRAME_OPTIONS = "DENY"

# HSTS de subdomínios e preload permanecem opt-in: habilitá-los sem controlar todos os
# subdomínios pode bloquear serviços legítimos. O gate continua falhando para qualquer outro
# alerta de implantação.
SILENCED_SYSTEM_CHECKS = [
    "security.W005",
    "security.W021",
    "drf_spectacular.W001",
    "drf_spectacular.W002",
]
