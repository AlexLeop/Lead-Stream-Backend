# Implementação do Canonical Lead Payload v2.4.0

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implementar o schema canônico completo v2.4.0 (`payload.json`) no LeadStream Backend, integrando inteligência de CNAEs/Natureza Jurídica, inferência econômica, validação técnica de e-mails/telefones, lead scoring e snapshot JSONB de alta performance.

**Architecture:** Módulos autônomos `leadstream.intelligence` (CNAEs, CONCLA, Economia, Scoring), `leadstream.validation` (DNS MX, RFC e E.164) e `leadstream.canonical` (Contratos Pydantic v2 e Builder). O compilador `CanonicalLeadBuilder` orquestra as fontes e grava um snapshot consolidado em `BatchItem.canonical_payload` (JSONB) indexado no PostgreSQL.

**Tech Stack:** Python 3.13, Django 5.2, Django REST Framework, Pydantic v2, PostgreSQL 17 JSONB, dnspython / socket, pytest, Celery.

**Spec:** `docs/superpowers/specs/2026-09-11-canonical-lead-architecture-design.md`

## Global Constraints
- Sem segredos ou credenciais expostas no repositório.
- Nenhuma dependência externa lenta ou síncrona que bloqueie a thread do worker.
- Cache Redis em todas as validações de domínio DNS MX com TTL de 24h.
- 100% de cobertura por testes automatizados com `pytest`.
- Todos os nomes de campos no JSON canônico devem corresponder exatamente à chave do `payload.json`.

---

### Task 1: Banco de Dados — Campo `canonical_payload` em `BatchItem`

**Files:**
- Modify: `src/leadstream/batches/models.py:120-140`
- Create: `src/leadstream/batches/migrations/0002_batchitem_canonical_payload.py`
- Test: `tests/batches/test_canonical_payload_model.py`

**Interfaces:**
- Consumes: `leadstream.batches.models.BatchItem`
- Produces: `BatchItem.canonical_payload` (JSONField default dict)

- [ ] **Step 1: Escrever teste de persistência do campo canonical_payload**

```python
import pytest
from leadstream.batches.models import BatchItem


@pytest.mark.django_db
def test_batch_item_has_canonical_payload(tenant, sample_batch):
    item = BatchItem.objects.create(
        tenant=tenant,
        batch=sample_batch,
        row_number=1,
        hygiene_state=BatchItem.HygieneState.CORRECTED,
        canonical_payload={"_meta": {"schema_version": "2.4.0"}},
    )
    item.refresh_from_db()
    assert item.canonical_payload["_meta"]["schema_version"] == "2.4.0"
```

- [ ] **Step 2: Executar teste para verificar falha (campo inexistente)**

Run: `.venv\Scripts\pytest tests/batches/test_canonical_payload_model.py`
Expected: FAIL com `TypeError: BatchItem() got unexpected keyword arguments: 'canonical_payload'`

- [ ] **Step 3: Adicionar campo canonical_payload no modelo e gerar migração**

Adicionar em `BatchItem`:
```python
canonical_payload = models.JSONField(
    default=dict, blank=True, help_text="Snapshot consolidado do payload canônico v2.4.0."
)
```
Executar:
`.venv\Scripts\python.exe manage.py makemigrations batches`

- [ ] **Step 4: Executar teste para verificar aprovação**

Run: `.venv\Scripts\pytest tests/batches/test_canonical_payload_model.py`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/leadstream/batches/ tests/batches/
git commit -m "feat(batches): add canonical_payload JSONField to BatchItem"
```

---

### Task 2: Dicionários de Inteligência — CNAEs e Naturezas Jurídicas

**Files:**
- Create: `src/leadstream/intelligence/__init__.py`
- Create: `src/leadstream/intelligence/cnae.py`
- Create: `src/leadstream/intelligence/natureza_juridica.py`
- Test: `tests/intelligence/test_cnae_and_natureza.py`

**Interfaces:**
- Consumes: Código bruto de CNAE (ex: "8599603" ou "85.99-6-03") e código de Natureza Jurídica (ex: "2135" ou "213-5")
- Produces: 
  - `lookup_cnae(code: str) -> dict[str, Any]` (contendo `codigo`, `descricao`, `setor`, `grau_risco_trabalho`)
  - `lookup_natureza_juridica(code: str) -> dict[str, str]` (contendo `codigo`, `descricao`)

- [ ] **Step 1: Escrever teste de lookup de CNAE e Natureza Jurídica**

```python
from leadstream.intelligence.cnae import lookup_cnae, format_cnae
from leadstream.intelligence.natureza_juridica import lookup_natureza_juridica


def test_cnae_formatting_and_lookup():
    info = lookup_cnae("8599603")
    assert info["codigo"] == "85.99-6-03"
    assert "Treinamento" in info["descricao"]
    assert info["setor"] == "Educação / Treinamento"
    assert info["grau_risco_trabalho"] in (1, 2, 3, 4)


def test_natureza_juridica_lookup():
    nat = lookup_natureza_juridica("2135")
    assert nat["codigo"] == "213-5"
    assert "Empresário" in nat["descricao"]
```

- [ ] **Step 2: Executar teste para verificar falha**

Run: `.venv\Scripts\pytest tests/intelligence/test_cnae_and_natureza.py`
Expected: FAIL com `ModuleNotFoundError: No module named 'leadstream.intelligence'`

- [ ] **Step 3: Implementar lookup de CNAEs IBGE e Naturezas Jurídicas CONCLA**

Criar dicionários com mapeamento das classes e subclasses principais do IBGE, normalização de máscaras de CNAE (`##.##-#-##`) e Natureza (`###-#`).

- [ ] **Step 4: Executar teste para verificar aprovação**

Run: `.venv\Scripts\pytest tests/intelligence/test_cnae_and_natureza.py`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/leadstream/intelligence/ tests/intelligence/
git commit -m "feat(intelligence): add CNAE and Natureza Juridica resolution engines"
```

---

### Task 3: Inteligência Econômica & Motor de Lead Scoring

**Files:**
- Create: `src/leadstream/intelligence/economics.py`
- Create: `src/leadstream/intelligence/scoring.py`
- Test: `tests/intelligence/test_economics_and_scoring.py`

**Interfaces:**
- Consumes: Capital social, Porte RFB, Opção MEI/Simples, CNAE principal, Status Cadastral, Contatos identificados
- Produces:
  - `infer_economics(...) -> dict` (`porte_sebrae`, `regime_tributario`, `faturamento_estimado_anual`, `faixa_faturamento`, `quantidade_funcionarios_estimada`, `faixa_funcionarios`)
  - `calculate_lead_score(...) -> dict` (`lead_score`, `lead_temperature`, `ideal_customer_profile_fit`, `tags`)

- [ ] **Step 1: Escrever teste de inferência econômica e score**

```python
from leadstream.intelligence.economics import infer_economics
from leadstream.intelligence.scoring import calculate_lead_score


def test_economics_inference_for_mei():
    eco = infer_economics(
        capital_social=10.0,
        porte_rfb="1",
        optante_mei=True,
        optante_simples=True,
        cnae_code="8599603",
    )
    assert eco["porte_sebrae"] == "MEI"
    assert eco["regime_tributario"] == "SIMEI"
    assert eco["faturamento_estimado_anual"] <= 81000.00


def test_lead_score_calculation():
    score_data = calculate_lead_score(
        is_active=True,
        has_decision_maker=True,
        has_verified_email=True,
        has_verified_phone=True,
        porte_sebrae="MEI",
    )
    assert score_data["lead_score"] == 100
    assert score_data["lead_temperature"] == "HOT"
    assert "WhatsApp Ativo" in score_data["tags"]
```

- [ ] **Step 2: Executar teste para verificar falha**

Run: `.venv\Scripts\pytest tests/intelligence/test_economics_and_scoring.py`
Expected: FAIL com import error

- [ ] **Step 3: Implementar regras econômicas e motor de pontuação**

Implementar tabelas de faixas de faturamento (Art. 3º LC 123/2006 e critérios SEBRAE) e motor determinístico de score.

- [ ] **Step 4: Executar teste para verificar aprovação**

Run: `.venv\Scripts\pytest tests/intelligence/test_economics_and_scoring.py`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/leadstream/intelligence/ tests/intelligence/
git commit -m "feat(intelligence): add economic inference and deterministic lead scoring"
```

---

### Task 4: Validação Técnica de Contatos (E-mail, DNS MX, Telefone & WhatsApp)

**Files:**
- Create: `src/leadstream/validation/__init__.py`
- Create: `src/leadstream/validation/dns_mx.py`
- Create: `src/leadstream/validation/email_check.py`
- Create: `src/leadstream/validation/phone_check.py`
- Test: `tests/validation/test_contact_validation.py`

**Interfaces:**
- Consumes: E-mails brutos e telefones brutos
- Produces:
  - `validate_email_technical(email: str) -> dict` (`endereco`, `tipo`, `status`, `mx_found`, `smtp_check`, `disposable`, `catch_all`)
  - `validate_phone_technical(phone: str, ddd: str = "") -> dict` (`tipo`, `numero`, `operadora`, `status_linha`, `whatsapp_status`)

- [ ] **Step 1: Escrever teste de validação de contatos**

```python
from leadstream.validation.email_check import validate_email_technical
from leadstream.validation.phone_check import validate_phone_technical


def test_email_validation():
    res = validate_email_technical("lx.leopoldo@outlook.com")
    assert res["status"] in ("ENTREGAVEL", "ENTREGAVEL_VALIDADO")
    assert res["mx_found"] is True
    assert res["disposable"] is False


def test_phone_validation_mobile():
    res = validate_phone_technical("96260135", ddd="21")
    assert res["tipo"] in ("MOVEL_WHATSAPP_EMPRESA", "MOVEL")
    assert res["numero"] == "+55 21 9626-0135" or "+552196260135" in res["numero"]
    assert res["whatsapp_status"]["tem_whatsapp"] is True
```

- [ ] **Step 2: Executar teste para verificar falha**

Run: `.venv\Scripts\pytest tests/validation/test_contact_validation.py`
Expected: FAIL

- [ ] **Step 3: Implementar validações técnicas com cache Redis para DNS**

Usar `dns.resolver` ou `socket` nativo para MX lookups, regras de prefixo ANATEL e lista de provedores descartáveis.

- [ ] **Step 4: Executar teste para verificar aprovação**

Run: `.venv\Scripts\pytest tests/validation/test_contact_validation.py`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/leadstream/validation/ tests/validation/
git commit -m "feat(validation): add technical email MX and phone/WhatsApp validation"
```

---

### Task 5: Contratos Pydantic v2 do Canonical Lead Payload

**Files:**
- Create: `src/leadstream/canonical/__init__.py`
- Create: `src/leadstream/canonical/contracts.py`
- Test: `tests/canonical/test_canonical_contracts.py`

**Interfaces:**
- Consumes: Dicionário estruturado
- Produces: `CanonicalLeadPayload` validado com exportação para dict/json correspondente ao `payload.json`

- [ ] **Step 1: Escrever teste de validação do contrato canônico**

```python
import json
from pathlib import Path
from leadstream.canonical.contracts import CanonicalLeadPayload


def test_payload_json_contract_compliance():
    payload_file = Path("payload.json")
    data = json.loads(payload_file.read_text(encoding="utf-8"))
    payload = CanonicalLeadPayload.model_validate(data)
    exported = payload.model_dump(mode="json")
    assert exported["_meta"]["schema_version"] == "2.4.0"
    assert exported["company"]["cnpj"] == data["company"]["cnpj"]
```

- [ ] **Step 2: Executar teste para verificar falha**

Run: `.venv\Scripts\pytest tests/canonical/test_canonical_contracts.py`
Expected: FAIL com `ModuleNotFoundError: No module named 'leadstream.canonical'`

- [ ] **Step 3: Implementar modelos Pydantic v2 para todas as seções do payload**

Modelar `MetaPayload`, `IdentificationPayload`, `CompanyPayload`, `CnaePayload`, `AddressPayload`, `ContactsPayload`, `DecisionMakerPayload`, etc.

- [ ] **Step 4: Executar teste para verificar aprovação**

Run: `.venv\Scripts\pytest tests/canonical/test_canonical_contracts.py`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/leadstream/canonical/ tests/canonical/
git commit -m "feat(canonical): define Pydantic v2 contracts matching payload.json schema"
```

---

### Task 6: Compilador do Lead Canônico (`CanonicalLeadBuilder`)

**Files:**
- Create: `src/leadstream/canonical/builder.py`
- Test: `tests/canonical/test_canonical_builder.py`

**Interfaces:**
- Consumes: `BatchItem`, `Company`, `Establishment`, observações e dados do provider
- Produces: `CanonicalLeadBuilder.build(item: BatchItem) -> dict[str, Any]`

- [ ] **Step 1: Escrever teste do CanonicalLeadBuilder**

```python
import pytest
from leadstream.canonical.builder import CanonicalLeadBuilder


@pytest.mark.django_db
def test_canonical_lead_builder_builds_full_payload(tenant, sample_item_with_company):
    builder = CanonicalLeadBuilder(tenant=tenant)
    payload = builder.build(item=sample_item_with_company)
    assert payload["_meta"]["schema_version"] == "2.4.0"
    assert "company" in payload
    assert "decision_makers_qsa" in payload
    assert "contacts" in payload
    assert "identification" in payload
```

- [ ] **Step 2: Executar teste para verificar falha**

Run: `.venv\Scripts\pytest tests/canonical/test_canonical_builder.py`
Expected: FAIL

- [ ] **Step 3: Implementar CanonicalLeadBuilder integrando inteligências e validações**

- [ ] **Step 4: Executar teste para verificar aprovação**

Run: `.venv\Scripts\pytest tests/canonical/test_canonical_builder.py`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/leadstream/canonical/ tests/canonical/
git commit -m "feat(canonical): implement CanonicalLeadBuilder compiler"
```

---

### Task 7: Integração no Pipeline Celery & Exposição na API REST

**Files:**
- Modify: `src/leadstream/providers/tasks.py`
- Modify: `src/leadstream/providers/orchestrator.py`
- Create: `src/leadstream/canonical/views.py`
- Create: `src/leadstream/canonical/urls.py`
- Modify: `src/config/urls.py`
- Test: `tests/canonical/test_canonical_api.py`

**Interfaces:**
- Consumes: Requisições HTTP da API REST e tarefas de enriquecimento
- Produces: Endpoint `GET /api/v1/leads/{id}/canonical/` e snapshot automático gravado no término do processamento

- [ ] **Step 1: Escrever teste do endpoint da API**

```python
import pytest
from rest_framework.test import APIClient


@pytest.mark.django_db
def test_get_canonical_lead_endpoint(tenant, enriched_batch_item):
    client = APIClient()
    response = client.get(
        f"/api/v1/leads/{enriched_batch_item.id}/canonical/", HTTP_X_TENANT_ID=tenant.slug
    )
    assert response.status_code == 200
    assert response.data["_meta"]["schema_version"] == "2.4.0"
```

- [ ] **Step 2: Executar teste para verificar falha**

Run: `.venv\Scripts\pytest tests/canonical/test_canonical_api.py`
Expected: FAIL

- [ ] **Step 3: Implementar view REST e chamada do builder no orquestrador**

- [ ] **Step 4: Executar teste para verificar aprovação**

Run: `.venv\Scripts\pytest tests/canonical/test_canonical_api.py`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/leadstream/ tests/canonical/
git commit -m "feat(canonical): expose canonical lead endpoint and hook builder to pipeline"
```

---

### Task 8: Teste de Integração End-to-End com o CNPJ `48.944.179/0001-61`

**Files:**
- Create: `tests/e2e/test_cnpj_alex_canonical.py`

- [ ] **Step 1: Escrever teste E2E do CNPJ 48.944.179/0001-61 comparando com as chaves do payload.json**

- [ ] **Step 2: Executar teste E2E**

Run: `.venv\Scripts\pytest tests/e2e/test_cnpj_alex_canonical.py`
Expected: PASS

- [ ] **Step 3: Executar suite completa do projeto**

Run: `.venv\Scripts\pytest`
Expected: 100% de testes passando sem regressões.

- [ ] **Step 4: Commit final e push**

```bash
git add tests/e2e/
git commit -m "test(e2e): verify canonical lead payload against real CNPJ 48.944.179/0001-61"
git push origin main
```
