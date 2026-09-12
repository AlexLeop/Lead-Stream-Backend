# Especificação Arquitetural: Torre de Gestão Master & White-Label (LeadStream)

**Data:** 12/09/2026  
**Status:** Aprovado  
**Autores:** Equipe de Engenharia LeadStream & Impeccable Design System  
**Padrão de UX:** `impeccable` (Product Register: Alta Densidade de Dados, Escala Compacta, Zero Fakes)

---

## 1. Visão Geral e Propósito

A **Torre de Gestão Master** transforma o LeadStream em uma plataforma corporativa multi-tenant e white-label completa, permitindo que o gestor/proprietário do sistema exerça governança, configuração e controle operacional irrestrito sobre toda a infraestrutura, clientes, precificação, limites, provedores e identidade da interface.

### Princípios Fundamentais
1. **Verdade Absoluta dos Dados (Zero Mocks / Zero Fakes)**:
   - Toda informação renderizada em tela reflete estritamente o estado real persistido no PostgreSQL (`leadstream_tenant`, `security_workspace_memberships`, `leadstream_credit_wallet`, `leadstream_price_rule`, `leadstream_batch`, `security_audit_logs`).
   - Se um cliente ou o sistema não possui registros cadastrados, a interface exibe contadores zerados (`0`) e *empty states* sóbrios e instrutivos, sem jamais injetar dados inventados.
2. **Densidade Compacta Enterprise (*Impeccable Product Register*)**:
   - Escala contida e calibrada (Linear/Datadog standard): numéricos principais em `text-base` / `text-lg` (font-mono), rótulos em `text-[11px]`, tabelas compactas com `py-1.5` / `py-2`, eliminando paddings inchados e cartões de escala gigante.
3. **Controle Total Multi-Tenant**:
   - Gestão de clientes, usuários, limites de execução, tabelas de preço, carteiras contábeis, chaves de API, provedores e branding customizado em um único painel.

---

## 2. Módulos Funcionais e Endpoints

### Módulo 1: Customização White-Label & Identidade Visual
- **Campos Configuráveis**:
  - `platform_name`: Nome exibido na interface e e-mails (padrão: "LeadStream").
  - `logo_url_dark` / `logo_url_light`: URLs das marcas para modo escuro e claro.
  - `favicon_url`: Ícone do navegador.
  - `accent_color`: Cor primária de destaque (Esmeralda `#10B981`, Safira `#3B82F6`, Índigo `#6366F1`, Âmbar `#F59E0B`).
  - `support_email`: E-mail de contato e suporte aos clientes.
  - `terms_url` / `privacy_url`: Links contratuais de governança.
- **Endpoints**:
  - `GET /api/v1/system/branding/` (Público/Autenticado): Retorna a identidade ativa.
  - `PATCH /api/v1/system/branding/` (Superadmin): Atualiza e persiste a identidade visual.

### Módulo 2: Clientes & Workspaces (Tenants)
- **Operações Administrativas**:
  - `GET /api/v1/admin/tenants/`: Lista todos os clientes com paginação, busca e filtros.
  - `POST /api/v1/admin/tenants/`: Criação de novo cliente (`name`, `slug`, `admin_email`, `initial_credits`).
  - `PATCH /api/v1/admin/tenants/<id>/`: Edição de limites operacionais:
    - `is_active` (Booleano): Ativação / Bloqueio instantâneo do cliente.
    - `max_batch_size`: Teto de linhas por lote (5k, 25k, 100k).
    - `rate_limit_per_minute`: Requisições por minuto permitidas.
    - `max_concurrency`: Concorrência de workers Celery alocados.
  - `POST /api/v1/admin/tenants/<id>/impersonate/`: Gera token de contexto para assumir o workspace do cliente em 1 clique.

### Módulo 3: Usuários, Equipes & Chaves de API
- **Operações Administrativas**:
  - `GET /api/v1/admin/users/`: Lista todos os usuários do sistema com seus respectivos workspaces e papéis.
  - `POST /api/v1/admin/users/`: Criação de usuário ou convite associado a um tenant.
  - `PATCH /api/v1/admin/users/<id>/`: Alteração de papel (`ADMIN`, `OPERATOR`, `READ_ONLY`), status ativo/inativo e redefinição de credenciais.
  - `GET /api/v1/admin/api-keys/`: Listagem de chaves de integração ativas por cliente.
  - `POST /api/v1/admin/api-keys/`: Emissão de nova chave criptográfica (`APIKey`).
  - `DELETE /api/v1/admin/api-keys/<id>/`: Revogação imediata de chave.

### Módulo 4: Planos, Preços por Bloco & Ledger Contábil
- **Operações Administrativas**:
  - `GET /api/v1/admin/pricing/`: Consulta de tabelas de preços (`PriceBook`) e regras (`PriceRule`).
  - `PUT /api/v1/admin/pricing/<book_id>/`: Edição dos valores unitários por bloco de dado:
    - `COMPANY_REGISTRY` (Centavos por CNPJ básico).
    - `DECISION_MAKER` (Centavos por decisor/sócio QSA identificado).
    - `DIRECT_EMAIL` (Centavos por e-mail validado RFC 5321).
    - `WHATSAPP` / `DIRECT_PHONE` (Centavos por telefone/WhatsApp móvel).
    - `minimum_confidence` e `refresh_window_days`.
  - `GET /api/v1/admin/wallets/`: Visão consolidada dos saldos de todos os clientes.
  - `POST /api/v1/admin/wallets/<tenant_id>/credit/`: Injeção ou estorno manual de créditos, gravando a justificativa obrigatória no livro-razão imutável (`CreditTransaction` com tipo `DEPOSIT`).

### Módulo 5: Provedores Externos, Orçamento & Roteamento
- **Operações Administrativas**:
  - `GET /api/v1/admin/providers/`: Status de conexão e credenciais de provedores (BigDataCorp, Apify, Receita Federal, Appwrite).
  - `PATCH /api/v1/admin/providers/<provider_id>/`: Habilitação, chave de API e ordem de fallback prioritário.
  - `PATCH /api/v1/admin/providers/budget/`: Configuração de limite financeiro diário e teto por lead (*circuit breaker*).

### Módulo 6: Governança, Lista de Supressão & LGPD
- **Operações Administrativas**:
  - `GET /api/v1/admin/suppression/`: Lista de CNPJs, domínios e e-mails bloqueados (Opt-Out).
  - `POST /api/v1/admin/suppression/`: Adição de identificadores à blacklist com motivo.
  - `DELETE /api/v1/admin/suppression/<id>/`: Remoção de supressão.
  - `GET /api/v1/admin/audit-logs/`: Consulta filtrável aos logs imutáveis (`SecurityAuditLog`).

### Módulo 7: Motor Zero-Bounce & Parâmetros SMTP
- **Operações Administrativas**:
  - `GET /api/v1/admin/smtp-config/`: Parâmetros do motor de validação.
  - `PATCH /api/v1/admin/smtp-config/`: Calibração de timeout de conexão MX, portas (25/587) e classificação de servidores *catch-all*.
  - `POST /api/v1/admin/smtp-probe/`: Teste interativo em tempo real de probe RFC 5321.

### Módulo 8: Orquestração de Lotes (100k) & Filas Celery
- **Operações Administrativas**:
  - `GET /api/v1/admin/batches/`: Monitoramento global de lotes em processamento em todos os workspaces.
  - `POST /api/v1/admin/batches/<id>/pause/`: Pausar execução do lote.
  - `POST /api/v1/admin/batches/<id>/resume/`: Retomar execução do lote.
  - `POST /api/v1/admin/batches/<id>/cancel/`: Cancelar lote com estorno automático da custódia.
  - `GET /api/v1/admin/celery/queues/`: Telemetria das filas (ingestão, chunks, normalização).

---

## 3. Arquitetura Frontend (`frontend/src/`)

### Design System Impeccable (Product Register)
- **Densidade Compacta**:
  - Navegação superior compacta com indicador de modo Superadmin, seletor de Workspace ativo e atalhos globais.
  - Rótulos e textos de interface estritamente contidos (`text-[11px]` e `text-[12px]`).
  - Tabelas de dados com cabeçalhos mono, linhas compactas (`py-2`), status tags monocromáticas e sem sombras difusas.
- **Estrutura de Componentes**:
  - `pages/AdminCenter.tsx`: Visão unificada com abas de alta densidade:
    - Aba: `Tenants & Clientes`
    - Aba: `Usuários & Permissões`
    - Aba: `Planos & Preços`
    - Aba: `Carteiras & Ledger`
    - Aba: `Lotes & Celery`
    - Aba: `Provedores & Roteamento`
    - Aba: `Governança & Supressão`
    - Aba: `Zero-Bounce SMTP`
    - Aba: `White-Label & Marca`
  - `components/BrandingProvider.tsx`: Injeta dinamicamente as cores de destaque, logo e nome da plataforma em toda a aplicação.

---

## 4. Plano de Validação & Conformidade

1. **Testes Unitários & Integração (Pytest)**:
   - Cobertura completa de todos os endpoints administrativos (`/api/v1/admin/*` e `/api/v1/system/branding/`).
   - Validação de permissão restrita a `is_superuser` / papéis administrativos master.
2. **Linting & Análise Estática**:
   - `ruff check src/ tests/` (100% de conformidade com PEP 8).
   - `mypy src/` (Zero erros de tipagem estrita).
   - `npm run lint` no frontend (TypeScript sem falhas).
3. **Deploy & Produção Real**:
   - Commit e envio para `origin/main`.
   - Validação dos endpoints e interface nos ambientes do EasyPanel.
