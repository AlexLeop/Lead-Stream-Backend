---
phase: 04-descoberta-e-enriquecimento-real
plan: "02"
status: partial
subsystem: discovery
tags: [bigquery, django, celery]
key-files:
  created:
    - src/leadstream/providers/discovery.py
    - src/leadstream/providers/migrations/0002_discoverysearch_discoveryresult_and_more.py
  modified:
    - src/leadstream/providers/adapters/bigquery.py
requirements-completed: []
completed: null
---

# Plano 04-02 — implementação e validação parcial

Descoberta assíncrona com filtros parametrizados, resultados persistidos, paginação por cursor na API e materialização em lotes. Commit: `3622aa3`.

## Verificação executada

- Provedores e lotes: 12 testes passaram com fixtures, banco SQLite em memória.
- Ruff e mypy: passaram (110 arquivos).
- Migrações: sem diferenças pendentes; verificações Django passaram.
- Cliente google-cloud-bigquery 3.45.0 instalado a partir do lockfile e importado.

## Desvios e trabalho restante

- A configuração do SQL e o esquema real da fonte ainda não foram homologados na conta Google.
- A paginação remota usa OFFSET; depende de ordenação estável e snapshot fixo no SQL configurado.
- Orçamento global de descoberta e proteção contra worker antigo precisam de testes adicionais.
- O adaptador BigDataCorp consulta empresas; a consulta de pessoas ainda depende do contrato contratado e da correlação explícita por empresa.
- Nenhuma chamada paga ou homologação real foi executada. Este resumo NÃO declara o plano ou a fase prontos para produção.

## Self-Check: PARTIAL

Os testes acima confirmam os fluxos implementados. Homologação externa e os pontos descritos permanecem abertos.
