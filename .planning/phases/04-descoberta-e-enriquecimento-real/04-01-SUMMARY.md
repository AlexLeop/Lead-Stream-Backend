---
phase: 04-descoberta-e-enriquecimento-real
plan: "01"
subsystem: providers
tags: [django, celery, redis, circuit-breaker, billing, provenance]
requires:
  - phase: 03-lotes-com-valor-mensuravel
    provides: lotes duráveis, ledger faturável e orçamento por bloco
provides:
  - contrato tipado único para provedores reais e fixtures
  - políticas por tenant com orçamento, quota e circuit breaker
  - execução idempotente com chamadas, métricas, evidências e custo persistidos
affects: [04-02, 04-03, observability, production-acceptance]
tech-stack:
  added: [google-cloud-bigquery]
  patterns: [provider-adapter, durable-provider-call, evidence-before-canonicalization]
key-files:
  created:
    - src/leadstream/providers/contracts.py
    - src/leadstream/providers/executor.py
    - src/leadstream/providers/resilience.py
    - src/leadstream/providers/persistence.py
  modified:
    - src/leadstream/billing/models.py
    - src/leadstream/billing/services.py
    - src/config/settings/base.py
key-decisions:
  - "Credenciais permanecem somente no ambiente e nunca em configuração persistida de ProviderPolicy."
  - "Resultados externos geram observações e evidências antes de qualquer decisão canônica ou cobrança."
patterns-established:
  - "Gate before call: orçamento, rate limit e estado do circuito são verificados antes da rede."
  - "External enums are normalized defensively before entering canonical entities."
requirements-completed: [PROV-01, PROV-06, PROV-07, OPS-02]
duration: 18min
completed: 2026-09-10
---

# Phase 4 Plan 1: SDK interno e resiliência Summary

**SDK interno de provedores com contratos tipados, execução idempotente, circuit breaker distribuído, orçamento e proveniência auditável antes da canonização**

## Performance

- **Duration:** 18 min
- **Started:** 2026-09-10T11:52:00-03:00
- **Completed:** 2026-09-10T12:10:00-03:00
- **Tasks:** 4
- **Files modified:** 39

## Accomplishments

- Criado contrato comum para observações, pessoas, contatos, perfis e resultados de provedores.
- Implementados rate limit por cache compartilhado, orçamento diário/por lote e circuit breaker persistente.
- Persistidas chamadas, latência, custo, evidências e entregas faturáveis de forma idempotente.
- Adicionada normalização defensiva de cargos externos em enums canônicos válidos.

## Task Commits

1. **SDK, resiliência, persistência e fixtures de provedores** - `649a5c2` (feat)

## Files Created/Modified

- `src/leadstream/providers/contracts.py` - Tipos de entrada e saída comuns.
- `src/leadstream/providers/resilience.py` - Quota, orçamento e circuit breaker.
- `src/leadstream/providers/executor.py` - Ciclo idempotente de execução e contabilização.
- `src/leadstream/providers/persistence.py` - Proveniência, entidades e cobrança seletiva.
- `src/leadstream/billing/models.py` - Métricas e blocos entregues por chamada.

## Decisions Made

- Dados externos nunca são promovidos diretamente a fato canônico.
- O primeiro resultado suficiente interrompe chamadas posteriores por bloco.
- Configuração operacional pode ser persistida; segredos permanecem exclusivamente no runtime.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Estado inicial de chamada aceitava lista vazia**
- **Found during:** validação automatizada do executor
- **Issue:** `full_clean()` rejeitava uma chamada antes de o provedor entregar qualquer bloco.
- **Fix:** o campo JSON passou a aceitar vazio no estado `REQUESTED`.
- **Verification:** 6 testes focados de provedores passaram.
- **Committed in:** `649a5c2`

**2. [Rule 1 - Bug] Cargos humanos eram gravados diretamente em enums internos**
- **Found during:** persistência de decisor em fixture
- **Issue:** valores como “Administrador” causavam erro de validação.
- **Fix:** mapeamento defensivo, sem acentos e bilíngue para qualificação e senioridade.
- **Verification:** suíte focada e `makemigrations --check` passaram.
- **Committed in:** `649a5c2`

**Total deviations:** 2 auto-fixed (1 missing critical, 1 bug). **Impact:** correções necessárias para permitir chamadas reais sem enfraquecer o contrato canônico.

## Issues Encountered

- O utilitário `gsd-sdk` não está no PATH desta instalação; os artefatos de acompanhamento foram atualizados diretamente, preservando o mesmo contrato.

## User Setup Required

Nenhuma credencial é necessária para executar fixtures e testes. Provedores reais só ficam ativos quando suas variáveis de ambiente forem configuradas.

## Next Phase Readiness

- A base está pronta para receber a descoberta paginada e a materialização em lote.
- Os adaptadores iniciais existem, mas descoberta persistente e execução Apify assíncrona ainda serão concluídas nos planos seguintes.

## Self-Check: PASSED

- `ruff check`: passou.
- `pytest tests/test_providers.py`: 6 passaram.
- `manage.py check`: passou.
- `makemigrations --check --dry-run`: nenhuma alteração pendente.

---
*Phase: 04-descoberta-e-enriquecimento-real*
*Completed: 2026-09-10*
