from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from leadstream.canonical.contracts import CanonicalLeadPayload, CanonicalPersonPayload


def test_canonical_lead_payload_validates_payload_json() -> None:
    payload_file = Path(__file__).resolve().parent.parent / "output_lead_canonical.json"
    if not payload_file.exists():
        payload_file = Path(__file__).resolve().parent.parent / "payload.json"
    data = json.loads(payload_file.read_text(encoding="utf-8"))
    payload = CanonicalLeadPayload.model_validate(data)

    exported = payload.model_dump(mode="json")
    assert exported["_meta"]["schema_version"] == "2.4.0"
    assert exported["company"]["cnpj"] == data["company"]["cnpj"]
    assert exported["cnae"]["principal"]["codigo"] == data["cnae"]["principal"]["codigo"]
    assert len(exported["decision_makers_qsa"]) == len(data["decision_makers_qsa"])
    assert exported["identification"]["lead_score"] == data["identification"]["lead_score"]


def test_canonical_lead_payload_minimal_valid_structure() -> None:
    empty_telefones: list[dict[str, Any]] = []
    empty_emails: list[dict[str, Any]] = []
    minimal_data = {
        "_meta": {
            "schema_version": "2.4.0",
            "canon_id": "canon_123",
            "generated_at": "2026-09-11T12:00:00Z",
            "tenant_id": "default",
        },
        "identification": {
            "lead_id": "lead-1",
            "status": "QUALIFIED",
            "lead_score": 80,
            "lead_temperature": "HOT",
        },
        "company": {
            "cnpj": "48.944.179/0001-61",
            "cnpj_raw": "48944179000161",
            "cnpj_raiz": "48944179",
            "cnpj_ordem": "0001",
            "cnpj_dv": "61",
            "razao_social": "ALEX LEOPOLDO",
            "situacao_cadastral": "ATIVA",
        },
        "cnae": {
            "principal": {
                "codigo": "85.99-6-03",
                "descricao": "Treinamento",
                "setor": "Educação / Treinamento",
                "grau_risco_trabalho": 1,
            }
        },
        "address": {
            "uf": "RJ",
            "municipio": "Rio de Janeiro",
        },
        "contacts": {
            "telefones": empty_telefones,
            "emails": empty_emails,
        },
    }
    payload = CanonicalLeadPayload.model_validate(minimal_data)
    exported = payload.model_dump(mode="json")
    assert exported["company"]["cnpj"] == "48.944.179/0001-61"
    assert exported["financial_and_banking"] is not None
    assert exported["governance_lgpd_and_compliance"]["enquadramento_legal"] == "LEI_13709_LGPD"


def test_canonical_person_payload_validates_payload_pf_json() -> None:
    payload_file = Path(__file__).resolve().parent.parent / "payload_pf.json"
    assert payload_file.exists(), "payload_pf.json deve existir na raiz do projeto"
    data = json.loads(payload_file.read_text(encoding="utf-8"))

    payload = CanonicalPersonPayload.model_validate(data)
    exported = payload.model_dump(mode="json")

    # 1. Metadados e Identificação
    assert exported["_meta"]["schema_version"] == "2.4.0"
    assert exported["_meta"]["entity_type"] == "PERSON"
    assert exported["identification"]["person_id"] == data["identification"]["person_id"]

    # 2. Validação Módulo 11 da RFB e Região Fiscal
    assert exported["document_validation"]["modulo_11_valido"] is True
    assert exported["document_validation"]["cpf_formatado"] == "529.982.247-25"
    assert exported["document_validation"]["regiao_fiscal"] is not None
    assert exported["document_validation"]["regiao_fiscal"]["codigo"] == "7"
    assert exported["document_validation"]["regiao_fiscal"]["regiao"] == "7ª Região Fiscal"

    # 3. Dados Cadastrais e Filtro de Perda (Óbito)
    assert exported["cadastral_data"]["nome"] == "SEBASTIAO FERREIRA COSTA"
    assert exported["loss_prevention_filter"]["is_deceased"] is False
    assert exported["loss_prevention_filter"]["elegivel_consignado"] is True

    # 4. Consignado INSS & Margens 45%
    assert exported["consignado_inss"]["possui_beneficio_inss"] is True
    assert exported["consignado_inss"]["beneficios"][0]["numero_beneficio"] == "123.456.789-0"
    assert exported["margem_consignavel_calculada"]["salario_base_calculo"] == 3000.00
    assert (
        exported["margem_consignavel_calculada"]["margem_emprestimo_35"]["valor_mensal_permitido"]
        == 1050.00
    )
    assert (
        exported["margem_consignavel_calculada"]["margem_rmc_cartao_5"]["valor_mensal_permitido"]
        == 150.00
    )
    assert (
        exported["margem_consignavel_calculada"]["margem_rcc_beneficio_5"]["valor_mensal_permitido"]
        == 150.00
    )
    assert (
        exported["margem_consignavel_calculada"]["margem_total_45"]["valor_mensal_permitido"]
        == 1350.00
    )

    # 5. WhatsApp Probe Técnico
    assert exported["whatsapp_probe_tecnico"]["gateway_configurado"] is True
    assert exported["whatsapp_probe_tecnico"]["resultado"]["garantido"] is True
    assert exported["whatsapp_probe_tecnico"]["resultado"]["numero_formatado"] == "(11) 98123-4567"

    # 6. Não Me Perturbe e Mailing Top 3
    assert len(exported["nao_me_perturbe_anatel_febraban"]["telefones_consultados"]) == 2
    assert len(exported["mailing_qualificado_top3"]) == 2
    assert exported["mailing_qualificado_top3"][0]["whatsapp_disponivel"] is True
    assert exported["mailing_qualificado_top3"][0]["nao_me_perturbe_inscrito"] is False
    assert exported["mailing_qualificado_top3"][1]["nao_me_perturbe_inscrito"] is True


def test_canonical_person_payload_minimal_valid_structure() -> None:
    minimal_data = {
        "_meta": {
            "schema_version": "2.4.0",
            "canon_id": "canon_pf_min_001",
            "generated_at": "2026-09-12T12:00:00Z",
            "tenant_id": "test_tenant",
        },
        "identification": {
            "person_id": "person_123",
            "status": "QUALIFIED",
            "lead_score": 85,
        },
        "document_validation": {
            "cpf_formatado": "529.982.247-25",
            "cpf_numerico": "52998224725",
            "digitos_verificadores": "25",
            "modulo_11_valido": True,
            "origem_validacao": "ALGORITMO_OFICIAL_RECEITA_FEDERAL",
        },
        "cadastral_data": {
            "nome": "MARIA DA SILVA",
            "cpf": "529.982.247-25",
            "cpf_numerico": "52998224725",
        },
        "loss_prevention_filter": {
            "status": "REGULAR",
            "is_deceased": False,
            "elegivel_consignado": True,
        },
    }
    payload = CanonicalPersonPayload.model_validate(minimal_data)
    exported = payload.model_dump(mode="json")
    assert exported["cadastral_data"]["nome"] == "MARIA DA SILVA"
    assert exported["document_validation"]["modulo_11_valido"] is True
    assert exported["loss_prevention_filter"]["status"] == "REGULAR"


def test_canonical_person_payload_missing_required_fields_raises_error() -> None:
    with pytest.raises(ValidationError):
        # Falta _meta e cadastral_data
        CanonicalPersonPayload.model_validate({"identification": {"person_id": "p1"}})
