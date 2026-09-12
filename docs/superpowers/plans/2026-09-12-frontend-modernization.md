# LeadStream Frontend — Plano de Implementação

> **Para execução autônoma (/goal):** Sub-skill `superpowers:subagent-driven-development` ou execução sequencial rigorosa. Cada etapa usa a sintaxe de checkbox `- [ ]`.

**Objetivo:** Migrar, modernizar e conectar o frontend do MVP (`C:\Users\lxleo\Documents\Meus projetos\LeadStream`) para o diretório `frontend/` neste repositório, alinhado aos contratos REST do Django 5.2, autenticação JWT, carteira contábil e estética corporativa clean (zero emojis).

**Spec de Referência:** [docs/superpowers/specs/2026-09-12-frontend-modernization-design.md](file:///c:/Users/lxleo/Documents/Meus%20projetos/LeadStream-Backend/docs/superpowers/specs/2026-09-12-frontend-modernization-design.md)

---

## Estrutura de Tarefas

### Task 1: Estrutura Base, Configurações e Containerização (`frontend/`)
- [ ] **Passo 1.1**: Criar o diretório `frontend/` e copiar os arquivos base do MVP (`package.json`, `tsconfig.json`, `vite.config.ts`, `index.html`, pasta `src/`, `public/`).
- [ ] **Passo 1.2**: Ajustar `package.json` para garantir dependências compatíveis e script de build limpo.
- [ ] **Passo 1.3**: Criar `frontend/Dockerfile` multi-stage (Node 22 build -> Nginx Alpine runtime) e `frontend/nginx.conf` com suporte a rotas SPA (`try_files`).
- [ ] **Passo 1.4**: Configurar `vite.config.ts` para ler `VITE_API_URL` e configurar proxy local para desenvolvimento.

### Task 2: Camada de API, Autenticação JWT e Tipos (`frontend/src/`)
- [ ] **Passo 2.1**: Atualizar `frontend/src/types.ts` com interfaces TypeScript que espelham exatamente os modelos e serializers do backend Django (Batch, BatchItem, CreditWallet, CreditTransaction, EmailValidation, User, Tenant).
- [ ] **Passo 2.2**: Refatorar `frontend/src/api.ts` para consumir `VITE_API_URL`, com injeção do token JWT `Bearer`, interceptor de auto-refresh em respostas 401 e métodos específicos para cada endpoint (`auth`, `batches`, `wallet`, `validation`, `canonical`).
- [ ] **Passo 2.3**: Criar a tela de login corporativa `frontend/src/pages/Login.tsx` (sóbria, minimalista, campos de usuário e senha, feedback de erro e redirecionamento).
- [ ] **Passo 2.4**: Implementar proteção de rotas (`PrivateRoute`) e contexto de autenticação/sessão em `frontend/src/LeadStreamContext.tsx`.

### Task 3: Design System Corporativo Clean & AppShell (Zero Emojis)
- [ ] **Passo 3.1**: Atualizar `frontend/src/index.css` com as diretrizes corporativas (Slate/Zinc 950, bordas de 1px sutis, fontes Inter e JetBrains Mono).
- [ ] **Passo 3.2**: Refatorar `frontend/src/pages/AppShell.tsx`:
  - Remover todos os emojis e ícones desnecessários.
  - Adicionar o **Pill de Carteira** no cabeçalho (Saldo Disponível em verde + Saldo em Custódia em âmbar).
  - Adicionar seletor discreto de workspace e botão de logout.

### Task 4: Integração das Telas e Modais ao Backend Django
- [ ] **Passo 4.1**: Adaptar `frontend/src/pages/Dashboard.tsx` para carregar métricas reais da API (empresas processadas, taxa de enriquecimento, economia por estornos).
- [ ] **Passo 4.2**: Adaptar `frontend/src/pages/Enrichment.tsx` e `frontend/src/components/UploadEnrichModal.tsx` para o fluxo de lotes do Django (`/api/v1/batches/`), incluindo upload multipart, seletor de chunk size e aviso de pré-autorização de créditos.
- [ ] **Passo 4.3**: Adaptar `frontend/src/components/LeadDetailsModal.tsx` para renderizar o dossiê da empresa canônica com QSA, decisores, LinkedIn verificado e selo Zero-Bounce de e-mails.
- [ ] **Passo 4.4**: Criar a página de Carteira e Ledger Contábil `frontend/src/pages/Wallet.tsx` com visualização do extrato duplo e destaque para estornos automáticos.
- [ ] **Passo 4.5**: Criar a página/modal de Validação Zero-Bounce `frontend/src/pages/EmailValidation.tsx` com console de handshake SMTP RFC 5321.

### Task 5: Build, Verificação e Validação Geral
- [ ] **Passo 5.1**: Executar instalação de dependências e compilação de produção (`npm run build`).
- [ ] **Passo 5.2**: Verificar ausência de erros de TypeScript (`npm run lint` ou `tsc --noEmit`).
- [ ] **Passo 5.3**: Commit de todas as alterações e documentação do fluxo de deploy no EasyPanel.
