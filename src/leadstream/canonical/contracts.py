from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


class BasePayloadModel(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)


class MetaPayload(BasePayloadModel):
    schema_version: str = "2.4.0"
    canon_id: str
    generated_at: str
    tenant_id: str
    pipeline_run_id: str | None = None
    confidence_score_global: float = 0.95


class IdentificationPayload(BasePayloadModel):
    lead_id: str
    status: str = "QUALIFIED"
    lead_score: int = 0
    lead_temperature: str = "WARM"
    ideal_customer_profile_fit: float = 50.0
    tags: list[str] = Field(default_factory=list)


class CompanyPayload(BasePayloadModel):
    cnpj: str
    cnpj_raw: str = ""
    cnpj_raiz: str = ""
    cnpj_ordem: str = ""
    cnpj_dv: str = ""
    tipo: str = "MATRIZ"
    razao_social: str
    nome_fantasia: str | None = None
    situacao_cadastral: str = "ATIVA"
    data_situacao_cadastral: str | None = None
    motivo_situacao_cadastral: str | None = None
    situacao_especial: str | None = None
    data_situacao_especial: str | None = None
    data_abertura: str | None = None
    idade_empresa_anos: float | None = None
    natureza_juridica: dict[str, Any] = Field(default_factory=dict)
    porte: str = "DEMAIS"
    porte_sebrae: str = "MICRO_EMPRESA"
    regime_tributario: str = "SIMPLES_NACIONAL"
    optante_simples: bool = False
    data_opcao_simples: str | None = None
    data_exclusao_simples: str | None = None
    optante_simei: bool = False
    data_opcao_simei: str | None = None
    capital_social: float = 0.0
    capital_social_formatado: str = "R$ 0,00"
    faturamento_estimado_anual: float = 0.0
    faixa_faturamento: str = "Até R$ 81.000"
    faixa_funcionarios: str = "Até 1 colaborador"
    quantidade_funcionarios_estimada: int = 1
    website: str | None = None
    dominio: str | None = None


class BankingInstitutionPayload(BasePayloadModel):
    codigo_compensacao: str = "260"
    nome_banco: str = "Nu Pagamentos S.A. (Nubank)"
    tipo_relacionamento: str = "CONTA_CORRENTE_PRINCIPAL"
    chave_pix_ativa: bool = True
    tipo_chave_pix: str = "CNPJ"
    chave_pix: str | None = None
    operacoes_cambio_ativas: bool = False
    tempo_relacionamento_anos: float | None = 2.0


class FinancialAndBankingPayload(BasePayloadModel):
    instituicoes_bancarias_principais: list[BankingInstitutionPayload] = Field(
        default_factory=list
    )
    bancos_relacionamento_detectados: list[BankingInstitutionPayload] = Field(
        default_factory=list
    )
    linhas_credito_ativas: list[str] = Field(default_factory=list)
    risco_credito_score: int | None = 750
    risco_credito_classificacao: str | None = "BAIXO_RISCO_A"
    limite_credito_estimado: float | None = 0.0
    capacidade_pagamento: str | None = "MEDIA"
    protestos_ativos_cartorio: int = 0
    valor_total_protestos: float = 0.0
    cheques_sem_fundo_ccf: int = 0
    pendencias_financeiras_ativas: bool = False


class FiscalAndTaxIntelligencePayload(BasePayloadModel):
    situacao_fiscal_federal: str = "REGULAR"
    situacao_pgfn_divida_ativa: str = "NADA_CONSTA"
    valor_divida_ativa_uniao: float = 0.0
    certidao_negativa_debito_cnd: dict[str, Any] = Field(
        default_factory=lambda: {
            "status": "EMITIDA_VALIDA",
            "numero_certidao": None,
            "validade": None,
        }
    )
    certidao_fgts_crf: dict[str, Any] = Field(
        default_factory=lambda: {"status": "REGULAR", "numero_crf": None, "validade": None}
    )
    inscricao_estadual: dict[str, Any] = Field(
        default_factory=lambda: {"numero": None, "uf": None, "status_sintegra": "HABILITADO_ATIVO"}
    )
    inscricao_municipal: dict[str, Any] = Field(
        default_factory=lambda: {"numero": None, "municipio": None, "status": "REGULAR"}
    )


class CnaePrincipal(BasePayloadModel):
    codigo: str
    descricao: str
    setor: str = "Outros Serviços"
    grau_risco_trabalho: int = 1


class CnaeItem(BasePayloadModel):
    codigo: str
    descricao: str


class CnaeSection(BasePayloadModel):
    principal: CnaePrincipal
    secundarios: list[CnaeItem] = Field(default_factory=list)


class AddressPayload(BasePayloadModel):
    tipo_logradouro: str | None = None
    logradouro: str | None = None
    numero: str | None = None
    complemento: str | None = None
    bairro: str | None = None
    municipio: str | None = None
    uf: str | None = None
    cep: str | None = None
    codigo_ibge_municipio: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    geocoding_precision: str | None = "APPROXIMATE"
    tipo_imovel: str | None = "COMERCIAL"
    valor_m2_regiao: float | None = None


class PhonePayload(BasePayloadModel):
    tipo: str = "FIXO_RECEITA"
    ddd: str | None = None
    numero: str
    ramal: str | None = None
    operadora: str = "DESCONHECIDA"
    status_linha: str = "ATIVA"
    principal: bool = False
    validado: bool = True
    whatsapp_status: dict[str, Any] = Field(default_factory=dict)
    confianca: float = 0.95

    @model_validator(mode="before")
    @classmethod
    def normalize_phone(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        raw_num = str(data.get("numero") or "")
        raw_ddd = str(data.get("ddd") or "")

        digits_num = "".join(c for c in raw_num if c.isdigit())
        digits_ddd = "".join(c for c in raw_ddd if c.isdigit())

        if digits_num.startswith("55") and len(digits_num) in (12, 13):
            digits_num = digits_num[2:]

        if digits_ddd.startswith("0") and len(digits_ddd) == 3:
            digits_ddd = digits_ddd[1:]

        if digits_num.startswith("0") and len(digits_num) in (11, 12):
            digits_num = digits_num[1:]

        if not digits_ddd and len(digits_num) in (10, 11):
            digits_ddd = digits_num[:2]
            digits_num = digits_num[2:]
        elif digits_ddd and len(digits_num) in (10, 11) and digits_num.startswith(digits_ddd):
            digits_num = digits_num[len(digits_ddd):]

        data["ddd"] = digits_ddd or None
        data["numero"] = digits_num
        return data


class EmailPayload(BasePayloadModel):
    endereco: str
    tipo: str = "GENERICO_RECEITA"
    status: str = "ENTREGAVEL"
    mx_found: bool = True
    smtp_check: bool = True
    disposable: bool = False
    catch_all: bool = False
    titular: str | None = None
    score_confiabilidade: float = 0.95


class ContactsPayload(BasePayloadModel):
    telefones: list[PhonePayload] = Field(default_factory=list)
    emails: list[EmailPayload] = Field(default_factory=list)


class DecisionMakerDirectContacts(BasePayloadModel):
    email_corporativo: str | None = None
    email_secundario: str | None = None
    ddd_celular: str | None = None
    celular_whatsapp: str | None = None
    whatsapp_validado: bool = False
    linkedin_url: str | None = None

    @model_validator(mode="before")
    @classmethod
    def normalize_direct_phone(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        raw_cel = str(data.get("celular_whatsapp") or "")
        raw_ddd = str(data.get("ddd_celular") or "")

        if raw_cel:
            digits_cel = "".join(c for c in raw_cel if c.isdigit())
            digits_ddd = "".join(c for c in raw_ddd if c.isdigit())

            if digits_cel.startswith("55") and len(digits_cel) in (12, 13):
                digits_cel = digits_cel[2:]

            if digits_ddd.startswith("0") and len(digits_ddd) == 3:
                digits_ddd = digits_ddd[1:]

            if digits_cel.startswith("0") and len(digits_cel) in (11, 12):
                digits_cel = digits_cel[1:]

            if not digits_ddd and len(digits_cel) in (10, 11):
                digits_ddd = digits_cel[:2]
                digits_cel = digits_cel[2:]
            elif digits_ddd and len(digits_cel) in (10, 11) and digits_cel.startswith(digits_ddd):
                digits_cel = digits_cel[len(digits_ddd):]

            data["ddd_celular"] = digits_ddd or None
            data["celular_whatsapp"] = digits_cel or None
        elif raw_ddd:
            digits_ddd = "".join(c for c in raw_ddd if c.isdigit())
            if digits_ddd.startswith("0") and len(digits_ddd) == 3:
                digits_ddd = digits_ddd[1:]
            data["ddd_celular"] = digits_ddd or None
        return data


class DecisionMakerPayload(BasePayloadModel):
    id: str | None = None
    nome: str
    cpf_mascarado: str | None = None
    qualificacao_socio: str = "49-Sócio-Administrador"
    data_entrada_sociedade: str | None = None
    percentual_capital_social: float | None = None
    faixa_etaria: str | None = None
    pais_origem: str = "Brasil"
    cargo_executivo_mercado: str = "Administrador"
    nivel_hierarquico: str = "C_LEVEL"
    poder_decisao: str = "FINAL_SIGNER"
    contatos_diretos: DecisionMakerDirectContacts = Field(
        default_factory=DecisionMakerDirectContacts
    )
    outras_empresas_como_socio: int = 0
    pep_pessoa_politicamente_exposta: bool = False


class ForeignTradeAndLogisticsPayload(BasePayloadModel):
    radar_siscomex: dict[str, Any] = Field(
        default_factory=lambda: {
            "habilitado": False,
            "modalidade": "INEXISTENTE",
            "status": "INATIVO",
            "data_habilitacao": None,
        }
    )
    historico_importacao: dict[str, Any] = Field(
        default_factory=lambda: {
            "importa_ultimos_12_meses": False,
            "volume_anual_importado_usd": 0.0,
            "principais_paises_origem": [],
            "categorias_ncm": [],
        }
    )
    historico_exportacao: dict[str, Any] = Field(
        default_factory=lambda: {"exporta_ultimos_12_meses": False}
    )
    frota_veiculos_cadastrada: dict[str, Any] = Field(
        default_factory=lambda: {
            "total_veiculos": 0,
            "automoveis": 0,
            "utilitarios": 0,
            "caminhoes": 0,
        }
    )


class LegalAndJudicialPayload(BasePayloadModel):
    total_processos_como_reu: int = 0
    total_processos_como_autor: int = 0
    processos_trabalhistas_ativos: int = 0
    processos_civeis_ativos: int = 0
    processos_tributarios_execucoes_fiscais: int = 0
    indice_judicializacao: str = "BAIXISSIMO"
    historico_recuperacao_judicial: bool = False
    historico_falencia: bool = False
    auditoria_trabalho_escravo_ibama: str = "LIMPO"


class DigitalPresenceAndTechStackPayload(BasePayloadModel):
    tecnologias_detectadas: list[dict[str, Any]] = Field(default_factory=list)
    redes_sociais: dict[str, Any] = Field(default_factory=dict)
    infraestrutura_web: dict[str, Any] = Field(
        default_factory=lambda: {
            "servidor_web": None,
            "certificado_ssl_valido": True,
            "emissor_ssl": None,
            "dns_seguranca": {},
        }
    )


class GovernanceLgpdAndCompliancePayload(BasePayloadModel):
    enquadramento_legal: str = "LEI_13709_LGPD"
    base_legal_prospeccao: str = "LEGITIMO_INTERESSE_ART_7_IX"
    finalidade_tratamento: str = "PROSPECCAO_COMERCIAL_B2B"
    dpo_encarregado_dados: str | None = None
    opt_out_solicitado: bool = False
    data_opt_out: str | None = None
    hash_rastreabilidade_consentimento: str | None = None
    politica_retencao_dias: int = 730


class CrmOutboxIntegrationPayload(BasePayloadModel):
    status_sincronizacao: str = "PENDING"
    integrado_com: list[str] = Field(default_factory=list)
    registros_remotos: dict[str, Any] = Field(default_factory=dict)
    idempotency_key: str | None = None
    data_ultima_sincronizacao: str | None = None
    tentativas_entrega: int = 0
    falhas: list[Any] = Field(default_factory=list)


class CanonicalLeadPayload(BasePayloadModel):
    meta_: MetaPayload = Field(alias="_meta")
    identification: IdentificationPayload
    company: CompanyPayload
    financial_and_banking: FinancialAndBankingPayload = Field(
        default_factory=FinancialAndBankingPayload
    )
    fiscal_and_tax_intelligence: FiscalAndTaxIntelligencePayload = Field(
        default_factory=FiscalAndTaxIntelligencePayload
    )
    cnae: CnaeSection
    address: AddressPayload
    contacts: ContactsPayload = Field(default_factory=ContactsPayload)
    decision_makers_qsa: list[DecisionMakerPayload] = Field(default_factory=list)
    foreign_trade_and_logistics: ForeignTradeAndLogisticsPayload = Field(
        default_factory=ForeignTradeAndLogisticsPayload
    )
    legal_and_judicial: LegalAndJudicialPayload = Field(default_factory=LegalAndJudicialPayload)
    digital_presence_and_tech_stack: DigitalPresenceAndTechStackPayload = Field(
        default_factory=DigitalPresenceAndTechStackPayload
    )
    governance_lgpd_and_compliance: GovernanceLgpdAndCompliancePayload = Field(
        default_factory=GovernanceLgpdAndCompliancePayload
    )
    crm_outbox_integration: CrmOutboxIntegrationPayload = Field(
        default_factory=CrmOutboxIntegrationPayload
    )

    def model_dump(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        kwargs.setdefault("by_alias", True)
        return super().model_dump(*args, **kwargs)
