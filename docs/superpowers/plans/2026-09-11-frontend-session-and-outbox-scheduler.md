# Frontend Session & Celery CRM Outbox Scheduler Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implementar os contratos de sessão do frontend (`GET /api/v1/auth/me/` e troca dinâmica de workspace `POST /api/v1/auth/switch-workspace/`) e a infraestrutura de mensageria assíncrona do Celery Beat com assinatura HMAC-SHA256 para webhooks e observabilidade do CRM Outbox.

**Architecture:** 
- O app `leadstream.security` ganha serializers e views dedicadas para fornecer perfil do usuário, workspace ativo, quotas resumidas, permissões calculadas e troca de contexto.
- O app `leadstream.integrations` ganha assinatura criptográfica HMAC-SHA256 com cabeçalho `X-LeadStream-Signature`, agendamento periódico de 30 segundos no Celery Beat (`process_crm_outbox_batch`), e endpoints de observabilidade de fila e reprocessamento de dead-letters.

**Tech Stack:** Python 3.13, Django 5.2 LTS, DRF 3.18, Celery 5.6, RabbitMQ 4.x, Redis 8.x, PostgreSQL 17+.

**Spec:** `docs/superpowers/specs/2026-09-11-frontend-session-and-outbox-scheduler-design.md`

## Global Constraints
- Toda requisição em `/api/v1/auth/me/` exige autenticação (`IsAuthenticated`).
- Requisições JWT retornam os dados do usuário, workspace ativo e lista de workspaces membros.
- Requisições autenticadas por API Key retornam o perfil da credencial de máquina amarrada ao seu tenant.
- A assinatura de webhook deve usar HMAC-SHA256 no formato `X-LeadStream-Signature: t=<timestamp>,v1=<signature>`.
- O agendador do Celery Beat não deve reprocessar mensagens já entregues (`DELIVERED`) ou em `DEAD_LETTER` sem solicitação explícita.
- Toda a suíte de testes (137 testes existentes) deve permanecer 100% verde.
- Formatação e linter via `ruff check .` com 0 violações.

---

### Task 1: Endpoints de Sessão e Perfil Frontend (`auth/me/` e `auth/switch-workspace/`)

**Files:**
- Modify: `src/leadstream/security/serializers.py`
- Modify: `src/leadstream/security/views.py`
- Modify: `src/leadstream/security/urls.py`
- Create: `tests/test_auth_me_api.py`

**Interfaces:**
- Consumes: `request.user`, `request.tenant`, `leadstream.security.models.WorkspaceMembership`.
- Produces: `GET /api/v1/auth/me/`, `POST /api/v1/auth/switch-workspace/`.

- [ ] **Step 1: Criar testes unitários para /api/v1/auth/me/ e /api/v1/auth/switch-workspace/ (RED)**
  Cobrir: chamada com JWT, chamada com API Key, listagem de workspaces, permissões, troca de workspace com sucesso e troca com 403 Forbidden para workspace inválido.
- [ ] **Step 2: Executar teste e validar falha esperada (RED)**
  Executar `.venv\Scripts\pytest.exe tests/test_auth_me_api.py`.
- [ ] **Step 3: Implementar serializers de perfil e troca de workspace**
  Em `src/leadstream/security/serializers.py`: `UserProfileSerializer`, `WorkspaceDetailSerializer`, `AuthMeResponseSerializer`, `SwitchWorkspaceSerializer`.
- [ ] **Step 4: Implementar views de perfil e troca de workspace**
  Em `src/leadstream/security/views.py`: `AuthMeView` e `SwitchWorkspaceView`.
- [ ] **Step 5: Registrar rotas em urls.py**
  Em `src/leadstream/security/urls.py`: registrar `auth/me/` e `auth/switch-workspace/`.
- [ ] **Step 6: Executar testes de sessão e validar aprovação (GREEN)**
  Executar `.venv\Scripts\pytest.exe tests/test_auth_me_api.py tests/test_security_api.py`.
- [ ] **Step 7: Commit da Task 1**
  `git add src/leadstream/security/ tests/test_auth_me_api.py; git commit -m "feat(security): implementar endpoints de sessao frontend /auth/me/ e troca de workspace"`

---

### Task 2: Assinatura Criptográfica HMAC-SHA256 para Webhooks de Integração

**Files:**
- Modify: `src/leadstream/integrations/services.py`
- Create: `tests/test_crm_webhook_hmac.py`

**Interfaces:**
- Consumes: `CRMOutboxMessage`, `CRMConnection`, `settings.DATA_HASH_KEY`.
- Produces: Header `X-LeadStream-Signature: t=<timestamp>,v1=<hex_hash>`.

- [ ] **Step 1: Criar teste unitário para assinatura HMAC de webhooks (RED)**
  Verificar que o header `X-LeadStream-Signature` é gerado no formato `t=<timestamp>,v1=<hash>` e validável pelo receptor.
- [ ] **Step 2: Executar teste e validar falha esperada (RED)**
  Executar `.venv\Scripts\pytest.exe tests/test_crm_webhook_hmac.py`.
- [ ] **Step 3: Implementar função de assinatura e injeção no conector Webhook**
  Em `src/leadstream/integrations/services.py`: computar HMAC com SHA256 sobre `f"t={timestamp}.{body}"` e incluir no dicionário de headers HTTP do POST.
- [ ] **Step 4: Executar testes e validar aprovação (GREEN)**
  Executar `.venv\Scripts\pytest.exe tests/test_crm_webhook_hmac.py tests/test_crm_integrations.py`.
- [ ] **Step 5: Commit da Task 2**
  `git add src/leadstream/integrations/services.py tests/test_crm_webhook_hmac.py; git commit -m "feat(integrations): adicionar assinatura criptografica HMAC-SHA256 para webhooks"`

---

### Task 3: Agendador Celery Beat, Status da Fila do Outbox e Reprocessamento de Dead-Letters

**Files:**
- Modify: `src/config/settings/base.py`
- Modify: `src/leadstream/integrations/views.py`
- Modify: `src/leadstream/integrations/urls.py`
- Create: `tests/test_crm_outbox_scheduler.py`

**Interfaces:**
- Consumes: `CRMOutboxMessage`, `CELERY_BEAT_SCHEDULE`.
- Produces: Tarefa periódica a cada 30s, endpoints `GET /api/v1/integracoes/outbox/status/` e `POST /api/v1/integracoes/outbox/retry-dead-letter/`.

- [ ] **Step 1: Criar testes para status do outbox e retry de dead-letter (RED)**
  Testar contagem por status, cálculo de idade da mensagem mais antiga, endpoint de status e rota de reprocessamento.
- [ ] **Step 2: Executar teste e validar falha esperada (RED)**
  Executar `.venv\Scripts\pytest.exe tests/test_crm_outbox_scheduler.py`.
- [ ] **Step 3: Atualizar CELERY_BEAT_SCHEDULE em base.py**
  Adicionar `process-crm-outbox` agendado a cada 30.0 segundos chamando `leadstream.integrations.process_crm_outbox_batch`.
- [ ] **Step 4: Implementar views e rotas em integrations**
  Adicionar `CRMOutboxStatusView` e `CRMOutboxRetryDeadLetterView` e mapear em `urls.py`.
- [ ] **Step 5: Executar testes e validar aprovação (GREEN)**
  Executar `.venv\Scripts\pytest.exe tests/test_crm_outbox_scheduler.py`.
- [ ] **Step 6: Commit da Task 3**
  `git add src/config/settings/base.py src/leadstream/integrations/ tests/test_crm_outbox_scheduler.py; git commit -m "feat(integrations): adicionar beat schedule para outbox, endpoint de status e retry de dead-letters"`

---

### Task 4: Atualização da Documentação, Testes de Regressão e Validação Geral

**Files:**
- Modify: `README.md`
- Modify: `deploy/easypanel.md`
- Modify: `docs/superpowers/plans/2026-09-11-frontend-session-and-outbox-scheduler.md`

- [ ] **Step 1: Atualizar README.md**
  Documentar `/api/v1/auth/me/`, `/api/v1/auth/switch-workspace/`, `/api/v1/integracoes/outbox/status/`, webhook HMAC e rotinas Celery Beat.
- [ ] **Step 2: Atualizar deploy/easypanel.md**
  Incluir instruções para monitorar os workers Celery e a fila de Outbox.
- [ ] **Step 3: Executar a suíte completa de testes e linter**
  Executar `.venv\Scripts\pytest.exe` e `.venv\Scripts\ruff.exe check .`.
- [ ] **Step 4: Commit da documentação e encerramento**
  `git add README.md deploy/easypanel.md docs/; git commit -m "docs: atualizar documentacao com contratos de sessao frontend e agendador outbox"`
