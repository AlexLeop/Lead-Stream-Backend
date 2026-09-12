# Master Administration & White-Label Center Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a complete, enterprise-grade Master Administration & White-Label Center ("Torre de Gestão Master") for the platform owner/super-administrator, giving total governance over multi-tenant workspaces, user permissions, API keys, block pricing, credit wallets, data providers, suppression lists, Zero-Bounce SMTP engine, batch orchestration, and visual white-label branding.

**Architecture:** Extend Django backend with specialized admin endpoints under `/api/v1/admin/*` and `/api/v1/system/branding/` protected by `IsAdminUser`/`is_superuser`. Implement immutable ledger operations for credit injection. Purge synthetic/mock data from analytics. Build high-density `impeccable` frontend with dynamic `BrandingProvider` and 8 compact governance tabs in `AdminCenter.tsx`.

**Tech Stack:** Python 3.13, Django 5.2 LTS, Django REST Framework, PostgreSQL, React 19, TypeScript, Tailwind CSS, Lucide React, Pytest, Ruff, Mypy, Vite.

**Spec:** [2026-09-12-master-administration-center-design.md](file:///c:/Users/lxleo/Documents/Meus%20projetos/LeadStream-Backend/docs/superpowers/specs/2026-09-12-master-administration-center-design.md)

## Global Constraints

- Absolute ban on fake/invented/mock data: everything rendered must reflect true database state; empty collections return empty lists (`[]`) and zero counts (`0`).
- Strict compliance with `impeccable` Product Register: high-density compact typography (`text-[11px]`, `text-[12px]`, `font-mono` for metrics), compact rows (`py-1.5`/`py-2`), hairline borders (`border-white/10`), zero fuzzy blurs or oversized card templates.
- Financial transactions in `CreditTransaction` and `BillableEvent` must remain strictly append-only.
- All admin endpoints require authenticated `is_superuser` or `is_staff` privileges.
- 100% Brazilian Portuguese for operational labels, validation messages, and system text.
- All existing 167 backend Pytest tests must continue to pass without regressions.

---

### Task 1: System Settings & White-Label Branding Backend

**Files:**
- Create: `src/leadstream/tenancy/branding_models.py`
- Modify: `src/leadstream/tenancy/models.py`
- Create: `src/leadstream/tenancy/branding_views.py`
- Modify: `src/leadstream/tenancy/urls.py`
- Modify: `src/leadstream/urls.py`
- Test: `tests/test_system_branding.py`

**Interfaces:**
- Produces:
  - `GET /api/v1/system/branding/` -> `{"platform_name": str, "logo_url_dark": str, "logo_url_light": str, "favicon_url": str, "accent_color": str, "support_email": str, "terms_url": str, "privacy_url": str}`
  - `PATCH /api/v1/system/branding/` -> updates and persists branding fields (superuser only).

- [ ] **Step 1: Write the failing test for branding endpoints**

```python
# tests/test_system_branding.py
import pytest
from rest_framework.test import APIClient
from django.contrib.auth import get_user_model
from leadstream.tenancy.branding_models import PlatformBranding

User = get_user_model()

@pytest.mark.django_db
def test_public_branding_get():
    client = APIClient()
    response = client.get("/api/v1/system/branding/")
    assert response.status_code == 200
    assert response.data["platform_name"] == "LeadStream"
    assert response.data["accent_color"] == "#10B981"

@pytest.mark.django_db
def test_branding_patch_unauthorized():
    client = APIClient()
    response = client.patch("/api/v1/system/branding/", {"platform_name": "Custom Leads"})
    assert response.status_code in [401, 403]

@pytest.mark.django_db
def test_branding_patch_superuser():
    user = User.objects.create_superuser(username="admin", email="admin@example.com", password="password123")
    client = APIClient()
    client.force_authenticate(user=user)
    response = client.patch("/api/v1/system/branding/", {
        "platform_name": "UltraLead Enterprise",
        "accent_color": "#3B82F6",
        "support_email": "suporte@ultralead.com.br"
    })
    assert response.status_code == 200
    assert response.data["platform_name"] == "UltraLead Enterprise"
    assert response.data["accent_color"] == "#3B82F6"
    assert response.data["support_email"] == "suporte@ultralead.com.br"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_system_branding.py -v`
Expected: FAIL (ImportError / 404)

- [ ] **Step 3: Implement PlatformBranding model, serializer, views, and migrations**

Create `src/leadstream/tenancy/branding_models.py`:
```python
from django.db import models

class PlatformBranding(models.Model):
    platform_name = models.CharField(max_length=120, default="LeadStream")
    logo_url_dark = models.URLField(blank=True, default="")
    logo_url_light = models.URLField(blank=True, default="")
    favicon_url = models.URLField(blank=True, default="")
    accent_color = models.CharField(max_length=32, default="#10B981")
    support_email = models.EmailField(blank=True, default="suporte@leadstream.com.br")
    terms_url = models.URLField(blank=True, default="")
    privacy_url = models.URLField(blank=True, default="")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "leadstream_platform_branding"
        verbose_name = "Configuração White-Label"

    @classmethod
    def get_active(cls) -> "PlatformBranding":
        obj, _ = cls.objects.get_or_create(id=1)
        return obj
```

Create `src/leadstream/tenancy/branding_views.py`:
```python
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAdminUser
from rest_framework import serializers
from leadstream.tenancy.branding_models import PlatformBranding
from leadstream.security.authentication import CombinedAuthentication

class PlatformBrandingSerializer(serializers.ModelSerializer):
    class Meta:
        model = PlatformBranding
        fields = [
            "platform_name", "logo_url_dark", "logo_url_light",
            "favicon_url", "accent_color", "support_email",
            "terms_url", "privacy_url"
        ]

class BrandingView(APIView):
    authentication_classes = (CombinedAuthentication,)

    def get_permissions(self):
        if self.request.method == "GET":
            return [AllowAny()]
        return [IsAdminUser()]

    def get(self, request):
        branding = PlatformBranding.get_active()
        serializer = PlatformBrandingSerializer(branding)
        return Response(serializer.data)

    def patch(self, request):
        branding = PlatformBranding.get_active()
        serializer = PlatformBrandingSerializer(branding, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)
```

Route `/api/v1/system/branding/` in `src/leadstream/urls.py` and run migrations.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_system_branding.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/leadstream/tenancy/ tests/test_system_branding.py src/leadstream/urls.py
git commit -m "feat(branding): add system white-label branding models and endpoints"
```

---

### Task 2: Multi-Tenant Workspace Governance Backend

**Files:**
- Modify: `src/leadstream/tenancy/models.py` (add `max_batch_size`, `rate_limit_per_minute`, `max_concurrency` fields)
- Create: `src/leadstream/tenancy/admin_views.py`
- Modify: `src/leadstream/urls.py`
- Test: `tests/test_admin_tenants.py`

**Interfaces:**
- Consumes: `Tenant` model, `PriceBook`, `CreditWallet`, `WorkspaceMembership`.
- Produces:
  - `GET /api/v1/admin/tenants/` -> list tenants with statistics, active status, members count, wallet balance.
  - `POST /api/v1/admin/tenants/` -> create tenant with name, slug, operational limits, initial credits, optional admin user.
  - `PATCH /api/v1/admin/tenants/<id>/` -> toggle `is_active`, edit limits (`max_batch_size`, `rate_limit_per_minute`, `max_concurrency`).
  - `POST /api/v1/admin/tenants/<id>/impersonate/` -> generate context token/header instructions for 1-click workspace switch.

- [ ] **Step 1: Write the failing test for tenant admin endpoints**

```python
# tests/test_admin_tenants.py
import pytest
from rest_framework.test import APIClient
from django.contrib.auth import get_user_model
from leadstream.tenancy.models import Tenant

User = get_user_model()

@pytest.mark.django_db
def test_admin_tenant_lifecycle():
    admin = User.objects.create_superuser(username="master", email="master@example.com", password="pass")
    client = APIClient()
    client.force_authenticate(user=admin)

    # 1. Create tenant
    create_resp = client.post("/api/v1/admin/tenants/", {
        "name": "Cliente Alfa",
        "slug": "cliente-alfa",
        "max_batch_size": 25000,
        "rate_limit_per_minute": 120,
        "max_concurrency": 8,
        "initial_credits": 1000
    })
    assert create_resp.status_code == 201
    tenant_id = create_resp.data["id"]

    # 2. List tenants
    list_resp = client.get("/api/v1/admin/tenants/")
    assert list_resp.status_code == 200
    assert any(t["slug"] == "cliente-alfa" for t in list_resp.data["results"])

    # 3. Patch tenant (deactivate)
    patch_resp = client.patch(f"/api/v1/admin/tenants/{tenant_id}/", {
        "is_active": False,
        "max_batch_size": 50000
    })
    assert patch_resp.status_code == 200
    assert patch_resp.data["is_active"] is False
    assert patch_resp.data["max_batch_size"] == 50000

    # 4. Impersonate tenant
    imp_resp = client.post(f"/api/v1/admin/tenants/{tenant_id}/impersonate/")
    assert imp_resp.status_code == 200
    assert imp_resp.data["tenant"]["slug"] == "cliente-alfa"
    assert "token" in imp_resp.data or "tenant_slug" in imp_resp.data
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_admin_tenants.py -v`
Expected: FAIL (404)

- [ ] **Step 3: Implement tenant operational fields and admin views**

In `src/leadstream/tenancy/models.py`:
Add `max_batch_size = models.PositiveIntegerField(default=100000)`
Add `rate_limit_per_minute = models.PositiveIntegerField(default=60)`
Add `max_concurrency = models.PositiveIntegerField(default=4)`
Generate migration.

In `src/leadstream/tenancy/admin_views.py`:
Implement `AdminTenantListCreateView`, `AdminTenantDetailView`, `AdminTenantImpersonateView`.
Connect with `CreditWallet` and `PriceBook` so new tenants get automatically initialized.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_admin_tenants.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/leadstream/tenancy/ tests/test_admin_tenants.py src/leadstream/urls.py
git commit -m "feat(admin): implement multi-tenant management endpoints and limits"
```

---

### Task 3: Users, Team Memberships & API Keys Backend

**Files:**
- Create: `src/leadstream/security/admin_views.py`
- Modify: `src/leadstream/urls.py`
- Test: `tests/test_admin_security.py`

**Interfaces:**
- Consumes: `User`, `WorkspaceMembership`, `APIKey`.
- Produces:
  - `GET /api/v1/admin/users/` -> list users with memberships, roles, status.
  - `POST /api/v1/admin/users/` -> create user, bind to tenant with specified role (`ADMIN`, `OPERATOR`, `READ_ONLY`).
  - `PATCH /api/v1/admin/users/<id>/` -> toggle `is_active`, update role or password.
  - `GET /api/v1/admin/api-keys/` -> list all API keys across tenants.
  - `POST /api/v1/admin/api-keys/` -> issue API key for tenant, returns plaintext once.
  - `DELETE /api/v1/admin/api-keys/<id>/` -> revoke API key.

- [ ] **Step 1: Write the failing test for security admin endpoints**

```python
# tests/test_admin_security.py
import pytest
from rest_framework.test import APIClient
from django.contrib.auth import get_user_model
from leadstream.tenancy.models import Tenant

User = get_user_model()

@pytest.mark.django_db
def test_admin_users_and_api_keys():
    master = User.objects.create_superuser(username="master", email="master@example.com", password="pass")
    tenant = Tenant.objects.create(name="Beta Corp", slug="beta-corp")
    client = APIClient()
    client.force_authenticate(user=master)

    # 1. Create user
    user_resp = client.post("/api/v1/admin/users/", {
        "username": "operador_beta",
        "email": "operador@betacorp.com",
        "password": "SecurePassword123!",
        "tenant_id": str(tenant.id),
        "role": "OPERATOR"
    })
    assert user_resp.status_code == 201
    user_id = user_resp.data["id"]

    # 2. List users
    list_users = client.get("/api/v1/admin/users/")
    assert list_users.status_code == 200
    assert any(u["username"] == "operador_beta" for u in list_users.data["results"])

    # 3. Patch user
    patch_resp = client.patch(f"/api/v1/admin/users/{user_id}/", {
        "role": "ADMIN",
        "is_active": True
    })
    assert patch_resp.status_code == 200

    # 4. Issue API Key
    key_resp = client.post("/api/v1/admin/api-keys/", {
        "tenant_id": str(tenant.id),
        "name": "Integration Key CRM",
        "role": "OPERATOR"
    })
    assert key_resp.status_code == 201
    assert "raw_key" in key_resp.data
    key_id = key_resp.data["id"]

    # 5. Revoke API Key
    del_resp = client.delete(f"/api/v1/admin/api-keys/{key_id}/")
    assert del_resp.status_code in [200, 204]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_admin_security.py -v`
Expected: FAIL (404)

- [ ] **Step 3: Implement security admin views and wire up routes**

Implement `AdminUserListView`, `AdminUserDetailView`, `AdminAPIKeyListView`, `AdminAPIKeyDetailView` in `src/leadstream/security/admin_views.py`.
Add endpoints to `src/leadstream/urls.py`.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_admin_security.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/leadstream/security/ tests/test_admin_security.py src/leadstream/urls.py
git commit -m "feat(admin): implement user management, role assignments and api key issuance"
```

---

### Task 4: Plans, Block Pricing & Double-Entry Ledger Backend

**Files:**
- Create: `src/leadstream/billing/admin_views.py`
- Modify: `src/leadstream/urls.py`
- Test: `tests/test_admin_billing.py`

**Interfaces:**
- Consumes: `PriceBook`, `PriceRule`, `CreditWallet`, `CreditTransaction`.
- Produces:
  - `GET /api/v1/admin/pricing/` -> list price books and block unit prices.
  - `PUT /api/v1/admin/pricing/<book_id>/` -> batch update rule prices, confidence, refresh window.
  - `GET /api/v1/admin/wallets/` -> list all tenant wallets with balance and status.
  - `POST /api/v1/admin/wallets/<tenant_id>/credit/` -> inject audited credit (creates append-only `CreditTransaction`, increments balance).
  - `GET /api/v1/admin/wallets/<tenant_id>/transactions/` -> transaction history for tenant.

- [ ] **Step 1: Write the failing test for billing admin endpoints**

```python
# tests/test_admin_billing.py
import pytest
from rest_framework.test import APIClient
from django.contrib.auth import get_user_model
from leadstream.tenancy.models import Tenant
from leadstream.billing.models import CreditWallet, PriceBook, PriceRule, DataBlock
from django.utils import timezone

User = get_user_model()

@pytest.mark.django_db
def test_admin_pricing_and_ledger():
    master = User.objects.create_superuser(username="master", email="master@example.com", password="pass")
    tenant = Tenant.objects.create(name="Delta Corp", slug="delta-corp")
    wallet = CreditWallet.objects.create(tenant=tenant, balance=500)
    book = PriceBook.objects.create(tenant=tenant, version=1, name="Plano Padrão", effective_at=timezone.now())
    PriceRule.objects.create(tenant=tenant, price_book=book, block=DataBlock.COMPANY_REGISTRY, unit_price_cents=10)
    
    client = APIClient()
    client.force_authenticate(user=master)

    # 1. List pricing
    price_resp = client.get("/api/v1/admin/pricing/")
    assert price_resp.status_code == 200
    assert len(price_resp.data) >= 1

    # 2. Update price rule
    update_resp = client.put(f"/api/v1/admin/pricing/{book.id}/", {
        "rules": [
            {"block": "COMPANY_REGISTRY", "unit_price_cents": 15, "minimum_confidence": 85, "refresh_window_days": 45}
        ]
    })
    assert update_resp.status_code == 200

    # 3. List wallets
    wallets_resp = client.get("/api/v1/admin/wallets/")
    assert wallets_resp.status_code == 200

    # 4. Inject audited credit
    credit_resp = client.post(f"/api/v1/admin/wallets/{tenant.id}/credit/", {
        "amount": 2500,
        "reason": "Recarga contratual via Pix - Pedido #8912"
    })
    assert credit_resp.status_code == 200
    assert credit_resp.data["balance"] == 3000

    # 5. List transactions
    tx_resp = client.get(f"/api/v1/admin/wallets/{tenant.id}/transactions/")
    assert tx_resp.status_code == 200
    assert len(tx_resp.data["results"]) >= 1
    assert tx_resp.data["results"][0]["amount"] == 2500
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_admin_billing.py -v`
Expected: FAIL (404)

- [ ] **Step 3: Implement billing admin views**

Implement `AdminPricingListView`, `AdminPriceBookUpdateView`, `AdminWalletListView`, `AdminWalletCreditInjectionView`, `AdminWalletTransactionsView` in `src/leadstream/billing/admin_views.py`.
Add endpoints to `src/leadstream/urls.py`.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_admin_billing.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/leadstream/billing/ tests/test_admin_billing.py src/leadstream/urls.py
git commit -m "feat(admin): implement block pricing matrix and double-entry ledger management"
```

---

### Task 5: External Providers, Budget Caps, Suppression & Zero-Bounce Engine Backend

**Files:**
- Create: `src/leadstream/governance/admin_views.py`
- Create: `src/leadstream/providers/admin_views.py`
- Create: `src/leadstream/validation/admin_views.py`
- Modify: `src/leadstream/urls.py`
- Test: `tests/test_admin_governance_providers.py`

**Interfaces:**
- Produces:
  - `GET /api/v1/admin/suppression/` -> list suppression entries.
  - `POST /api/v1/admin/suppression/` -> add CNPJ, email or domain to opt-out.
  - `DELETE /api/v1/admin/suppression/<id>/` -> delete suppression entry.
  - `GET /api/v1/admin/audit-logs/` -> read immutable audit logs.
  - `GET /api/v1/admin/providers/` & `PATCH /api/v1/admin/providers/` -> provider status and budget caps.
  - `GET /api/v1/admin/smtp-config/` & `PATCH /api/v1/admin/smtp-config/` -> Zero-bounce calibration.
  - `POST /api/v1/admin/smtp-probe/` -> interactive real-time test of single email validation.

- [ ] **Step 1: Write the failing test for governance, providers, and SMTP**

```python
# tests/test_admin_governance_providers.py
import pytest
from rest_framework.test import APIClient
from django.contrib.auth import get_user_model
from leadstream.tenancy.models import Tenant
from leadstream.governance.models import Suppression
from leadstream.security.models import SecurityAuditLog
from django.utils import timezone

User = get_user_model()

@pytest.mark.django_db
def test_admin_governance_providers_smtp():
    master = User.objects.create_superuser(username="master", email="master@example.com", password="pass")
    tenant = Tenant.objects.create(name="Omega Corp", slug="omega-corp")
    client = APIClient()
    client.force_authenticate(user=master)

    # 1. Suppression Opt-Out
    supp_resp = client.post("/api/v1/admin/suppression/", {
        "tenant_id": str(tenant.id),
        "scope": "EMAIL",
        "value": "optout@cliente.com.br",
        "reason": "Solicitação LGPD do titular"
    })
    assert supp_resp.status_code == 201
    supp_id = supp_resp.data["id"]

    list_supp = client.get("/api/v1/admin/suppression/")
    assert list_supp.status_code == 200

    del_supp = client.delete(f"/api/v1/admin/suppression/{supp_id}/")
    assert del_supp.status_code in [200, 204]

    # 2. Audit Logs
    SecurityAuditLog.objects.create(
        tenant=tenant, actor_type="SUPERADMIN", actor_id="master",
        action="CONFIG_UPDATE", resource_accessed="/api/v1/admin/suppression/", status_code=200
    )
    logs_resp = client.get("/api/v1/admin/audit-logs/")
    assert logs_resp.status_code == 200
    assert len(logs_resp.data["results"]) >= 1

    # 3. Providers Config & Budget
    prov_resp = client.get("/api/v1/admin/providers/")
    assert prov_resp.status_code == 200

    budget_resp = client.patch("/api/v1/admin/providers/budget/", {
        "daily_limit_usd": 150.0,
        "circuit_breaker_rate": 0.15
    })
    assert budget_resp.status_code == 200

    # 4. SMTP Config & Probe
    smtp_resp = client.get("/api/v1/admin/smtp-config/")
    assert smtp_resp.status_code == 200

    probe_resp = client.post("/api/v1/admin/smtp-probe/", {
        "email": "test@gmail.com"
    })
    assert probe_resp.status_code == 200
    assert "status" in probe_resp.data
    assert "mx_host" in probe_resp.data
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_admin_governance_providers.py -v`
Expected: FAIL (404)

- [ ] **Step 3: Implement admin views for governance, providers, and SMTP engine**

In `src/leadstream/governance/admin_views.py`, implement suppression CRUD and audit logs viewer.
In `src/leadstream/providers/admin_views.py`, implement provider status and budget limit settings.
In `src/leadstream/validation/admin_views.py`, implement SMTP config and live probe.
Register all endpoints in `src/leadstream/urls.py`.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_admin_governance_providers.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/leadstream/governance/ src/leadstream/providers/ src/leadstream/validation/ tests/test_admin_governance_providers.py src/leadstream/urls.py
git commit -m "feat(admin): implement suppression opt-out, audit logs, provider budgets and smtp probe"
```

---

### Task 6: Batch Operations Backend + Purge of Mock Data in Analytics

**Files:**
- Create: `src/leadstream/batches/admin_views.py`
- Modify: `src/leadstream/analytics/views.py` (purge dummy leads, fake lists, fake 98.4% rates, fake minimums)
- Modify: `src/leadstream/urls.py`
- Test: `tests/test_admin_batches_analytics.py`

**Interfaces:**
- Produces:
  - `GET /api/v1/admin/batches/` -> global batches monitor.
  - `POST /api/v1/admin/batches/<id>/pause/`, `resume/`, `cancel/`.
  - `GET /api/v1/admin/celery/queues/` -> telemetry of queues.
  - `/api/v1/analytics/dashboard/`, `/api/v1/analytics/leads/`, `/api/v1/analytics/datasets/` now return pure authentic database counts and empty lists `[]` when database has no data.

- [ ] **Step 1: Write the failing test for batch operations and honest analytics**

```python
# tests/test_admin_batches_analytics.py
import pytest
from rest_framework.test import APIClient
from django.contrib.auth import get_user_model
from leadstream.tenancy.models import Tenant
from leadstream.batches.models import Batch

User = get_user_model()

@pytest.mark.django_db
def test_admin_batches_and_clean_analytics():
    master = User.objects.create_superuser(username="master", email="master@example.com", password="pass")
    tenant = Tenant.objects.create(name="Epsilon Corp", slug="epsilon-corp")
    batch = Batch.objects.create(tenant=tenant, name="Lote 10k SP", status=Batch.Status.RUNNING, total_rows=10000)

    client = APIClient()
    client.force_authenticate(user=master)

    # 1. Admin Batches
    batch_resp = client.get("/api/v1/admin/batches/")
    assert batch_resp.status_code == 200
    assert len(batch_resp.data["results"]) >= 1

    # 2. Pause Batch
    pause_resp = client.post(f"/api/v1/admin/batches/{batch.id}/pause/")
    assert pause_resp.status_code == 200
    batch.refresh_from_db()
    assert batch.status == Batch.Status.PAUSED

    # 3. Resume Batch
    resume_resp = client.post(f"/api/v1/admin/batches/{batch.id}/resume/")
    assert resume_resp.status_code == 200
    batch.refresh_from_db()
    assert batch.status == Batch.Status.RUNNING

    # 4. Celery Queue telemetry
    queue_resp = client.get("/api/v1/admin/celery/queues/")
    assert queue_resp.status_code == 200

    # 5. Clean Analytics Verification (Zero Fakes)
    empty_tenant = Tenant.objects.create(name="Empty Corp", slug="empty-corp")
    client.credentials(HTTP_X_TENANT_SLUG="empty-corp")
    
    dash_resp = client.get("/api/v1/analytics/dashboard/")
    assert dash_resp.status_code == 200
    # Must be real zeros, NOT artificial 120 or 50
    assert dash_resp.data["summary"]["contacts"] == 0
    assert dash_resp.data["summary"]["companies"] == 0

    leads_resp = client.get("/api/v1/analytics/leads/")
    assert leads_resp.status_code == 200
    # Must NOT contain "Carlos Eduardo" or fake demo leads
    assert len(leads_resp.data) == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_admin_batches_analytics.py -v`
Expected: FAIL (404 / assertion error on artificial leads)

- [ ] **Step 3: Implement batch admin views and clean analytics views**

Implement `AdminBatchesListView`, `AdminBatchActionView`, `AdminCeleryQueuesView` in `src/leadstream/batches/admin_views.py`.
In `src/leadstream/analytics/views.py`:
- Remove fake fallback "Carlos Eduardo Silveira", "Nexus Cloud".
- Remove fake fallback "Base Piloto de Empresas Ativas".
- Remove fake fallback activities.
- Remove artificial `max(..., 50)` or `max(..., 120)` in `DashboardView` and `DataHealthView`. Return honest `0` when empty.
- Register endpoints in `src/leadstream/urls.py`.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_admin_batches_analytics.py -v`
Expected: PASS

- [ ] **Step 5: Run full test suite to ensure no regressions across all apps**

Run: `pytest -v`
Expected: All tests PASS.

- [ ] **Step 6: Commit**

```bash
git add src/leadstream/batches/ src/leadstream/analytics/ tests/test_admin_batches_analytics.py src/leadstream/urls.py
git commit -m "feat(admin): implement batch orchestration endpoints and purge synthetic mock analytics"
```

---

### Task 7: Frontend White-Label Branding System & Core App Integration

**Files:**
- Create: `frontend/src/components/BrandingProvider.tsx`
- Modify: `frontend/src/types.ts`
- Modify: `frontend/src/api/client.ts`
- Modify: `frontend/src/components/AppShell.tsx`
- Modify: `frontend/src/App.tsx`
- Test: Build check (`npm run build` in `frontend/`)

**Interfaces:**
- Produces:
  - `useBranding()` hook exposing dynamic `branding` data (`platform_name`, `accent_color`, logos).
  - CSS variables `--color-accent` and `--color-primary` injected into `:root`.
  - Dynamic `document.title` and `<link rel="icon">`.
  - Superadmin role detection in `AppShell` with high-density "Torre Master" navigation link.

- [ ] **Step 1: Define TypeScript types in frontend/src/types.ts**

Add interfaces for:
`PlatformBranding`, `AdminTenant`, `AdminUser`, `AdminAPIKey`, `AdminPriceBook`, `AdminPriceRule`, `AdminWallet`, `AdminCreditTransaction`, `AdminProviderConfig`, `AdminSuppression`, `AdminBatch`, `AdminQueueStatus`, `SMTPProbeResult`.

- [ ] **Step 2: Add API client methods in frontend/src/api/client.ts**

Add:
- `getBranding()`, `updateBranding(data)`
- `getAdminTenants()`, `createAdminTenant(data)`, `updateAdminTenant(id, data)`, `impersonateTenant(id)`
- `getAdminUsers()`, `createAdminUser(data)`, `updateAdminUser(id, data)`
- `getAdminAPIKeys()`, `createAdminAPIKey(data)`, `revokeAdminAPIKey(id)`
- `getAdminPricing()`, `updateAdminPriceBook(id, data)`
- `getAdminWallets()`, `injectAdminCredit(tenantId, data)`, `getAdminWalletTransactions(tenantId)`
- `getAdminProviders()`, `updateAdminProviderBudget(data)`
- `getAdminSuppression()`, `createAdminSuppression(data)`, `deleteAdminSuppression(id)`
- `getAdminAuditLogs(params)`
- `getAdminSMTPConfig()`, `updateAdminSMTPConfig(data)`, `probeSMTP(email)`
- `getAdminBatches()`, `actionAdminBatch(id, action)`, `getAdminCeleryQueues()`

- [ ] **Step 3: Create BrandingProvider.tsx**

In `frontend/src/components/BrandingProvider.tsx`:
- Fetch branding on mount.
- Apply accent color CSS variables and document title.
- Wrap application in `App.tsx`.

- [ ] **Step 4: Update AppShell.tsx**

- Add "Torre Master" link with Shield/Settings icon in top bar or navigation drawer when user has `is_staff` or `is_superuser`.
- Maintain compact scale (`text-[11px]` labels, compact layout).

- [ ] **Step 5: Run Vite build check**

Run: `npm run build` in `frontend/`
Expected: PASS with 0 errors.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/types.ts frontend/src/api/client.ts frontend/src/components/BrandingProvider.tsx frontend/src/components/AppShell.tsx frontend/src/App.tsx
git commit -m "feat(frontend): integrate dynamic white-label branding provider and master admin navigation"
```

---

### Task 8: Frontend Master Administration Center UI (`frontend/src/pages/AdminCenter.tsx`)

**Files:**
- Create: `frontend/src/pages/AdminCenter.tsx`
- Modify: `frontend/src/App.tsx` (add `/admin` route)
- Test: Build check (`npm run build` in `frontend/`) and browser verification

**Interfaces:**
- Produces:
  - Enterprise Master Administration page with 8 specialized compact tabs:
    1. `Workspaces & Clientes`
    2. `Usuários & Chaves de API`
    3. `Planos & Preços`
    4. `Carteiras & Ledger`
    5. `Lotes & Filas Celery`
    6. `Provedores & Orçamento`
    7. `Governança & Supressão`
    8. `Zero-Bounce SMTP & Marca`
  - Strict high-density `impeccable` design: Linear/Datadog standard, `text-[11px]`/`text-[12px]`, `py-1.5` table rows, hairline `border-white/10`, zero fake data.

- [ ] **Step 1: Implement AdminCenter.tsx**

Build `AdminCenter.tsx` containing:
- High-density top bar with Master System status, active tenant switch, and live stats.
- 8 compact tab buttons with subtle active indicator.
- Tab 1: Tenant table (name, slug, limits, status toggle, 1-click impersonate button, "Novo Workspace" modal).
- Tab 2: User list (roles, active toggle) and API Key management (issue key modal, revoke).
- Tab 3: PriceBook rules matrix (unit price in BRL cents, minimum confidence, refresh window).
- Tab 4: Wallet balances overview, "Injetar Créditos" modal with mandatory audit reason, immutable transaction ledger.
- Tab 5: Global batches table with pause/resume/cancel controls and Celery queue health meters.
- Tab 6: External provider cards (BigDataCorp, Apify, Serpro), priority ordering, daily USD budget limit and circuit breaker rate.
- Tab 7: Suppression opt-out blacklist (add/remove CNPJ, email, domain) and filterable security audit log.
- Tab 8: Live SMTP RFC 5321 interactive tester (email input, test button, shows MX host, code, deliverability) + White-label visual identity editor (platform name, logos, accent color picker, support email).

- [ ] **Step 2: Connect route in App.tsx**

Add `<Route path="/admin" element={<AdminCenter />} />`.

- [ ] **Step 3: Run Vite build check**

Run: `npm run build` in `frontend/`
Expected: PASS with 0 errors.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/AdminCenter.tsx frontend/src/App.tsx
git commit -m "feat(frontend): implement comprehensive master administration center with 8 high-density governance modules"
```

---

### Task 9: Full Branch Verification, Pytest & Production Deployment

**Files:**
- All modified files
- Documentation: `docs/superpowers/specs/2026-09-12-master-administration-center-design.md`

- [ ] **Step 1: Run full Pytest suite**

Run: `pytest -v`
Expected: 100% tests PASS.

- [ ] **Step 2: Run Ruff linting and formatting**

Run: `ruff check src/ tests/`
Expected: All checks passed.

- [ ] **Step 3: Run Mypy typecheck**

Run: `mypy src/leadstream/analytics/`
Expected: 0 errors.

- [ ] **Step 4: Run Frontend build**

Run: `cd frontend && npm run build`
Expected: Build successfully completes.

- [ ] **Step 5: Git commit, push and deploy to EasyPanel**

Push clean commit to `origin/main` and verify endpoints.
