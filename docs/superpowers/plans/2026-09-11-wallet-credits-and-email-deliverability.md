# Sistema de Carteira de Créditos (Pay-Per-Value) e Motor de Entregabilidade de E-mail Zero-Bounce — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implementar o subsistema de Carteira e Créditos com Ledger Contábil de dupla entrada (Pay-per-Value) e o Motor de Verificação Atômica de E-mails com Handshake SMTP e detecção de Catch-all (Zero-Bounce Guarantee), integrados ao faturamento de lotes.

**Architecture:** O módulo `leadstream.billing` ganha `CreditWallet`, `CreditReservation` e `CreditTransaction` (append-only) com isolamento multi-tenant, bloqueio de lotes por saldo insuficiente e estorno automático de leads ausentes/inválidos. O módulo `leadstream.validation` ganha `verify_email_smtp_deep` com handshake RFC 5321 e probe canário de catch-all. Ambos são expostos via DRF e integrados ao pipeline de lotes.

**Tech Stack:** Python 3.13, Django 5.2 LTS, Django REST Framework, PostgreSQL 17, Celery 5.6, smtplib / socket, drf-spectacular.

**Spec:** [docs/superpowers/specs/2026-09-11-wallet-credits-and-email-deliverability-design.md](file:///c:/Users/lxleo/Documents/Meus%20projetos/LeadStream-Backend/docs/superpowers/specs/2026-09-11-wallet-credits-and-email-deliverability-design.md)

## Global Constraints

- Django 5.2 LTS e Python 3.13 rigorosamente tipados.
- Transações de créditos são estritamente `append-only` (`update()` e `delete()` bloqueados no ORM).
- Isolamento multi-tenant obrigatório em todas as queries e rotas de carteira (`resolve_tenant`).
- Probes SMTP devem possuir timeout estrito de 3.0 segundos para evitar bloqueios de thread/worker.
- Testes cobrem 100% dos fluxos (mockando conexões de rede externas).
- Nenhuma dependência externa não documentada.

---

### Task 1: Modelos de Carteira, Reserva e Ledger de Créditos (`leadstream.billing`)

**Files:**
- Modify: `src/leadstream/billing/models.py`
- Create: `src/leadstream/billing/services.py`
- Create: `tests/test_credit_wallet_ledger.py`

**Interfaces:**
- Produces:
  - `CreditWallet` (`tenant`, `balance`, `reserved_balance`, `is_unlimited`)
  - `CreditReservation` (`wallet`, `batch`, `amount`, `captured_amount`, `released_amount`, `status`)
  - `CreditTransaction` (`wallet`, `reservation`, `transaction_type`, `amount`, `balance_after`, `reference_id`, `metadata`)
  - `get_or_create_wallet(tenant: Tenant) -> CreditWallet`
  - `hold_credits(wallet: CreditWallet, amount: int, batch: Batch | None, description: str) -> CreditReservation`
  - `capture_and_release(reservation: CreditReservation, actual_amount: int) -> tuple[CreditTransaction, CreditTransaction | None]`
  - `deposit_credits(wallet: CreditWallet, amount: int, reference_id: str = "", metadata: dict | None = None) -> CreditTransaction`

- [ ] **Step 1: Escrever teste unitário falhando para o Ledger de Créditos**

```python
# tests/test_credit_wallet_ledger.py
import pytest
from leadstream.tenancy.models import Tenant
from leadstream.billing.models import CreditWallet, CreditReservation, CreditTransaction
from leadstream.billing.services import (
    get_or_create_wallet,
    deposit_credits,
    hold_credits,
    capture_and_release,
)

@pytest.mark.django_db
def test_wallet_creation_and_deposit():
    tenant = Tenant.objects.create(name="Workspace Teste", slug="ws-teste")
    wallet = get_or_create_wallet(tenant)
    assert wallet.balance == 500  # Saldo cortesia inicial
    assert wallet.reserved_balance == 0

    tx = deposit_credits(wallet, amount=1000, reference_id="PIX-001")
    wallet.refresh_from_db()
    assert wallet.balance == 1500
    assert tx.transaction_type == "DEPOSIT"
    assert tx.amount == 1000
    assert tx.balance_after == 1500

@pytest.mark.django_db
def test_wallet_hold_and_capture_with_release():
    tenant = Tenant.objects.create(name="Workspace Teste 2", slug="ws-teste-2")
    wallet = get_or_create_wallet(tenant) # balance = 500

    # Hold de 300 créditos
    reservation = hold_credits(wallet, amount=300, batch=None, description="Reserva Lote Teste")
    wallet.refresh_from_db()
    assert wallet.balance == 200
    assert wallet.reserved_balance == 300
    assert reservation.status == "ACTIVE"

    # Captura 180 (leads úteis) e estorna 120 (ausentes)
    cap_tx, rel_tx = capture_and_release(reservation, actual_amount=180)
    wallet.refresh_from_db()
    assert wallet.balance == 320  # 200 anterior + 120 liberados
    assert wallet.reserved_balance == 0
    assert reservation.status == "SETTLED"
    assert reservation.captured_amount == 180
    assert reservation.released_amount == 120
    assert cap_tx.amount == -180
    assert rel_tx.amount == 120
```

- [ ] **Step 2: Executar teste para verificar falha**

Executar: `pytest tests/test_credit_wallet_ledger.py`  
Esperado: FAIL com `ImportError` ou atributos não encontrados.

- [ ] **Step 3: Implementar modelos e camada de serviços**

Em `src/leadstream/billing/models.py`:
- Adicionar classes `CreditWallet`, `CreditReservation`, `CreditTransaction`.
- Bloquear edição/exclusão em `CreditTransaction` (`append-only`).

Em `src/leadstream/billing/services.py`:
- Implementar `get_or_create_wallet`, `deposit_credits`, `hold_credits`, `capture_and_release` com `transaction.atomic()` e `select_for_update()`.

- [ ] **Step 4: Gerar e rodar migrações do Django**

Executar: `python src/manage.py makemigrations billing`  
Executar: `python src/manage.py migrate billing`

- [ ] **Step 5: Executar teste para verificar sucesso**

Executar: `pytest tests/test_credit_wallet_ledger.py -v`  
Esperado: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/leadstream/billing/ tests/test_credit_wallet_ledger.py
git commit -m "feat(billing): add CreditWallet, CreditReservation and CreditTransaction ledger"
```

---

### Task 2: Motor de Verificação Atômica de E-mails e Handshake SMTP (`leadstream.validation`)

**Files:**
- Create: `src/leadstream/validation/smtp_probe.py`
- Modify: `src/leadstream/validation/email_check.py`
- Create: `tests/test_email_smtp_deliverability.py`

**Interfaces:**
- Produces:
  - `verify_email_smtp_deep(email: str, timeout: float = 3.0, check_catch_all: bool = True) -> dict[str, Any]`
  - Chaves de retorno: `endereco`, `status` (`DELIVERABLE`, `RISKY_CATCH_ALL`, `UNDELIVERABLE`, `DISPOSABLE`, `INVALID_SYNTAX`, `NO_MX`), `mx_server`, `is_catch_all`, `score_confiabilidade`, `details`

- [ ] **Step 1: Escrever teste unitário falhando com mock de SMTP**

```python
# tests/test_email_smtp_deliverability.py
from unittest.mock import patch, MagicMock
import pytest
from leadstream.validation.smtp_probe import verify_email_smtp_deep

def test_verify_email_invalid_syntax():
    res = verify_email_smtp_deep("email-invalido@")
    assert res["status"] == "INVALID_SYNTAX"
    assert res["is_deliverable"] is False

def test_verify_email_disposable():
    res = verify_email_smtp_deep("teste@tempmail.com")
    assert res["status"] == "DISPOSABLE"
    assert res["is_deliverable"] is False

@patch("leadstream.validation.smtp_probe.check_domain_mx")
@patch("leadstream.validation.smtp_probe.smtplib.SMTP")
def test_verify_email_smtp_deliverable(mock_smtp_cls, mock_mx):
    mock_mx.return_value = {"mx_found": True, "mail_servers": ["mx.empresa.com.br"]}
    mock_client = MagicMock()
    mock_smtp_cls.return_value.__enter__.return_value = mock_client
    
    # Simula EHLO OK, MAIL FROM OK
    mock_client.ehlo.return_value = (250, b"OK")
    mock_client.mail.return_value = (250, b"OK")
    # Simula probe canário rejeitado (550) e alvo aceito (250)
    mock_client.rcpt.side_effect = [
        (550, b"User unknown"),  # canary
        (250, b"Recipient OK"),  # target
    ]

    res = verify_email_smtp_deep("ceo@empresa.com.br")
    assert res["status"] == "DELIVERABLE"
    assert res["is_deliverable"] is True
    assert res["is_catch_all"] is False

@patch("leadstream.validation.smtp_probe.check_domain_mx")
@patch("leadstream.validation.smtp_probe.smtplib.SMTP")
def test_verify_email_smtp_catch_all(mock_smtp_cls, mock_mx):
    mock_mx.return_value = {"mx_found": True, "mail_servers": ["mx.empresa.com.br"]}
    mock_client = MagicMock()
    mock_smtp_cls.return_value.__enter__.return_value = mock_client
    
    # Ambos aceitos -> servidor catch-all
    mock_client.rcpt.side_effect = [
        (250, b"OK"),  # canary aceito
        (250, b"OK"),  # target aceito
    ]

    res = verify_email_smtp_deep("diretor@empresa.com.br")
    assert res["status"] == "RISKY_CATCH_ALL"
    assert res["is_catch_all"] is True
```

- [ ] **Step 2: Executar teste para verificar falha**

Executar: `pytest tests/test_email_smtp_deliverability.py`  
Esperado: FAIL com `ModuleNotFoundError: No module named 'leadstream.validation.smtp_probe'`.

- [ ] **Step 3: Implementar `smtp_probe.py` e atualizar `email_check.py`**

- Criar `src/leadstream/validation/smtp_probe.py` com conexões seguras, timeouts, tratamento de exceções de socket e cache em memória/Redis de domínios.
- Integrar com `src/leadstream/validation/email_check.py` para fornecer validação unificada.

- [ ] **Step 4: Executar testes**

Executar: `pytest tests/test_email_smtp_deliverability.py -v`  
Esperado: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/leadstream/validation/ tests/test_email_smtp_deliverability.py
git commit -m "feat(validation): implement real-time SMTP deliverability probe and catch-all detector"
```

---

### Task 3: Endpoints REST para Carteira, Extrato e Validação de E-mails

**Files:**
- Create: `src/leadstream/billing/serializers.py`
- Modify: `src/leadstream/billing/views.py`
- Modify: `src/leadstream/billing/urls.py`
- Create: `src/leadstream/validation/views.py`
- Create: `src/leadstream/validation/urls.py`
- Modify: `src/config/urls.py`
- Create: `tests/test_wallet_and_email_api.py`

**Interfaces:**
- Endpoints:
  - `GET /api/v1/faturamento/carteira/` $\implies$ `CreditWalletSerializer`
  - `GET /api/v1/faturamento/carteira/extrato/` $\implies$ `CreditTransactionSerializer` (paginado)
  - `POST /api/v1/faturamento/carteira/recarga/` $\implies$ recarrega créditos com idempotência
  - `POST /api/v1/validacao/emails/` $\implies$ valida lista ou único e-mail com probe completo

- [ ] **Step 1: Escrever teste de API**

```python
# tests/test_wallet_and_email_api.py
import pytest
from rest_framework.test import APIClient
from django.contrib.auth.models import User
from leadstream.tenancy.models import Tenant
from leadstream.billing.services import get_or_create_wallet

@pytest.mark.django_db
def test_wallet_api_endpoints():
    client = APIClient()
    user = User.objects.create_user(username="operador", password="password123")
    tenant = Tenant.objects.create(name="Org API", slug="org-api")
    wallet = get_or_create_wallet(tenant)
    client.force_authenticate(user=user)

    # 1. Consultar carteira
    res = client.get("/api/v1/faturamento/carteira/", HTTP_X_TENANT_ID=str(tenant.id))
    assert res.status_code == 200
    assert res.data["balance"] == 500
    assert res.data["reserved_balance"] == 0

    # 2. Recarga simulada
    res = client.post(
        "/api/v1/faturamento/carteira/recarga/",
        {"amount": 250, "reference_id": "REC-01"},
        HTTP_X_TENANT_ID=str(tenant.id)
    )
    assert res.status_code == 200
    assert res.data["balance"] == 750

    # 3. Extrato
    res = client.get("/api/v1/faturamento/carteira/extrato/", HTTP_X_TENANT_ID=str(tenant.id))
    assert res.status_code == 200
    assert len(res.data["results"]) >= 2
```

- [ ] **Step 2: Executar teste para verificar falha**

Executar: `pytest tests/test_wallet_and_email_api.py`  
Esperado: FAIL com 404.

- [ ] **Step 3: Implementar Serializers, Views e rotas**

- Criar serializers em `src/leadstream/billing/serializers.py`.
- Adicionar views em `src/leadstream/billing/views.py` e rotas em `src/leadstream/billing/urls.py`.
- Criar `src/leadstream/validation/views.py`, `src/leadstream/validation/urls.py` e registrar em `src/config/urls.py`.

- [ ] **Step 4: Executar testes da API**

Executar: `pytest tests/test_wallet_and_email_api.py -v`  
Esperado: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/leadstream/billing/ src/leadstream/validation/ src/config/urls.py tests/test_wallet_and_email_api.py
git commit -m "feat(api): expose wallet balance, ledger transactions and email validation endpoints"
```

---

### Task 4: Integração de Pay-Per-Value e Reserva nos Lotes (`leadstream.batches`)

**Files:**
- Modify: `src/leadstream/batches/views.py`
- Modify: `src/leadstream/batches/tasks.py`
- Create: `tests/test_batch_pay_per_value.py`

**Interfaces:**
- Lógica de negócio:
  - Na criação de um `Batch`, calcular custo orçado e acionar `hold_credits`.
  - Se `balance < estimated_credits` e `not wallet.is_unlimited`, rejeitar lote com erro explicativo (`INSUFFICIENT_CREDITS`).
  - Na conclusão do lote, acionar `capture_and_release(reservation, actual_billable_total)`.

- [ ] **Step 1: Escrever teste de ponta a ponta do Pay-Per-Value**

```python
# tests/test_batch_pay_per_value.py
import pytest
from leadstream.tenancy.models import Tenant
from leadstream.batches.models import Batch
from leadstream.billing.services import get_or_create_wallet, hold_credits, capture_and_release
from leadstream.billing.models import BillableEvent, PriceBook, PriceRule, DataBlock

@pytest.mark.django_db
def test_pay_per_value_batch_settlement():
    tenant = Tenant.objects.create(name="Empresa B2B", slug="empresa-b2b")
    wallet = get_or_create_wallet(tenant) # balance = 500
    
    # Criar lote e reserva de 200 créditos
    batch = Batch.objects.create(tenant=tenant, name="Lote Prospeccao")
    reservation = hold_credits(wallet, amount=200, batch=batch, description=f"Lote {batch.name}")
    
    assert wallet.balance == 300
    assert wallet.reserved_balance == 200

    # Simula que apenas 75 créditos foram de leads úteis entregues
    cap_tx, rel_tx = capture_and_release(reservation, actual_amount=75)
    
    wallet.refresh_from_db()
    assert wallet.balance == 425  # 300 + 125 estornados
    assert wallet.reserved_balance == 0
```

- [ ] **Step 2: Executar teste e implementar no pipeline de lotes**

Executar: `pytest tests/test_batch_pay_per_value.py`  
Implementar integração atômica no `Batch`.

- [ ] **Step 3: Commit**

```bash
git add src/leadstream/batches/ tests/test_batch_pay_per_value.py
git commit -m "feat(batches): integrate credit reservation and pay-per-value refund on batch completion"
```

---

### Task 5: Documentação, Atualização do OpenAPI e Validação Global

**Files:**
- Modify: `README.md`
- Modify: `deploy/easypanel.md`

- [ ] **Step 1: Rodar suíte completa de testes**

Executar: `pytest -v`  
Esperado: Todos os 150+ testes passando.

- [ ] **Step 2: Rodar checagem de linter e formatação**

Executar: `ruff check .`  
Esperado: 0 erros.

- [ ] **Step 3: Atualizar documentação com novos endpoints de Carteira e Validação**

- [ ] **Step 4: Commit e push para o repositório**

```bash
git add README.md deploy/easypanel.md
git commit -m "docs: document wallet credit ledger and email deliverability verification engine"
git push origin main
```
