---
phase: 04-descoberta-e-enriquecimento-real
plan: "03"
subsystem: providers
tags: [apify, generic-adapters, cascade, billing, lgpd, provenance]
requires:
  - phase: 04-01
    provides: sdk interno, circuit breaker, ledger faturável e executor
  - phase: 04-02
    provides: descoberta assíncrona BigQuery e materialização em lote
provides:
  - actor Apify assíncrono com polling, reconciliação de run, dataset paginado e taxa FX
  - adaptadores genéricos configuráveis Open Enrich e Premium para fallback
  - cascata de enriquecimento orquestrada por blocos faltantes, prioridade e orçamento
  - persistência estrita de decisores societários/comerciais sem promoção indevida de inferências
affects: [06-endurecimento-seguranca-carga, batches, billing]
tech-stack:
  added: []
  patterns: [async-provider-run, durable-execution-token, strict-decision-maker-qualification]
key-files:
  created:
    - src/leadstream/billing/migrations/0004_providercall_execution_token_and_more.py
  modified:
    - src/leadstream/providers/adapters/apify.py
    - src/leadstream/providers/adapters/generic.py
    - src/leadstream/providers/persistence.py
    - src/leadstream/providers/orchestrator.py
    - src/leadstream/providers/pipeline.py
    - src/leadstream/billing/models.py
    - src/leadstream/billing/services.py
    - src/config/settings/base.py
    - tests/test_providers.py
key-decisions:
  - "Apify executa de forma assíncrona com token durável; se o worker reiniciar ou pausar, a consulta ao run_id é retomada sem disparar nova execução paga."
  - "Qualificações societárias e administrativas canônicas (ex: Administrador, Sócio) e papéis de compra confirmados qualificam para DECISION_MAKER; papéis inferidos permanecem não faturáveis como decisão canônica."
  - "A taxa de câmbio USD -> BRL e o timeout de polling do Apify são parametrizados em settings e arredondados para cima (ROUND_CEILING) para contabilidade de custo real."
requirements-completed: [PROV-04, PROV-05, PROV-07, OPS-02]
duration: 25min
completed: 2026-09-10
---

# Phase 4 Plan 3: Apify, Fallbacks e Cascata Summary

**Actor Apify assíncrono com polling durável, adaptadores genéricos de enriquecimento configuráveis, orquestração de cascata por blocos faltantes e persistência estrita com proveniência.**

## Performance

- **Duração:** 25 min
- **Status:** Concluído com 100% de gates aprovados.
- **Testes:** 67 testes passando, 2 ignorados intencionalmente, 0 falhas.

## Accomplishments

- **Apify Assíncrono com Reconciliação:** Suporte completo à submissão assíncrona (`waitForFinish=0`), polling resiliente com `ProviderPending`, paginação defensiva de datasets (`APIFY_DATASET_PAGE_SIZE`) e conversão de custo USD para centavos de Real (`APIFY_USD_RATE_CENTS`).
- **Adaptadores Genéricos:** Implementado `GenericPeopleEnrichmentAdapter` em `generic.py` atendendo aos fallbacks `open-enrich` e `premium-enrich` com autenticação bearer e extração de candidatos a pessoas e contatos.
- **Cascata e Orquestração:** Orquestração de enriquecimento por lote e chunk (`start_batch_enrichment`, `run_enrichment_cascade`), interrompendo chamadas conforme blocos solicitados são entregues com qualidade e sob orçamento.
- **Persistência Estrita e Evidência:** Regras para distinguir papéis comprovados de inferências não promovidas, geração da migration `0004_providercall_execution_token_and_more.py` e deduplicação estrita de eventos faturáveis por bloco e item.
- **Qualidade e Estabilidade:** 100% de aprovação nos gates Ruff, Mypy estrito, Migrations pendentes, Configuração de produção e Testes.
