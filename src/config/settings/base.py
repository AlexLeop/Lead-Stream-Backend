from __future__ import annotations

from pathlib import Path

import dj_database_url

from leadstream.common.env import env, env_bool, env_int, env_list
from leadstream.common.logging import build_logging_config

BASE_DIR = Path(__file__).resolve().parents[3]

SECRET_KEY = env("DJANGO_SECRET_KEY", default="dev-only-unsafe-secret-key")
DEBUG = env_bool("DJANGO_DEBUG", default=False)
configured_hosts = env_list("DJANGO_ALLOWED_HOSTS", default=["localhost", "127.0.0.1"])
if "*" in configured_hosts:
    ALLOWED_HOSTS = ["*"]
else:
    ALLOWED_HOSTS = list(dict.fromkeys(["localhost", "127.0.0.1", "testserver", *configured_hosts]))

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.staticfiles",
    "rest_framework",
    "drf_spectacular",
    "leadstream.tenancy.apps.TenancyConfig",
    "leadstream.entities.apps.EntitiesConfig",
    "leadstream.evidence.apps.EvidenceConfig",
    "leadstream.governance.apps.GovernanceConfig",
    "leadstream.batches.apps.BatchesConfig",
    "leadstream.billing.apps.BillingConfig",
    "leadstream.providers.apps.ProvidersConfig",
    "leadstream.integrations.apps.IntegrationsConfig",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "leadstream.common.request_context.RequestContextMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
ASGI_APPLICATION = "config.asgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {"context_processors": []},
    }
]

DATABASE_URL = env(
    "DATABASE_URL",
    default="postgresql://leadstream:leadstream@localhost:5432/leadstream",
)
DATABASES = {
    "default": dj_database_url.parse(
        DATABASE_URL,
        conn_max_age=env_int("DATABASE_CONN_MAX_AGE", default=60),
        conn_health_checks=True,
    )
}

CELERY_BROKER_URL = env(
    "CELERY_BROKER_URL",
    default="amqp://leadstream:leadstream@localhost:5672//",
)
REDIS_URL = env("REDIS_URL", default="redis://localhost:6379/0")
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": REDIS_URL,
    }
}
CELERY_RESULT_BACKEND = None
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_ACKS_LATE = True
CELERY_TASK_REJECT_ON_WORKER_LOST = True
CELERY_WORKER_PREFETCH_MULTIPLIER = 1
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True
CELERY_TASK_TRACK_STARTED = False
CELERY_TASK_TIME_LIMIT = env_int("CELERY_TASK_TIME_LIMIT", default=600)
CELERY_TASK_SOFT_TIME_LIMIT = env_int("CELERY_TASK_SOFT_TIME_LIMIT", default=540)
CELERY_BEAT_SCHEDULE = {
    "recover-stalled-batches": {
        "task": "leadstream.batches.recover",
        "schedule": 60.0,
    },
    "recover-stalled-discoveries": {
        "task": "leadstream.providers.recover_discovery",
        "schedule": 60.0,
    },
}
DEPENDENCY_CHECK_TIMEOUT_SECONDS = env_int("DEPENDENCY_CHECK_TIMEOUT_SECONDS", default=2)
APPWRITE_ENDPOINT = env("APPWRITE_ENDPOINT")
APPWRITE_PROJECT_ID = env("APPWRITE_PROJECT_ID")
APPWRITE_API_KEY = env("APPWRITE_API_KEY")
APPWRITE_TIMEOUT_SECONDS = env_int("APPWRITE_TIMEOUT_SECONDS", default=3)
APPWRITE_STORAGE_BUCKET_EXPORTS = env("APPWRITE_STORAGE_BUCKET_EXPORTS", default="exports")
DATA_HASH_KEY = env("DATA_HASH_KEY", default="dev-only-data-hash-key")
DATA_HASH_KEY_VERSION = env("DATA_HASH_KEY_VERSION", default="v1")
DATA_HASH_PREVIOUS_KEYS = env_list("DATA_HASH_PREVIOUS_KEYS", default=[])
BATCH_STORAGE_ROOT = Path(env("BATCH_STORAGE_ROOT", default=str(BASE_DIR / "data" / "batches")))
BATCH_MAX_UPLOAD_BYTES = env_int("BATCH_MAX_UPLOAD_BYTES", default=50 * 1024 * 1024)
BATCH_MAX_ROWS = env_int("BATCH_MAX_ROWS", default=100_000)
BATCH_LEASE_SECONDS = env_int("BATCH_LEASE_SECONDS", default=300)
BIGQUERY_PROJECT_ID = env("BIGQUERY_PROJECT_ID")
GOOGLE_CREDENTIALS_JSON = env("GOOGLE_CREDENTIALS_JSON")
GOOGLE_APPLICATION_CREDENTIALS = env("GOOGLE_APPLICATION_CREDENTIALS")
OPEN_CNPJ_BIGQUERY_SQL = env("OPEN_CNPJ_BIGQUERY_SQL")
OPEN_CNPJ_DISCOVERY_SQL = env("OPEN_CNPJ_DISCOVERY_SQL")
BIGQUERY_MAXIMUM_BYTES_BILLED = env_int("BIGQUERY_MAXIMUM_BYTES_BILLED", default=10_000_000_000)
BIGQUERY_TIMEOUT_SECONDS = env_int("BIGQUERY_TIMEOUT_SECONDS", default=60)
BIGQUERY_COST_CENTS_PER_TIB = env_int("BIGQUERY_COST_CENTS_PER_TIB", default=3500)
BIGQUERY_COST_CENTS = env_int("BIGQUERY_COST_CENTS", default=0)
BIGQUERY_PROVIDER_PRIORITY = env_int("BIGQUERY_PROVIDER_PRIORITY", default=10)
BIGQUERY_CONFIDENCE = env_int("BIGQUERY_CONFIDENCE", default=100)

BIGDATACORP_BASE_URL = env("BIGDATACORP_BASE_URL", default="https://plataforma.bigdatacorp.com.br")
BIGDATACORP_ACCESS_TOKEN = env("BIGDATACORP_ACCESS_TOKEN")
BIGDATACORP_TOKEN_ID = env("BIGDATACORP_TOKEN_ID")
BIGDATACORP_DATASETS = env("BIGDATACORP_DATASETS", default="basic_data,relationships")
BIGDATACORP_TIMEOUT_SECONDS = env_int("BIGDATACORP_TIMEOUT_SECONDS", default=30)
BIGDATACORP_COST_CENTS = env_int("BIGDATACORP_COST_CENTS", default=0)
BIGDATACORP_PROVIDER_PRIORITY = env_int("BIGDATACORP_PROVIDER_PRIORITY", default=20)
BIGDATACORP_CONFIDENCE = env_int("BIGDATACORP_CONFIDENCE", default=80)

APIFY_BASE_URL = env("APIFY_BASE_URL", default="https://api.apify.com/v2")
APIFY_TOKEN = env("APIFY_TOKEN")
APIFY_DECISION_MAKER_ACTOR_ID = env("APIFY_DECISION_MAKER_ACTOR_ID")
APIFY_TIMEOUT_SECONDS = env_int("APIFY_TIMEOUT_SECONDS", default=300)
APIFY_MAX_RESULTS_PER_COMPANY = env_int("APIFY_MAX_RESULTS_PER_COMPANY", default=10)
APIFY_COST_CENTS = env_int("APIFY_COST_CENTS", default=0)
APIFY_USD_RATE_CENTS = env_int("APIFY_USD_RATE_CENTS", default=600)
APIFY_RUN_TIMEOUT_SECONDS = env_int("APIFY_RUN_TIMEOUT_SECONDS", default=300)
APIFY_DATASET_PAGE_SIZE = env_int("APIFY_DATASET_PAGE_SIZE", default=100)
APIFY_POLL_SECONDS = env_int("APIFY_POLL_SECONDS", default=10)
APIFY_PROVIDER_PRIORITY = env_int("APIFY_PROVIDER_PRIORITY", default=30)
APIFY_CONFIDENCE = env_int("APIFY_CONFIDENCE", default=70)

OPEN_ENRICH_URL = env("OPEN_ENRICH_URL")
OPEN_ENRICH_TOKEN = env("OPEN_ENRICH_TOKEN")
OPEN_ENRICH_COST_CENTS = env_int("OPEN_ENRICH_COST_CENTS", default=0)
OPEN_ENRICH_TIMEOUT_SECONDS = env_int("OPEN_ENRICH_TIMEOUT_SECONDS", default=30)
OPEN_ENRICH_CONFIDENCE = env_int("OPEN_ENRICH_CONFIDENCE", default=75)
OPEN_ENRICH_PROVIDER_PRIORITY = env_int("OPEN_ENRICH_PROVIDER_PRIORITY", default=40)

PREMIUM_ENRICH_URL = env("PREMIUM_ENRICH_URL")
PREMIUM_ENRICH_TOKEN = env("PREMIUM_ENRICH_TOKEN")
PREMIUM_ENRICH_COST_CENTS = env_int("PREMIUM_ENRICH_COST_CENTS", default=0)
PREMIUM_ENRICH_TIMEOUT_SECONDS = env_int("PREMIUM_ENRICH_TIMEOUT_SECONDS", default=30)
PREMIUM_ENRICH_CONFIDENCE = env_int("PREMIUM_ENRICH_CONFIDENCE", default=85)
PREMIUM_ENRICH_PROVIDER_PRIORITY = env_int("PREMIUM_ENRICH_PROVIDER_PRIORITY", default=50)

CRM_CONNECTOR_DEFAULT_TIMEOUT_SECONDS = env_int("CRM_CONNECTOR_DEFAULT_TIMEOUT_SECONDS", default=10)
LOG_LEVEL = env("LOG_LEVEL", default="INFO")
LOGGING = build_logging_config(LOG_LEVEL)

LANGUAGE_CODE = "pt-br"
TIME_ZONE = "America/Sao_Paulo"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.AllowAny"],
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "UNAUTHENTICATED_USER": None,
    "DEFAULT_PAGINATION_CLASS": "leadstream.common.pagination.StandardPagination",
    "PAGE_SIZE": 50,
}

API_DESCRIPTION = """
### Visão Geral

LeadStream é uma API REST para extração, higienização, descoberta e enriquecimento
de dados cadastrais de empresas e decisores corporativos no Brasil.

---

### Autenticação e Multi-tenancy
- Requisições autenticadas devem enviar o cabeçalho HTTP `X-Tenant-ID: <UUID>`
  especificando o workspace do cliente.
- Na ausência do cabeçalho em ambiente de testes ou desenvolvimento, o sistema assume
  o contexto do workspace operacional interno (`00000000-0000-4000-8000-000000000001`).

---

### Modos de Operação
1. **Lotes e Enriquecimento em Massa (`/api/v1/lotes/`)**: Ingestão assíncrona de arquivos
   CSV, validação cadastral de CNPJ, enriquecimento em cascata e exportação tabular.
2. **Descobertas Cadastrais (`/api/v1/descobertas/`)**: Filtragem em bases públicas oficiais
   por CNAE, localização e porte, com materialização direta em novos lotes de leads.
3. **Consulta de Entidades (`/api/v1/dados/`)**: Consulta pontual e estruturação de empresas,
   quadro societário, canais de contato direto e perfis profissionais de decisores.
4. **Integrações e Webhooks (`/api/v1/integracoes/`)**: Conexões com CRMs (HubSpot,
   Pipedrive, RD Station, Salesforce, Ploomes) e disparos com garantia de entrega transacional
   via outbox e assinatura HMAC-SHA256 (`X-LeadStream-Signature`).
"""

SPECTACULAR_SETTINGS = {
    "TITLE": "LeadStream API Reference",
    "DESCRIPTION": API_DESCRIPTION,
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "SWAGGER_UI_SETTINGS": {
        "deepLinking": True,
        "persistAuthorization": True,
        "displayRequestDuration": True,
        "filter": True,
        "docExpansion": "none",
        "defaultModelsExpandDepth": 2,
        "defaultModelExpandDepth": 2,
    },
    "TAGS": [
        {
            "name": "Lotes",
            "description": (
                "Ingestão de arquivos CSV, fatiamento em chunks, ciclo de vida e exportações."
            ),
        },
        {
            "name": "Descobertas",
            "description": (
                "Busca por CNAE, UF, porte e situação cadastral com materialização em lotes."
            ),
        },
        {
            "name": "Empresas",
            "description": "Consulta e estruturação de empresas e estabelecimentos (CNPJ).",
        },
        {
            "name": "Pessoas",
            "description": "Decisores, executivos e sócios normalizados.",
        },
        {
            "name": "Vínculos",
            "description": "Relações societárias e profissionais entre pessoas e empresas.",
        },
        {
            "name": "Contatos",
            "description": "Canais de contato direto (e-mails corporativos e telefones).",
        },
        {
            "name": "Perfis sociais",
            "description": "Perfis profissionais e públicos de decisores.",
        },
        {
            "name": "Integrações - Conexões CRM",
            "description": "Gestão de conexões com CRMs e Webhooks Universais.",
        },
        {
            "name": "Cockpit do CEO - Métricas de Integrações",
            "description": "Telemetria consolidada da outbox, DLQ e taxas de entrega.",
        },
        {
            "name": "Faturamento",
            "description": (
                "Tabelas de preços por bloco de dados, auditoria de chamadas e margem por lote."
            ),
        },
        {
            "name": "Evidências e governança",
            "description": (
                "Proveniência de dados, cálculo de confiança, resolução de conflitos, "
                "supressões e políticas LGPD."
            ),
        },
        {
            "name": "Operação interna",
            "description": (
                "Consultas de workspace, metadados de infraestrutura e probes de saúde do sistema."
            ),
        },
    ],
    "ENUM_NAME_OVERRIDES": {
        "ContactStatusEnum": "leadstream.entities.models.CONTACT_POINT_STATUS_CHOICES",
        "EvidenceStatusEnum": "leadstream.evidence.models.EvidenceStatus.choices",
        "ConflictStatusEnum": ["OPEN", "RESOLVED"],
        "RetentionRunStatusEnum": ["RUNNING", "COMPLETED", "FAILED"],
        "ContactPointScopeEnum": "leadstream.entities.models.CONTACT_POINT_SCOPE_CHOICES",
        "SuppressionScopeEnum": "leadstream.governance.models.SUPPRESSION_SCOPE_CHOICES",
        "DataBlockEnum": "leadstream.billing.models.DATA_BLOCK_CHOICES",
        "ProviderCallStatusEnum": "leadstream.billing.models.PROVIDER_CALL_STATUS_CHOICES",
    },
}
