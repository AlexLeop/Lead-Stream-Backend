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
    confidence_score_global: float = 0.0
    entity_type: str | None = None
    provenance_method: str | None = None


class IdentificationPayload(BasePayloadModel):
    lead_id: str
    status: str = "UNASSESSED"
    lead_score: int = 0
    lead_temperature: str = "UNKNOWN"
    ideal_customer_profile_fit: float = 0.0
    tags: list[str] = Field(default_factory=list)


class CompanyPayload(BasePayloadModel):
    cnpj: str
    cnpj_raw: str = ""
    cnpj_raiz: str = ""
    cnpj_ordem: str = ""
    cnpj_dv: str = ""
    tipo: str = "NAO_INFORMADO"
    razao_social: str
    nome_fantasia: str | None = None
    situacao_cadastral: str = "DESCONHECIDA"
    data_situacao_cadastral: str | None = None
    motivo_situacao_cadastral: str | None = None
    situacao_especial: str | None = None
    data_situacao_especial: str | None = None
    data_abertura: str | None = None
    idade_empresa_anos: float | None = None
    natureza_juridica: dict[str, Any] = Field(default_factory=dict)
    porte: str = "NAO_INFORMADO"
    porte_sebrae: str = "NAO_INFORMADO"
    regime_tributario: str = "NAO_INFORMADO"
    optante_simples: bool | None = None
    data_opcao_simples: str | None = None
    data_exclusao_simples: str | None = None
    optante_simei: bool | None = None
    data_opcao_simei: str | None = None
    capital_social: float = 0.0
    capital_social_formatado: str = "R$ 0,00"
    faturamento_estimado_anual: float = 0.0
    faixa_faturamento: str = "Não informado"
    faixa_funcionarios: str = "Não informado"
    quantidade_funcionarios_estimada: int | None = None
    website: str | None = None
    dominio: str | None = None


class BankingInstitutionPayload(BasePayloadModel):
    codigo_compensacao: str = ""
    nome_banco: str = ""
    tipo_relacionamento: str = "NAO_INFORMADO"
    chave_pix_ativa: bool | None = None
    tipo_chave_pix: str = "NAO_INFORMADO"
    chave_pix: str | None = None
    operacoes_cambio_ativas: bool | None = None
    tempo_relacionamento_anos: float | None = None


class FinancialAndBankingPayload(BasePayloadModel):
    instituicoes_bancarias_principais: list[BankingInstitutionPayload] = Field(default_factory=list)
    bancos_relacionamento_detectados: list[BankingInstitutionPayload] = Field(default_factory=list)
    linhas_credito_ativas: list[str] = Field(default_factory=list)
    risco_credito_score: int | None = None
    risco_credito_classificacao: str | None = None
    limite_credito_estimado: float | None = None
    capacidade_pagamento: str | None = None
    protestos_ativos_cartorio: int | None = None
    valor_total_protestos: float | None = None
    cheques_sem_fundo_ccf: int | None = None
    pendencias_financeiras_ativas: bool | None = None


class FiscalAndTaxIntelligencePayload(BasePayloadModel):
    situacao_fiscal_federal: str = "NAO_CONSULTADA"
    situacao_pgfn_divida_ativa: str = "NAO_CONSULTADA"
    valor_divida_ativa_uniao: float | None = None
    certidao_negativa_debito_cnd: dict[str, Any] = Field(
        default_factory=lambda: {
            "status": "NAO_CONSULTADA",
            "numero_certidao": None,
            "validade": None,
        }
    )
    certidao_fgts_crf: dict[str, Any] = Field(
        default_factory=lambda: {"status": "NAO_CONSULTADA", "numero_crf": None, "validade": None}
    )
    inscricao_estadual: dict[str, Any] = Field(
        default_factory=lambda: {"numero": None, "uf": None, "status_sintegra": "NAO_CONSULTADO"}
    )
    inscricao_municipal: dict[str, Any] = Field(
        default_factory=lambda: {"numero": None, "municipio": None, "status": "NAO_CONSULTADO"}
    )


class CnaePrincipal(BasePayloadModel):
    codigo: str
    descricao: str
    setor: str = "Não informado"
    grau_risco_trabalho: int = 0


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
    geocoding_precision: str | None = None
    tipo_imovel: str | None = None
    valor_m2_regiao: float | None = None


class PhonePayload(BasePayloadModel):
    tipo: str = "DESCONHECIDO"
    ddd: str | None = None
    numero: str
    ramal: str | None = None
    operadora: str = "DESCONHECIDA"
    status_linha: str = "DESCONHECIDA"
    principal: bool = False
    validado: bool = False
    whatsapp_status: dict[str, Any] = Field(default_factory=dict)
    confianca: float = 0.0

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
            digits_num = digits_num[len(digits_ddd) :]

        data["ddd"] = digits_ddd or None
        data["numero"] = digits_num
        return data


class EmailPayload(BasePayloadModel):
    endereco: str
    tipo: str = "NAO_CLASSIFICADO"
    status: str = "NAO_VERIFICADO"
    mx_found: bool = False
    smtp_check: bool = False
    disposable: bool = False
    catch_all: bool = False
    titular: str | None = None
    score_confiabilidade: float = 0.0


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
                digits_cel = digits_cel[len(digits_ddd) :]

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
    qualificacao_socio: str = "NAO_INFORMADA"
    data_entrada_sociedade: str | None = None
    percentual_capital_social: float | None = None
    faixa_etaria: str | None = None
    pais_origem: str = "Não informado"
    cargo_executivo_mercado: str = "Não informado"
    nivel_hierarquico: str = "UNKNOWN"
    poder_decisao: str = "UNKNOWN"
    contatos_diretos: DecisionMakerDirectContacts = Field(
        default_factory=DecisionMakerDirectContacts
    )
    outras_empresas_como_socio: int | None = None
    pep_pessoa_politicamente_exposta: bool | None = None


def _default_historico_importacao() -> dict[str, Any]:
    empty_paises: list[str] = []
    empty_ncm: list[str] = []
    return {
        "importa_ultimos_12_meses": None,
        "volume_anual_importado_usd": None,
        "principais_paises_origem": empty_paises,
        "categorias_ncm": empty_ncm,
    }


def _default_infraestrutura_web() -> dict[str, Any]:
    empty_dns: dict[str, Any] = {}
    return {
        "servidor_web": None,
        "certificado_ssl_valido": None,
        "emissor_ssl": None,
        "dns_seguranca": empty_dns,
    }


class ForeignTradeAndLogisticsPayload(BasePayloadModel):
    radar_siscomex: dict[str, Any] = Field(
        default_factory=lambda: {
            "habilitado": None,
            "modalidade": "NAO_CONSULTADA",
            "status": "NAO_CONSULTADO",
            "data_habilitacao": None,
        }
    )
    historico_importacao: dict[str, Any] = Field(default_factory=_default_historico_importacao)
    historico_exportacao: dict[str, Any] = Field(
        default_factory=lambda: {"exporta_ultimos_12_meses": None}
    )
    frota_veiculos_cadastrada: dict[str, Any] = Field(
        default_factory=lambda: {
            "total_veiculos": None,
            "automoveis": None,
            "utilitarios": None,
            "caminhoes": None,
        }
    )


class LegalAndJudicialPayload(BasePayloadModel):
    total_processos_como_reu: int | None = None
    total_processos_como_autor: int | None = None
    processos_trabalhistas_ativos: int | None = None
    processos_civeis_ativos: int | None = None
    processos_tributarios_execucoes_fiscais: int | None = None
    indice_judicializacao: str = "NAO_CONSULTADO"
    historico_recuperacao_judicial: bool | None = None
    historico_falencia: bool | None = None
    auditoria_trabalho_escravo_ibama: str = "NAO_CONSULTADA"


class DigitalPresenceAndTechStackPayload(BasePayloadModel):
    tecnologias_detectadas: list[dict[str, Any]] = Field(default_factory=list)
    redes_sociais: dict[str, Any] = Field(default_factory=dict)
    infraestrutura_web: dict[str, Any] = Field(default_factory=_default_infraestrutura_web)


class GovernanceLgpdAndCompliancePayload(BasePayloadModel):
    enquadramento_legal: str = "LEI_13709_LGPD"
    base_legal_prospeccao: str = "NAO_DOCUMENTADA"
    finalidade_tratamento: str = "NAO_DOCUMENTADA"
    dpo_encarregado_dados: str | None = None
    opt_out_solicitado: bool = False
    data_opt_out: str | None = None
    hash_rastreabilidade_consentimento: str | None = None
    politica_retencao_dias: int | None = None


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


# =============================================================================
# CONTRATO CANÔNICO DE PESSOA FÍSICA (PF - HIGIENIZAÇÃO & ENRIQUECIMENTO)
# =============================================================================


class PersonIdentificationPayload(BasePayloadModel):
    person_id: str
    entity_type: str = "PERSON"
    status: str = "UNASSESSED"
    lead_score: int = 0
    confidence_score: float = 0.0
    cost_credits: int = 0
    tags: list[str] = Field(default_factory=list)


class DocumentValidationPayload(BasePayloadModel):
    cpf_formatado: str
    cpf_numerico: str
    digitos_verificadores: str
    modulo_11_valido: bool = False
    origem_validacao: str = "CALCULO_ESTRUTURAL_LOCAL_MODULO_11"
    regiao_fiscal: dict[str, Any] | None = None


class PersonCadastralDataPayload(BasePayloadModel):
    nome: str | None = None
    cpf: str
    cpf_numerico: str
    data_nascimento: str | None = None
    idade: int | None = None
    genero: str | None = None
    nome_mae: str | None = None
    nome_pai: str | None = None
    situacao_cadastral_rfb: str = "DESCONHECIDA"
    data_situacao_cadastral: str | None = None
    codigo_controle_rfb: str | None = None


class LossPreventionFilterPayload(BasePayloadModel):
    status: str = "INCONCLUSIVO"
    is_deceased: bool | None = None
    death_date: str | None = None
    tax_status: str = "DESCONHECIDA"
    elegivel_consignado: bool = False
    motivo_expurgo: str | None = None
    deve_cobrar_credito: bool | None = None
    fontes_consultadas: list[str] = Field(default_factory=list)


class BeneficioInssPayload(BasePayloadModel):
    numero_beneficio: str
    especie_codigo: str
    especie_descricao: str
    categoria_aptidao: str = "DESCONHECIDO"
    status_beneficio: str = "DESCONHECIDO"
    data_concessao: str | None = None
    data_cessacao: str | None = None
    valor_beneficio_bruto: float = 0.0
    valor_beneficio_liquido: float | None = None
    descontos_obrigatorios: float | None = None
    bloqueado_para_emprestimo: bool | None = None
    alerta_elegibilidade: str | None = None
    banco_pagador: dict[str, Any] = Field(default_factory=dict)


class ConsignadoInssPayload(BasePayloadModel):
    possui_beneficio_inss: bool = False
    quantidade_beneficios: int = 0
    beneficios: list[BeneficioInssPayload] = Field(default_factory=list)


class VinculoSiapePayload(BasePayloadModel):
    matricula: str
    orgao: str
    uorg: str | None = None
    cargo: str | None = None
    regime_juridico: str | None = None
    situacao_funcional: str | None = None
    uf_lotacao: str | None = None
    rendimento_bruto_declarado: float = 0.0


class ConsignadoSiapePayload(BasePayloadModel):
    possui_vinculo_publico: bool = False
    quantidade_vinculos: int = 0
    vinculos: list[VinculoSiapePayload] = Field(default_factory=list)


class MargemParcelaPayload(BasePayloadModel):
    percentual: float = 0.0
    valor_mensal_permitido: float = 0.0


class MargemConsignavelPayload(BasePayloadModel):
    base_legal: str = "POLITICA_NAO_INFORMADA"
    elegivel: bool | None = None
    vinculo_base: str | None = None
    numero_beneficio_base: str | None = None
    salario_base_calculo: float = 0.0
    margem_emprestimo_35: MargemParcelaPayload | dict[str, Any] = Field(default_factory=dict)
    margem_rmc_cartao_5: MargemParcelaPayload | dict[str, Any] = Field(default_factory=dict)
    margem_rcc_beneficio_5: MargemParcelaPayload | dict[str, Any] = Field(default_factory=dict)
    margem_total_45: MargemParcelaPayload | dict[str, Any] = Field(default_factory=dict)


class TelefoneHigienizadoPayload(BasePayloadModel):
    ddd: str | None = None
    numero: str
    numero_formatado: str
    numero_e164: str
    tipo_linha: str = "MOVEL_CELULAR"
    operadora: str = ""
    score_recencia: float = 0.0
    indicador_atividade: str = ""


class TelefoniaHigienizadaPayload(BasePayloadModel):
    total_linhas_encontradas: int = 0
    telefones: list[TelefoneHigienizadoPayload] = Field(default_factory=list)


class WhatsAppProbeResultadoPayload(BasePayloadModel):
    garantido: bool = False
    status: str = "INDISPONIVEL"
    numero_formatado: str | None = None
    numero_e164: str | None = None
    tipo_conta: str = "NENHUMA"
    jid: str | None = None
    foto_perfil: str | None = None
    link_direto: str | None = None
    verificado_em: str | None = None


class WhatsAppProbeTecnicoPayload(BasePayloadModel):
    gateway_configurado: bool = False
    provedor: str | None = None
    resultado: WhatsAppProbeResultadoPayload | dict[str, Any] | None = None


class TelefoneNaoMePerturbePayload(BasePayloadModel):
    numero: str | None = None
    numero_formatado: str | None = None
    status_consulta: str = "NAO_CONSULTADO"
    inscrito_bloqueio: bool | None = None
    entidade: str | None = None
    data_bloqueio: str | None = None
    motivo: str | None = None
    seguro_discagem_fria: bool = False
    risco_multa: str = "DESCONHECIDO"
    badge_texto: str = ""


class NaoMePerturbePayload(BasePayloadModel):
    fonte_reguladora: str | None = None
    consulta_executada: bool = False
    telefones_consultados: list[TelefoneNaoMePerturbePayload] = Field(default_factory=list)


class MailingQualificadoItemPayload(BasePayloadModel):
    ordem_prioridade: int = 1
    numero_formatado: str
    numero_raw: str
    numero_e164: str
    ddd: str | None = None
    operadora: str = ""
    whatsapp_disponivel: bool = False
    whatsapp_tipo_conta: str = "NENHUMA"
    link_whatsapp: str | None = None
    nao_me_perturbe_inscrito: bool | None = None
    seguro_para_discagem_fria: bool = False
    risco_multa: str = "DESCONHECIDO"
    score_assertividade: int = 0
    recomendacao_canal: str = "AGUARDAR_VALIDACAO_COMPLIANCE"
    rotulo_canal: str = ""


class AddressCadastralPayload(BasePayloadModel):
    logradouro: str | None = None
    numero: str | None = None
    complemento: str | None = None
    bairro: str | None = None
    municipio: str | None = None
    uf: str | None = None
    cep: str | None = None
    codigo_ibge: str | None = None


class FinancialIndicatorsPayload(BasePayloadModel):
    renda_estimada_declarada: float = 0.0
    faixa_renda: str = ""
    fontes_renda_identificadas: list[str] = Field(default_factory=list)


class GovernanceLgpdPayload(BasePayloadModel):
    enquadramento_legal: str = "LEI_FEDERAL_13709_LGPD"
    base_legal: str = "NAO_DOCUMENTADA"
    finalidade: str = "NAO_DOCUMENTADA"
    trilha_auditoria_hash: str | None = None
    data_consulta: str | None = None


class CanonicalPersonPayload(BasePayloadModel):
    meta_: MetaPayload = Field(alias="_meta")
    identification: PersonIdentificationPayload
    document_validation: DocumentValidationPayload
    cadastral_data: PersonCadastralDataPayload
    loss_prevention_filter: LossPreventionFilterPayload
    consignado_inss: ConsignadoInssPayload = Field(default_factory=ConsignadoInssPayload)
    consignado_siape_publico: ConsignadoSiapePayload = Field(default_factory=ConsignadoSiapePayload)
    margem_consignavel_calculada: MargemConsignavelPayload = Field(
        default_factory=MargemConsignavelPayload
    )
    telefonia_higienizada: TelefoniaHigienizadaPayload = Field(
        default_factory=TelefoniaHigienizadaPayload
    )
    whatsapp_probe_tecnico: WhatsAppProbeTecnicoPayload = Field(
        default_factory=WhatsAppProbeTecnicoPayload
    )
    nao_me_perturbe_anatel_febraban: NaoMePerturbePayload = Field(
        default_factory=NaoMePerturbePayload
    )
    mailing_qualificado_top3: list[MailingQualificadoItemPayload] = Field(default_factory=list)
    address_cadastral: AddressCadastralPayload | None = None
    financial_indicators: FinancialIndicatorsPayload = Field(
        default_factory=FinancialIndicatorsPayload
    )
    governance_and_lgpd: GovernanceLgpdPayload = Field(default_factory=GovernanceLgpdPayload)

    def model_dump(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        kwargs.setdefault("by_alias", True)
        return super().model_dump(*args, **kwargs)
