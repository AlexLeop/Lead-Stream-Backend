from __future__ import annotations

from datetime import timedelta
from pathlib import Path
from typing import Any

import dj_database_url
from corsheaders.defaults import default_headers

from leadstream.common.env import env, env_bool, env_int, env_list
from leadstream.common.logging import build_logging_config

BASE_DIR = Path(__file__).resolve().parents[3]

SECRET_KEY = env(
    "DJANGO_SECRET_KEY", default="dev-only-unsafe-secret-key-that-is-at-least-32-chars-long"
)
DEBUG = env_bool("DJANGO_DEBUG", default=False)
configured_hosts = env_list("DJANGO_ALLOWED_HOSTS", default=["localhost", "127.0.0.1"])
if "*" in configured_hosts:
    ALLOWED_HOSTS = ["*"]
else:
    ALLOWED_HOSTS = list(dict.fromkeys(["localhost", "127.0.0.1", "testserver", *configured_hosts]))

INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.staticfiles",
    "corsheaders",
    "rest_framework",
    "rest_framework_simplejwt",
    "rest_framework_simplejwt.token_blacklist",
    "drf_spectacular",
    "leadstream.tenancy.apps.TenancyConfig",
    "leadstream.security.apps.SecurityConfig",
    "leadstream.entities.apps.EntitiesConfig",
    "leadstream.evidence.apps.EvidenceConfig",
    "leadstream.governance.apps.GovernanceConfig",
    "leadstream.batches.apps.BatchesConfig",
    "leadstream.billing.apps.BillingConfig",
    "leadstream.providers.apps.ProvidersConfig",
    "leadstream.integrations.apps.IntegrationsConfig",
    "leadstream.analytics.apps.AnalyticsConfig",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "leadstream.common.request_context.RequestContextMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
ASGI_APPLICATION = "config.asgi.application"

_empty_context_processors: list[str] = []
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {"context_processors": _empty_context_processors},
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
    "recover-stalled-enrichment-jobs": {
        "task": "leadstream.providers.recover_enrichment_jobs",
        "schedule": 60.0,
    },
    "purge-expired-enrichment-payloads": {
        "task": "leadstream.providers.purge_enrichment_payloads",
        "schedule": 3600.0,
    },
    "process-crm-outbox": {
        "task": "leadstream.integrations.process_crm_outbox_batch",
        "schedule": 30.0,
        "kwargs": {"batch_size": 50},
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
# A primeira chave cifra novos valores; as demais permitem rotação e leitura histórica.
# A chave pública abaixo existe somente para desenvolvimento local e é substituída em produção.
FIELD_ENCRYPTION_KEYS = env_list(
    "FIELD_ENCRYPTION_KEYS",
    default=["OkGiQUn8hkcGWPMhkXlYkVh9lBo2Cmjo-6O3F0PQRpY="],
)
BATCH_STORAGE_ROOT = Path(env("BATCH_STORAGE_ROOT", default=str(BASE_DIR / "data" / "batches")))
BATCH_MAX_UPLOAD_BYTES = env_int("BATCH_MAX_UPLOAD_BYTES", default=50 * 1024 * 1024)
BATCH_MAX_ROWS = env_int("BATCH_MAX_ROWS", default=100_000)
BATCH_LEASE_SECONDS = env_int("BATCH_LEASE_SECONDS", default=300)
ENRICHMENT_JOB_LEASE_SECONDS = env_int("ENRICHMENT_JOB_LEASE_SECONDS", default=600)
ENRICHMENT_JOB_RETENTION_DAYS = env_int("ENRICHMENT_JOB_RETENTION_DAYS", default=30)
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
BIGDATACORP_PERSON_DATASETS = env(
    "BIGDATACORP_PERSON_DATASETS",
    default=(
        "basic_data,phones_extended,addresses_extended,financial_data,financial_risk,"
        "social_assistance_extended,profession_data,university_student_data"
    ),
)
BIGDATACORP_PERSON_ONDEMAND_DATASETS = env(
    "BIGDATACORP_PERSON_ONDEMAND_DATASETS",
    default="ondemand_tse_polling_place_person",
)
# Opt-in explícito: os datasets restritivos de marketplace têm custo unitário elevado.
BIGDATACORP_PERSON_CREDIT_DATASETS = env(
    "BIGDATACORP_PERSON_CREDIT_DATASETS", default=""
)
BIGDATACORP_PERSON_RESPONSE_V2 = env_bool(
    "BIGDATACORP_PERSON_RESPONSE_V2", default=True
)
BIGDATACORP_TIMEOUT_SECONDS = env_int("BIGDATACORP_TIMEOUT_SECONDS", default=30)
BIGDATACORP_COST_CENTS = env_int("BIGDATACORP_COST_CENTS", default=0)
BIGDATACORP_PROVIDER_PRIORITY = env_int("BIGDATACORP_PROVIDER_PRIORITY", default=20)
BIGDATACORP_CONFIDENCE = env_int("BIGDATACORP_CONFIDENCE", default=80)

# WhatsApp Probe Gateway (Evolution API, EvolutionGo, WPPConnect)
WHATSAPP_PROBE_PROVIDER = env("WHATSAPP_PROBE_PROVIDER", default="evolution")
WHATSAPP_PROBE_URL = env("WHATSAPP_PROBE_URL")
WHATSAPP_PROBE_API_KEY = env("WHATSAPP_PROBE_API_KEY")
WHATSAPP_PROBE_INSTANCE = env("WHATSAPP_PROBE_INSTANCE", default="leadstream")
WHATSAPP_PROBE_TIMEOUT_SECONDS = env_int("WHATSAPP_PROBE_TIMEOUT_SECONDS", default=10)

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

# Portal da Transparência — API oficial da Controladoria-Geral da União.
PORTAL_TRANSPARENCIA_BASE_URL = env(
    "PORTAL_TRANSPARENCIA_BASE_URL",
    default="https://api.portaldatransparencia.gov.br/api-de-dados",
)
PORTAL_TRANSPARENCIA_TOKEN = env("PORTAL_TRANSPARENCIA_TOKEN")
PORTAL_TRANSPARENCIA_TIMEOUT_SECONDS = env_int(
    "PORTAL_TRANSPARENCIA_TIMEOUT_SECONDS", default=20
)
PORTAL_TRANSPARENCIA_COST_CENTS = env_int("PORTAL_TRANSPARENCIA_COST_CENTS", default=0)
PORTAL_TRANSPARENCIA_PROVIDER_PRIORITY = env_int(
    "PORTAL_TRANSPARENCIA_PROVIDER_PRIORITY", default=15
)
PORTAL_TRANSPARENCIA_DAY_RPM = env_int("PORTAL_TRANSPARENCIA_DAY_RPM", default=400)
PORTAL_TRANSPARENCIA_NIGHT_RPM = env_int("PORTAL_TRANSPARENCIA_NIGHT_RPM", default=700)
PORTAL_TRANSPARENCIA_RESTRICTED_RPM = env_int(
    "PORTAL_TRANSPARENCIA_RESTRICTED_RPM", default=180
)
PORTAL_TRANSPARENCIA_CACHE_SECONDS = env_int(
    "PORTAL_TRANSPARENCIA_CACHE_SECONDS", default=86_400
)
PORTAL_TRANSPARENCIA_MAX_PAGES = env_int("PORTAL_TRANSPARENCIA_MAX_PAGES", default=5)
PORTAL_TRANSPARENCIA_MAX_DETAIL_RECORDS = env_int(
    "PORTAL_TRANSPARENCIA_MAX_DETAIL_RECORDS", default=3
)
PORTAL_TRANSPARENCIA_REMUNERATION_LOOKBACK_MONTHS = env_int(
    "PORTAL_TRANSPARENCIA_REMUNERATION_LOOKBACK_MONTHS", default=3
)
PORTAL_TRANSPARENCIA_EXPENSE_LOOKBACK_YEARS = env_int(
    "PORTAL_TRANSPARENCIA_EXPENSE_LOOKBACK_YEARS", default=2
)

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
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "leadstream.security.authentication.CombinedAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "leadstream.security.permissions.TenantAccessPermission",
    ],
    "DEFAULT_THROTTLE_CLASSES": [
        "leadstream.security.throttling.TenantApiKeyRateThrottle",
    ],
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "UNAUTHENTICATED_USER": None,
    "DEFAULT_PAGINATION_CLASS": "leadstream.common.pagination.StandardPagination",
    "PAGE_SIZE": 50,
    "DEFAULT_THROTTLE_RATES": {
        "auth": "5/min",
        "auth_refresh": "10/min",
        "tenant": "120/min",
    },
}

CORS_ALLOWED_ORIGINS = env_list("CORS_ALLOWED_ORIGINS", default=[])
CORS_ALLOW_ALL_ORIGINS = env_bool("CORS_ALLOW_ALL_ORIGINS", default=DEBUG)
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_HEADERS = env_list(
    "CORS_ALLOW_HEADERS",
    default=[
        *default_headers,
        "idempotency-key",
        "x-tenant",
        "x-workspace-id",
        "x-request-id",
        "x-correlation-id",
    ],
)
CORS_EXPOSE_HEADERS = env_list(
    "CORS_EXPOSE_HEADERS",
    default=[
        "content-disposition",
        "x-total-count",
        "x-request-id",
    ],
)

SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"

AUTHENTICATION_BACKENDS = [
    "leadstream.security.backends.EmailOrUsernameModelBackend",
    "django.contrib.auth.backends.ModelBackend",
]

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=env_int("JWT_ACCESS_MINUTES", default=30)),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=env_int("JWT_REFRESH_DAYS", default=14)),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "UPDATE_LAST_LOGIN": True,
    "ALGORITHM": "HS256",
    "SIGNING_KEY": SECRET_KEY,
    "AUTH_HEADER_TYPES": ("Bearer",),
    "USER_ID_FIELD": "id",
    "USER_ID_CLAIM": "user_id",
}
AUTH_REFRESH_COOKIE_NAME = env("AUTH_REFRESH_COOKIE_NAME", default="leadstream_refresh")
AUTH_COOKIE_SECURE = env_bool("AUTH_COOKIE_SECURE", default=False)
AUTH_COOKIE_SAMESITE = env("AUTH_COOKIE_SAMESITE", default="Strict")
AUTH_COOKIE_DOMAIN = env("AUTH_COOKIE_DOMAIN")
AUTH_COOKIE_PATH = env("AUTH_COOKIE_PATH", default="/api/v1/auth/")

API_DESCRIPTION = """
# LeadStream API — Plataforma Enterprise de Inteligência Cadastral & Leads B2B

O **LeadStream Backend** é o núcleo analítico e operacional independente, *Brasil-first*, desenvolvido para extração, higienização, descoberta, enriquecimento e governança de dados empresariais e decisores corporativos.

A API parte de uma empresa brasileira real (CNPJ), resolve seus estabelecimentos, quadro societário (QSA), descobre seus decisores e executivos C-level, identifica canais diretos de contato atribuíveis e perfis profissionais públicos (LinkedIn), consolidando todas as evidências com proveniência de fontes, score de confiança, tarifação por bloco útil e conformidade LGPD.

---

### 🔑 Autenticação Híbrida & Multi-tenancy Enterprise

O LeadStream opera com arquitetura multi-tenant com autenticação híbrida e controle de acesso RBAC estrito:
- **Autenticação Humana (JWT):** Login através de `/api/v1/auth/token/` (Access token: 30m, Refresh token: 14 dias) com rotação e blacklist.
- **Autenticação Máquina / Integrações (API Keys):** Chaves criptográficas prefixadas (`ls_live_...` e `ls_test_...`) com hash SHA-256 no banco e timing-safe comparison.
- **Headers Aceitos:** `Authorization: Bearer <token_jwt_ou_api_key>` ou `X-API-Key: <api_key>`.
- **Prevenção Total de IDOR:** Cada requisição amarra-se ao tenant autorizado da credencial; Super Administradores podem chavear contexto com `X-Tenant-ID`.
- **Proteção Anti-Abuso:** Throttling no Redis com limite de 5 req/min no login e 120 req/min por tenant.

---

### 🚀 Ciclo Operacional & Arquitetura de Dados

O processamento no LeadStream segue um fluxo em 6 estágios de alta confiabilidade:

1. **Ingestão & Fatiamento (`/api/v1/lotes/`):**
   Upload de arquivos CSV com até 100.000 CNPJs. Os arquivos são fatiados em chunks idempotentes (25–100 leads) e distribuídos para workers assíncronos (Celery + RabbitMQ), tolerantes a reinícios e falhas transitórias de rede.
2. **Higienização & Deduplicação:**
   Normalização rigorosa de CNPJs (com separação de raiz, ordem e dígito verificador módulo 11), padronização de razões sociais, nomes de sócios, formatação de CEP e endereços, e separação estrita de DDD e número de telefone (dígitos puros, sem hífens, sinais de soma ou espaços).
3. **Enriquecimento em Cascata de Provedores:**
   Orquestração inteligente com fallback automático e teto orçamentário configurável por lead:
   - **Camada 1 (Bases Públicas Oficiais / OpenCNPJ BigQuery):** Dados cadastrais da RFB, QSA oficial, CNAEs secundários, capital social, porte e situação cadastral em milissegundos.
   - **Camada 2 (BigDataCorp):** Enriquecimento aprofundado com inteligência de crédito, processos judiciais, presença digital e telefones operacionais.
   - **Camada 3 (Apify / Google Search & LinkedIn):** Descoberta de perfis profissionais públicos de decisores com higienização de URLs (eliminação de subdomínios geográficos e sufixos de idioma como `/en` ou `/pt`).
4. **Resolução de Entidades & Governança LGPD (`/api/v1/dados/`):**
   Separação clara entre fatos observados, evidências e dados inferidos. Gestão de bases legais (Art. 7º, IX da LGPD — Legítimo Interesse para prospecção B2B comercial), canal de supressão (*opt-out* de titulares) e política estrita de retenção de dados temporais.
5. **Materialização Canônica v2.4.0 (`/api/v1/leads/{lead_id}/canonical/`):**
   Estrutura consolidada unificada de 14 blocos de inteligência pronta para consumo analítico e operacional por equipes de SDRs, pré-vendas e inteligência de mercado.
6. **Integrações & Outbox Transacional (`/api/v1/integracoes/`):**
   Sincronização assíncrona com CRMs líderes (HubSpot, Pipedrive, Salesforce, RD Station, Ploomes) com padrão Transactional Outbox, reentregas exponenciais, Dead Letter Queue (DLQ) e assinatura criptográfica HMAC-SHA256 (`X-LeadStream-Signature`).

---

### 📦 Estrutura do Payload Canônico v2.4.0 (14 Blocos)

| Bloco | Chave no Payload | Descrição dos Dados |
| :--- | :--- | :--- |
| **01. Metadados** | `_meta` | UUID canônico, timestamp ISO 8601, tenant e score global de confiança da consolidação. |
| **02. Identificação & ICP** | `identification` | Lead score comercial (0 a 100), temperatura do lead (`COLD`/`WARM`/`HOT`), fit percentual de ICP e tags. |
| **03. Dados da Empresa** | `company` | CNPJ formatado e partes separadas, Razão Social, Nome Fantasia, data de abertura, idade, porte Sebrae, regime tributário (Simples/Simei), capital social, faturamento anual estimado, colaboradores e website. |
| **04. Inteligência Financeira & Bancária** | `financial_and_banking` | Bancos de relacionamento identificados (ex: Nu Pagamentos/Nubank, Itaú), linhas de crédito ativas, score de risco de crédito, capacidade de pagamento e protestos em cartório. |
| **05. Inteligência Fiscal & Tributária** | `fiscal_and_tax_intelligence` | Situação fiscal federal, dívida ativa na PGFN, certidão negativa de débitos (CND), certidão de regularidade do FGTS (CRF), Inscrição Estadual (SINTEGRA) e Inscrição Municipal. |
| **06. CNAE & Atividades Econômicas** | `cnae` | CNAE Principal detalhado (com classificação setorial e grau de risco de trabalho 1-4) e lista completa de CNAEs secundários. |
| **07. Endereço & Localização** | `address` | Endereço higienizado com tipo de logradouro, número, complemento, bairro, município, UF, CEP formatado, código IBGE e precisão de geocodificação. |
| **08. Contatos Validados** | `contacts` | Telefones com DDD separado e número em dígitos puros (sem `-`, `+` ou espaços, status WhatsApp e operadora ANATEL) e e-mails com status de entregabilidade, MX ativo e verificação anti-descarte. |
| **09. Decisores & QSA** | `decision_makers_qsa` | Sócios e administradores mapeados com qualificação, cargo executivo de mercado, contatos diretos higienizados (DDD celular, número WhatsApp) e URL de perfil LinkedIn público validado. |
| **10. Comércio Exterior & Logística** | `foreign_trade_and_logistics` | Habilitação no Radar SISCOMEX, histórico de importação/exportação nos últimos 12 meses e frota de veículos cadastrada por tipo. |
| **11. Jurídico & Judicial** | `legal_and_judicial` | Contagem de processos ativos como réu/autor (cíveis, trabalhistas, fiscais), índice de judicialização, recuperação judicial e auditoria de trabalho escravo / IBAMA. |
| **12. Presença Digital & Stack Tecnológico** | `digital_presence_and_tech_stack` | Tecnologias detectadas no domínio, redes sociais da empresa, servidores web e certificados SSL válidos. |
| **13. Governança LGPD & Compliance** | `governance_lgpd_and_compliance` | Base legal de prospecção comercial B2B (art. 7º IX), canal de opt-out, prazo de retenção e hash de rastreabilidade. |
| **14. Integrações CRM** | `crm_outbox_integration` | Status de sincronização com CRMs externos, identificadores remotos e chave de idempotência. |

---

### 🛡️ Tratamento de Erros e Códigos HTTP

A API adota os códigos padronizados do protocolo HTTP:
- `200 OK`: Consulta realizada com sucesso e corpo retornado.
- `201 Created`: Recurso cadastrado ou lote inicializado com sucesso.
- `202 Accepted`: Requisição assíncrona aceita e enfileirada para processamento.
- `400 Bad Request`: Parâmetros inválidos, corpo JSON malformatado ou CNPJ inconsistente.
- `401 Unauthorized / 403 Forbidden`: Workspace (tenant) ausente, inválido ou inativo.
- `404 Not Found`: Recurso não localizado para o workspace informado.
- `422 Unprocessable Entity`: Regra de negócio ou integridade violada (ex: teto orçamentário estourado).
- `503 Service Unavailable`: Serviço temporariamente indisponível ou dependência essencial inacessível.
"""

_empty_security_scopes: list[str] = []
SPECTACULAR_SETTINGS: dict[str, Any] = {
    "TITLE": "LeadStream API Reference — Inteligência Cadastral B2B",
    "DESCRIPTION": API_DESCRIPTION,
    "VERSION": "2.4.0",
    "OAS_VERSION": "3.1.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "SERVE_PERMISSIONS": ["rest_framework.permissions.AllowAny"],
    "SECURITY": [{"BearerAuth": _empty_security_scopes}, {"ApiKeyAuth": _empty_security_scopes}],
    "APPEND_COMPONENTS": {
        "securitySchemes": {
            "BearerAuth": {
                "type": "http",
                "scheme": "bearer",
                "bearerFormat": "JWT",
                "description": "Token JWT de acesso ou API Key (formato Bearer ls_live_...)",
            },
            "ApiKeyAuth": {
                "type": "apiKey",
                "in": "header",
                "name": "X-API-Key",
                "description": "Chave de API criptográfica (formato ls_live_... ou ls_test_...)",
            },
            "TenantHeader": {
                "type": "apiKey",
                "in": "header",
                "name": "X-Tenant-ID",
                "description": (
                    "UUID ou slug identificador do workspace do cliente (ex: "
                    "`00000000-0000-4000-8000-000000000001` ou `interno`). "
                    "Utilizado para chaveamento de tenant por Super Administradores."
                ),
            },
        }
    },
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
            "name": "Leads Canônicos",
            "description": (
                "Consulta do Lead Canônico v2.4.0 consolidado com 14 blocos de inteligência de dados, "
                "incluindo identificação, empresa, inteligência bancária, fiscal, CNAEs, contatos validados "
                "com DDD separado, QSA com LinkedIn público e outbox CRM."
            ),
        },
        {
            "name": "Lotes",
            "description": (
                "Ingestão assíncrona de arquivos CSV com até 100 mil empresas, fatiamento em chunks idempotentes, "
                "monitoramento de progresso e geração de exportações tabulares."
            ),
        },
        {
            "name": "Descoberta",
            "description": (
                "Prospecção orientada a filtros em bases públicas oficiais da Receita Federal por CNAE fiscal, "
                "unidade federativa (UF), município e porte, com materialização direta em lotes de leads."
            ),
        },
        {
            "name": "Enriquecimento",
            "description": (
                "Disparo manual ou sob demanda de enriquecimento em cascata para leads e itens de lote."
            ),
        },
        {
            "name": "Provedores",
            "description": (
                "Gerenciamento de provedores externos (BigQuery OpenCNPJ, BigDataCorp, Apify), políticas de cascata, "
                "prioridades e controle de orçamento por chamada."
            ),
        },
        {
            "name": "Provedores — métricas",
            "description": (
                "Telemetria de provedores: tempo de resposta, taxas de sucesso, erros e custos faturados."
            ),
        },
        {
            "name": "Dados — empresas",
            "description": (
                "Cadastro operacional de empresas e estabelecimentos (matrizes e filiais) por CNPJ."
            ),
        },
        {
            "name": "Dados — pessoas",
            "description": (
                "Pessoas físicas mapeadas, decisores de mercado, executivos C-level e sócios normalizados."
            ),
        },
        {
            "name": "Dados — vínculos",
            "description": (
                "Relações societárias, administrativas e profissionais entre pessoas e empresas."
            ),
        },
        {
            "name": "Dados — contatos",
            "description": (
                "Pontos de contato corporativos (e-mails corporativos e telefones com DDD separado e dígitos limpos)."
            ),
        },
        {
            "name": "Dados — perfis sociais",
            "description": (
                "Perfis profissionais públicos comprováveis (LinkedIn verificado sem sufixos de país)."
            ),
        },
        {
            "name": "Dados — governança",
            "description": (
                "Definição de finalidades de uso legítimo e políticas de retenção temporal de dados."
            ),
        },
        {
            "name": "Dados — fontes",
            "description": (
                "Catálogo de fontes de dados públicas e privadas com termos de uso e prioridade."
            ),
        },
        {
            "name": "Dados — evidências",
            "description": (
                "Trilha de auditoria e proveniência detalhada de cada informação coletada de fontes externas."
            ),
        },
        {
            "name": "Dados — observações",
            "description": (
                "Valores observados em fontes com instante de coleta, estado de validação e confiança."
            ),
        },
        {
            "name": "Dados — canonização",
            "description": (
                "Decisões automáticas de canonização de atributos com resolução de fontes conflitantes."
            ),
        },
        {
            "name": "Dados — conflitos",
            "description": (
                "Gestão de divergências entre fontes com histórico de resolução e auditoria."
            ),
        },
        {
            "name": "Dados — supressão",
            "description": (
                "Gestão de supressões e opt-out de titulares de dados em conformidade com a LGPD."
            ),
        },
        {
            "name": "Dados — retenção",
            "description": (
                "Execuções periódicas de expiração e purga de dados conforme políticas de retenção."
            ),
        },
        {
            "name": "Faturamento",
            "description": (
                "Tabelas de preços por bloco de dados entregue, auditoria de chamadas tarifadas e margem bruta por lote."
            ),
        },
        {
            "name": "Integrações - Conexões CRM",
            "description": (
                "Gerenciamento de conexões com CRMs parceiros (HubSpot, Pipedrive, Salesforce, RD Station, Ploomes)."
            ),
        },
        {
            "name": "Integrações - Mapeamento de Campos",
            "description": (
                "Configuração de equivalência de campos entre o modelo canônico do LeadStream e os objetos do CRM."
            ),
        },
        {
            "name": "Integrações - Outbox Transacional",
            "description": (
                "Fila transacional outbox garantindo entrega exatamente-uma-vez e resiliência a falhas no CRM."
            ),
        },
        {
            "name": "Integrações - Disparo para CRM",
            "description": (
                "Disparos imediatos e reprocessamento de eventos com assinatura HMAC-SHA256."
            ),
        },
        {
            "name": "Cockpit do CEO - Métricas de Integrações",
            "description": (
                "Telemetria em tempo real das integrações: volume de eventos, taxa de sucesso, latência e DLQ."
            ),
        },
        {
            "name": "Saúde",
            "description": (
                "Endpoints operacionais de liveness, readiness e diagnóstico de dependências de infraestrutura."
            ),
        },
        {
            "name": "Operação interna",
            "description": (
                "Consultas de workspace, metadados de infraestrutura e parâmetros internos de execução."
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
