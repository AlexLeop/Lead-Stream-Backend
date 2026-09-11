from __future__ import annotations

import hashlib
import time
from datetime import timedelta
from typing import TYPE_CHECKING, Any, cast
from uuid import UUID

from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.utils import timezone

from leadstream.batches.models import Batch, BatchItem
from leadstream.entities.models import (
    Company,
    ContactPoint,
    Establishment,
    Relationship,
    SocialProfile,
)

from .connectors.base import ConnectionTestResult
from .connectors.registry import get_connector_for_connection
from .models import (
    CRMConnection,
    CRMConnectionStatus,
    CRMFieldEntityType,
    CRMFieldMapping,
    CRMOutboxMessage,
    CRMSyncEvent,
    OutboxStatus,
)

if TYPE_CHECKING:
    pass


def verify_crm_connection(connection: CRMConnection) -> ConnectionTestResult:
    """Testa a conectividade e credenciais da conexão e atualiza seu status no banco."""
    connector = get_connector_for_connection(connection)
    result = connector.test_connection(connection)

    connection.last_tested_at = timezone.now()
    if result.success:
        connection.last_status = CRMConnectionStatus.HEALTHY
        connection.last_error_message = ""
    else:
        connection.last_status = CRMConnectionStatus.FAILED
        connection.last_error_message = result.message
    connection.save(
        update_fields=["last_tested_at", "last_status", "last_error_message", "updated_at"]
    )
    return result


def enqueue_batch_to_crm(
    batch: Batch,
    connection: CRMConnection,
    selected_statuses: list[str] | None = None,
    lead_level: str = "DECISION_MAKER",
) -> int:
    """Cria mensagens de outbox de forma transacional e idempotente para os itens de um lote."""
    if connection.tenant_id != batch.tenant_id:
        raise PermissionDenied("A conexão informada não pertence ao mesmo tenant do lote.")

    qs = BatchItem.objects.filter(batch=batch)
    if selected_statuses:
        qs = qs.filter(status__in=selected_statuses)
    else:
        qs = qs.exclude(status="FAILED")

    items = list(qs.order_by("row_number"))
    if not items:
        return 0

    # Bulk prefetch de entidades para evitar N+1
    entity_ids = [item.entity_id for item in items if item.entity_id]
    companies_map: dict[UUID, Company] = {}
    establishments_map: dict[UUID, list[Establishment]] = {}
    relationships_map: dict[UUID, list[Relationship]] = {}
    contacts_map: dict[UUID, list[ContactPoint]] = {}
    socials_map: dict[UUID, list[SocialProfile]] = {}

    if entity_ids:
        for comp in Company.objects.filter(entity_id__in=entity_ids):
            companies_map[cast(UUID, comp.pk)] = comp

        for estab in Establishment.objects.filter(company_id__in=entity_ids):
            c_id = cast(UUID, cast(Any, estab.company_id))
            establishments_map.setdefault(c_id, []).append(estab)

        for rel in Relationship.objects.filter(company_id__in=entity_ids).select_related("person"):
            c_id = cast(UUID, cast(Any, rel.company_id))
            relationships_map.setdefault(c_id, []).append(rel)

        # Contatos de pessoas e empresas
        person_ids = [
            rel.person_id for rels in relationships_map.values() for rel in rels if rel.person_id
        ]
        all_target_entities = list(entity_ids) + person_ids

        for cp in ContactPoint.objects.filter(owner_id__in=all_target_entities):
            contacts_map.setdefault(cp.owner_id, []).append(cp)

        for sp in SocialProfile.objects.filter(owner_id__in=all_target_entities):
            socials_map.setdefault(sp.owner_id, []).append(sp)

    messages_to_create: list[CRMOutboxMessage] = []

    for item in items:
        company = companies_map.get(item.entity_id) if item.entity_id else None
        estabs = establishments_map.get(item.entity_id, []) if item.entity_id else []
        headquarters = next((e for e in estabs if e.is_headquarters), estabs[0] if estabs else None)
        rels = relationships_map.get(item.entity_id, []) if item.entity_id else []

        # Dados da Empresa
        company_data: dict[str, Any] = {
            "cnpj": headquarters.cnpj if headquarters else (item.normalized_data.get("cnpj") or ""),
            "razao_social": company.legal_name
            if company
            else (item.normalized_data.get("razao_social") or ""),
            "nome_fantasia": company.trade_name
            if company
            else (item.normalized_data.get("nome_fantasia") or ""),
            "situacao_cadastral": headquarters.registration_status if headquarters else "",
            "cnae_principal": item.normalized_data.get("cnae_principal", ""),
            "uf": item.normalized_data.get("uf", ""),
            "municipio": item.normalized_data.get("municipio", ""),
            "logradouro": item.normalized_data.get("logradouro", ""),
            "cep": item.normalized_data.get("cep", ""),
        }

        if lead_level == "COMPANY" or not rels:
            # Mensagem em nível de empresa
            comp_contacts = contacts_map.get(item.entity_id, []) if item.entity_id else []
            email_cp = next((c for c in comp_contacts if c.kind == ContactPoint.Kind.EMAIL), None)
            phone_cp = next(
                (
                    c
                    for c in comp_contacts
                    if c.kind in (ContactPoint.Kind.PHONE, ContactPoint.Kind.WHATSAPP)
                ),
                None,
            )
            if email_cp:
                company_data["email"] = email_cp.normalized_value
            if phone_cp:
                company_data["telefone"] = phone_cp.normalized_value

            idempotency_raw = f"{connection.id}:{batch.id}:{item.id}:COMPANY"
            idempotency_key = hashlib.sha256(idempotency_raw.encode("utf-8")).hexdigest()

            messages_to_create.append(
                CRMOutboxMessage(
                    tenant=batch.tenant,
                    connection=connection,
                    batch=batch,
                    batch_item=item,
                    entity_type=CRMFieldEntityType.COMPANY,
                    idempotency_key=idempotency_key,
                    canonical_payload=company_data,
                    status=OutboxStatus.PENDING,
                )
            )
        else:
            # Mensagem para cada decisor relacionado
            for rel in rels:
                person = rel.person
                p_contacts = contacts_map.get(person.entity_id, [])
                p_socials = socials_map.get(person.entity_id, [])

                email_cp = next((c for c in p_contacts if c.kind == ContactPoint.Kind.EMAIL), None)
                whats_cp = next(
                    (c for c in p_contacts if c.kind == ContactPoint.Kind.WHATSAPP), None
                )
                phone_cp = whats_cp or next(
                    (c for c in p_contacts if c.kind == ContactPoint.Kind.PHONE), None
                )
                linkedin_sp = next(
                    (s for s in p_socials if s.network == SocialProfile.Network.LINKEDIN), None
                )

                is_whats = bool(whats_cp) or (
                    bool(phone_cp and phone_cp.capabilities.get("is_whatsapp"))
                )

                lead_data = dict(company_data)
                lead_data.update(
                    {
                        "nome_decisor": person.full_name,
                        "cargo_observado": rel.observed_title or "",
                        "qualificacao_societaria": rel.qualification or "",
                        "papel_compra": rel.buying_role or "",
                        "email_direto": email_cp.normalized_value if email_cp else "",
                        "status_email": email_cp.status if email_cp else "",
                        "telefone_direto": phone_cp.normalized_value if phone_cp else "",
                        "tipo_linha": phone_cp.kind if phone_cp else "",
                        "whatsapp_validado": is_whats,
                        "linkedin_url": linkedin_sp.normalized_url if linkedin_sp else "",
                    }
                )

                idempotency_raw = f"{connection.id}:{batch.id}:{item.id}:CONTACT:{person.entity_id}"
                idempotency_key = hashlib.sha256(idempotency_raw.encode("utf-8")).hexdigest()

                messages_to_create.append(
                    CRMOutboxMessage(
                        tenant=batch.tenant,
                        connection=connection,
                        batch=batch,
                        batch_item=item,
                        entity_type=CRMFieldEntityType.CONTACT,
                        idempotency_key=idempotency_key,
                        canonical_payload=lead_data,
                        status=OutboxStatus.PENDING,
                    )
                )

    if not messages_to_create:
        return 0

    existing_keys = set(
        CRMOutboxMessage.objects.filter(
            connection=connection,
            idempotency_key__in=[m.idempotency_key for m in messages_to_create],
        ).values_list("idempotency_key", flat=True)
    )
    new_messages = [m for m in messages_to_create if m.idempotency_key not in existing_keys]

    with transaction.atomic():
        if new_messages:
            CRMOutboxMessage.objects.bulk_create(new_messages, ignore_conflicts=True)
        CRMSyncEvent.objects.create(
            tenant=batch.tenant,
            connection=connection,
            batch=batch,
            total_enqueued=len(new_messages),
            status="ENQUEUED",
        )

    return len(new_messages)


def dispatch_outbox_message(message: CRMOutboxMessage) -> bool:
    """Executa o envio da mensagem para o CRM e registra o resultado com controle de falhas."""
    connector = get_connector_for_connection(message.connection)
    mappings = list(
        CRMFieldMapping.objects.filter(
            connection=message.connection,
            entity_type=message.entity_type,
        )
    )

    start = time.perf_counter()
    if message.entity_type == CRMFieldEntityType.COMPANY:
        result = connector.sync_company(message.connection, message.canonical_payload, mappings)
    elif message.entity_type == CRMFieldEntityType.CONTACT:
        result = connector.sync_contact(message.connection, message.canonical_payload, mappings)
    else:
        result = connector.sync_deal(message.connection, message.canonical_payload, mappings)
    latency = (time.perf_counter() - start) * 1000.0

    now = timezone.now()
    log_entry = {
        "timestamp": now.isoformat(),
        "latency_ms": round(latency, 2),
        "status_code": result.status_code,
        "success": result.success,
        "error_code": result.error_code,
        "error_message": result.error_message,
    }
    execution_log = list(message.execution_log)
    execution_log.append(log_entry)
    message.execution_log = execution_log
    message.last_attempted_at = now

    if result.success:
        message.status = OutboxStatus.DELIVERED
        message.delivered_at = now
        message.remote_id = result.remote_id
        message.error_code = ""
        message.error_message = ""
        message.save(
            update_fields=[
                "status",
                "delivered_at",
                "remote_id",
                "error_code",
                "error_message",
                "execution_log",
                "last_attempted_at",
                "updated_at",
            ]
        )
        return True

    # Tratamento de falha com retry backoff
    message.retry_count += 1
    if message.retry_count >= message.max_retries:
        message.status = OutboxStatus.DEAD_LETTER
    else:
        message.status = OutboxStatus.FAILED
        delay_seconds = result.retry_after_seconds or min(3600, 10 * (2**message.retry_count))
        message.next_retry_at = now + timedelta(seconds=delay_seconds)

    message.error_code = result.error_code
    message.error_message = result.error_message
    message.save(
        update_fields=[
            "status",
            "retry_count",
            "next_retry_at",
            "error_code",
            "error_message",
            "execution_log",
            "last_attempted_at",
            "updated_at",
        ]
    )
    return False
