---
phase: 03-lotes-com-valor-mensuravel
plan: "03"
status: complete
requirements-completed: [BILL-01, BILL-02, BILL-03, BILL-04, BILL-05]
completed: 2026-09-10
---

# 03-03 Summary — Custos e cobrança

- Tabela padrão soma R$ 0,80 por registro quando todos os oito blocos são entregues.
- Chamadas registram custo estimado e confirmado por provedor/bloco.
- Cobrança exige entrega tecnicamente validada ou confirmada e confiança mínima.
- Replay usa chave idempotente por item, bloco, valor e janela de atualização.
- Dashboard financeiro expõe custo, receita, lucro, margem e cobertura.
- Eventos faturáveis são append-only no ORM e por trigger PostgreSQL.

Commit: `05128ff`.
