from __future__ import annotations

from typing import Any

from leadstream.entities.normalization import only_digits


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def records(value: Any, *keys: str) -> list[dict[str, Any]]:
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    data = as_dict(value)
    for key in keys:
        nested = data.get(key)
        if isinstance(nested, list):
            return [item for item in nested if isinstance(item, dict)]
    return []


def optional_bool(*values: Any) -> bool | None:
    for value in values:
        if value is None:
            continue
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return bool(value)
        normalized = str(value).strip().casefold()
        if normalized in {"true", "1", "sim", "yes", "ativo", "active"}:
            return True
        if normalized in {"false", "0", "não", "nao", "no", "inativo", "inactive"}:
            return False
    return None


def number(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def dataset(root: dict[str, Any], *names: str) -> Any:
    for name in names:
        if root.get(name) is not None:
            return root[name]
    return None


def response_root(body: Any) -> tuple[dict[str, Any], dict[str, Any]]:
    metadata = body if isinstance(body, dict) else {}
    if isinstance(body, dict) and isinstance(body.get("Result"), list):
        items = records(body["Result"])
        return (items[0] if items else {}), metadata
    if isinstance(body, list):
        items = records(body)
        return (items[0] if items else {}), metadata
    return as_dict(body), metadata


def parse_phones(root: dict[str, Any]) -> list[dict[str, Any]]:
    from leadstream.validation.phone_check import get_phone_operator_hint

    registration = as_dict(dataset(root, "RegistrationData", "registration_data"))
    value = dataset(
        root, "ExtendedPhones", "PhonesExtended", "Phones", "phones", "Telefones"
    ) or registration.get("Phones")
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in records(value, "Phones", "ExtendedPhones", "Telefones"):
        ddd = only_digits(str(item.get("AreaCode") or item.get("DDD") or ""))
        phone = only_digits(str(item.get("Number") or item.get("Numero") or ""))
        if len(phone) in {10, 11} and not ddd:
            ddd, phone = phone[:2], phone[2:]
        if not phone or f"{ddd}{phone}" in seen:
            continue
        seen.add(f"{ddd}{phone}")
        line_type = str(item.get("Type") or item.get("PhoneType") or "").upper()
        mobile = optional_bool(item.get("IsMobile"))
        if mobile is None:
            mobile = "MOBILE" in line_type or (len(phone) == 9 and phone.startswith("9"))
        result.append(
            {
                "ddd": ddd,
                "numero": phone,
                "is_celular": mobile,
                "operadora": str(
                    item.get("CurrentCarrier")
                    or item.get("Carrier")
                    or get_phone_operator_hint(ddd, phone)
                ),
                "score": number(item.get("Priority") or item.get("Score")),
                "recencia": item.get("EntityLastPassageDate")
                or item.get("LastValidationDate")
                or item.get("LastUpdateDate"),
                "ativo": optional_bool(item.get("IsActive")),
                "principal": optional_bool(item.get("IsMainForEntity")),
                "nao_me_perturbe": optional_bool(item.get("IsInDoNotCallList")),
            }
        )
    result.sort(
        key=lambda item: (
            item["principal"] is True,
            item["ativo"] is not False,
            item["is_celular"],
            item["score"],
        ),
        reverse=True,
    )
    return result


def parse_addresses(root: dict[str, Any]) -> list[dict[str, Any]]:
    registration = as_dict(dataset(root, "RegistrationData", "registration_data"))
    value = dataset(root, "ExtendedAddresses", "AddressesExtended", "Addresses", "addresses")
    value = value or registration.get("Addresses")
    result = [
        {
            "logradouro": item.get("AddressMain") or item.get("Street"),
            "numero": item.get("Number"),
            "complemento": item.get("Complement"),
            "bairro": item.get("Neighborhood"),
            "municipio": item.get("City"),
            "uf": item.get("State"),
            "cep": only_digits(str(item.get("ZipCode") or "")),
            "pais": item.get("Country") or "BRASIL",
            "tipo": item.get("Type") or item.get("Typology"),
            "principal": optional_bool(item.get("IsMainForEntity")),
            "ativo": optional_bool(item.get("IsActive")),
            "validado_em": item.get("LastValidationDate"),
            "atualizado_em": item.get("LastUpdateDate"),
        }
        for item in records(value, "Addresses", "ExtendedAddresses", "Enderecos")
    ]
    result.sort(
        key=lambda item: (item["principal"] is True, item["ativo"] is not False),
        reverse=True,
    )
    return result


def parse_benefits(root: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    from leadstream.intelligence.consignado import get_inss_species_info

    official = dataset(
        root,
        "ExtendedSocialAssistancePrograms",
        "SocialAssistanceExtended",
        "social_assistance_extended",
    )
    official_records = records(official, "SocialAssistances", "Benefits", "Programs")
    legacy_records = records(
        dataset(root, "SocialBenefits", "social_benefits", "InssBenefits", "Benefits"),
        "Benefits",
    )
    benefits: list[dict[str, Any]] = []
    inss: list[dict[str, Any]] = []
    legacy_ids = {id(item) for item in legacy_records}
    for item in official_records + legacy_records:
        details = as_dict(item.get("AssistanceDetails"))
        program = str(
            item.get("ProgramName")
            or item.get("BenefitDescription")
            or item.get("Name")
            or "BENEFÍCIO NÃO INFORMADO"
        )
        benefit_number = str(
            details.get("BenefitNumber") or item.get("BenefitNumber") or item.get("NB") or ""
        )
        value = number(item.get("Value") or item.get("BenefitValue") or item.get("TotalAmount"))
        benefits.append(
            {
                "programa": program,
                "numero_beneficio": benefit_number,
                "status": str(item.get("Status") or "DESCONHECIDO").upper(),
                "valor": value,
                "valor_total": number(item.get("TotalAmount")),
                "parcelas": item.get("Installments") or item.get("TotalInstallments"),
                "inicio": item.get("StartDate"),
                "fim": item.get("EndDate"),
                "municipio": details.get("County") or details.get("City"),
                "uf": item.get("State"),
                "historico_pagamentos": records(item.get("PaymentHistory")),
            }
        )
        upper = program.upper()
        if id(item) in legacy_ids or any(
            marker in upper
            for marker in ("INSS", "PREVID", "APOSENT", "PENSÃO", "PENSAO", "BPC")
        ):
            species_code = str(
                item.get("BenefitType")
                or item.get("SpeciesCode")
                or item.get("CodigoEspecie")
                or ""
            )
            species = get_inss_species_info(species_code)
            blocked = optional_bool(item.get("IsBlockedForLoans"), item.get("BloqueadoEmprestimo"))
            status = str(item.get("Status") or "DESCONHECIDO").upper()
            inss.append(
                {
                    "numero_beneficio": benefit_number,
                    "especie_codigo": species_code or species["codigo"],
                    "especie_descricao": program or species["descricao"],
                    "categoria": species["categoria"],
                    "elegivel_consignado": (
                        species["elegivel"] and blocked is False and status == "ATIVO"
                    ),
                    "valor_beneficio": value,
                    "status": status,
                    "data_concessao": str(item.get("StartDate") or "")[:10] or None,
                    "bloqueado_para_emprestimo": blocked,
                    "alerta": species["alerta"],
                }
            )
    return benefits, inss


def parse_professions(root: dict[str, Any]) -> list[dict[str, Any]]:
    value = dataset(
        root,
        "ProfessionData",
        "profession_data",
        "EmploymentRelationships",
        "employment_relationships",
    )
    result: list[dict[str, Any]] = []
    for item in records(value, "Professions", "EmploymentRelationships", "WorkRecords"):
        employer = str(item.get("CompanyName") or item.get("EmployerName") or "")
        sector = str(item.get("Sector") or item.get("RelationshipType") or "")
        source = str(item.get("Source") or "")
        public = any(
            marker in f"{sector} {source} {employer}".upper()
            for marker in (
                "PUBLIC",
                "PÚBLIC",
                "SERVIDOR",
                "SIAPE",
                "GOVERNO",
                "PREFEITURA",
                "TRIBUNAL",
            )
        )
        result.append(
            {
                "empregador": employer,
                "cnpj_empregador": only_digits(str(item.get("EmployerTaxId") or "")),
                "tipo_vinculo": sector or "NÃO INFORMADO",
                "orgao_siape": item.get("Agency") or (employer if public else ""),
                "matricula": str(item.get("RegistrationNumber") or ""),
                "cargo": item.get("Occupation") or item.get("JobTitle") or item.get("Area"),
                "salario": number(item.get("Income") or item.get("Salary")),
                "uf": item.get("State"),
                "ativo": optional_bool(item.get("IsActive"), item.get("Status")),
                "eh_servidor_publico": public,
                "inicio": item.get("StartDate"),
                "fim": item.get("EndDate"),
                "historico_remuneracao": as_dict(item.get("AdditionalDetails")).get(
                    "IncomeHistory", []
                ),
            }
        )
    return result


def parse_financial(root: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    value = as_dict(dataset(root, "FinantialData", "FinancialData", "financial_data"))
    estimates = records(value.get("IncomeEstimates"), "IncomeEstimates")
    estimate = estimates[0] if estimates else as_dict(value.get("IncomeEstimate"))
    tax_returns = records(value.get("TaxReturns"), "TaxReturns")
    banks = [
        {
            "instituicao": item.get("Bank") or item.get("BankName"),
            "agencia": item.get("Branch"),
            "ano": item.get("Year"),
            "situacao": item.get("Status"),
            "tipo_vinculo": "DESTINO_RESTITUICAO_IR",
            "fonte": "BIGDATACORP_FINANCIAL_DATA",
        }
        for item in tax_returns
        if item.get("Bank") or item.get("BankName")
    ]
    return (
        {
            "renda_estimada": number(
                estimate.get("EstimatedIncome")
                or estimate.get("Income")
                or value.get("EstimatedIncome")
            ),
            "faixa_renda": estimate.get("IncomeRange") or value.get("IncomeRange") or "",
            "patrimonio_total": number(value.get("TotalAssets")),
            "declaracoes_ir": tax_returns,
        },
        banks,
    )


def parse_financial_risk(root: dict[str, Any]) -> dict[str, Any]:
    value = as_dict(dataset(root, "FinancialRisk", "financial_risk"))
    protests = value.get("Protests")
    bad_checks = value.get("BadChecks") or value.get("CcfOccurrences")
    return {
        "possui_pendencias": optional_bool(value.get("IsCurrentlyOnCollection")),
        "ocorrencias_ultimos_365_dias": value.get("Last365DaysCollectionOccurrences"),
        "meses_consecutivos_em_cobranca": value.get("CurrentConsecutiveCollectionMonths"),
        "score_risco": value.get("FinancialRiskScore"),
        "nivel_risco": value.get("FinancialRiskLevel"),
        "protestos": protests,
        "cheques_sem_fundo": bad_checks,
        "detalhes_restritivos_contratados": protests is not None or bad_checks is not None,
    }


def parse_do_not_call(root: dict[str, Any]) -> tuple[list[dict[str, Any]], bool]:
    keys = ("DoNotCall", "do_not_call", "ProconBlocks", "NaoMePerturbe")
    consulted = any(key in root for key in keys)
    raw = dataset(root, *keys)
    result: list[dict[str, Any]] = []
    for item in records(raw, "Records", "Phones"):
        phone = only_digits(str(item.get("Phone") or item.get("Number") or ""))
        if phone:
            result.append(
                {
                    "phone": phone,
                    "blocked": optional_bool(item.get("Blocked"), item.get("IsBlocked")),
                    "entity": item.get("Entity") or "ANATEL_FEBRABAN",
                    "block_date": str(item.get("Date") or item.get("BlockDate") or "")[:10]
                    or None,
                }
            )
    return result, consulted


def parse_education(root: dict[str, Any]) -> dict[str, Any]:
    value = dataset(root, "UniversityStudentData", "university_student_data")
    history = records(
        value,
        "UniversityStudents",
        "EducationHistory",
        "AcademicRecords",
        "Records",
    )
    levels = [
        str(item.get("Level") or item.get("EducationLevel") or item.get("Degree") or "")
        for item in history
    ]
    return {
        "highest_level": next((level for level in reversed(levels) if level), None),
        "historico": history,
    }


def parse_electoral_response(body: Any) -> dict[str, Any] | None:
    root, _ = response_root(body)
    queries = records(root.get("OnlineQueries"), "OnlineQueries")
    data = as_dict(queries[0].get("QueryResultData")) if queries else as_dict(
        root.get("QueryResultData")
    )
    if not data:
        return None
    return {
        "titulo_eleitor": data.get("RegistrationNumber"),
        "status_titulo": data.get("Status"),
        "status_biometria": data.get("BiometricStatus"),
        "nome_civil": data.get("CivilName"),
        "nome_social": data.get("SocialName"),
        "data_nascimento": data.get("BirthDate"),
        "local_votacao": data.get("PollingPlace.LocationName"),
        "numero_local": data.get("PollingPlace.LocationNumber"),
        "endereco_local": data.get("PollingPlace.Address"),
        "bairro": data.get("PollingPlace.Neighborhood"),
        "municipio": data.get("PollingPlace.City"),
        "uf": data.get("PollingPlace.UF"),
        "zona": data.get("PollingPlace.Zone"),
        "secao": data.get("PollingPlace.Section"),
        "secao_acessivel": data.get("PollingPlace.SectionWithAccessibility"),
    }


def _redact_documents(value: Any) -> Any:
    if isinstance(value, list):
        return [_redact_documents(item) for item in value]
    if not isinstance(value, dict):
        return value
    return {
        str(key): _redact_documents(item)
        for key, item in value.items()
        if not any(
            marker in str(key).casefold().replace("_", "")
            for marker in ("cpf", "taxidnumber", "docnumber")
        )
    }


def parse_credit_response(body: Any) -> dict[str, Any] | None:
    root, metadata = response_root(body)
    if not root:
        return None
    return {
        "provedor": "BIGDATACORP_MARKETPLACE",
        "query_id": metadata.get("QueryId"),
        "detalhes": _redact_documents(root),
    }


def parse_person_response(
    *,
    body: Any,
    cpf: str,
    datasets: str,
    electoral_data: dict[str, Any] | None = None,
    electoral_error: str | None = None,
    credit_data: dict[str, Any] | None = None,
    credit_error: str | None = None,
) -> dict[str, Any]:
    root, metadata = response_root(body)
    if not root:
        return {
            "encontrado": False,
            "dados_cadastrais": None,
            "telefones": [],
            "dados_eleitorais": electoral_data,
        }
    registration = as_dict(dataset(root, "RegistrationData", "registration_data"))
    basic = as_dict(
        dataset(root, "BasicData", "basic_data", "DadosBasicos")
        or registration.get("BasicData")
    )
    phones = parse_phones(root)
    addresses = parse_addresses(root)
    social_benefits, inss_benefits = parse_benefits(root)
    work = parse_professions(root)
    financial, banks = parse_financial(root)
    restrictions = parse_financial_risk(root)
    if credit_data:
        restrictions["detalhes_restritivos"] = credit_data
        restrictions["detalhes_restritivos_contratados"] = True
    education = parse_education(root)
    do_not_call, do_not_call_consulted = parse_do_not_call(root)
    marital = as_dict(basic.get("MaritalStatusData"))
    birth_date = basic.get("BirthDate") or basic.get("DataNascimento")
    death_date = basic.get("DeathDate") or root.get("DeathDate")
    name = str(
        basic.get("Name")
        or basic.get("Nome")
        or root.get("Name")
        or root.get("Nome")
        or ""
    )
    return {
        "encontrado": bool(
            name or phones or addresses or social_benefits or work or electoral_data
        ),
        "dados_cadastrais": {
            "nome": name,
            "cpf": f"{cpf[:3]}.{cpf[3:6]}.{cpf[6:9]}-{cpf[9:]}",
            "cpf_digitos": cpf,
            "data_nascimento": str(birth_date)[:10] if birth_date else None,
            "idade": basic.get("Age") or basic.get("Idade"),
            "nome_mae": basic.get("MotherName") or basic.get("NomeMae") or "",
            "nome_pai": basic.get("FatherName") or basic.get("NomePai") or "",
            "genero": basic.get("Gender") or basic.get("Genero") or "",
            "estado_civil": marital.get("Status")
            or marital.get("Description")
            or basic.get("MaritalStatus"),
            "instrucao": education.get("highest_level"),
            "situacao_cpf": basic.get("TaxIdStatus")
            or basic.get("TaxIdFiscalStatus")
            or basic.get("SituacaoCadastral")
            or "DESCONHECIDA",
            "origem_cpf": basic.get("TaxIdOrigin") or basic.get("OrigemCpf"),
            "regiao_fiscal_cpf": basic.get("TaxIdFiscalRegion"),
            "data_situacao_cadastral": basic.get("TaxIdStatusDate"),
            "is_deceased": optional_bool(
                basic.get("HasObitIndication"), basic.get("IsDeceased"), root.get("IsDeceased")
            ),
            "death_date": str(death_date)[:10] if death_date else None,
            "endereco": addresses[0] if addresses else None,
        },
        "enderecos": addresses,
        "telefones": phones,
        "beneficios_sociais": social_benefits,
        "beneficios_inss": inss_benefits,
        "vinculos_empregaticios": work,
        "renda": financial,
        "restricoes_financeiras": restrictions,
        "relacionamentos_bancarios": banks,
        "dados_eleitorais": electoral_data,
        "escolaridade": education,
        "bloqueios_nao_perturbe": do_not_call,
        "nao_me_perturbe_consultado": do_not_call_consulted,
        "metadados_provedor": {
            "query_id": metadata.get("QueryId"),
            "elapsed_milliseconds": metadata.get("ElapsedMilliseconds"),
            "datasets": [item.strip() for item in datasets.split(",") if item.strip()],
            "electoral_error": electoral_error,
            "credit_error": credit_error,
        },
    }
