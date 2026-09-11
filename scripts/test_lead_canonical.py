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

import django

django.setup()

from django.core.management import call_command

# Run migrations in memory if using test settings
call_command("migrate", verbosity=0)

from leadstream.batches.models import Batch, BatchItem
from leadstream.canonical.builder import CanonicalLeadBuilder
from leadstream.tenancy.services import get_internal_tenant


def run_canonical_test(cnpj_input: str = "48.944.179/0001-61") -> dict:
    tenant = get_internal_tenant()
    batch, _ = Batch.objects.get_or_create(
        tenant=tenant,
        idempotency_key="teste-interativo-cli-001",
        defaults={"name": "Lote Interativo de Teste"},
    )

    clean_digits = "".join(c for c in cnpj_input if c.isdigit())
    if clean_digits == "48944179000161":
        dados_empresa = {
            "cnpj": "48.944.179/0001-61",
            "razao_social": "ALEX LEOPOLDO DE OLIVEIRA 17351600762",
            "nome_fantasia": "ALEX LEOPOLDO",
            "situacao_cadastral": "ATIVA",
            "data_situacao_cadastral": "2022-12-20",
            "data_inicio_atividade": "2022-12-20",
            "codigo_natureza_juridica": "2135",
            "cnae_fiscal": "8599603",
            "cnaes_secundarios": (
                "9511800,4789099,4773300,4772500,4781400,4751201,4755503,"
                "4763602,4763601,4754703,4789008,4789007,4782201,4783102,4783101"
            ),
            "porte": "01",
            "opcao_pelo_simples": True,
            "opcao_pelo_mei": True,
            "capital_social": 10.0,
            "tipo_logradouro": "ESTRADA",
            "logradouro": "DA AGUA GRANDE - DE 756 AO FIM - LADO PAR",
            "numero": "1202",
            "complemento": "COND AMOVILA",
            "bairro": "VISTA ALEGRE",
            "municipio": "RIO DE JANEIRO",
            "uf": "RJ",
            "cep": "21230-355",
            "codigo_municipio_ibge": "3304557",
            "correio_eletronico": "lx.leopoldo@outlook.com",
            "ddd_telefone_1": "21996260135",
            "instituicoes_bancarias_principais": [
                {
                    "codigo_compensacao": "260",
                    "nome_banco": "Nu Pagamentos S.A. (Nubank)",
                    "tipo_relacionamento": "CONTA_CORRENTE_PJ_PRINCIPAL",
                    "chave_pix_ativa": True,
                    "tipo_chave_pix": "CNPJ",
                    "chave_pix": "48944179000161",
                    "operacoes_cambio_ativas": False,
                    "tempo_relacionamento_anos": 2.0,
                },
                {
                    "codigo_compensacao": "077",
                    "nome_banco": "Banco Inter S.A.",
                    "tipo_relacionamento": "CONTA_SECUNDARIA",
                    "chave_pix_ativa": True,
                    "tipo_chave_pix": "EMAIL",
                    "chave_pix": "lx.leopoldo@outlook.com",
                    "operacoes_cambio_ativas": False,
                    "tempo_relacionamento_anos": 1.5,
                },
            ],
            "qsa": [
                {
                    "nome_socio": "ALEX LEOPOLDO DE OLIVEIRA",
                    "qualificacao_socio": "Empresário",
                    "faixa_etaria": "31-40 anos",
                    "linkedin_url": "https://www.linkedin.com/in/alex-leopoldo",
                }
            ],
            "linkedin_company": "https://www.linkedin.com/company/alex-leopoldo",
        }
    else:
        # Fallback for custom CNPJ test
        dados_empresa = {
            "cnpj": cnpj_input,
            "razao_social": f"EMPRESA TESTE {clean_digits}",
            "situacao_cadastral": "ATIVA",
            "cnae_fiscal": "6202300",
            "codigo_natureza_juridica": "2062",
            "porte": "03",
            "capital_social": 50000.0,
            "uf": "SP",
            "municipio": "SÃO PAULO",
            "correio_eletronico": "contato@empresa.com.br",
            "ddd_telefone_1": "11987654321",
        }

    item = BatchItem.objects.create(
        tenant=tenant,
        batch=batch,
        row_number=1,
        hygiene_state=BatchItem.HygieneState.CORRECTED,
        normalized_data=dados_empresa,
    )

    builder = CanonicalLeadBuilder(tenant=tenant)
    payload = builder.build_and_save(item)
    return payload


def main() -> None:
    cnpj_arg = sys.argv[1] if len(sys.argv) > 1 else "48.944.179/0001-61"
    print("\n=======================================================")
    print("🚀 TESTANDO GERADOR DE CANONICAL LEAD PAYLOAD v2.4.0")
    print(f"🏢 CNPJ: {cnpj_arg}")
    print("=======================================================\n")

    payload = run_canonical_test(cnpj_arg)

    # Summary table
    comp = payload["company"]
    cnae = payload["cnae"]["principal"]
    ident = payload["identification"]
    contacts = payload["contacts"]
    qsa = payload.get("decision_makers_qsa", [])

    print("📊 DADOS CADASTRAIS & ECONÔMICOS:")
    print(f"  • Razão Social:       {comp['razao_social']}")
    print(f"  • Situação:           {comp['situacao_cadastral']}")
    print(f"  • Natureza Jurídica:  {comp['natureza_juridica']['codigo']} - {comp['natureza_juridica']['descricao']}")
    print(f"  • CNAE Principal:     {cnae['codigo']} - {cnae['descricao']}")
    print(f"  • Setor / Risco NR04: {cnae['setor']} (Grau {cnae['grau_risco_trabalho']})")
    print(f"  • Porte Sebrae:       {comp['porte_sebrae']}")
    print(f"  • Regime Tributário:  {comp['regime_tributario']}")
    print(f"  • Capital Social:     {comp['capital_social_formatado']}")
    print(f"  • Faturamento Est.:   R$ {comp['faturamento_estimado_anual']:,.2f} ({comp['faixa_faturamento']})")
    print(f"  • Equipe Estimada:    {comp['quantidade_funcionarios_estimada']} ({comp['faixa_funcionarios']})")

    print("\n📞 CONTATOS & VALIDAÇÃO TÉCNICA:")
    for email in contacts.get("emails", []):
        mx_status = "✅ MX Ativo" if email.get("mx_found") else "❌ Sem MX"
        print(f"  • E-mail:    {email['endereco']} [{email['tipo']}] -> {email['status']} ({mx_status})")
    for tel in contacts.get("telefones", []):
        wa_status = "🟢 WhatsApp Ativo" if tel.get("whatsapp_status", {}).get("tem_whatsapp") else "⚪ Fixo"
        print(f"  • Telefone:  {tel['numero']} [{tel['operadora']}] -> {wa_status}")

    print("\n🎯 QUALIFICAÇÃO & SCORE COMERCIAL:")
    print(f"  • Lead Score:  {ident['lead_score']}/100")
    print(f"  • Temperatura: {ident['lead_temperature']}")
    print(f"  • Fit ICP:     {ident['ideal_customer_profile_fit']}%")
    print(f"  • Tags:        {', '.join(ident['tags'])}")

    if qsa:
        print("\n👥 DECISORES / QSA:")
        for socio in qsa:
            print(f"  • {socio['nome']} ({socio['qualificacao_socio']}) - {socio['cargo_executivo_mercado']}")

    output_path = Path("output_lead_canonical.json")
    output_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n💾 Payload JSON completo (14 seções) salvo em: {output_path.resolve()}\n")


if __name__ == "__main__":
    main()
