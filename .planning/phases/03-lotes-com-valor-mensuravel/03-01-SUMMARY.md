---
phase: 03-lotes-com-valor-mensuravel
plan: "01"
status: complete
requirements-completed: [BATCH-01, BATCH-02, BATCH-03, BATCH-04, BATCH-05]
completed: 2026-09-10
---

# 03-01 Summary — Lotes duráveis

- Upload idempotente retorna `202` antes do processamento.
- Lote, itens, chunks, tentativas, lease e checkpoint vivem no PostgreSQL.
- Pausa, retomada e cancelamento preservam efeitos concluídos.
- Beat e comando operacional recuperam ingestões e leases abandonados.
- Replay de chunk não recria empresa nem tentativa concluída.

Commits: `6e09396`, `951cbda`.
