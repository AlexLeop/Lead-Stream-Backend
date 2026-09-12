# LeadStream Frontend

Interface Web Corporativa, Clean e Responsiva para o LeadStream, desenvolvida em React 19, Vite, TypeScript e Tailwind CSS v4.

Desenvolvida sob a premissa de estética corporativa e minimalista (*zero emojis*, tipografia refinada com Inter e JetBrains Mono, bordas finas de 1px e paleta escura de alta densidade informativa inspirada em Bloomberg / Stripe).

---

## 🚀 Como subir no EasyPanel como Serviço Independente

O Frontend foi projetado para rodar como um container Docker desacoplado e independente do backend Django, servido via Nginx Alpine com alta performance e cache de assets estáticos.

### Passo a Passo no EasyPanel:
1. No painel do EasyPanel, crie um **Novo Serviço** do tipo **App**.
2. Em **Source**, conecte ao repositório GitHub do LeadStream-Backend (`main`).
3. Em **Build**:
   - **Build Method**: `Dockerfile`
   - **Root Directory**: `/frontend`
   - **Dockerfile Path**: `Dockerfile`
4. Em **Environment**:
   - Defina a variável de conexão com o backend:
     ```env
     VITE_API_URL=https://sua-api-leadstream.dominio.com
     ```
     *(Substitua pela URL pública ou interna onde o backend Django está respondendo).*
5. Em **Ports**:
   - Mapeie a porta `80` (HTTP do container Nginx).
6. Em **Domains**:
   - Adicione o seu domínio desejado (ex: `app.leadstream.com.br`) e ative o certificado SSL/HTTPS automático do EasyPanel.
7. Clique em **Deploy**.

---

## 💻 Desenvolvimento Local

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
- `src/api.ts`: Cliente HTTP com suporte a JWT (tokens `access` e `refresh`), renovação automática transparente, tratamento de erros e integração com todos os endpoints do Django REST.
- `src/LeadStreamContext.tsx`: Gerenciador de estado global (autenticação JWT, dados do usuário, tenant, créditos em carteira, listas e conjuntos).
- `src/types.ts`: Definições TypeScript rigorosas correspondentes aos modelos de domínio e DTOs do backend Django 5.2.
- `src/pages/Login.tsx`: Tela corporativa de autenticação limpa com validação, indicação de segurança de sessão e lembrete de credenciais.
- `src/pages/Wallet.tsx`: Painel financeiro de créditos e livro-razão (*Pay-per-Value ledger*), exibindo saldo total, saldo retido (*hold*), histórico de transações e regras de cobrança por evidência útil.
- `src/pages/EmailValidation.tsx`: Terminal de inspeção e validação RFC 5321 (DNS MX, SMTP Handshake, detecção Catch-all e score de entregabilidade zero-bounce).
- `src/pages/AppShell.tsx`: Navegação corporativa com status de carteira em tempo real e seletor de tenant.
- `Dockerfile`: Multi-stage build (Node 22 -> Nginx Alpine) otimizado para produção.
- `nginx.conf`: Configuração do Nginx com SPA fallback (`try_files $uri $uri/ /index.html;`) e headers de cache para assets estáticos.
