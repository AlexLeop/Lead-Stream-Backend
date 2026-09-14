# LeadStream Frontend

Interface React do LeadStream, servida por Nginx e projetada para operar no mesmo domínio
lógico da API. A sessão usa access token efêmero em memória e refresh token em cookie
HttpOnly; nenhum token é persistido em `localStorage`.

---

## Como subir no EasyPanel como serviço independente

O Frontend foi projetado para rodar como um container Docker desacoplado e independente do backend Django, servido via Nginx Alpine com alta performance e cache de assets estáticos.

### Passo a Passo no EasyPanel:
1. No painel do EasyPanel, crie um **Novo Serviço** do tipo **App**.
2. Em **Source**, conecte ao repositório GitHub do LeadStream-Backend (`main`).
3. Em **Build**:
   - **Build Method**: `Dockerfile`
   - **Root Directory**: `/frontend`
   - **Dockerfile Path**: `Dockerfile`
4. Em **Environment**, defina o endereço alcançável pelo Nginx em tempo de execução:
     ```env
     BACKEND_UPSTREAM=https://sua-api-leadstream.dominio.com
     ```
   Prefira o endereço interno da rede do EasyPanel quando os serviços compartilham rede.
   Não inclua `/api` no final.
5. Em **Ports**:
   - Mapeie a porta `80` (HTTP do container Nginx).
6. Em **Domains**:
   - Adicione o seu domínio desejado (ex: `app.leadstream.com.br`) e ative o certificado SSL/HTTPS automático do EasyPanel.
7. Clique em **Deploy**.

---

## Desenvolvimento local

### Pré-requisitos
- Node.js 20+ ou 22 LTS
- Backend Django rodando (porta `8000`)

### Comandos
```bash
# 1. Entrar no diretório
cd frontend

# 2. Instalar dependências
npm install

# 3. Iniciar servidor de desenvolvimento (porta 5173 com proxy para http://localhost:8000)
npm run dev

# 4. Checagem de tipos (TypeScript)
npm run lint

# 5. Gerar bundle de produção
npm run build
```

---

## 📁 Estrutura de Diretórios
- `src/api.ts`: cliente HTTP com access token em memória, refresh em cookie HttpOnly e renovação automática.
- `src/LeadStreamContext.tsx`: Gerenciador de estado global (autenticação JWT, dados do usuário, tenant, créditos em carteira, listas e conjuntos).
- `src/types.ts`: Definições TypeScript rigorosas correspondentes aos modelos de domínio e DTOs do backend Django 5.2.
- `src/pages/Login.tsx`: Tela corporativa de autenticação limpa com validação, indicação de segurança de sessão e lembrete de credenciais.
- `src/pages/Wallet.tsx`: Painel financeiro de créditos e livro-razão (*Pay-per-Value ledger*), exibindo saldo total, saldo retido (*hold*), histórico de transações e regras de cobrança por evidência útil.
- `src/pages/EmailValidation.tsx`: Terminal de inspeção e validação RFC 5321 (DNS MX, SMTP Handshake, detecção Catch-all e score de entregabilidade zero-bounce).
- `src/pages/AppShell.tsx`: Navegação corporativa com status de carteira em tempo real e seletor de tenant.
- `Dockerfile`: Multi-stage build (Node 22 -> Nginx Alpine) otimizado para produção.
- `nginx.conf`: Configuração do Nginx com SPA fallback (`try_files $uri $uri/ /index.html;`) e headers de cache para assets estáticos.
