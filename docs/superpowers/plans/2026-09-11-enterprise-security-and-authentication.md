# Enterprise Security & Hybrid Authentication Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implementar arquitetura de segurança enterprise completa no LeadStream Backend: autenticação híbrida (JWT com rotação de refresh tokens + API Keys criptográficas com hash SHA-256), controle de acesso RBAC por workspace/tenant, fim do fallback permissivo de tenant, rate limiting anti-abuso no Redis, CORS, headers defensivos e trilha de auditoria LGPD.

**Architecture:** Módulo dedicado `leadstream.security` integrando `djangorestframework-simplejwt` e `django-cors-headers`. O autenticador `CombinedAuthentication` inspeciona o header `Authorization` (JWT ou API Key `ls_...`) e `X-API-Key`, injetando com segurança o `request.tenant` no contexto da requisição. Rotas sensíveis exigem pertinência ao tenant com prevenção total de IDOR.

**Tech Stack:** Python 3.13, Django 5.2 LTS, Django REST Framework 3.18, `djangorestframework-simplejwt` 5.4, `django-cors-headers` 4.7, Redis 8.x, PostgreSQL 17+, drf-spectacular 0.30.

**Spec:** `docs/superpowers/specs/2026-09-11-enterprise-security-and-authentication-design.md`

## Global Constraints
- Nenhuma chave bruta ou segredo pode ser versionado ou persistido em texto claro no banco de dados.
- O campo `hashed_key` armazena exclusivamente o hash SHA-256 do segredo completo.
- Toda rota protegida rejeita requisições não autenticadas com `401 Unauthorized` (fim do fallback automático para tenant interno).
- O Super Admin do sistema tem acesso irrestrito auditado com capacidade de chavear tenants via `X-Tenant-ID`.
- A suíte de 117 testes existentes deve permanecer 100% verde sem regressões.
- Todo código deve seguir lint `ruff check .` e tipagem estrita.

---

### Task 1: Dependências e Configurações de Borda (CORS & Headers)

**Files:**
- Modify: `pyproject.toml:11-28`
- Modify: `src/config/settings/base.py:15-45, 170-185`
- Test: `tests/test_production_settings.py`

**Interfaces:**
- Consumes: Configurações existentes do Django e DRF.
- Produces: `CorsMiddleware` habilitado, `REST_FRAMEWORK` configurado com autenticação padrão, `SIMPLE_JWT` e `CORS_*` definidos.

- [ ] **Step 1: Adicionar dependências no pyproject.toml**
  Adicionar `"djangorestframework-simplejwt>=5.4,<6.0"` e `"django-cors-headers>=4.7,<5.0"`.
- [ ] **Step 2: Instalar pacotes no ambiente virtual**
  Executar `.venv\Scripts\pip.exe install "djangorestframework-simplejwt>=5.4" "django-cors-headers>=4.7"`.
- [ ] **Step 3: Configurar base.py**
  Adicionar `"corsheaders"` e `"rest_framework_simplejwt"` em `INSTALLED_APPS`.
  Adicionar `"corsheaders.middleware.CorsMiddleware"` no topo de `MIDDLEWARE` antes de `CommonMiddleware`.
  Configurar `CORS_ALLOWED_ORIGINS`, `CORS_ALLOW_ALL_ORIGINS`, `SECURE_CONTENT_TYPE_NOSNIFF`, `X_FRAME_OPTIONS = "DENY"`.
  Configurar `SIMPLE_JWT` (access token: 30min, refresh token: 14 dias, rotação ativa, blacklist ativa).
- [ ] **Step 4: Executar testes de configurações**
  Executar `.venv\Scripts\pytest.exe tests/test_production_settings.py`.
- [ ] **Step 5: Commit das configurações**
  `git add pyproject.toml src/config/settings/base.py && git commit -m "chore(deps): adicionar simplejwt e corsheaders com politicas defensivas"`

---

### Task 2: Modelagem de Dados de Segurança (`leadstream.security`)

**Files:**
- Create: `src/leadstream/security/__init__.py`
- Create: `src/leadstream/security/apps.py`
- Create: `src/leadstream/security/models.py`
- Create: `src/leadstream/security/crypto.py`
- Create: `src/leadstream/security/migrations/0001_initial.py`
- Test: `tests/test_security_models.py`

**Interfaces:**
- Consumes: `leadstream.tenancy.models.Tenant`, `django.contrib.auth.models.User`.
- Produces: `WorkspaceMembership`, `APIKey`, `SecurityAuditLog`, funções `generate_api_key(tenant, name, role, env)` e `hash_api_key(raw_key)`.

- [ ] **Step 1: Escrever teste unitário falhando para crypto e modelos (RED)**
  Testar `generate_api_key` gerando formato `ls_live_...` e hash SHA-256 consistente.
  Testar criação de `WorkspaceMembership` e `APIKey`.
- [ ] **Step 2: Executar teste e validar falha esperada (RED)**
  `.venv\Scripts\pytest.exe tests/test_security_models.py`
- [ ] **Step 3: Implementar crypto.py**
  Funções `generate_api_key`, `hash_api_key`, `verify_api_key` com `secrets.token_urlsafe(32)`.
- [ ] **Step 4: Implementar models.py**
  Modelos `WorkspaceRole`, `WorkspaceMembership`, `APIKey`, `SecurityAuditLog`.
- [ ] **Step 5: Registrar app e gerar migrations**
  Adicionar `"leadstream.security.apps.SecurityConfig"` em `INSTALLED_APPS`.
  Executar `.venv\Scripts\python.exe -m django makemigrations security`.
  Executar `.venv\Scripts\python.exe -m django migrate`.
- [ ] **Step 6: Executar teste e validar sucesso (GREEN)**
  `.venv\Scripts\pytest.exe tests/test_security_models.py`
- [ ] **Step 7: Commit dos modelos**
  `git add src/leadstream/security/ tests/test_security_models.py && git commit -m "feat(security): criar modelos de credenciais, workspace membership e api keys com hash"`

---

### Task 3: Motor de Autenticação Híbrida & Injeção Segura de Tenant

**Files:**
- Create: `src/leadstream/security/authentication.py`
- Create: `src/leadstream/security/permissions.py`
- Test: `tests/test_security_authentication.py`

**Interfaces:**
- Consumes: `leadstream.security.models.APIKey`, `leadstream.security.models.WorkspaceMembership`.
- Produces: `CombinedAuthentication` (classe DRF), `IsTenantMember`, `HasWorkspaceRole`, `IsSuperAdminUser`.

- [ ] **Step 1: Escrever teste unitário para autenticação combinada (RED)**
  Testar requisição com API Key válida injetando `request.tenant` e `request.auth`.
  Testar requisição com JWT válido de membro injetando `request.user` e `request.tenant`.
  Testar requisição de Super Admin com `X-Tenant-ID`.
  Testar requisição com chave revogada ou expirada retornando `401`.
  Testar requisição sem credencial retornando `401`.
- [ ] **Step 2: Executar teste e validar falha (RED)**
  `.venv\Scripts\pytest.exe tests/test_security_authentication.py`
- [ ] **Step 3: Implementar authentication.py**
  Classe `CombinedAuthentication(BaseAuthentication)` que processa tanto `Bearer ls_...` / `X-API-Key` quanto JWT tokens.
- [ ] **Step 4: Implementar permissions.py**
  Classes `IsTenantMember`, `HasWorkspaceRole(role)`, `IsSuperAdminUser`.
- [ ] **Step 5: Executar teste e validar sucesso (GREEN)**
  `.venv\Scripts\pytest.exe tests/test_security_authentication.py`
- [ ] **Step 6: Commit da autenticação**
  `git add src/leadstream/security/ tests/test_security_authentication.py && git commit -m "feat(security): implementar CombinedAuthentication e validacao de permissao por tenant"`

---

### Task 4: Endpoints de Autenticação, Gestão de Chaves e Auditoria

**Files:**
- Create: `src/leadstream/security/serializers.py`
- Create: `src/leadstream/security/views.py`
- Create: `src/leadstream/security/urls.py`
- Modify: `src/config/urls.py:30-50`
- Test: `tests/test_security_api.py`

**Interfaces:**
- Consumes: `CombinedAuthentication`, `APIKey`, `SecurityAuditLog`.
- Produces: Endpoints `/api/v1/auth/token/`, `/api/v1/auth/token/refresh/`, `/api/v1/auth/token/revoke/`, `/api/v1/security/keys/`, `/api/v1/security/audit-logs/`.

- [ ] **Step 1: Escrever teste de API para login e gestão de chaves (RED)**
  Testar login e recebimento de tokens JWT.
  Testar criação de API Key retornando `raw_key` uma única vez.
  Testar revogação de API Key.
  Testar consulta de audit logs.
- [ ] **Step 2: Executar teste e validar falha (RED)**
  `.venv\Scripts\pytest.exe tests/test_security_api.py`
- [ ] **Step 3: Implementar serializers.py**
  `APIKeyCreateSerializer`, `APIKeyReadSerializer`, `SecurityAuditLogSerializer`, `TokenObtainPairResponseSerializer`.
- [ ] **Step 4: Implementar views.py e urls.py**
  Views com anotações `@extend_schema` completas e registro em `config/urls.py`.
- [ ] **Step 5: Executar teste e validar sucesso (GREEN)**
  `.venv\Scripts\pytest.exe tests/test_security_api.py`
- [ ] **Step 6: Commit dos endpoints**
  `git add src/leadstream/security/ src/config/urls.py tests/test_security_api.py && git commit -m "feat(security): adicionar endpoints de login jwt, gestao de api keys e auditoria"`

---

### Task 5: Throttling & Proteção Anti-Abuso (Redis)

**Files:**
- Create: `src/leadstream/security/throttling.py`
- Modify: `src/config/settings/base.py:173-180`
- Modify: `src/leadstream/security/views.py`
- Test: `tests/test_security_throttling.py`

**Interfaces:**
- Consumes: Redis Cache (`CACHES["default"]`), DRF Throttling.
- Produces: `AuthRateThrottle` (5 req/min por IP), `TenantApiKeyRateThrottle` (120 req/min por Tenant/Key).

- [ ] **Step 1: Escrever teste de throttling (RED)**
  Testar que após 5 requisições sucessivas ao login na mesma janela temporal, a 6ª requisição retorna `429 Too Many Requests`.
- [ ] **Step 2: Executar teste e validar falha (RED)**
  `.venv\Scripts\pytest.exe tests/test_security_throttling.py`
- [ ] **Step 3: Implementar throttling.py**
  Classes `AuthRateThrottle` e `TenantApiKeyRateThrottle`.
- [ ] **Step 4: Conectar throttles nas views de autenticação**
- [ ] **Step 5: Executar teste e validar sucesso (GREEN)**
  `.venv\Scripts\pytest.exe tests/test_security_throttling.py`
- [ ] **Step 6: Commit do throttling**
  `git add src/leadstream/security/ src/config/settings/base.py tests/test_security_throttling.py && git commit -m "feat(security): implementar rate limiting anti-abuso no redis para login e chamadas por tenant"`

---

### Task 6: Proteção das Rotas Existentes, Isolamento de Tenant e Fixtures de Teste

**Files:**
- Modify: `src/leadstream/canonical/views.py:18-50`
- Modify: `src/leadstream/batches/views.py`
- Modify: `src/leadstream/entities/views.py`
- Modify: `src/leadstream/integrations/views.py`
- Modify: `src/leadstream/billing/views.py`
- Modify: `tests/conftest.py` (ou helpers de teste)
- Test: Suíte completa de testes (`tests/`)

**Interfaces:**
- Consumes: `request.tenant` injetado por `CombinedAuthentication`.
- Produces: Todas as rotas de dados protegidas exigindo autenticação válida, eliminando chamadas cegas a `get_internal_tenant()`.

- [ ] **Step 1: Criar helper de autenticação em conftest.py**
  Prover fixtures `api_client_authenticated` e `internal_api_key` para que os testes existentes executem autenticados com o tenant correto.
- [ ] **Step 2: Configurar DEFAULT_AUTHENTICATION_CLASSES e DEFAULT_PERMISSION_CLASSES em base.py**
  Configurar `CombinedAuthentication` e `IsAuthenticated` como padrão global.
- [ ] **Step 3: Refatorar views para consumir `request.tenant`**
  Substituir chamadas residuais de `get_internal_tenant()` nas views pelo `request.tenant` fornecido pela autenticação.
- [ ] **Step 4: Executar toda a suíte de testes existente**
  `.venv\Scripts\pytest.exe` garantindo que todos os 117+ testes passem com 100% de sucesso.
- [ ] **Step 5: Commit do reforço transversal de segurança**
  `git add src/ tests/ && git commit -m "feat(security): blindar todas as rotas com CombinedAuthentication e amarrar queries ao request.tenant"`

---

### Task 7: Comando de Inicialização (CLI) & Documentação Interativa (`/api/v1/docs/`)

**Files:**
- Create: `src/leadstream/security/management/commands/setup_security_admin.py`
- Modify: `src/config/settings/base.py` (SPECTACULAR_SETTINGS)
- Modify: `templates/docs/scalar.html`
- Test: `tests/test_logging.py`

**Interfaces:**
- Consumes: Modelos de autenticação, drf-spectacular.
- Produces: Comando `python manage.py setup_security_admin` para provisionar Super Admin e primeira API Key mestre; documentação Swagger/Scalar com botões de autorização funcional.

- [ ] **Step 1: Implementar comando de gestão setup_security_admin**
  Permite criar ou redefinir a senha do Super Admin e emitir uma API Key mestre inicial para o proprietário com saída formatada no terminal.
- [ ] **Step 2: Atualizar SPECTACULAR_SETTINGS com BearerAuth e ApiKeyAuth**
  Adicionar esquemas OpenAPI para JWT e API Key.
- [ ] **Step 3: Testar `/api/v1/docs/` e `/api/v1/schema/`**
  Validar geração do schema sem erros e renderização da UI.
- [ ] **Step 4: Executar suíte completa de testes e linter**
  `.venv\Scripts\pytest.exe`
  `.venv\Scripts\ruff.exe check .`
- [ ] **Step 5: Commit final e push para origin/main**
  `git commit -m "feat(security): adicionar comando setup_security_admin e integrar autenticacao na documentacao interativa"`
  `git push origin main`
