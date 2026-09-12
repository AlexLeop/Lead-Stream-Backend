# LeadStream Frontend — Especificação Arquitetural e de Design

**Data:** 2026-09-12  
**Status:** Aprovado  
**Autor:** Antigravity + AlexLeop  
**Projeto:** LeadStream Frontend (Reaproveitamento, Modernização e Migração do MVP)

---

## 1. Visão Geral e Objetivos

O **LeadStream Frontend** é a interface web corporativa do ecossistema LeadStream, conectando usuários e operadores ao núcleo backend independente Django 5.2 / Celery / PostgreSQL.

O objetivo deste projeto é migrar e elevar a base do frontend existente em `C:\Users\lxleo\Documents\Meus projetos\LeadStream` para um subdiretório `frontend/` neste repositório (`LeadStream-Backend`), aperfeiçoando-o para atender aos rigorosos requisitos corporativos:
- **Zero emojis e poluição visual**: Design sério, sóbrio, limpo e institucional (estilo Stripe / Bloomberg / Linear).
- **Consumo da API Django 5.2**: Conexão aos endpoints REST `/api/v1/` com autenticação JWT segura, auto-refresh e proteção de rotas.
- **Visualização do Ledger Pay-Per-Value**: Exibição em tempo real de saldo disponível, saldo em custódia e extrato contábil auditável com estornos automáticos de leads ausentes.
- **Monitoramento de Lotes Assíncronos**: Upload de arquivos com chunking (50 a 5.000 linhas), progresso em tempo real e exportação sob demanda.
- **Deploy Independente no EasyPanel**: Containerização multi-stage (Node 22 build -> Nginx Alpine runtime) para execução leve e isolada na porta 80.

---

## 2. Stack Tecnológica

| Tecnologia | Versão | Finalidade |
|---|---|---|
| **React** | 19.x | Biblioteca de UI declarativa |
| **Vite** | 6.x | Bundler de alta performance e servidor local |
| **TypeScript** | 5.8+ | Tipagem estrita com contratos espelhados do backend DRF |
| **Tailwind CSS** | 4.x | Estilização por tokens utilitários com paleta corporativa |
| **Lucide React** | 0.546+ | Ícones funcionais mínimos (12-16px) |
| **Recharts** | 3.x | Gráficos e métricas financeiras/operacionais |
| **Nginx Alpine** | Alpine 3.20+ | Webserver de produção leve (~20MB RAM) para rotas SPA |

---

## 3. Diretrizes de Design & Estética Corporativa

1. **Restrições Visuais Rígidas**:
   - Proibido uso de emojis em títulos, botões, tabelas ou notificações.
   - Proibido ícones decorativos grandes ou ilustrações lúdicas. Usar apenas ícones funcionais discretos (ex: setas de navegação, status dots de 6px).
   - Tipografia: **Inter** para títulos e textos gerais; **JetBrains Mono** para CNPJs, valores de saldo, créditos, hashes de proveniência e timestamps.
2. **Paleta de Cores Institucional**:
   - Fundo base: Dark Mode refinado (Slate/Zinc 950 `#090A0F`, cartões `#12141C`, bordas sutis `rgba(255, 255, 255, 0.08)`).
   - Destaque funcional Verde Esmeralda (`#10B981`): Apenas para dados verificados, saldo ativo e status de sucesso.
   - Destaque funcional Âmbar (`#F59E0B`): Para créditos em custódia preventiva (hold) e status em processamento.
   - Destaque funcional Carmesim (`#EF4444`): Para falhas reais de validação e emails inválidos.
   - Neutro Texto: Branco off-white (`#F8FAFC`) para títulos, cinza médio (`#94A3B8`) para labels.

---

## 4. Arquitetura de Autenticação e Rede

1. **Tokens JWT**:
   - `POST /api/v1/auth/token/`: Autentica `username` e `password`. Retorna `access` e `refresh`.
   - `POST /api/v1/auth/token/refresh/`: Renova o token de acesso.
   - `GET /api/v1/auth/me/`: Obtém perfil do usuário, workspace/tenant e papel (`role`).
2. **Armazenamento e Interceptação**:
   - Armazenamento em `localStorage` (`leadstream_access_token`, `leadstream_refresh_token`).
   - Interceptor de requisições:
     - Injeta `Authorization: Bearer <access_token>` em todas as chamadas.
     - Intercepta `401 Unauthorized`: chama `/auth/token/refresh/` transparentemente; se falhar, limpa o estado e redireciona para `/login`.
3. **Roteamento Protegido**:
   - Rota `/login`: Pública.
   - Todas as outras rotas (`/`, `/lotes`, `/carteira`, `/validacao`, `/pesquisa`): Protegidas pelo componente `PrivateRoute`.

---

## 5. Mapeamento de Telas e Módulos

### 5.1. Tela de Login (`/login`)
- Layout centralizado minimalista, sem distrações.
- Formulário com campos `Usuário` e `Senha`.
- Tratamento de erro com mensagem em português claro.
- Redirecionamento para a página inicial após autenticação bem-sucedida.

### 5.2. Cabeçalho Global e Barra de Saldo (`AppShell.tsx`)
- Seletor de Workspace / Tenant ativo.
- **Pill de Carteira Contábil**:
  - Saldo Disponível (em destaque verde/branco).
  - Saldo Reservado em Custódia (em âmbar, indicando lotes em processamento).
  - Botão de ação direta para detalhes da carteira.
- Status do Sistema (indicador verde de latência da API).
- Perfil do operador com opção de Logout.

### 5.3. Painel de Controle (`/` ou `/dashboard`)
- Indicadores principais: Empresas Processadas, Taxa de Enriquecimento (Match Rate), Eficiência Zero-Bounce, Créditos Estornados por Pay-per-Value.
- Lotes recentes e jobs Celery ativos com barra de progresso em tempo real.

### 5.4. Central de Lotes e Upload (`/lotes`)
- Drag-and-drop de arquivos CSV ou Parquet (até 100.000 linhas).
- Seletor de tamanho de chunk (50, 100, 500, 1000).
- Aviso de pré-autorização de créditos e estorno automático de linhas sem dados úteis.
- Tabela de Lotes: ID, Nome, Data, Total, Sucesso, Falhas, Estornos, Estado, Ações (Pausar, Retomar, Cancelar, Exportar CSV/Parquet).

### 5.5. Dossiê Completo da Empresa (`LeadDetailsModal.tsx`)
- Slide-over / Modal corporativo:
  - Cabeçalho: CNPJ formatado, Razão Social, Fantasia, Situação Cadastral na Receita Federal.
  - Decisores e QSA: Nomes, Cargos, Nível Hierárquico, LinkedIn validado, Score de Confiança (0-100%).
  - Matriz de Contatos: E-mails corporativos com selo de entregabilidade Zero-Bounce (SMTP 250 OK, Catch-All, Inválido).
  - Prova de Evidência e Proveniência: Origem dos blocos de dados, carimbo temporal oficial e hash SHA-256.

### 5.6. Carteira e Ledger Contábil (`/carteira`)
- Cards de Saldo: Disponível vs Em Custódia vs Total Histórico.
- Tabela contábil de dupla entrada (Ledger): Data/Hora, Operação (Depósito, Hold, Captura, Estorno), Montante, Saldo Resultante, Lote associado.
- Destaque claro de estornos: *"Estorno automático de X créditos — ausência de dados úteis"*.

### 5.7. Validador de E-mail Zero-Bounce (`/validacao`)
- Verificação atômica de e-mail corporativo.
- Exibição do handshake SMTP RFC 5321 (DNS MX, HELO, MAIL FROM, RCPT TO) e teste de canário anti-catch-all.

---

## 6. Containerização e Deploy no EasyPanel

### 6.1. Dockerfile Multi-Stage (`frontend/Dockerfile`)
```dockerfile
# Stage 1: Build
FROM node:22-alpine AS builder
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm ci || npm install
COPY . .
ARG VITE_API_URL
ENV VITE_API_URL=$VITE_API_URL
RUN npm run build

# Stage 2: Production Web Server
FROM nginx:alpine
COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
```

### 6.2. Configuração Nginx (`frontend/nginx.conf`)
```nginx
server {
    listen 80;
    server_name localhost;

    location / {
        root /usr/share/nginx/html;
        index index.html index.htm;
        try_files $uri $uri/ /index.html;
    }

    error_page 500 502 503 504 /50x.html;
    location = /50x.html {
        root /usr/share/nginx/html;
    }
}
```

---

## 7. Critérios de Aceitação e Verificação

1. Todo o código do frontend compila perfeitamente sem erros de TypeScript (`npm run build`).
2. Rota `/login` realiza autenticação contra o backend Django e armazena tokens JWT.
3. Rotas autenticadas consomem dados reais de `/api/v1/batches/`, `/api/v1/billing/wallet/`, `/api/v1/validation/email/`.
4. Interface estritamente aderente ao padrão corporativo clean (zero emojis, paleta refinada, tipografia Inter/Monospace).
5. O `Dockerfile` e `nginx.conf` estão prontos para deploy no EasyPanel como serviço independente.
