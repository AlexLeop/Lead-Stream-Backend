from __future__ import annotations

import logging
from typing import Any

import httpx
from django.conf import settings

from leadstream.common.redaction import correlation_tag, mask_cpf
from leadstream.entities.normalization import only_digits
from leadstream.providers.exceptions import (
    ProviderNotConfigured,
    ProviderPermanentError,
    ProviderTemporaryError,
)

logger = logging.getLogger(__name__)


def _optional_bool(*values: Any) -> bool | None:
    """Mantém False explícito e não converte ausência em um fato positivo."""
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


def format_cpf_br(digits: str) -> str:
    """Formata 11 dígitos numéricos de CPF no padrão '000.000.000-00'."""
    d = only_digits(digits)
    if len(d) != 11:
        return digits
    return f"{d[:3]}.{d[3:6]}.{d[6:9]}-{d[9:]}"


class BigDataCorpPersonAdapter:
    """Adaptador oficial da BigDataCorp para inteligência cadastral de Pessoas Físicas (CPF)."""

    slug = "bigdatacorp_person"

    def __init__(self, client: httpx.Client | None = None) -> None:
        self._client = client

    def is_configured(self) -> bool:
        return bool(settings.BIGDATACORP_ACCESS_TOKEN and settings.BIGDATACORP_TOKEN_ID)

    def enrich_cpf(self, cpf: str) -> dict[str, Any]:
        """Consulta dados cadastrais e telefones de um CPF na BigDataCorp.

        Caso as credenciais não estejam configuradas, levanta ProviderNotConfigured
        (sem dados simulados ou fictícios).
        """
        if not self.is_configured():
            raise ProviderNotConfigured(
                "BigDataCorp não configurada. Defina BIGDATACORP_ACCESS_TOKEN e "
                "BIGDATACORP_TOKEN_ID."
            )

        clean_cpf = only_digits(cpf)
        if len(clean_cpf) != 11:
            raise ProviderPermanentError(
                f"CPF inválido para consulta: '{cpf}' (esperado 11 dígitos)."
            )

        access_token = settings.BIGDATACORP_ACCESS_TOKEN
        token_id = settings.BIGDATACORP_TOKEN_ID
        assert access_token is not None and token_id is not None

        base_url = getattr(
            settings, "BIGDATACORP_BASE_URL", "https://plataforma.bigdatacorp.com.br"
        )
        url = f"{base_url.rstrip('/')}/pessoas"
        headers = {
            "AccessToken": access_token,
            "TokenId": token_id,
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        datasets = getattr(settings, "BIGDATACORP_PERSON_DATASETS", "basic_data,phones_extended")
        payload = {"q": f"doc{{{clean_cpf}}}", "Datasets": datasets}

        timeout = getattr(settings, "BIGDATACORP_TIMEOUT_SECONDS", 30)
        client = self._client or httpx.Client(timeout=timeout)

        try:
            response = client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            body: Any = response.json()
        except (httpx.TimeoutException, httpx.NetworkError) as exc:
            logger.warning(
                "Falha temporária ao consultar BigDataCorp Pessoas para CPF %s [%s]: %s",
                mask_cpf(clean_cpf),
                correlation_tag(clean_cpf),
                exc.__class__.__name__,
            )
            raise ProviderTemporaryError(
                "Falha temporária na comunicação com a BigDataCorp."
            ) from exc
        except httpx.HTTPStatusError as exc:
            logger.error(
                "Erro HTTP %s na BigDataCorp Pessoas para CPF %s [%s]",
                exc.response.status_code,
                mask_cpf(clean_cpf),
                correlation_tag(clean_cpf),
            )
            if exc.response.status_code >= 500 or exc.response.status_code == 429:
                raise ProviderTemporaryError(
                    "BigDataCorp indisponível ou rate limit atingido."
                ) from exc
            raise ProviderPermanentError(
                f"Consulta BigDataCorp rejeitada: HTTP {exc.response.status_code}"
            ) from exc
        finally:
            if self._client is None:
                client.close()

        if not isinstance(body, (dict, list)):
            raise ProviderPermanentError("Resposta da BigDataCorp fora do contrato esperado.")

        # Tratamento do retorno BigDataCorp (lista ou dict único)
        empty_root: dict[str, Any] = {}
        root: dict[str, Any] = (
            body[0]
            if isinstance(body, list) and body and isinstance(body[0], dict)
            else (body if isinstance(body, dict) else empty_root)
        )
        if not root:
            return {
                "encontrado": False,
                "dados_cadastrais": None,
                "telefones": [],
            }

        basic_data = (
            root.get("BasicData") or root.get("basic_data") or root.get("DadosBasicos") or {}
        )
        nome = (
            basic_data.get("Name")
            or basic_data.get("Nome")
            or root.get("Name")
            or root.get("Nome")
            or ""
        )
        data_nasc = basic_data.get("BirthDate") or basic_data.get("DataNascimento") or ""
        idade = basic_data.get("Age") or basic_data.get("Idade")
        nome_mae = basic_data.get("MotherName") or basic_data.get("NomeMae") or ""
        genero = basic_data.get("Gender") or basic_data.get("Genero") or ""
        situacao_cpf = (
            basic_data.get("TaxIdStatus")
            or basic_data.get("TaxIdFiscalStatus")
            or basic_data.get("SituacaoCadastral")
            or "DESCONHECIDA"
        )

        # Filtro de Perda: Óbito
        is_deceased = _optional_bool(
            basic_data.get("IsDeceased"),
            basic_data.get("is_deceased"),
            root.get("IsDeceased"),
            root.get("is_deceased"),
        )
        death_date = (
            basic_data.get("DeathDate")
            or basic_data.get("death_date")
            or root.get("DeathDate")
            or root.get("death_date")
            or None
        )

        phones_data = (
            root.get("PhonesExtended")
            or root.get("Phones")
            or root.get("phones")
            or root.get("Telefones")
            or []
        )

        from leadstream.intelligence.consignado import get_inss_species_info
        from leadstream.validation.phone_check import get_phone_operator_hint

        telefones: list[dict[str, Any]] = []
        if isinstance(phones_data, list):
            for p in phones_data:
                if not isinstance(p, dict):
                    continue
                ddd = str(p.get("AreaCode") or p.get("DDD") or p.get("ddd") or "")
                numero = str(p.get("Number") or p.get("Numero") or p.get("phone") or "")
                clean_num = only_digits(numero)
                is_celular = bool(
                    p.get("IsMobile")
                    or p.get("is_mobile")
                    or (len(clean_num) == 9 and clean_num.startswith("9"))
                )
                score = float(p.get("Score") or p.get("ranking_score") or p.get("Priority") or 0.0)
                recency = str(p.get("Recency") or p.get("ActivityIndicator") or "")
                operadora = str(
                    p.get("Carrier")
                    or p.get("carrier")
                    or p.get("Operadora")
                    or get_phone_operator_hint(ddd, clean_num)
                )

                if clean_num:
                    telefones.append(
                        {
                            "ddd": ddd,
                            "numero": clean_num,
                            "is_celular": is_celular,
                            "operadora": operadora,
                            "score": score,
                            "recencia": recency,
                        }
                    )

        # Ordenar celulares primeiro com maior score
        telefones.sort(key=lambda t: (1 if t["is_celular"] else 0, t["score"]), reverse=True)

        # Benefícios Previdenciários (INSS)
        benefits_raw = (
            root.get("SocialBenefits")
            or root.get("social_benefits")
            or root.get("InssBenefits")
            or root.get("inss_benefits")
            or root.get("BeneficiosSociais")
            or root.get("Benefits")
            or []
        )
        beneficios_inss: list[dict[str, Any]] = []
        if isinstance(benefits_raw, list):
            for b in benefits_raw:
                if not isinstance(b, dict):
                    continue
                nb = str(
                    b.get("BenefitNumber")
                    or b.get("benefit_number")
                    or b.get("NumeroBeneficio")
                    or b.get("NB")
                    or ""
                )
                cod_esp = str(
                    b.get("BenefitType")
                    or b.get("benefit_type")
                    or b.get("SpeciesCode")
                    or b.get("CodigoEspecie")
                    or ""
                )
                desc_esp = str(
                    b.get("BenefitDescription")
                    or b.get("benefit_description")
                    or b.get("DescricaoEspecie")
                    or ""
                )
                status_ben = str(
                    b.get("Status") or b.get("BenefitStatus") or "DESCONHECIDO"
                ).upper()

                try:
                    val_ben = float(
                        b.get("Value") or b.get("BenefitValue") or b.get("Valor") or 0.0
                    )
                except (ValueError, TypeError):
                    val_ben = 0.0

                start_date = str(
                    b.get("StartDate") or b.get("ConcessionDate") or b.get("DataInicio") or ""
                )
                loan_blocked = _optional_bool(
                    b.get("IsBlockedForLoans"),
                    b.get("BloqueadoEmprestimo"),
                )

                species_info = get_inss_species_info(cod_esp)
                beneficios_inss.append(
                    {
                        "numero_beneficio": nb,
                        "especie_codigo": cod_esp or species_info["codigo"],
                        "especie_descricao": desc_esp or species_info["descricao"],
                        "categoria": species_info["categoria"],
                        "elegivel_consignado": species_info["elegivel"]
                        and loan_blocked is False
                        and status_ben == "ATIVO",
                        "valor_beneficio": val_ben,
                        "status": status_ben,
                        "data_concessao": start_date[:10] if start_date else None,
                        "bloqueado_para_emprestimo": loan_blocked,
                        "alerta": species_info["alerta"],
                    }
                )

        # Vínculos Empregatícios e SIAPE
        work_raw = (
            root.get("EmploymentRelationships")
            or root.get("employment_relationships")
            or root.get("WorkRecords")
            or root.get("work_records")
            or root.get("Vinculos")
            or root.get("VinculosEmpregaticios")
            or []
        )
        vinculos_empregaticios: list[dict[str, Any]] = []
        if isinstance(work_raw, list):
            for v in work_raw:
                if not isinstance(v, dict):
                    continue
                emp_name = str(
                    v.get("EmployerName") or v.get("Employer") or v.get("RazaoSocial") or ""
                )
                cnpj_emp = only_digits(str(v.get("EmployerTaxId") or v.get("Cnpj") or ""))
                tipo_vinc = str(v.get("RelationshipType") or v.get("TipoVinculo") or "CLT").upper()
                orgao = str(v.get("Agency") or v.get("Ministerio") or v.get("Orgao") or "")
                matr = str(v.get("RegistrationNumber") or v.get("Matricula") or "")
                cargo = str(v.get("JobTitle") or v.get("Cargo") or "")
                uf = str(v.get("State") or v.get("UF") or "")
                is_active = _optional_bool(
                    v.get("IsActive"),
                    v.get("Active"),
                    v.get("Ativo"),
                )

                try:
                    sal = float(v.get("Salary") or v.get("Salario") or 0.0)
                except (ValueError, TypeError):
                    sal = 0.0

                is_public_servant = (
                    "SERVIDOR" in tipo_vinc
                    or "ESTATUTARIO" in tipo_vinc
                    or "PUBLICO" in tipo_vinc
                    or "SIAPE" in tipo_vinc
                    or "MINISTERIO" in emp_name.upper()
                    or "PREFEITURA" in emp_name.upper()
                    or "GOVERNO" in emp_name.upper()
                    or "TRIBUNAL" in emp_name.upper()
                )

                vinculos_empregaticios.append(
                    {
                        "empregador": emp_name,
                        "cnpj_empregador": cnpj_emp,
                        "tipo_vinculo": tipo_vinc,
                        "orgao_siape": orgao,
                        "matricula": matr,
                        "cargo": cargo,
                        "salario": sal,
                        "uf": uf,
                        "ativo": is_active,
                        "eh_servidor_publico": is_public_servant,
                    }
                )

        # Rendimentos / Incomes
        incomes_raw = root.get("Incomes") or root.get("incomes") or root.get("Rendimentos") or {}
        try:
            renda_est = float(
                incomes_raw.get("EstimatedIncome")
                or incomes_raw.get("RendaEstimada")
                or incomes_raw.get("Income")
                or 0.0
            )
        except (ValueError, TypeError):
            renda_est = 0.0

        faixa_renda = str(
            incomes_raw.get("IncomeBracket")
            or incomes_raw.get("FaixaRenda")
            or incomes_raw.get("Class")
            or ""
        )

        # Não Me Perturbe / Do Not Call
        dnc_raw = (
            root.get("DoNotCall")
            or root.get("do_not_call")
            or root.get("ProconBlocks")
            or root.get("NaoMePerturbe")
            or []
        )
        nmp_consultado = any(
            key in root
            for key in ("DoNotCall", "do_not_call", "ProconBlocks", "NaoMePerturbe")
        )
        bloqueios_nao_perturbe: list[dict[str, Any]] = []
        if isinstance(dnc_raw, list):
            for d in dnc_raw:
                if not isinstance(d, dict):
                    continue
                num_bloq = only_digits(
                    str(d.get("Phone") or d.get("Number") or d.get("phone") or "")
                )
                bloq_active = _optional_bool(d.get("Blocked"), d.get("IsBlocked"))
                entity = str(d.get("Entity") or d.get("entidade") or "ANATEL_FEBRABAN")
                dt_bloq = str(d.get("Date") or d.get("BlockDate") or "")
                if num_bloq:
                    bloqueios_nao_perturbe.append(
                        {
                            "phone": num_bloq,
                            "blocked": bloq_active,
                            "entity": entity,
                            "block_date": dt_bloq[:10] if dt_bloq else None,
                        }
                    )

        return {
            "encontrado": bool(nome or telefones or beneficios_inss or vinculos_empregaticios),
            "dados_cadastrais": {
                "nome": nome,
                "cpf": format_cpf_br(clean_cpf),
                "cpf_digitos": clean_cpf,
                "data_nascimento": str(data_nasc)[:10] if data_nasc else None,
                "idade": idade,
                "nome_mae": nome_mae,
                "genero": genero,
                "situacao_cpf": situacao_cpf,
                "is_deceased": is_deceased,
                "death_date": str(death_date)[:10] if death_date else None,
            },
            "telefones": telefones,
            "beneficios_inss": beneficios_inss,
            "vinculos_empregaticios": vinculos_empregaticios,
            "renda": {
                "renda_estimada": renda_est,
                "faixa_renda": faixa_renda,
            },
            "bloqueios_nao_perturbe": bloqueios_nao_perturbe,
            "nao_me_perturbe_consultado": nmp_consultado,
        }
