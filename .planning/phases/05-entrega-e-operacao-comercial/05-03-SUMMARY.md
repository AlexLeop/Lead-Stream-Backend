---
phase: 05-entrega-e-operacao-comercial
plan: "03"
status: completed
completed_at: "2026-09-10T20:56:00-03:00"
requirements: [EXP-01, EXP-02, EXP-03, CRM-01, CRM-02, CRM-03, CRM-04, COMP-04, OPS-05]
---

# 05-03 — Resumo da Validação Operacional de Ponta a Ponta, Piloto Medido e Runbooks de Produção

## O que foi entregue

1. **Validação Operacional dos 3 Modos Reais de Uso (`tests/test_operational_pilot.py`):**
   - **Jornada 1 (Base Própria do Cliente):**
     - Submissão de CSV contendo CNPJs válidos, duplicados e inválidos.
     - Ingestão, higienização com detecção automática de duplicadas e inválidas e partição em chunks.
     - Processamento pelo worker com instanciação das empresas e decisores.
     - Exportação Comercial de Alta Performance com UTF-8-SIG, delimitador `;`, manifesto JSON com SHA-256 e **Zero Mascaramento** (todos os e-mails e telefones em texto claro).
     - Sincronização via Outbox Transacional para CRM/Webhook com assinatura `X-LeadStream-Signature` (HMAC-SHA256) e verificação estrita de **idempotência** (0 duplicações em re-envios).
   - **Jornada 2 (Extração do Zero via Descoberta):**
     - Busca por critérios (CNAE 6201-5/01 TI, SP, Matriz) e materialização automática em novo lote estruturado pronto para enriquecimento ou exportação.
   - **Jornada 3 (Busca Manual / Pontual de Lead):**
     - Cadastro e consulta pontual de empresa por CNPJ na API REST com validação matemática de dígitos verificadores e vinculação de decisores.
   - **Cockpit do CEO vs. Isolamento B2B:**
     - Endpoint do CEO (`/api/v1/admin/integracoes/metricas/` e `/api/v1/metricas/provedores/`) reportando telemetria agregada, custos acumulados e taxas de sucesso.
     - Proteção contra IDOR comprovada (bloqueio com HTTP 404 em acessos a recursos de outro tenant).

2. **Script Executável do Piloto Operacional (`scripts/validate_e2e_pilot.py`):**
   - Validador Python autônomo e resiliente executável no ambiente (Windows/Linux) com saída formatada no terminal, reportando métricas, contadores de registros, bytes gerados e tempos de resposta reais em runtime.

3. **Runbook Operacional de Produção (`deploy/runbook_operacional.md`):**
   - Procedimentos detalhados e testáveis para:
     - **Backup e Restauração do PostgreSQL:** Scripts de dump com compressão gzip, checksum SHA-256 e roteiro de drill de teste em container isolado.
     - **Recuperação de Lotes Interrompidos (`recover_stalled_work`):** Como o sistema detecta chunks com lease expirado e retoma o lote sem duplicação de entidades ou cobranças.
     - **Gestão e Drenagem da Dead Letter Queue (DLQ):** Consultas SQL/API e comandos de reprocessamento em massa após resolução de falhas externas de CRM.
     - **Rotação de Credenciais sem Downtime:** Provedores de enriquecimento, segredos de Webhook HMAC e segredo de hash com tolerância a chaves anteriores (`DATA_HASH_PREVIOUS_KEYS`).
     - **Procedimento de Rollback:** Reversão segura de tags de imagens no EasyPanel.

4. **Conformidade Estrita nos 5 Gates de Qualidade (`scripts/quality.ps1`):**
   - **Ruff:** 0 erros de lint ou formatação.
   - **Mypy:** 100% de conformidade com tipagem estrita nos 111 arquivos fonte.
   - **Migrations:** Zero migrações pendentes.
   - **Deploy Check:** Zero warnings em `manage.py check --deploy`.
   - **Pytest:** **84 testes executados e aprovados** com 0 falhas.
