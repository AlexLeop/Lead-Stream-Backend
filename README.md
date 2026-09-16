# LeadStream Backend

Plataforma *Brasil-first* independente de inteligência cadastral e enriquecimento em cascata para **Pessoa Jurídica (B2B / CNPJ)** e **Pessoa Física (Crédito Consignado / CPF)**, com higienização rigorosa de dados, prova técnica de WhatsApp, tarifação transparente Pay-Per-Value e governança LGPD.

O sistema opera sob o princípio estrito de **não fabricação de dados**: cada informação entregue possui origem auditável, carimbo de tempo, método determinístico, score estatístico de confiança e base legal explicitada.

---

## 🚀 Principais Capacidades

### 1. Payload Canônico PJ v2.4.0 (14 Blocos B2B)
Disponível em `GET /api/v1/leads/{lead_id}/canonical/` (especificação canônica em [`payload.json`](payload.json)):
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

### 2. Módulo Canônico PF & Crédito Consignado v2.4.0 (15 Blocos de Inteligência)
Disponível em `POST /api/v1/enrichment/person/` e `GET /api/v1/leads/lookup/?q={cpf}` (especificação completa em [`payload_pf.json`](payload_pf.json)):

- **01. Metadados (`_meta`):** UUID canônico da pessoa física, timestamp ISO 8601, tenant contextualizado, ID do pipeline de execução e score global de confiança (ex: `0.98`).
- **02. Identificação & Qualificação (`identification`):** Status de qualificação cadastral (`QUALIFIED`), lead score (0 a 100), confiança estatística, cobrança de créditos e tags financeiras (`CPF_REGULAR`, `INSS_BENEFICIARIO_ATIVO`, `ESPECIE_41_APTO`, `MARGEM_DISPONIVEL`, `WHATSAPP_CONFIRMADO`, `NAO_ME_PERTURBE_PARCIAL`).
- **03. Validação Documental & Módulo 11 RFB (`document_validation`):** CPF formatado (`000.000.000-00`) e numérico puro, conferência rigorosa dos 2 dígitos verificadores pelo algoritmo oficial Módulo 11 da Receita Federal e mapeamento determinístico da Região Fiscal de emissão.
- **04. Dados Cadastrais Oficiais (`cadastral_data`):** Nome completo, data de nascimento, idade calculada, gênero, filiação completa (nome da mãe e do pai), situação cadastral RFB (`REGULAR`, `SUSPENSA`, etc.), data da situação e código de controle da certidão.
- **05. Filtro de Perda & Tarifa Zero de Créditos (`loss_prevention_filter`):** Verificação atômica de óbito via Sistema Nacional de Informações de Registro Civil (RCPN/SIRC) e situação cadastral na RFB. Caso detectado óbito ou documento cancelado/nulo, o pipeline expurga o lead imediatamente, bloqueia chamadas a provedores pagos subsequentes e **tarifa ZERO créditos** da carteira do cliente.
- **06. Core Consignado INSS (`consignado_inss`):** Benefícios previdenciários, espécie com código oficial (ex: `41` - Aposentadoria por Idade, `21` - Pensão por Morte) e descrição, categoria de aptidão (`APTO_CONSIGNAVEL`), status ativo, datas de concessão e cessação, valores bruto e líquido, descontos obrigatórios, flag de bloqueio para empréstimo e dados bancários da conta pagadora (código de compensação bancária, nome do banco, agência, conta corrente/magnética, meio de pagamento, município e UF).
- **07. Consignado SIAPE & Vínculos Públicos (`consignado_siape_publico`):** Matrícula funcional, órgão público de vínculo, unidade organizacional (UORG), cargo efetivo, regime estatutário, situação funcional (ativo, aposentado, pensionista), UF de lotação e remuneração bruta declarada.
- **08. Margem Consignável Calculada (`margem_consignavel_calculada`):** Base legal da Lei Federal nº 14.431/2022. Desdobramento matemático rigoroso em 4 margens auditáveis:
  - **Margem de Empréstimo (35%):** Limite para empréstimos consignados tradicionais (`percentual: 35.0`).
  - **Margem RMC (5%):** Reserva de Margem Consignável para Cartão de Crédito Consignado (`percentual: 5.0`).
  - **Margem RCC (5%):** Reserva de Cartão Consignado de Benefício (`percentual: 5.0`).
  - **Margem Total Disponível (45%):** Teto regulatório consolidado (`percentual: 45.0`).
- **09. Telefonia Higienizada (`telefonia_higienizada`):** Extração e normalização de telefones com **DDD separado do número em dígitos puros** (sem `-`, `+` ou espaços), formato internacional E.164 (`+55...`), operadora oficial ANATEL (Vivo, Claro, TIM, Oi), tipo de linha (`MOVEL_CELULAR` vs `FIXO`) e score de recência/atividade.
- **10. WhatsApp Probe Técnico (`whatsapp_probe_tecnico`):** Gateway ativo de validação em tempo real (Evolution API / WPPConnect). Confirma a existência do número na rede WhatsApp, extrai o JID oficial (`...@s.whatsapp.net`), classifica a conta (`WHATSAPP_PESSOAL` vs `WHATSAPP_BUSINESS`), recupera foto de perfil real e link de contato direto (`https://wa.me/...`).
- **11. Não Me Perturbe Anatel & Febraban (`nao_me_perturbe_anatel_febraban`):** Consulta da lista regulatória nacional de bloqueio de telemarketing para crédito consignado e serviços financeiros. Identifica inscrições ativas, data do bloqueio, flag `seguro_discagem_fria` e nível de risco de multas PROCON (`BAIXO` vs `ALTO`).
- **12. Mailing Qualificado Top 3 Celulares (`mailing_qualificado_top3`):** Ranqueamento inteligente dos melhores números móveis com score de assertividade (0 a 100). Cruza WhatsApp validado com status de Não Me Perturbe, fornecendo recomendação de canal operacional (`DISCAGEM_E_WHATSAPP` ou `APENAS_WHATSAPP_COMPLIANCE`).
- **13. Endereço Cadastral Higienizado (`address_cadastral`):** Logradouro oficial, número, complemento, bairro, município, UF, CEP com máscara e código IBGE do município.
- **14. Indicadores Financeiros & Renda (`financial_indicators`):** Renda mensal estimada e declarada, enquadramento em faixas de salários mínimos e fontes de renda identificadas (INSS, SIAPE, CLT).
- **15. Governança LGPD & Compliance (`governance_and_lgpd`):** Enquadramento legal sob a Lei Geral de Proteção de Dados (Art. 7º, X — Proteção do Crédito e Art. 7º, IX — Legítimo Interesse), finalidade estrita de prevenção a fraudes e análise de crédito, e hash criptográfico SHA-256 de auditoria imutável.

#### 🛡️ As 4 Camadas Especializadas de Negócio (Pipeline Consignado)

| Camada | Denominação | Função Técnica e Regra de Negócio |
|---|---|---|
| **Camada 1** | **Filtro de Perda** | Expurgo preventivo de óbitos (RCPN/SIRC) e CPFs irregulares na RFB. **Corta chamadas a provedores pagos e tarifa ZERO créditos** do cliente. |
| **Camada 2** | **Core Consignado** | Leitura de benefícios INSS e SIAPE com cálculo exato das 4 margens da Lei 14.431/2022 (35% empréstimo + 5% RMC + 5% RCC = 45% total), analisando espécies aptas e bloqueios. |
| **Camada 3** | **Não Me Perturbe** | Consulta à lista Anatel/Febraban contra multas do PROCON, segregando telefones liberados para discagem fria daqueles restritos a abordagens de compliance. |
| **Camada 4** | **Mailing Top 3 & WhatsApp Probe** | Ranqueamento dos 3 melhores celulares com teste de handshake no gateway de WhatsApp (Evolution API), extração de JID, tipo de conta e foto de perfil. |

#### 🧮 Algoritmo Módulo 11 da Receita Federal & 10 Regiões Fiscais

O CPF é composto por 11 dígitos no formato `ABC.DEF.GHI-JK`. Os 9 primeiros dígitos (`ABCDEFGHI`) constituem a base documental, o 9º dígito (`I`) define a **Região Fiscal de emissão**, e os 2 últimos dígitos (`JK`) são os **Dígitos Verificadores (DV)** gerados pelo algoritmo oficial Módulo 11:

1. **Cálculo do 1º Dígito Verificador (`J`):**
   $$\text{Soma}_1 = (A \times 10) + (B \times 9) + (C \times 8) + (D \times 7) + (E \times 6) + (F \times 5) + (G \times 4) + (H \times 3) + (I \times 2)$$
   $$\text{Resto}_1 = \text{Soma}_1 \pmod{11}$$
   $$J = 0 \quad \text{se } \text{Resto}_1 < 2, \quad \text{senão } J = 11 - \text{Resto}_1$$

2. **Cálculo do 2º Dígito Verificador (`K`):**
   $$\text{Soma}_2 = (A \times 11) + (B \times 10) + (C \times 9) + (D \times 8) + (E \times 7) + (F \times 6) + (G \times 5) + (H \times 4) + (I \times 3) + (J \times 2)$$
   $$\text{Resto}_2 = \text{Soma}_2 \pmod{11}$$
   $$K = 0 \quad \text{se } \text{Resto}_2 < 2, \quad \text{senão } K = 11 - \text{Resto}_2$$

##### Mapeamento Determinístico das Regiões Fiscais da Receita Federal:
| 9º Dígito | Região Fiscal | Jurisdição / Estados (UFs) | Sede Regional |
|:---:|:---:|:---|:---|
| **0** | 10ª Região Fiscal | Rio Grande do Sul (RS) | Porto Alegre / RS |
| **1** | 1ª Região Fiscal | Distrito Federal (DF), Goiás (GO), Mato Grosso (MT), Mato Grosso do Sul (MS), Tocantins (TO) | Brasília / DF |
| **2** | 2ª Região Fiscal | Acre (AC), Amazonas (AM), Amapá (AP), Pará (PA), Rondônia (RO), Roraima (RR) | Belém / PA |
| **3** | 3ª Região Fiscal | Ceará (CE), Maranhão (MA), Piauí (PI) | Fortaleza / CE |
| **4** | 4ª Região Fiscal | Alagoas (AL), Paraíba (PB), Pernambuco (PE), Rio Grande do Norte (RN) | Recife / PE |
| **5** | 5ª Região Fiscal | Bahia (BA), Sergipe (SE) | Salvador / BA |
| **6** | 6ª Região Fiscal | Minas Gerais (MG) | Belo Horizonte / MG |
| **7** | 7ª Região Fiscal | Espírito Santo (ES), Rio de Janeiro (RJ) | Rio de Janeiro / RJ |
| **8** | 8ª Região Fiscal | São Paulo (SP) | São Paulo / SP |
| **9** | 9ª Região Fiscal | Paraná (PR), Santa Catarina (SC) | Curitiba / PR |

#### Como Consultar Pessoas Físicas (CPF) via API:

```bash
# Consulta com enriquecimento especializado e validação técnica de WhatsApp
curl -X POST http://localhost:8000/api/v1/enrichment/person/ \
  -H "Authorization: Bearer <token_jwt>" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "14715435799",
    "capabilities": [
      "cpf_cadastral",
      "consignado_core",
      "filtro_perda_obito",
      "nao_me_perturbe",
      "mailing_top3_discagem",
      "phones_whatsapp_garantido"
    ]
  }'

# Lookup unificado de lead por documento (detecta 11 dígitos = PF)
curl -X GET "http://localhost:8000/api/v1/leads/lookup/?q=14715435799" \
  -H "Authorization: Bearer <token_jwt>"
```

---

### 3. Camada de Segurança Enterprise, Sessão Frontend & RBAC
- **Autenticação Híbrida & Sessão do Usuário:**
  - **Perfil & Sessão Unificada (`GET /api/v1/auth/me/`):** Retorna os dados do operador/chave autenticado, tenant ativo, permissões de acesso e listagem de workspaces disponíveis para troca de contexto.
  - **Troca Dinâmica de Workspace (`POST /api/v1/auth/switch-workspace/`):** Permite a operadores humanos alternar o tenant ativo em tempo real, recebendo novos tokens JWT vinculados ao workspace solicitado.
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

### 4. Processamento em Massa, Outbox Contínuo & Webhooks
- **Ingestão de Lotes (`/api/v1/lotes/`):** Processamento assíncrono de até 100.000 registros fatiados em chunks idempotentes (25–100 leads) no Celery + RabbitMQ.
- **Agendador Contínuo Celery Beat:**
  - Tarefa periódica `process_crm_outbox_batch` executando a cada 30 segundos para drenar a fila transacional do Outbox e retentar falhas transitórias com backoff exponencial.
- **Assinatura Criptográfica HMAC-SHA256 para Webhooks:**
  - Headers `X-LeadStream-Signature` (SHA-256 direto) e `X-LeadStream-Signature-V2` (`t=<timestamp>,v1=<signature>`) com proteção ativa contra *replay attacks*.
- **Observabilidade & Gestão de Dead-Letter:**
  - `GET /api/v1/integracoes/outbox/status/`: Métricas em tempo real sobre mensagens `PENDING`, `DELIVERED`, `FAILED` e `DEAD_LETTER`.
  - `POST /api/v1/integracoes/outbox/retry-dead-letter/`: Reprocessamento manual ou em lote de mensagens em falha definitiva.
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
       +------------+---> Cascata de Provedores (OpenCNPJ / Portal da Transparência / BigDataCorp / Apify)
```

### Portal da Transparência / CGU

O provedor `portal-transparencia` usa uma cascata guiada pelo perfil-resumo oficial. Ele não
dispara todos os endpoints para cada lead: primeiro consulta `pessoa-juridica` ou
`pessoa-fisica`, aciona somente as famílias sinalizadas e pagina cada rota dentro dos limites
configurados. IDs retornados podem abrir detalhes de contratos e notas fiscais, também com
limite explícito. A resposta registra endpoints executados, endpoints omitidos, cobertura,
truncamento, data da observação e identificadores externos de requisição.

- **PJ:** CEIS, CNEP, CEPIM e acordos de leniência são sempre verificados no bloco de risco;
  contratos, notas fiscais, renúncias fiscais, recursos, documentos de despesa e cartões são
  consultados somente quando o perfil indicar o vínculo.
- **PF:** PEP é verificado porque o perfil não possui flag correspondente. Servidor público,
  imóvel funcional, sanções CEIS/CNEP/CEAF, contratos, viagens, cartões e recebimentos públicos
  são consultados somente quando sinalizados. Benefícios sociais, remuneração e pensões são
  deliberadamente excluídos da cascata automática.

O token é enviado exclusivamente no cabeçalho `chave-api-dados`. A quota é global entre todos
os workspaces e contabiliza somente requisições HTTP reais (acertos de cache não consomem
quota): 400 por minuto entre 06:00 e 23:59, 700 entre 00:00 e 05:59 e 180 para rotas restritas.
Ao atingir a quota, o chunk volta à fila sem consumir uma tentativa técnica nem classificar o
lead como ausente. Respostas ficam em cache por 24 horas por padrão. Os limites de páginas,
detalhes e janela histórica são controlados por `PORTAL_TRANSPARENCIA_MAX_PAGES`,
`PORTAL_TRANSPARENCIA_MAX_DETAIL_RECORDS` e
`PORTAL_TRANSPARENCIA_EXPENSE_LOOKBACK_YEARS`.

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

## 💰 Carteira de Créditos & Faturamento Pay-Per-Value

O LeadStream opera com faturamento baseado exclusivamente no valor útil entregue:
- **Reserva Atômica (Hold):** Ao submeter um lote, os créditos orçados são reservados temporariamente.
- **Cobrança Real (Capture):** Apenas blocos enriquecidos e validados com alta confiança geram faturamento.
- **Estorno Automático (Release):** Se dados de decisores ou e-mails estiverem ausentes ou inválidos, os créditos não utilizados são estornados instantaneamente na conclusão do lote.

```bash
# Consultar saldo e reserva do Workspace ativo
curl -X GET http://localhost:8000/api/v1/faturamento/carteira/ \
  -H "Authorization: Bearer <token_jwt>"

# Consultar extrato contábil imutável
curl -X GET http://localhost:8000/api/v1/faturamento/carteira/extrato/ \
  -H "Authorization: Bearer <token_jwt>"

# Recarregar créditos
curl -X POST http://localhost:8000/api/v1/faturamento/carteira/recarga/ \
  -H "Authorization: Bearer <token_jwt>" \
  -H "Content-Type: application/json" \
  -d '{"amount": 500, "reference_id": "RECARGA-PIX-001"}'
```

---

## ✉️ Motor de Entregabilidade de E-mails (Zero-Bounce Guarantee)

Validação atômica profunda em 5 níveis com handshake SMTP em tempo real e detecção de servidores *Catch-All*:

```bash
curl -X POST http://localhost:8000/api/v1/validacao/emails/ \
  -H "Authorization: Bearer <token_jwt>" \
  -H "Content-Type: application/json" \
  -d '{"email": "ceo@empresa.com.br", "deep_smtp": true}'
```

---

## 📄 Contratos Canônicos & Artefatos de Referência

O LeadStream disponibiliza especificações JSON canônicas estritas que servem como padrão contratual da API:

| Arquivo de Referência | Entidade | Versão | Blocos de Inteligência | Foco de Negócio |
|---|:---:|:---:|:---:|---|
| [`payload.json`](payload.json) | **Pessoa Jurídica (PJ)** | v2.4.0 | 14 blocos | Decisores corporativos, QSA, enriquecimento LinkedIn, inteligência fiscal/tributária e entregabilidade de e-mails. |
| [`payload_pf.json`](payload_pf.json) | **Pessoa Física (PF)** | v2.4.0 | 15 blocos | Crédito consignado (INSS / SIAPE), 4 margens (Lei 14.431/2022), filtro de óbito, Não Me Perturbe e WhatsApp Probe. |

---

## 🧪 Qualidade & Testes Automatizados

O repositório opera sob um pipeline rigoroso de integração contínua e qualidade estrita com **100% de aprovação**:

```bash
# Executar todos os 5 gates de qualidade de uma só vez (Windows PowerShell)
powershell -File scripts/quality.ps1

# Ou executar individualmente:
uv run pytest -q                 # 199 testes automatizados
uv run mypy src                  # Verificação estrita de tipos
uv run ruff check .              # Verificação de lint e boas práticas
python manage.py makemigrations --check --dry-run  # Integridade do banco
python manage.py check --deploy  # Verificação de conformidade para produção
```

### Métricas Auditadas:
- **199 testes automatizados aprovados** (`199 passed, 2 skipped`): cobertura ponta a ponta de segurança, RBAC, modelos relacionais, contratos canônicos v2.4.0 (PJ e PF), CRM outbox, carteira de créditos (pay-per-value), motor de probe SMTP e pipelines de dados.
- **Zero erros de Mypy** em **164 arquivos de código-fonte** (`Success: no issues found in 164 source files`): tipagem forte e estrita em todos os adaptadores de provedores, serializadores e views.
- **Zero erros de lint e formatação** sob as regras do Ruff (`pyproject.toml`).
- **Verificação de deployment ativa**: aprovação no check de segurança para produção do Django.

---

## 📦 Implantação em Produção

Siga o [Runbook do EasyPanel](deploy/easypanel.md) e utilize [`deploy/env.production.example`](deploy/env.production.example) como checklist de variáveis de ambiente. Segredos reais pertencem exclusivamente ao cofre do EasyPanel e nunca devem ser versionados no Git.
