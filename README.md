# LeadStream Backend

Plataforma *Brasil-first* independente de inteligência cadastral B2B, enriquecimento em cascata de decisores corporativos, higienização rigorosa de dados e governança LGPD.

A API parte de um CNPJ, resolve seus estabelecimentos, descobre o quadro de sócios e administradores (QSA), localiza canais diretos de contato atribuíveis e perfis profissionais públicos (LinkedIn), consolidando evidências com proveniência, score de confiança, tarifação por bloco útil e conformidade legal.

---

## 🚀 Principais Capacidades

### 1. Payload Canônico v2.4.0 (14 Blocos de Inteligência)
Disponível em `GET /api/v1/leads/{lead_id}/canonical/`:
- **01. Metadados (`_meta`):** UUID canônico, timestamp ISO 8601, tenant e score global de consolidação.
- **02. Identificação & ICP (`identification`):** Lead score (0 a 100), temperatura (`COLD`/`WARM`/`HOT`) e fit de ICP.
- **03. Dados da Empresa (`company`):** CNPJ formatado e partes separadas, Razão Social, Nome Fantasia, data de abertura, porte, Simples/Simei, capital social e colaboradores.
- **04. Inteligência Financeira & Bancária (`financial_and_banking`):** Bancos de relacionamento identificados, risco de crédito e capacidade de pagamento.
- **05. Inteligência Fiscal & Tributária (`fiscal_and_tax_intelligence`):** Situação cadastral RFB, dívida ativa PGFN, certidões negativas (CND/CRF), Inscrição Estadual e Municipal.
- **06. CNAE & Atividades Econômicas (`cnae`):** CNAE principal com divisão setorial e grau de risco trabalhista (1–4), além de CNAEs secundários.
- **07. Endereço & Localização (`address`):** Endereço padronizado com tipo de logradouro, CEP formatado, município, UF e código IBGE.
- **08. Contatos Validados (`contacts`):** Telefones com **DDD separado do número em dígitos puros** (sem `-`, `+` ou espaços, status WhatsApp e operadora ANATEL) e e-mails com status MX e anti-descarte.
- **09. Decisores & QSA (`decision_makers_qsa`):** Sócios e executivos C-level com cargo de mercado, contatos diretos e URL do **LinkedIn público higienizada** (sem subdomínios geográficos ou sufixos de idioma como `/en` e `/pt`).
- **10. Comércio Exterior & Logística (`foreign_trade_and_logistics`):** Radar SISCOMEX, importação/exportação e frota veicular.
- **11. Jurídico & Judicial (`legal_and_judicial`):** Processos ativos (cíveis, trabalhistas, fiscais), recuperação judicial e auditoria de conformidade.
- **12. Presença Digital & Stack Tecnológico (`digital_presence_and_tech_stack`):** Domínio, tecnologias detectadas e redes sociais corporativas.
- **13. Governança LGPD & Compliance (`governance_lgpd_and_compliance`):** Base legal (Art. 7º, IX da LGPD — Legítimo Interesse comercial B2B), canal de *opt-out*, retenção e rastreabilidade.
- **14. Integrações CRM (`crm_outbox_integration`):** Status de entrega e sincronização transacional com CRMs externos.

---

### 2. Camada de Segurança Enterprise & Autenticação Híbrida
- **Autenticação Híbrida:**
  - **Operadores Humanos (JWT):** Login via `/api/v1/auth/token/` (Access: 30 min, Refresh: 14 dias com rotação e blacklist).
  - **Sistemas & Integrações (API Keys):** Chaves prefixadas `ls_live_...` e `ls_test_...` com hash SHA-256 no banco e comparação segura contra timing attacks (`hmac.compare_digest`).
  - **Headers Suportados:** `Authorization: Bearer <token>` ou `X-API-Key: <chave>`.
- **Multi-Tenancy Estrito & RBAC:**
  - Papéis hierárquicos: `ADMIN`, `OPERATOR` e `READ_ONLY`.
  - Blindagem total contra IDOR: queries amarradas estritamente ao workspace contextualizado.
  - Chaveamento seguro de workspace para Super Administradores via `X-Tenant-ID`.
- **Proteção de Borda & Anti-Abuso:**
  - CORS configurável via `CORS_ALLOWED_ORIGINS`.
  - Cabeçalhos defensivos: `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`.
  - Throttling no Redis: 5 req/min no login, 10 req/min no refresh e 120 req/min por tenant.
- **Auditoria LGPD (`SecurityAuditLog`):**
  - Registro imutável de logins, falhas, revogações e criações de chaves com IP e User-Agent.

---

### 3. Processamento em Massa & Integrações
- **Ingestão de Lotes (`/api/v1/lotes/`):** Processamento assíncrono de até 100.000 CNPJs fatiados em chunks idempotentes (25–100 leads) no Celery + RabbitMQ.
- **Transactional Outbox:** Sincronização assíncrona com CRMs (HubSpot, RD Station, Pipedrive, Webhooks) com garantia de entrega única e idempotência.
- **Documentação OpenAPI 3.1.0:** Interface interativa em `/api/v1/docs/` (Scalar e Swagger UI) com suporte a `BearerAuth`, `ApiKeyAuth` e `TenantHeader`.

---

## 🏗️ Arquitetura

```text
Cliente Web / CRM / Integração
       |
       v
[ Proxy Reverso (HTTPS / TLS) ]
       |
       v
[ LeadStream API (Django 5.2 + DRF) ] <--- CombinedAuthentication (JWT / API Key)
       |
       +---> [ PostgreSQL 17+ ]  (Fonte Canônica, RBAC & Outbox)
       |
       +---> [ Redis 8+ ]        (Cache, Throttling & Locks Distribuídos)
       |
       +---> [ RabbitMQ 4+ ]     (Broker de Mensagens Durável)
       |            |
       |            v
       |     [ Celery Workers ]  (Fatiamento, Higienização & Enriquecimento)
       |            |
       +------------+---> Cascata de Provedores (OpenCNPJ BigQuery / BigDataCorp / Apify)
```

---

## ⚡ Como Executar

### 1. Com Docker Compose (Recomendado)

1. Crie o arquivo `.env` a partir do template:
   ```bash
   cp .env.example .env
   ```
2. Inicialize os serviços:
   ```bash
   docker compose --profile release run --rm release
   docker compose up -d api worker
   ```
3. Acesse os endpoints:
   - Health Check de Vida: `http://127.0.0.1:8000/health/live`
   - Health Check de Prontidão: `http://127.0.0.1:8000/health/ready`
   - Documentação Interativa: `http://127.0.0.1:8000/api/v1/docs/`
   - Especificação OpenAPI: `http://127.0.0.1:8000/api/v1/schema/`

---

### 2. Sem Docker (Ambiente Local com uv)

Requisitos: Python 3.13+, PostgreSQL 17+, RabbitMQ 4+ e Redis 8+.

```bash
uv sync --extra dev
uv run python manage.py migrate
uv run python manage.py setup_security_admin --username admin --email admin@leadstream.local
uv run python manage.py runserver
```

Em outro terminal, inicie o worker Celery:
```bash
uv run celery -A config.celery:app worker --loglevel=INFO --concurrency=2
```

---

## 🛡️ Gestão de Segurança & Credenciais

### Provisionar o Super Administrador via CLI
```bash
python manage.py setup_security_admin --username admin --email admin@leadstream.com.br
```
*O comando cria ou redefine o superusuário mestre, garante o tenant interno e emite uma Master API Key exibida uma única vez.*

### Obter Token JWT (Operadores)
```bash
curl -X POST http://localhost:8000/api/v1/auth/token/ \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "<senha>"}'
```

### Criar uma API Key de Integração
```bash
curl -X POST http://localhost:8000/api/v1/security/keys/ \
  -H "Authorization: Bearer <token_jwt>" \
  -H "Content-Type: application/json" \
  -d '{"name": "CRM HubSpot Produção", "role": "OPERATOR", "env": "live"}'
```

### Consultar a API com a API Key
```bash
curl -X GET http://localhost:8000/api/v1/leads/<lead_id>/canonical/ \
  -H "X-API-Key: ls_live_<chave_gerada>"
```

---

## 🧪 Qualidade & Testes Automatizados

O repositório possui gate estrito de qualidade com **100% de aprovação**:

```bash
# Executar suíte de testes
uv run pytest

# Executar verificação de lint e estilo
uv run ruff check .
```

- **137 testes automatizados** cobrindo segurança, modelos, contratos canônicos v2.4.0, CRM outbox e pipelines de dados.
- **Zero erros de lint** sob regras estritas do Ruff (`pyproject.toml`).

---

## 📦 Implantação em Produção

Siga o [Runbook do EasyPanel](deploy/easypanel.md) e utilize [`deploy/env.production.example`](deploy/env.production.example) como checklist de variáveis de ambiente. Segredos reais pertencem exclusivamente ao cofre do EasyPanel e nunca devem ser versionados no Git.
