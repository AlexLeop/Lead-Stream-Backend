from __future__ import annotations

from leadstream.intelligence.cnae import format_cnae, lookup_cnae, parse_cnaes_list
from leadstream.intelligence.natureza_juridica import (
    format_natureza_juridica,
    lookup_natureza_juridica,
)


def test_cnae_formatting():
    assert format_cnae("8599603") == "85.99-6-03"
    assert format_cnae("6202300") == "62.02-3-00"
    assert format_cnae("62.02-3-00") == "62.02-3-00"
    assert format_cnae("") == ""


def test_cnae_lookup():
    info = lookup_cnae("8599603")
    assert info["codigo"] == "85.99-6-03"
    assert "Treinamento" in info["descricao"]
    assert info["setor"] in ("Educação / Treinamento", "Serviços")
    assert info["grau_risco_trabalho"] in (1, 2, 3, 4)

    tech = lookup_cnae("6202300")
    assert tech["codigo"] == "62.02-3-00"
    assert "computador" in tech["descricao"].lower()
    assert tech["setor"] == "Tecnologia da Informação"
    assert tech["grau_risco_trabalho"] == 1


def test_parse_cnaes_list():
    raw = "9511800,4789099,4773300"
    results = parse_cnaes_list(raw)
    assert len(results) == 3
    assert results[0]["codigo"] == "95.11-8-00"
    assert "descricao" in results[0]


def test_natureza_juridica_lookup():
    assert format_natureza_juridica("2135") == "213-5"
    assert format_natureza_juridica("2062") == "206-2"

    nat_mei = lookup_natureza_juridica("2135")
    assert nat_mei["codigo"] == "213-5"
    assert "Empresário" in nat_mei["descricao"]

    nat_ltda = lookup_natureza_juridica("206-2")
    assert nat_ltda["codigo"] == "206-2"
    assert "Sociedade Empresária Limitada" in nat_ltda["descricao"]
