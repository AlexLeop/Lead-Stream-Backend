# Especificação Técnica de Design: Enterprise Security & Hybrid Authentication

> **Documento de Design Arquitetural**  
> **Data:** 11/09/2026  
> **Status:** Aprovado  
> **Módulo:** `leadstream.security`, `leadstream.common`, `leadstream.tenancy`

---

## 1. Visão Geral e Objetivos

O **LeadStream Backend** implementa uma camada de segurança robusta baseada no modelo **Defesa em Camadas (*Defense in Depth*)**, provendo autenticação híbrida (Sessão JWT para operadores humanos e API Keys criptográficas para integrações B2B/máquinas), autorização RBAC vinculada a workspaces (tenants), prevenção absoluta de IDOR, controle de vazão (throttling no Redis), headers defensivos de borda e auditoria completa de conformidade LGPD.

### Metas Principais:
1. **Autenticação Híbrida Segura:**
   - JWT stateless via `djangorestframework-simplejwt` para operadores humanos, com access tokens de curta duração (30m) e refresh tokens rotativos com blacklist em Redis.
   - API Keys criptográficas para chamadas de máquina (CRMs, workers e scripts) com prefixo identificador (`ls_live_` ou `ls_test_`), armazenando no banco exclusivamente o hash SHA-256 do segredo.
2. **Eliminação do Fallback Permissivo de Tenant:**
   - Toda requisição autenticada é amarrada ao seu `request.tenant` derivado de forma criptográfica da API Key ou do token JWT.
   - Chamadas não autenticadas em rotas de dados recebem `401 Unauthorized` imediato.
   - Super Admin (proprietário) possui privilégio global auditado com capacidade de chavear entre tenants via `X-Tenant-ID`.
3. **Controle de Acesso RBAC e Prevenção de IDOR:**
   - Papéis granulares por workspace (`ADMIN`, `OPERATOR`, `READ_ONLY`).
   - QuerySets escopados automaticamente por tenant (`TenantScopedQuerySet`), impedindo vazamento de dados entre clientes.
4. **Proteção de Borda & Throttling (Redis):**
   - Rate limiting restrito no login (5 req/min por IP) para proteção contra ataques de força bruta.
   - Rate limiting por Workspace / API Key (120 req/min padrão, com headers de resposta `X-RateLimit-*`).
   - CORS restritivo via `django-cors-headers` configurável por ambiente.
   - Headers defensivos HTTP (`nosniff`, `DENY` clickjacking, HSTS em produção).
5. **Trilha de Auditoria (`SecurityAuditLog`):**
   - Registro imutável de eventos críticos de segurança (logins, falhas, criação/revogação de chaves, exportações em massa).
6. **Preservação de Retrocompatibilidade e Testes:**
   - Provisionamento automático de API Key de teste para o tenant interno nas fixtures de teste, garantindo que a suíte existente de 117 testes continue 100% verde.

---

## 2. Arquitetura das Camadas de Segurança

```
                   INTERNET / CLIENTES / CRMs / FRONTEND
                                     │
┌────────────────────────────────────▼─────────────────────────────────────┐
│ CAMADA 1: Borda & Perímetro (Headers HTTP, CORS Whitelist, Max Payload)  │
└────────────────────────────────────┬─────────────────────────────────────┘
                                     │
┌────────────────────────────────────▼─────────────────────────────────────┐
│ CAMADA 2: Throttling & Anti-Abuso (Redis Sliding Window por IP e Tenant) │
└────────────────────────────────────┬─────────────────────────────────────┘
                                     │
┌────────────────────────────────────▼─────────────────────────────────────┐
│ CAMADA 3: Motor de Autenticação Híbrido (JWT Bearer + API Key SHA-256)   │
│   • Validação de Assinatura Criptográfica                               │
│   • Extração de Identidade e Injeção do Tenant no Contexto da Requisição │
│   • Bloqueio Rígido (Fim do fallback permissivo para tenant interno)      │
└────────────────────────────────────┬─────────────────────────────────────┘
                                     │
┌────────────────────────────────────▼─────────────────────────────────────┐
│ CAMADA 4: Autorização & RBAC (Role-Based Access Control + Escopos)       │
│   • Super Admin: Acesso irrestrito com auditoria                         │
│   • Membro/API Key: ADMIN, OPERATOR, READ_ONLY                           │
│   • Isolamento Criptográfico de Tenant (Prevenção Total de IDOR)         │
└────────────────────────────────────┬─────────────────────────────────────┘
                                     │
┌────────────────────────────────────▼─────────────────────────────────────┐
│ CAMADA 5: Trilha de Auditoria & LGPD (SecurityAuditLog com Hash e IP)    │
└────────────────────────────────────┬─────────────────────────────────────┘
                                     │
                       APLICAÇÃO / SERVIÇOS / BANCO
```

---

## 3. Modelagem de Dados (`leadstream.security.models`)

### 3.1 `WorkspaceMembership`
Vincula um usuário Django (`auth.User`) a um `Tenant` com papel de autorização:
```python
class WorkspaceRole(models.TextChoices):
    ADMIN = "ADMIN", "Administrador"
    OPERATOR = "OPERATOR", "Operador"
    READ_ONLY = "READ_ONLY", "Somente Leitura"

class WorkspaceMembership(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="workspace_memberships")
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.CASCADE, related_name="memberships")
    role = models.CharField(max_length=20, choices=WorkspaceRole.choices, default=WorkspaceRole.OPERATOR)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user", "tenant"], name="unique_user_tenant_membership")
        ]
```

### 3.2 `APIKey`
Representa chaves de máquina e integrações vinculadas a um tenant:
```python
class APIKey(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.CASCADE, related_name="api_keys")
    name = models.CharField(max_length=120)
    prefix = models.CharField(max_length=16, db_index=True)  # ex: ls_live_9f8a3c2b
    hashed_key = models.CharField(max_length=64, unique=True, db_index=True)  # SHA-256 do segredo
    role = models.CharField(max_length=20, choices=WorkspaceRole.choices, default=WorkspaceRole.OPERATOR)
    scopes = models.JSONField(default=list, blank=True)
    is_active = models.BooleanField(default=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    last_used_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def clean_prefix(self) -> str:
        return self.prefix
```

### 3.3 `SecurityAuditLog`
Log de auditoria imutável de eventos sensíveis:
```python
class SecurityAuditLog(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.SET_NULL, null=True, blank=True)
    actor_type = models.CharField(max_length=20)  # USER / API_KEY / ANONYMOUS
    actor_id = models.CharField(max_length=64, blank=True, default="")
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=255, blank=True, default="")
    action = models.CharField(max_length=64, db_index=True)  # LOGIN_SUCCESS, LOGIN_FAIL, KEY_CREATE, etc.
    resource_accessed = models.CharField(max_length=255, blank=True, default="")
    status_code = models.IntegerField(default=200)
    details = models.JSONField(default=dict, blank=True)
```

---

## 4. Motor de Autenticação (`CombinedAuthentication`)

O autenticador inspeciona a requisição na seguinte ordem de precedência:

1. **Header `Authorization: Bearer <token>`:**
   - Se `<token>` inicia com `ls_live_` ou `ls_test_`: trata como **API Key**.
     - Calcula hash `SHA-256(<token>)`.
     - Busca `APIKey` ativa e não expirada.
     - Injeta `request.user = None`, `request.auth = api_key` e `request.tenant = api_key.tenant`.
     - Atualiza assincronamente ou em lote o `last_used_at`.
   - Caso contrário: trata como **Token JWT** via SimpleJWT.
     - Valida assinatura criptográfica e expiração.
     - Extrai `user_id`.
     - Determina o tenant:
       - Se `user.is_superuser` e header `X-Tenant-ID` presente: associa `request.tenant` ao tenant informado.
       - Senão: valida pertinência na tabela `WorkspaceMembership`. Se não tiver vínculo ativo, nega autorização (`403 Forbidden`).
2. **Header `X-API-Key: <token>`:**
   - Mesmo fluxo de API Key acima.
3. **Ausência de Credenciais:**
   - Em rotas protegidas: rejeição com `401 Unauthorized` e cabeçalho `WWW-Authenticate`.
   - Em rotas públicas (`/health/*`, `/api/v1/docs/`, etc.): permitido sem autenticação.

---

## 5. Mapeamento de Rotas & Segurança

| Rota | Classificação | Permissão Mínima |
| :--- | :--- | :--- |
| `GET /health/live`, `/ready`, `/dependencies` | Público | Nenhuma |
| `GET /api/v1/docs/`, `/swagger/`, `/redoc/`, `/schema/` | Público | Nenhuma |
| `POST /api/v1/auth/token/` | Público (Throttled) | 5 req/min por IP |
| `POST /api/v1/auth/token/refresh/` | Público (Throttled) | 10 req/min por IP |
| `POST /api/v1/auth/token/revoke/` | Protegido | Usuário Autenticado |
| `GET, POST /api/v1/security/keys/` | Protegido | `ADMIN` do Tenant |
| `DELETE /api/v1/security/keys/{id}/` | Protegido | `ADMIN` do Tenant |
| `GET /api/v1/leads/{id}/canonical/` | Protegido | `READ_ONLY`+ do Tenant |
| `ALL /api/v1/lotes/*` | Protegido | `OPERATOR`+ do Tenant |
| `ALL /api/v1/dados/*` | Protegido | `OPERATOR`+ do Tenant |
| `ALL /api/v1/integracoes/*` | Protegido | `OPERATOR`+ do Tenant |
| `ALL /api/v1/billing/*` | Protegido | `ADMIN` do Tenant |

---

## 6. Documentação OpenAPI (Swagger/Scalar)

No `SPECTACULAR_SETTINGS`:
- Registrados `BearerAuth` (HTTP Bearer JWT) e `ApiKeyAuth` (Header `X-API-Key`).
- As rotas protegidas exigem uma das duas credenciais para testes diretos na UI de documentação.
