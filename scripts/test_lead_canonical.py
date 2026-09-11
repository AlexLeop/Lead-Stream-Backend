from __future__ import annotations

import json
import os
import sys
from pathlib import Path

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Ensure Django environment is configured
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.test")

def _load_dotenv() -> None:
    env_file = Path(__file__).resolve().parent.parent / ".env"
    if env_file.is_file():
        try:
            with env_file.open("r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    key, value = line.split("=", 1)
                    key = key.strip()
                    value = value.strip()
                    if (value.startswith('"') and value.endswith('"')) or (
                        value.startswith("'") and value.endswith("'")
                    ):
                        value = value[1:-1]
                    if key:
                        os.environ[key] = value
        except OSError:
            pass


_load_dotenv()
os.environ["DJANGO_SETTINGS_MODULE"] = "config.settings.test"

import django

django.setup()

from django.core.management import call_command

# Run migrations in memory if using test settings
call_command("migrate", verbosity=0)

from leadstream.batches.hygiene import normalize_row
from leadstream.batches.models import Batch, BatchItem
from leadstream.canonical.builder import CanonicalLeadBuilder
from leadstream.entities.services import create_company
from leadstream.providers.orchestrator import run_enrichment_cascade
from leadstream.tenancy.services import get_internal_tenant


def run_canonical_test(cnpj_input: str = "48.944.179/0001-61") -> dict:
    """
    Executes the real LeadStream Backend pipeline end-to-end:
    1. Input ingestion and validation
    2. Data hygiene & normalization (RFB CNPJ standard)
    3. Canonical Entity & Company creation in database
    4. Real Enrichment Cascade (calling active providers, e.g. OpenCNPJ BigQuery)
    5. Provider evidence persistence & observation canonicalization
    6. Canonical Lead Payload construction strictly from verified observations and entities
    """
    tenant = get_internal_tenant()
    batch, _ = Batch.objects.get_or_create(
        tenant=tenant,
        idempotency_key="teste-interativo-cli-001",
        defaults={"name": "Lote Interativo de Teste"},
    )

    # 1. Raw input as submitted by user
    raw_row = {"cnpj": cnpj_input}

    # 2. Real Backend Hygiene: normalize, validate CNPJ checksum and structure
    hygiene_res = normalize_row(raw_row)

    # 3. Create or resolve canonical Company entity in database
    ident = create_company(
        tenant=tenant,
        cnpj=hygiene_res.normalized.get("cnpj", cnpj_input),
        legal_name=hygiene_res.normalized.get("legal_name") or f"Empresa {cnpj_input}",
        trade_name=hygiene_res.normalized.get("trade_name", ""),
    )

    # 4. Create BatchItem with normalized data and company entity
    item, _ = BatchItem.objects.update_or_create(
        tenant=tenant,
        batch=batch,
        row_number=1,
        defaults={
            "original_data": raw_row,
            "normalized_data": hygiene_res.normalized,
            "hygiene_state": hygiene_res.state,
            "applied_rules": hygiene_res.rules,
            "issues": hygiene_res.issues,
            "fingerprint": hygiene_res.fingerprint,
            "entity": ident.company.entity,
            "status": BatchItem.Status.SUCCEEDED,
        },
    )

    # 5. Run the real Backend Enrichment Cascade (calling active providers, e.g. OpenCNPJ BigQuery)
    run_enrichment_cascade(
        tenant=tenant,
        batch=batch,
        item=item,
    )

    # Reload item to pick up normalized_data updated during provider persistence
    item.refresh_from_db()

    # 6. Build the Canonical Lead Payload from real enriched entity and observations
    builder = CanonicalLeadBuilder(tenant=tenant)
    payload = builder.build_and_save(item)

    # Write output to output_lead_canonical.json
    output_path = Path("output_lead_canonical.json")
    output_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    return payload


def main() -> None:
    cnpj_arg = sys.argv[1] if len(sys.argv) > 1 else "48.944.179/0001-61"
    print("\n=======================================================")
    print("🚀 EXECUTANDO PIPELINE REAL DE ENRIQUECIMENTO & HIGIENIZAÇÃO")
    print(f"🏢 CNPJ: {cnpj_arg}")
    print("=======================================================\n")

    payload = run_canonical_test(cnpj_arg)

    # Summary table
    comp = payload["company"]
    cnae = payload["cnae"]["principal"]
    cnaes_sec = payload["cnae"].get("secundarios", [])
    ident = payload["identification"]
    contacts = payload["contacts"]
    qsa = payload.get("decision_makers_qsa", [])
    address = payload.get("address", {})
    banks = payload.get("financial_and_banking", {}).get("instituicoes_bancarias_principais", [])

    print("📊 DADOS CADASTRAIS & ECONÔMICOS (RECEITA FEDERAL / BIGQUERY):")
    print(f"  • Razão Social:       {comp['razao_social']}")
    print(f"  • Nome Fantasia:      {comp.get('nome_fantasia') or '(Nenhum / Ausente na RFB)'}")
    print(f"  • Situação:           {comp['situacao_cadastral']}")
    print(f"  • Data de Abertura:   {comp.get('data_abertura')}")
    print(f"  • Natureza Jurídica:  {comp['natureza_juridica']['codigo']} - {comp['natureza_juridica']['descricao']}")
    print(f"  • CNAE Principal:     {cnae['codigo']} - {cnae['descricao']}")
    print(f"  • CNAEs Secundários:  {len(cnaes_sec)} atividades cadastradas")
    print(f"  • Porte Sebrae:       {comp['porte_sebrae']}")
    print(f"  • Capital Social:     {comp['capital_social_formatado']}")

    print("\n📍 ENDEREÇO DA EMPRESA (RECEITA FEDERAL):")
    tipo_logr = address.get("tipo_logradouro") or ""
    logr = address.get("logradouro") or ""
    num = address.get("numero") or "S/N"
    comp_end = f", {address['complemento']}" if address.get("complemento") else ""
    bairro = address.get("bairro") or ""
    mun = address.get("municipio") or ""
    uf = address.get("uf") or ""
    cep = address.get("cep") or ""
    print(f"  • Logradouro:         {tipo_logr} {logr}, {num}{comp_end}".strip())
    print(f"  • Bairro/Cidade/UF:   {bairro} - {mun}/{uf}")
    print(f"  • CEP:                {cep}")

    print("\n📞 CONTATOS & VALIDAÇÃO TÉCNICA:")
    for email in contacts.get("emails", []):
        mx_status = "✅ MX Ativo" if email.get("mx_found") else "❌ Sem MX"
        print(f"  • E-mail:    {email['endereco']} [{email['tipo']}] -> {email['status']} ({mx_status})")
    for tel in contacts.get("telefones", []):
        wa_status = "🟢 WhatsApp Ativo" if tel.get("whatsapp_status", {}).get("tem_whatsapp") else "⚪ Fixo"
        print(f"  • Telefone:  {tel['numero']} [{tel['operadora']}] -> {wa_status}")

    print("\n👥 DECISORES / QSA:")
    if qsa:
        for socio in qsa:
            linkedin_str = socio["contatos_diretos"].get("linkedin_url") or "(Não localizado pelos provedores)"
            print(f"  • {socio['nome']} ({socio['qualificacao_socio']}) - {socio['cargo_executivo_mercado']}")
            print(f"    LinkedIn: {linkedin_str}")
    else:
        print("  • Nenhum sócio ou decisor identificado")

    print("\n🏦 INSTITUIÇÕES BANCÁRIAS:")
    if banks:
        for b in banks:
            print(f"  • Banco: {b.get('nome_banco')} (Cód: {b.get('codigo_compensacao')})")
    else:
        print("  • (Nenhuma instituição bancária detectada nos provedores ativos)")

    print("\n🎯 QUALIFICAÇÃO & SCORE COMERCIAL:")
    print(f"  • Lead Score:  {ident['lead_score']}/100")
    print(f"  • Temperatura: {ident['lead_temperature']}")
    print(f"  • Fit ICP:     {ident['ideal_customer_profile_fit']}%")
    print(f"  • Tags:        {', '.join(ident['tags'])}")

    output_path = Path("output_lead_canonical.json")
    print(f"\n💾 Payload JSON completo (14 seções) gerado pelo backend em: {output_path.resolve()}\n")


if __name__ == "__main__":
    main()
