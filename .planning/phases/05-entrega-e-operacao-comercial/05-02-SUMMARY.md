---
phase: 05-entrega-e-operacao-comercial
plan: "02"
status: completed
completed_at: "2026-09-10T19:05:00-03:00"
requirements: [CRM-01, CRM-02, CRM-03, CRM-04]
---

# 05-02 — Resumo do Outbox Transacional, Conectores de CRM e Webhooks Universais

## O que foi entregue

1. **Modelo e Migração da Camada de Integrações (`leadstream.integrations`):**
   - Criação da app `src/leadstream/integrations` registrada no `INSTALLED_APPS`.
   - Implementação dos modelos em `src/leadstream/integrations/models.py` e migração `0001_initial.py`:
     - `CRMConnection`: Gestão de credenciais protegidas (`write_only`), endpoint customizado, status (`ACTIVE`, `INACTIVE`, `ERROR`) e contadores de sucesso/falha.
     - `CRMFieldMapping`: Motor de de-para dinâmico de campos canônicos para campos do CRM com suporte a transformações (`RAW`, `LOWER`, `UPPER`, `DIGITS_ONLY`, `FIRST_NAME`, `LAST_NAME`).
     - `CRMOutboxMessage`: Tabela transacional de outbox com garantia 'at-least-once', `idempotency_key` (SHA-256 único por lote+lead+conexão), payload canônico normalizado, status (`PENDING`, `PROCESSING`, `DELIVERED`, `FAILED`, `DEAD_LETTER`), backoff exponencial e logs detalhados de execução.
     - `CRMSyncEvent`: Auditoria de disparos de sincronização em lote.

2. **Arquitetura Pluggable de Conectores (`src/leadstream/integrations/connectors/`):**
   - **`BaseCRMConnector`**: Classe abstrata definindo contratos universais para `test_connection()` e `sync_lead()`.
   - **`WebhookConnector` (Universal & No-Code Ready):**
     - Entrega via HTTP POST com assinatura criptográfica `X-LeadStream-Signature: sha256=<hmac>` e `X-LeadStream-Event`.
     - Presets nativos para webhooks customizados, n8n, Make e Zapier.
   - **Conectores Especializados:**
     - `HubSpotConnector`: Criação/atualização de Companies e Contacts via API v3.
     - `PipedriveConnector`: Criação/atualização de Organizations e Persons via API v1.
     - `RDStationConnector`: Conversão e atualização de contatos na API de CRM do RD Station.
     - `SalesforceConnector`: Upsert em Accounts e Contacts via REST API.
     - `PloomesConnector`: Integração Brasil-first para Contatos e Clientes.
   - **`CRMConnectorRegistry`**: Fábrica com fallback transparente para `WebhookConnector` para suportar qualquer CRM futuro sem alteração no núcleo da aplicação.

3. **Motor de Despacho e Resiliência (`src/leadstream/integrations/services.py`):**
   - `enqueue_batch_to_crm`: Extração e canonicalização de dados de empresas, decisores e contatos com geração atômica de chaves de idempotência e inserção em lote na outbox.
   - `dispatch_outbox_message`: Despacho isolado por mensagem com medição de latência, tolerância a falhas, respeito a cabeçalhos `Retry-After` de HTTP 429 (Rate Limit) e transição para `DEAD_LETTER` após atingir o limite máximo de tentativas.
   - `verify_crm_connection`: Teste em tempo real de credenciais e conectividade com registro de status e latência.

4. **Tarefas Assíncronas Celery (`src/leadstream/integrations/tasks.py`):**
   - `process_crm_outbox_batch`: Varredura periódica de mensagens pendentes/retentáveis com chunking de 50 mensagens e bloqueio atômico.
   - `sync_batch_to_crm_task`: Tarefa disparada pela API para enfileiramento de lote completo e acionamento de processamento do outbox.

5. **API REST e Contratos para Múltiplos Frontends (`src/leadstream/integrations/views.py`):**
   - **Endpoints B2B (Tenant Isolado via `resolve_tenant`):**
     - `GET/POST /api/v1/integracoes/conexoes/`: Listagem e cadastro de conexões.
     - `GET/PATCH/DELETE /api/v1/integracoes/conexoes/{id}/`: Detalhes e atualização de conexão.
     - `POST /api/v1/integracoes/conexoes/{id}/testar/`: Teste de conectividade e credenciais em tempo real.
     - `GET/POST /api/v1/integracoes/conexoes/{id}/mapeamentos/`: Gerenciamento de mapeamento de campos.
     - `POST /api/v1/lotes/{batch_id}/sincronizar-crm/`: Disparo de sincronização de lote com conexão CRM.
     - `GET /api/v1/integracoes/outbox/`: Monitoramento e consulta de status de entregas do outbox.
   - **Endpoint Cockpit do CEO:**
     - `GET /api/v1/admin/integracoes/metricas/`: Visão consolidada em nível de plataforma (total de conexões, mensagens entregues, falhas, DLQ e distribuição por tipo de conector).

6. **Validação Rigorosa de Qualidade (5 Gates Aprovados):**
   - **Ruff:** 0 erros de lint e formatação.
   - **Mypy:** 100% de conformidade com tipagem estrita em 111 arquivos fonte.
   - **Migrations:** Zero migrações pendentes.
   - **Deploy Check:** Zero warnings em verificação de produção (`check --deploy`).
   - **Pytest:** 80 testes executados com 100% de sucesso (8 novos testes específicos de integração CRM em `tests/test_crm_integrations.py`).
