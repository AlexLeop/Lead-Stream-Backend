from __future__ import annotations

import re
from typing import Any

# Specific high-frequency CNAE details
KNOWN_CNAES: dict[str, dict[str, Any]] = {
    "8599603": {
        "descricao": "Treinamento em desenvolvimento profissional e gerencial",
        "setor": "Educação / Treinamento",
        "grau_risco_trabalho": 1,
    },
    "6202300": {
        "descricao": "Desenvolvimento e licenciamento de programas de computador customizáveis",
        "setor": "Tecnologia da Informação",
        "grau_risco_trabalho": 1,
    },
    "6201501": {
        "descricao": "Desenvolvimento de programas de computador sob encomenda",
        "setor": "Tecnologia da Informação",
        "grau_risco_trabalho": 1,
    },
    "6203100": {
        "descricao": "Desenvolvimento e licenciamento de programas de computador não-customizáveis",
        "setor": "Tecnologia da Informação",
        "grau_risco_trabalho": 1,
    },
    "6204000": {
        "descricao": "Consultoria em tecnologia da informação",
        "setor": "Tecnologia da Informação",
        "grau_risco_trabalho": 1,
    },
    "6209100": {
        "descricao": "Suporte técnico, manutenção e outros serviços em tecnologia da informação",
        "setor": "Tecnologia da Informação",
        "grau_risco_trabalho": 1,
    },
    "6311900": {
        "descricao": "Tratamento de dados, provedores de serviços de aplicação e hospedagem na internet",
        "setor": "Tecnologia da Informação",
        "grau_risco_trabalho": 1,
    },
    "6319400": {
        "descricao": "Portais, provedores de conteúdo e outros serviços de informação na internet",
        "setor": "Tecnologia da Informação",
        "grau_risco_trabalho": 1,
    },
    "9511800": {
        "descricao": "Reparação e manutenção de computadores e de equipamentos periféricos",
        "setor": "Tecnologia da Informação",
        "grau_risco_trabalho": 2,
    },
    "4789099": {
        "descricao": "Comércio varejista de outros produtos não especificados anteriormente",
        "setor": "Comércio",
        "grau_risco_trabalho": 2,
    },
    "4773300": {
        "descricao": "Comércio varejista de artigos médicos e ortopédicos",
        "setor": "Comércio",
        "grau_risco_trabalho": 2,
    },
    "4772500": {
        "descricao": "Comércio varejista de cosméticos, produtos de perfumaria e de higiene pessoal",
        "setor": "Comércio",
        "grau_risco_trabalho": 2,
    },
    "4781400": {
        "descricao": "Comércio varejista de artigos do vestuário e acessórios",
        "setor": "Comércio",
        "grau_risco_trabalho": 2,
    },
    "4751201": {
        "descricao": "Comércio varejista especializado de equipamentos e suprimentos de informática",
        "setor": "Comércio",
        "grau_risco_trabalho": 2,
    },
    "4755503": {
        "descricao": "Comercio varejista de artigos de cama, mesa e banho",
        "setor": "Comércio",
        "grau_risco_trabalho": 2,
    },
    "4763602": {
        "descricao": "Comércio varejista de artigos esportivos",
        "setor": "Comércio",
        "grau_risco_trabalho": 2,
    },
    "4763601": {
        "descricao": "Comércio varejista de brinquedos e artigos recreativos",
        "setor": "Comércio",
        "grau_risco_trabalho": 2,
    },
    "4754703": {
        "descricao": "Comércio varejista de artigos de iluminação",
        "setor": "Comércio",
        "grau_risco_trabalho": 2,
    },
    "4789008": {
        "descricao": "Comércio varejista de artigos fotográficos e para filmagem",
        "setor": "Comércio",
        "grau_risco_trabalho": 2,
    },
    "4789007": {
        "descricao": "Comércio varejista de equipamentos para escritório",
        "setor": "Comércio",
        "grau_risco_trabalho": 2,
    },
    "4782201": {
        "descricao": "Comércio varejista de calçados",
        "setor": "Comércio",
        "grau_risco_trabalho": 2,
    },
    "4783102": {
        "descricao": "Comércio varejista de artigos de relojoaria",
        "setor": "Comércio",
        "grau_risco_trabalho": 2,
    },
    "4783101": {
        "descricao": "Comércio varejista de artigos de joalheria",
        "setor": "Comércio",
        "grau_risco_trabalho": 2,
    },
    "7311400": {
        "descricao": "Agências de publicidade",
        "setor": "Publicidade e Marketing",
        "grau_risco_trabalho": 1,
    },
    "7319002": {
        "descricao": "Promoção de vendas",
        "setor": "Publicidade e Marketing",
        "grau_risco_trabalho": 1,
    },
    "7020400": {
        "descricao": "Atividades de consultoria em gestão empresarial",
        "setor": "Serviços Profissionais e Técnicos",
        "grau_risco_trabalho": 1,
    },
}

# Sector and risk by CNAE 2-digit division
DIVISION_RULES: dict[int, tuple[str, int, str]] = {
    1: ("Agropecuária", 3, "Agricultura, Pecuária e Serviços Relacionados"),
    2: ("Agropecuária", 3, "Produção Florestal"),
    3: ("Agropecuária", 3, "Pesca e Aquicultura"),
    5: ("Indústria Extrativa", 4, "Extração de Carvão Mineral"),
    6: ("Indústria Extrativa", 4, "Extração de Petróleo e Gás Natural"),
    7: ("Indústria Extrativa", 4, "Extração de Minerais Metálicos"),
    8: ("Indústria Extrativa", 4, "Extração de Minerais Não-Metálicos"),
    9: ("Indústria Extrativa", 4, "Atividades de Apoio à Extração de Minerais"),
    10: ("Indústria de Transformação", 3, "Fabricação de Produtos Alimentícios"),
    11: ("Indústria de Transformação", 3, "Fabricação de Bebidas"),
    12: ("Indústria de Transformação", 3, "Fabricação de Produtos do Fumo"),
    13: ("Indústria de Transformação", 3, "Fabricação de Produtos Têxteis"),
    14: ("Indústria de Transformação", 2, "Confecção de Artigos do Vestuário"),
    15: ("Indústria de Transformação", 3, "Preparação de Couros e Fabricação de Calçados"),
    16: ("Indústria de Transformação", 3, "Fabricação de Produtos de Madeira"),
    17: ("Indústria de Transformação", 3, "Fabricação de Celulose e Papel"),
    18: ("Indústria de Transformação", 3, "Impressão e Reprodução de Gravações"),
    19: ("Indústria de Transformação", 3, "Fabricação de Coque e Derivados do Petróleo"),
    20: ("Indústria de Transformação", 3, "Fabricação de Produtos Químicos"),
    21: ("Indústria de Transformação", 3, "Fabricação de Produtos Farmoquímicos e Farmacêuticos"),
    22: ("Indústria de Transformação", 3, "Fabricação de Produtos de Borracha e Plástico"),
    23: ("Indústria de Transformação", 4, "Fabricação de Produtos de Minerais Não-Metálicos"),
    24: ("Indústria de Transformação", 4, "Metalurgia"),
    25: ("Indústria de Transformação", 3, "Fabricação de Produtos de Metal"),
    26: ("Indústria de Transformação", 3, "Fabricação de Equipamentos de Informática e Eletrônicos"),
    27: ("Indústria de Transformação", 3, "Fabricação de Máquinas e Materiais Elétricos"),
    28: ("Indústria de Transformação", 3, "Fabricação de Máquinas e Equipamentos"),
    29: ("Indústria de Transformação", 3, "Fabricação de Veículos Automotores"),
    30: ("Indústria de Transformação", 3, "Fabricação de Outros Equipamentos de Transporte"),
    31: ("Indústria de Transformação", 3, "Fabricação de Móveis"),
    32: ("Indústria de Transformação", 3, "Fabricação de Produtos Diversos"),
    33: ("Indústria de Transformação", 3, "Manutenção e Reparação de Máquinas e Equipamentos"),
    35: ("Serviços de Utilidade Pública", 3, "Eletricidade, Gás e Outras Utilidades"),
    36: ("Serviços de Utilidade Pública", 3, "Captação, Tratamento e Distribuição de Água"),
    37: ("Serviços de Utilidade Pública", 3, "Esgoto e Atividades Relacionadas"),
    38: ("Serviços de Utilidade Pública", 3, "Coleta, Tratamento e Disposição de Resíduos"),
    41: ("Construção Civil", 4, "Construção de Edifícios"),
    42: ("Construção Civil", 4, "Obras de Infraestrutura"),
    43: ("Construção Civil", 4, "Serviços Especializados para Construção"),
    45: ("Comércio", 2, "Comércio e Reparação de Veículos Automotores"),
    46: ("Comércio", 2, "Comércio Atacadista"),
    47: ("Comércio", 2, "Comércio Varejista"),
    49: ("Transporte e Logística", 3, "Transporte Terrestre"),
    50: ("Transporte e Logística", 3, "Transporte Aquaviário"),
    51: ("Transporte e Logística", 3, "Transporte Aéreo"),
    52: ("Transporte e Logística", 3, "Armazenamento e Atividades Auxiliares aos Transportes"),
    53: ("Transporte e Logística", 2, "Correio e Outras Atividades de Entrega"),
    55: ("Hotelaria e Alimentação", 2, "Alojamento"),
    56: ("Hotelaria e Alimentação", 2, "Alimentação"),
    58: ("Tecnologia da Informação", 1, "Edição e Edição Integrada à Impressão"),
    59: ("Tecnologia da Informação", 2, "Atividades Cinematográficas e Produção de Vídeos"),
    60: ("Tecnologia da Informação", 1, "Atividades de Rádio e de Televisão"),
    61: ("Tecnologia da Informação", 2, "Telecomunicações"),
    62: ("Tecnologia da Informação", 1, "Atividades dos Serviços de Tecnologia da Informação"),
    63: ("Tecnologia da Informação", 1, "Atividades de Prestação de Serviços de Informação"),
    64: ("Financeiro e Seguros", 1, "Atividades de Serviços Financeiros"),
    65: ("Financeiro e Seguros", 1, "Seguros, Resseguros e Previdência Complementar"),
    66: ("Financeiro e Seguros", 1, "Atividades Auxiliares dos Serviços Financeiros"),
    68: ("Imobiliário", 1, "Atividades Imobiliárias"),
    69: ("Serviços Profissionais e Técnicos", 1, "Atividades Jurídicas, de Contabilidade e de Auditoria"),
    70: ("Serviços Profissionais e Técnicos", 1, "Atividades de Sedes de Empresas e de Consultoria em Gestão"),
    71: ("Serviços Profissionais e Técnicos", 1, "Serviços de Arquitetura e Engenharia"),
    72: ("Serviços Profissionais e Técnicos", 1, "Pesquisa e Desenvolvimento Científico"),
    73: ("Publicidade e Marketing", 1, "Publicidade e Pesquisa de Mercado"),
    74: ("Serviços Profissionais e Técnicos", 1, "Outras Atividades Profissionais, Científicas e Técnicas"),
    75: ("Serviços Veterinários", 2, "Atividades Veterinárias"),
    77: ("Serviços Administrativos", 2, "Aluguéis Não-Imobiliários e Gestão de Ativos"),
    78: ("Serviços Administrativos", 2, "Seleção, Agenciamento e Locação de Mão-de-Obra"),
    79: ("Serviços Administrativos", 1, "Agências de Viagens e Operadores Turísticos"),
    80: ("Serviços Administrativos", 3, "Atividades de Vigilância, Segurança e Investigação"),
    81: ("Serviços Administrativos", 3, "Serviços para Edifícios e Atividades Paisagísticas"),
    82: ("Serviços Administrativos", 1, "Serviços de Escritório e Apoio Administrativo"),
    84: ("Administração Pública", 1, "Administração Pública, Defesa e Seguridade Social"),
    85: ("Educação / Treinamento", 2, "Educação"),
    86: ("Saúde e Serviços Sociais", 3, "Atividades de Atenção à Saúde Humana"),
    87: ("Saúde e Serviços Sociais", 3, "Atividades de Atenção à Saúde Humana Integradas com Assistência Social"),
    88: ("Saúde e Serviços Sociais", 2, "Serviços de Assistência Social sem Alojamento"),
    90: ("Cultura, Esporte e Lazer", 2, "Atividades Artísticas, Criativas e de Espetáculos"),
    91: ("Cultura, Esporte e Lazer", 2, "Atividades Ligadas ao Patrimônio Cultural e Ambiental"),
    92: ("Cultura, Esporte e Lazer", 2, "Atividades de Exploração de Jogos de Azar e Apostas"),
    93: ("Cultura, Esporte e Lazer", 2, "Atividades Esportivas e de Recreação e Lazer"),
    94: ("Outros Serviços", 2, "Atividades de Organizações Associativas"),
    95: ("Outros Serviços", 2, "Reparação e Manutenção de Equipamentos de Informática e Comunicação"),
    96: ("Outros Serviços", 2, "Outras Atividades de Serviços Pessoais"),
}


def clean_digits(value: str) -> str:
    return "".join(character for character in value if character.isdigit())


def format_cnae(code: str) -> str:
    digits = clean_digits(code)
    if not digits:
        return ""
    if len(digits) < 7:
        digits = digits.zfill(7)
    return f"{digits[:2]}.{digits[2:4]}-{digits[4]}-{digits[5:7]}"


def lookup_cnae(code: str) -> dict[str, Any]:
    digits = clean_digits(code)
    if len(digits) < 7:
        digits = digits.zfill(7)
    formatted = format_cnae(digits)
    if digits in KNOWN_CNAES:
        match = KNOWN_CNAES[digits]
        return {
            "codigo": formatted,
            "descricao": match["descricao"],
            "setor": match["setor"],
            "grau_risco_trabalho": match["grau_risco_trabalho"],
        }
    division = int(digits[:2]) if len(digits) >= 2 and digits[:2].isdigit() else 0
    division_info = DIVISION_RULES.get(division, ("Outros Serviços", 2, "Atividades Econômicas Diversas"))
    return {
        "codigo": formatted,
        "descricao": division_info[2],
        "setor": division_info[0],
        "grau_risco_trabalho": division_info[1],
    }


def parse_cnaes_list(raw: str | list[str] | None) -> list[dict[str, Any]]:
    if not raw:
        return []
    items: list[str] = []
    if isinstance(raw, list):
        items = raw
    elif isinstance(raw, str):
        items = [part.strip() for part in raw.split(",") if part.strip()]
    results: list[dict[str, Any]] = []
    for item in items:
        info = lookup_cnae(item)
        results.append({"codigo": info["codigo"], "descricao": info["descricao"]})
    return results
