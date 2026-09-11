from __future__ import annotations

import json
from pathlib import Path

from leadstream.canonical.contracts import CanonicalLeadPayload


def test_canonical_lead_payload_validates_payload_json():
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


def test_canonical_lead_payload_minimal_valid_structure():
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
            "telefones": [],
            "emails": [],
        },
    }
    payload = CanonicalLeadPayload.model_validate(minimal_data)
    exported = payload.model_dump(mode="json")
    assert exported["company"]["cnpj"] == "48.944.179/0001-61"
    assert exported["financial_and_banking"] is not None
    assert exported["governance_lgpd_and_compliance"]["enquadramento_legal"] == "LEI_13709_LGPD"
