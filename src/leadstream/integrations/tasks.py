from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from celery import shared_task
from django.db.models import Q
from django.utils import timezone

from leadstream.batches.models import Batch

from .models import CRMConnection, CRMOutboxMessage, OutboxStatus
from .services import dispatch_outbox_message, enqueue_batch_to_crm

logger = logging.getLogger(__name__)


@shared_task(name="leadstream.integrations.process_crm_outbox_batch")  # type: ignore[untyped-decorator]
def process_crm_outbox_batch(batch_size: int = 50) -> dict[str, int]:
    """Processa um lote de mensagens pendentes na fila de Outbox do CRM."""
    now = timezone.now()
    messages = list(
        CRMOutboxMessage.objects.filter(
            Q(status=OutboxStatus.PENDING)
            | (Q(status=OutboxStatus.FAILED) & Q(next_retry_at__lte=now))
        )
        .select_related("connection")
        .order_by("created_at")[:batch_size]
    )

    success_count = 0
    failure_count = 0

    for msg in messages:
        try:
            ok = dispatch_outbox_message(msg)
            if ok:
                success_count += 1
            else:
                failure_count += 1
        except Exception as exc:
            logger.error(f"Erro inesperado ao despachar mensagem {msg.id}: {exc}", exc_info=True)
            failure_count += 1

    return {
        "processed": len(messages),
        "success": success_count,
        "failed": failure_count,
    }


@shared_task(name="leadstream.integrations.sync_batch_to_crm_task")  # type: ignore[untyped-decorator]
def sync_batch_to_crm_task(
    batch_id: str,
    connection_id: str,
    selected_statuses: list[str] | None = None,
    lead_level: str = "DECISION_MAKER",
) -> dict[str, Any]:
    """Tarefa assíncrona para enfileirar e iniciar o envio de um lote para o CRM."""
    try:
        batch = Batch.objects.get(id=UUID(batch_id))
        connection = CRMConnection.objects.get(id=UUID(connection_id))
    except (Batch.DoesNotExist, CRMConnection.DoesNotExist, ValueError) as exc:
        return {"error": f"Lote ou conexão não encontrados: {exc}", "enqueued": 0}

    enqueued = enqueue_batch_to_crm(
        batch=batch,
        connection=connection,
        selected_statuses=selected_statuses,
        lead_level=lead_level,
    )
    if enqueued > 0:
        process_crm_outbox_batch.delay()

    return {"batch_id": batch_id, "connection_id": connection_id, "enqueued": enqueued}
