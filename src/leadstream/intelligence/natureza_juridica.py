from __future__ import annotations

from typing import Any

KNOWN_NATUREZAS: dict[str, str] = {
    # 1xx - Administração Pública
    "1015": "Órgão Público do Poder Executivo Federal",
    "1023": "Órgão Público do Poder Executivo Estadual ou do Distrito Federal",
    "1031": "Órgão Público do Poder Executivo Municipal",
    "1040": "Órgão Público do Poder Legislativo Federal",
    "1058": "Órgão Público do Poder Legislativo Estadual ou do Distrito Federal",
    "1066": "Órgão Público do Poder Legislativo Municipal",
    "1074": "Órgão Público do Poder Judiciário Federal",
    "1082": "Órgão Público do Poder Judiciário Estadual",
    "1104": "Autarquia Federal",
    "1112": "Autarquia Estadual ou do Distrito Federal",
    "1120": "Autarquia Municipal",
    "1139": "Fundação Pública de Direito Público Federal",
    "1147": "Fundação Pública de Direito Público Estadual ou do Distrito Federal",
    "1155": "Fundação Pública de Direito Público Municipal",
    "1163": "Órgão Público Autônomo Federal",
    "1171": "Órgão Público Autônomo Estadual ou do Distrito Federal",
    "1180": "Órgão Público Autônomo Municipal",
    # 2xx - Entidades Empresariais
    "2011": "Empresa Pública",
    "2038": "Sociedade de Economia Mista",
    "2046": "Sociedade Anônima Aberta",
    "2054": "Sociedade Anônima Fechada",
    "2062": "Sociedade Empresária Limitada",
    "2070": "Sociedade Empresária em Nome Coletivo",
    "2089": "Sociedade Empresária em Comandita Simples",
    "2097": "Sociedade Empresária em Comandita por Ações",
    "2127": "Sociedade em Conta de Participação",
    "2135": "Empresário (Individual)",
    "2143": "Cooperativa",
    "2151": "Consórcio de Sociedades",
    "2160": "Grupo de Sociedades",
    "2178": "Estabelecimento, no Brasil, de Sociedade Estrangeira",
    "2194": "Estabelecimento, no Brasil, de Empresa Binacional",
    "2216": "Empresa Domiciliada no Exterior",
    "2224": "Clube/Fundo de Investimento",
    "2232": "Sociedade Simples Pura",
    "2240": "Sociedade Simples Limitada",
    "2259": "Sociedade Simples em Nome Coletivo",
    "2267": "Sociedade Simples em Comandita Simples",
    "2275": "Empresa Binacional",
    "2283": "Consórcio de Empregadores",
    "2291": "Consórcio Simples",
    "2305": "Empresa Individual de Responsabilidade Limitada (EIRELI)",
    "2313": "Empresa Individual Imobiliária",
    "2321": "Sociedade Unipessoal de Advocacia",
    "2330": "Cooperativas de Consumo",
    # 3xx - Entidades Sem Fins Lucrativos
    "3034": "Serviço Notarial e Registral (Cartório)",
    "3069": "Fundação Privada",
    "3077": "Serviço Social Autônomo",
    "3085": "Condomínio Edilício",
    "3107": "Comissão de Conciliação Prévia",
    "3115": "Entidade de Mediação e Arbitragem",
    "3131": "Entidade Sindical",
    "3204": "Estabelecimento, no Brasil, de Fundação ou Associação Estrangeiras",
    "3212": "Fundação ou Associação Domiciliada no Exterior",
    "3220": "Organização Religiosa",
    "3239": "Comunidade Indígena",
    "3247": "Fundo Privado",
    "3999": "Associação Privada",
    # 4xx - Pessoas Físicas
    "4014": "Empresa Individual Imobiliária",
    "4022": "Segurado Especial",
    "4081": "Contribuinte Individual",
    "4090": "Candidato a Cargo Político Eletivo",
    "4111": "Leiloeiro",
    "4120": "Produtor Rural (Pessoa Física)",
    # 5xx - Organizações Internacionais
    "5010": "Organização Internacional",
    "5029": "Representação Diplomática Estrangeira",
    "5037": "Outras Instituições Extraterritoriais",
}


def clean_digits(value: str) -> str:
    return "".join(character for character in value if character.isdigit())


def format_natureza_juridica(code: str) -> str:
    digits = clean_digits(code)
    if not digits:
        return ""
    if len(digits) < 4:
        digits = digits.zfill(4)
    # Format as ###-# (e.g. 213-5, 206-2)
    return f"{digits[:3]}-{digits[3:]}"


def lookup_natureza_juridica(code: str) -> dict[str, str]:
    digits = clean_digits(code)
    if not digits:
        return {"codigo": "", "descricao": "Não Informada"}

    if len(digits) < 4:
        digits = digits.zfill(4)

    formatted = format_natureza_juridica(digits)

    if digits in KNOWN_NATUREZAS:
        return {"codigo": formatted, "descricao": KNOWN_NATUREZAS[digits]}

    first_digit = digits[0]
    category_fallbacks: dict[str, str] = {
        "1": "Administração Pública",
        "2": "Entidade Empresarial",
        "3": "Entidade Sem Fins Lucrativos",
        "4": "Pessoa Física",
        "5": "Organização Internacional",
    }
    fallback_desc = category_fallbacks.get(first_digit, "Entidade Não Classificada")
    return {"codigo": formatted, "descricao": fallback_desc}
