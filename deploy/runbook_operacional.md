# Runbook Operacional de Produção — LeadStream Backend

Este documento estabelece os procedimentos operacionais padrão (SOP) para administração, resiliência, contingência e manutenção contínua do **LeadStream Backend** em ambiente de produção (EasyPanel / VPS).

---

## 1. Topologia e Serviços Monitorados

| Componente | Função | Porta Interna | Verificação de Saúde |
|---|---|---|---|
| `leadstream-api` | Servidor Web REST & OpenAPI | 8000 | `GET /health/ready` |
| `leadstream-worker` | Processamento assíncrono de lotes e outbox | — | Celery inspect ping |
| `PostgreSQL 17+` | Fonte operacional de verdade e outbox transacional | 5432 | `pg_isready` |
| `RabbitMQ 4.x` | Broker durável de mensagens | 5672 (15672 mgmt) | `rabbitmq-diagnostics check_running` |
| `Redis 8.x` | Cache, locks distribuídos e rate limits | 6379 | `redis-cli ping` |
| `Appwrite Storage` | Armazenamento de arquivos de exportação e evidências | 443 (externo) | `GET /health/dependencies` |

---

## 2. Procedimento de Backup e Restauração do PostgreSQL

### 2.1 Política de Continuidade
- **RPO (Recovery Point Objective)**: <= 1 hora (backups incrementais ou dumps horários).
- **RTO (Recovery Time Objective)**: <= 15 minutos para restauração completa em caso de desastre.
- **Retenção**: 7 backups diários, 4 semanais e 12 mensais.

### 2.2 Rotina de Backup Automatizado
Execute via Cron na VPS ou tarefa agendada do EasyPanel:

```bash
#!/usr/bin/env bash
set -euo pipefail

BACKUP_DIR="/var/backups/leadstream/postgres"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_FILE="${BACKUP_DIR}/leadstream_backup_${TIMESTAMP}.sql.gz"

mkdir -p "${BACKUP_DIR}"

echo "Iniciando dump do PostgreSQL LeadStream..."
docker exec leadstream-postgres-1 pg_dump \
    -U "${POSTGRES_USER}" \
    -d "${POSTGRES_DB}" \
    --format=custom \
    --no-owner \
    --no-privileges | gzip -9 > "${BACKUP_FILE}"

# Gera checksum SHA-256 para auditoria de integridade
sha256sum "${BACKUP_FILE}" > "${BACKUP_FILE}.sha256"

echo "Backup concluído com sucesso: ${BACKUP_FILE}"
ls -lh "${BACKUP_FILE}"
```

### 2.3 Procedimento de Teste de Restauração (Drill Periódico)
Para validar que o backup é íntegro sem impactar a base de produção:

1. Suba uma instância isolada temporária de PostgreSQL:
   ```bash
   docker run -d --name pg-restore-drill -e POSTGRES_PASSWORD=drillpass -e POSTGRES_DB=leadstream_drill postgres:17-alpine
   ```
2. Descompacte e restaure o dump:
   ```bash
   gunzip -c /var/backups/leadstream/postgres/leadstream_backup_YYYYMMDD_HHMMSS.sql.gz | \
   docker exec -i pg-restore-drill pg_restore -U postgres -d leadstream_drill --clean --if-exists
   ```
3. Valide a integridade dos dados e contagens essenciais:
   ```bash
   docker exec -i pg-restore-drill psql -U postgres -d leadstream_drill -c "
       SELECT count(*) AS total_tenants FROM leadstream_tenant;
       SELECT count(*) AS total_companies FROM leadstream_company;
       SELECT count(*) AS total_batches FROM leadstream_batch;
       SELECT count(*) AS total_outbox FROM leadstream_crm_outbox_message;
   "
   ```
4. Remova o container de teste:
   ```bash
   docker rm -f pg-restore-drill
   ```

---

## 3. Recuperação de Lotes Interrompidos (`recover_stalled_work`)

Se a VPS reiniciar inesperadamente ou um worker for terminado durante o processamento de um lote de 100.000 registros, o mecanismo de **leases transacionais** impede perda ou duplicação.

### 3.1 Como Funciona a Detecção
- Chunks e tentativas possuem um tempo de locação (`leased_until`).
- Se o worker expirar sem renovar o lease (`now() > leased_until`), o chunk é classificado como órfão/estagnado (*stalled*).

### 3.2 Comando de Recuperação Manual
Execute dentro do container da API ou do worker:

```bash
docker exec -it leadstream-api-1 python manage.py shell -c "
from leadstream.batches.services import recover_stalled_work
requeued = recover_stalled_work()
print(f'Chunks recuperados e reenfileirados com sucesso: {requeued}')
"
```

### 3.3 Garantias de Integridade
- Chunks já marcados como `COMPLETED` são ignorados (*skipped*).
- Mensagens da outbox utilizam chave determinística SHA-256 baseada em `(connection_id, batch_id, item_id, entity_type)`. Mesmo que o chunk seja reprocessado, nenhuma mensagem é duplicada na Outbox e nenhum contato repetido é enviado ao CRM.

---

## 4. Monitoramento e Gestão da Dead Letter Queue (DLQ)

A Outbox Transacional garante entrega confiável com retentativas exponenciais. Se o CRM remoto retornar erros consecutivos (ex.: token expirado, HTTP 401 ou 500) e exceder 5 tentativas, a mensagem é movida para `DEAD_LETTER`.

### 4.1 Consulta de Mensagens em Falha Crítica
Pela API (Cockpit do CEO):
```bash
curl -s -H "Host: api.seu-dominio.com" https://localhost:8000/api/v1/admin/integracoes/metricas/ | jq .
```

Pelo PostgreSQL:
```sql
SELECT id, connection_id, entity_type, retry_count, error_code, error_message, updated_at
FROM leadstream_crm_outbox_message
WHERE status = 'DEAD_LETTER'
ORDER BY updated_at DESC
LIMIT 50;
```

### 4.2 Reprocessamento Seguro de Mensagens da DLQ
Após corrigir a credencial do CRM ou resolver o bloqueio remoto:

```bash
docker exec -it leadstream-api-1 python manage.py shell -c "
from leadstream.integrations.models import CRMOutboxMessage, OutboxStatus
from django.utils import timezone

count = CRMOutboxMessage.objects.filter(status=OutboxStatus.DEAD_LETTER).update(
    status=OutboxStatus.PENDING,
    retry_count=0,
    next_retry_at=timezone.now(),
    error_code='',
    error_message='Reenfileirado manualmente pelo operador',
)
print(f'Total de mensagens da DLQ reenfileiradas: {count}')
"
```

Em seguida, o Celery (`process_crm_outbox_batch`) consome e despacha as mensagens pendentes automaticamente.

---

## 5. Rotação Segura de Credenciais e Segredos

### 5.1 Rotação de Tokens de Provedores Externos
1. Obtenha o novo token no painel do parceiro (ex.: BigDataCorp, Apify).
2. Atualize a variável no cofre do EasyPanel (`BIGDATACORP_ACCESS_TOKEN` ou `APIFY_TOKEN`).
3. Execute restart gracioso do serviço `leadstream-worker`:
   ```bash
   # No EasyPanel: clique em 'Deploy/Restart' no serviço leadstream-worker
   ```
4. Valide a comunicação sem downtime:
   ```bash
   curl -s -H "Host: api.seu-dominio.com" https://localhost:8000/api/v1/provedores/ | jq .
   ```

### 5.2 Rotação de Segredo de Hash e Supressão (`DATA_HASH_KEY`)
O LeadStream suporta rotação com tolerância a chaves anteriores:
1. No cofre do EasyPanel, defina:
   - `DATA_HASH_PREVIOUS_KEYS=<chave_antiga_v1>`
   - `DATA_HASH_KEY=<nova_chave_aleatoria_v2>`
   - `DATA_HASH_KEY_VERSION=v2`
2. Reinicie API e Worker. Novos dados serão hasheados com `v2`, enquanto verificações de supressão continuam reconhecendo assinaturas geradas com `v1`.

### 5.3 Rotação de Segredos de Webhook HMAC
1. Acesse as conexões cadastradas:
   `PATCH /api/v1/integracoes/conexoes/{id}/` com novo `credentials.signing_secret`.
2. O LeadStream assina imediatamente os novos payloads utilizando o segredo atualizado.

---

## 6. Procedimento de Rollback de Versão

Caso um release recente apresente anomalia grave:

1. **Reversão de Imagem**:
   - No EasyPanel, altere a tag da imagem de `leadstream-api` e `leadstream-worker` para o hash de commit estável anterior (ex.: `:abc1234` em vez de `:latest`).
2. **Avaliação de Migrações de Banco**:
   - As migrações do LeadStream seguem o padrão **somente aditivo** (criação de novas tabelas e colunas com `default` ou `null=True`).
   - Não reverta migrações que já receberam dados operacionais, a menos que estritamente necessário.
3. **Verificação Pós-Rollback**:
   ```bash
   curl -s -f http://localhost:8000/health/ready || echo "API não está pronta!"
   curl -s -f http://localhost:8000/health/live || echo "API travada!"
   ```
