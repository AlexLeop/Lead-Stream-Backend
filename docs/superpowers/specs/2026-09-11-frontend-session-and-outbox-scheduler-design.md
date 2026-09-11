# Especificação Técnica de Design: Frontend Session & Celery CRM Outbox Scheduler

> **Documento de Design Arquitetural**  
> **Data:** 11/09/2026  
> **Status:** Aprovado  
> **Módulos:** `leadstream.security`, `leadstream.tenancy`, `leadstream.integrations`, `config`

---

## 1. Visão Geral e Objetivos

O **LeadStream Backend** alcança neste marco a prontidão operacional de ponta a ponta para produção (*Production Readiness v2.5*), endereçando duas frentes críticas complementares:

1. **Camada de Sessão & Perfil do Frontend (`/api/v1/auth/me/` e Gestão de Workspaces):**
   - Fornece ao frontend cliente (React / Next.js / Vue / Mobile) o contrato completo da sessão autenticada.
   - Expõe dados do usuário autenticado, identificação do workspace ativo, papéis e permissões (RBAC) e listagem de workspaces disponíveis para troca dinâmica de contexto (`/api/v1/auth/switch-workspace/`).
   - Retorna métricas essenciais de consumo e quotas do workspace ativo (lotes, leads e chaves).

2. **Automação Contínua e Monitoramento do Celery CRM Outbox:**
   - Registro e ativação da tarefa de drenagem periódica `process_crm_outbox_batch` no `CELERY_BEAT_SCHEDULE` (executando a cada 30 segundos).
   - Assinatura criptográfica robusta HMAC-SHA256 (`X-LeadStream-Signature`) com timestamp para evitar ataques de repetição (*replay attacks*) em webhooks customizados (n8n, Zapier, Make).
   - API de observabilidade da fila de integração (`GET /api/v1/integracoes/outbox/status/`) com métricas agregadas (`PENDING`, `DELIVERED`, `FAILED`, `DEAD_LETTER`).
   - Mecanismo de recuperação manual ou em lote de mensagens em Dead-Letter (`POST /api/v1/integracoes/outbox/retry-dead-letter/`).

---

## 2. Contratos de API e Estrutura de Dados

### 2.1. Endpoint de Sessão: `GET /api/v1/auth/me/`
- **Permissão:** `IsAuthenticated` (compatível tanto com Bearer JWT quanto com API Key).
- **Cabeçalhos Opcionais:** `X-Tenant-ID` (para Super Admin chavear contexto sob demanda).
- **Resposta 200 OK:**
```json
{
  "user": {
    "id": 1,
    "username": "alex",
    "email": "alex@leadstream.com.br",
    "first_name": "Alex",
    "last_name": "Leopoldo",
    "is_superuser": true,
    "is_staff": true
  },
  "auth_type": "JWT",
  "active_workspace": {
    "id": "c7a8b910-...",
    "name": "LeadStream Matriz",
    "slug": "leadstream-matriz",
    "tier": "ENTERPRISE",
    "role": "OWNER",
    "is_owner": true,
    "stats": {
      "total_batches": 12,
      "total_leads_processed": 14500,
      "active_api_keys": 3
    }
  },
  "workspaces": [
    {
      "id": "c7a8b910-...",
      "name": "LeadStream Matriz",
      "slug": "leadstream-matriz",
      "role": "OWNER",
      "is_active": true
    },
    {
      "id": "e5f6a7b8-...",
      "name": "Operações Filial SP",
      "slug": "operacoes-sp",
      "role": "OPERATOR",
      "is_active": false
    }
  ],
  "permissions": [
    "batches:view",
    "batches:create",
    "batches:export",
    "leads:view",
    "leads:enrich",
    "integrations:manage",
    "security:manage_keys",
    "security:view_audit"
  ]
}
```

### 2.2. Troca de Workspace: `POST /api/v1/auth/switch-workspace/`
- **Permissão:** `IsAuthenticated` (Apenas operadores JWT humanos com login).
- **Corpo da Requisição:**
```json
{
  "workspace_id": "e5f6a7b8-..."
}
```
- **Regras de Negócio:**
  - Verifica se o usuário autenticado possui registro em `UserTenantMembership` para o workspace especificado (ou se é `is_superuser`).
  - Caso não possua acesso, retorna `403 Forbidden` com código `WORKSPACE_ACCESS_DENIED`.
  - Atualiza o workspace ativo preferencial do usuário e emite novos tokens JWT de acesso contendo a claim `tenant_id` atualizada.

### 2.3. Status do Outbox: `GET /api/v1/integracoes/outbox/status/`
- **Permissão:** `IsAuthenticated` (Escopado por Tenant).
- **Resposta 200 OK:**
```json
{
  "tenant_id": "c7a8b910-...",
  "counts": {
    "pending": 4,
    "processing": 1,
    "delivered": 1240,
    "failed": 2,
    "dead_letter": 0
  },
  "oldest_pending_seconds": 15,
  "is_healthy": true
}
```

### 2.4. Reprocessamento de Dead Letters: `POST /api/v1/integracoes/outbox/retry-dead-letter/`
- **Permissão:** `IsAuthenticated` & `IsWorkspaceAdmin`.
- **Corpo da Requisição (opcional):**
```json
{
  "message_ids": ["uuid-1", "uuid-2"]
}
```
- **Comportamento:**
  - Se `message_ids` for omitido ou vazio, reprocessa todas as mensagens em `DEAD_LETTER` do tenant.
  - Altera status para `PENDING`, zera `retry_count = 0`, seta `next_retry_at = now()` e agenda execução imediata da Celery task.

---

## 3. Arquitetura de Webhook e HMAC-SHA256

Para conectores do tipo `WEBHOOK_CUSTOM`, `WEBHOOK_N8N`, `WEBHOOK_ZAPIER` e `WEBHOOK_MAKE`, o serviço de despacho assina o corpo HTTP com HMAC-SHA256:

- **Chave de Assinatura:** `connection.credentials.get("secret")` ou fallback para `settings.DATA_HASH_KEY`.
- **Cabeçalho:** `X-LeadStream-Signature: t=1726087200,v1=a3b5c7...`
- **Payload Assinado:** `f"t={timestamp}.{json_payload_str}"`.

---

## 4. Agendador Celery Beat

Em `src/config/settings/base.py`:
```python
CELERY_BEAT_SCHEDULE = {
    "recover-stalled-batches": {
        "task": "leadstream.batches.recover",
        "schedule": 60.0,
    },
    "recover-stalled-discoveries": {
        "task": "leadstream.providers.recover_discovery",
        "schedule": 60.0,
    },
    "process-crm-outbox": {
        "task": "leadstream.integrations.process_crm_outbox_batch",
        "schedule": 30.0,
        "kwargs": {"batch_size": 50},
    },
}
```

---

## 5. Estratégia de Testes e Validação

1. `tests/test_security_api.py` / `tests/test_auth_me_api.py`:
   - Teste de `GET /api/v1/auth/me/` com JWT (retorna perfil, permissões e workspaces).
   - Teste de `GET /api/v1/auth/me/` com API Key (retorna perfil de máquina associado ao tenant da chave).
   - Teste de `POST /api/v1/auth/switch-workspace/` com permissão válida e não autorizada (`403 Forbidden`).
2. `tests/test_crm_outbox_scheduler.py`:
   - Teste de assinatura HMAC com verificação de integridade e timestamp.
   - Teste de `GET /api/v1/integracoes/outbox/status/`.
   - Teste de reprocessamento de dead-letter messages via API e via Celery task.
3. Cobertura completa de regressão: todos os 137 testes existentes devem permanecer 100% verdes.
