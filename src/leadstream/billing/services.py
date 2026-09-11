from __future__ import annotations

import hashlib
from collections.abc import Iterable
from datetime import datetime
from typing import Any, cast
from uuid import UUID

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Count, Max, Q, Sum
from django.db.models.functions import Coalesce
from django.utils import timezone

from leadstream.batches.models import Batch, BatchItem
from leadstream.evidence.models import CanonicalDecision, EvidenceStatus
from leadstream.tenancy.models import Tenant

from .models import (
    BillableEvent,
    CreditReservation,
    CreditTransaction,
    CreditWallet,
    DataBlock,
    PriceBook,
    PriceRule,
    ProviderCall,
)

DEFAULT_PRICE_RULES: tuple[tuple[str, int, int, int], ...] = (
    (DataBlock.COMPANY_REGISTRY, 8, 85, 30),
    (DataBlock.HYGIENE, 6, 100, 30),
    (DataBlock.DECISION_MAKER, 12, 85, 30),
    (DataBlock.DIRECT_EMAIL, 14, 90, 30),
    (DataBlock.DIRECT_PHONE, 14, 90, 30),
    (DataBlock.WHATSAPP, 12, 95, 15),
    (DataBlock.SOCIAL_PROFILES, 9, 85, 30),
    (DataBlock.BANKING, 5, 95, 30),
)
ELIGIBLE_EVIDENCE_STATUSES = {
    EvidenceStatus.TECHNICALLY_VALIDATED,
    EvidenceStatus.CONFIRMED,
}
TERMINAL_CALL_STATUSES = {
    ProviderCall.Status.SUCCEEDED,
    ProviderCall.Status.ABSENT,
    ProviderCall.Status.FAILED,
    ProviderCall.Status.BLOCKED_BUDGET,
}


@transaction.atomic
def create_price_book(
    *,
    tenant: Tenant,
    name: str,
    rules: Iterable[dict[str, Any]],
    effective_at: datetime | None = None,
) -> PriceBook:
    rule_data = list(rules)
    blocks = [str(item.get("block", "")) for item in rule_data]
    if len(blocks) != len(set(blocks)):
        raise ValidationError("Cada bloco pode aparecer apenas uma vez na tabela.")
    if not rule_data:
        raise ValidationError("A tabela de preços exige ao menos uma regra.")
    Tenant.objects.select_for_update().get(pk=tenant.pk)
    current_version = (
        PriceBook.objects.filter(tenant=tenant).aggregate(value=Max("version"))["value"] or 0
    )
    effective = effective_at or timezone.now()
    PriceBook.objects.filter(
        tenant=tenant, retired_at__isnull=True, effective_at__lte=effective
    ).update(retired_at=effective)
    price_book = PriceBook.objects.create(
        tenant=tenant,
        version=current_version + 1,
        name=" ".join(name.split())[:160],
        currency="BRL",
        effective_at=effective,
    )
    instances: list[PriceRule] = []
    for item in rule_data:
        rule = PriceRule(
            tenant=tenant,
            price_book=price_book,
            block=item["block"],
            unit_price_cents=item["unit_price_cents"],
            minimum_confidence=item.get("minimum_confidence", 80),
            refresh_window_days=item.get("refresh_window_days", 30),
        )
        rule.full_clean()
        instances.append(rule)
    PriceRule.objects.bulk_create(instances)
    return price_book


def ensure_default_price_book(tenant: Tenant) -> PriceBook:
    existing = PriceBook.objects.filter(tenant=tenant).order_by("-version").first()
    if existing is not None:
        return existing
    rules = [
        {
            "block": block,
            "unit_price_cents": cents,
            "minimum_confidence": confidence,
            "refresh_window_days": window,
        }
        for block, cents, confidence, window in DEFAULT_PRICE_RULES
    ]
    try:
        return create_price_book(
            tenant=tenant,
            name="Tabela padrão R$ 0,80",
            rules=rules,
        )
    except IntegrityError:
        return PriceBook.objects.filter(tenant=tenant).order_by("-version").get()


def active_price_book(*, tenant: Tenant, at: datetime | None = None) -> PriceBook:
    effective = at or timezone.now()
    price_book = (
        PriceBook.objects.filter(tenant=tenant, effective_at__lte=effective)
        .filter(Q(retired_at__isnull=True) | Q(retired_at__gt=effective))
        .order_by("-version")
        .first()
    )
    return price_book or ensure_default_price_book(tenant)


@transaction.atomic
def register_provider_call(
    *,
    tenant: Tenant,
    batch: Batch,
    provider: str,
    operation: str,
    block: str,
    idempotency_key: str,
    estimated_cost_cents: int,
    item: BatchItem | None = None,
    currency: str = "BRL",
) -> ProviderCall:
    if batch.tenant_id != tenant.pk or (item and item.tenant_id != tenant.pk):
        raise ValidationError("Chamada contém lote ou item de outro tenant.")
    existing = ProviderCall.objects.filter(tenant=tenant, idempotency_key=idempotency_key).first()
    if existing is not None:
        return existing
    call = ProviderCall(
        tenant=tenant,
        batch=batch,
        item=item,
        provider=provider,
        operation=operation,
        block=block,
        idempotency_key=idempotency_key,
        estimated_cost_cents=estimated_cost_cents,
        currency=currency.upper(),
        started_at=timezone.now(),
    )
    call.full_clean()
    call.save()
    return call


@transaction.atomic
def finalize_provider_call(
    *,
    call: ProviderCall,
    status: str,
    confirmed_cost_cents: int,
    external_request_id: str = "",
    error_code: str = "",
    latency_ms: int = 0,
    delivered_blocks: Iterable[str] = (),
) -> ProviderCall:
    locked = ProviderCall.objects.select_for_update().select_related("batch").get(pk=call.pk)
    if status not in TERMINAL_CALL_STATUSES:
        raise ValidationError("Estado final de chamada inválido.")
    if locked.status in TERMINAL_CALL_STATUSES:
        if locked.status != status or locked.confirmed_cost_cents != confirmed_cost_cents:
            raise ValidationError("A chamada já foi finalizada com outro resultado.")
        return locked
    locked.status = status
    locked.confirmed_cost_cents = confirmed_cost_cents
    locked.external_request_id = external_request_id[:255]
    locked.error_code = error_code[:64]
    locked.latency_ms = max(latency_ms, 0)
    locked.delivered_blocks = sorted(set(delivered_blocks))
    locked.completed_at = timezone.now()
    locked.save()
    refresh_batch_financials(locked.batch_id)
    return locked


def _dedup_key(*, tenant: Tenant, item: BatchItem, rule: PriceRule) -> str:
    # Uma compra por bloco e item do lote; novos valores/fallbacks não são novas compras.
    material = f"{tenant.pk}:{item.pk}:{rule.block}"
    return hashlib.sha256(material.encode()).hexdigest()


@transaction.atomic
def record_billable_delivery(
    *,
    tenant: Tenant,
    batch: Batch,
    item: BatchItem,
    block: str,
    delivered_value_fingerprint: str,
    evidence_status: str,
    confidence: int,
    decision: CanonicalDecision | None = None,
    delivered_at: datetime | None = None,
) -> BillableEvent | None:
    if batch.tenant_id != tenant.pk or item.tenant_id != tenant.pk or item.batch_id != batch.pk:
        raise ValidationError("Entrega contém lote ou item de outro tenant.")
    if decision and decision.tenant_id != tenant.pk:
        raise ValidationError("Decisão canônica pertence a outro tenant.")
    if evidence_status not in ELIGIBLE_EVIDENCE_STATUSES:
        return None
    BatchItem.objects.select_for_update().get(pk=item.pk, tenant=tenant, batch=batch)
    existing = BillableEvent.objects.filter(tenant=tenant, item=item, block=block).first()
    if existing is not None:
        return cast(BillableEvent, existing)
    price_book = active_price_book(tenant=tenant, at=delivered_at)
    try:
        rule = price_book.rules.get(block=block)
    except PriceRule.DoesNotExist as exc:
        raise ValidationError("Bloco sem preço vigente.") from exc
    if confidence < rule.minimum_confidence:
        return None
    event_time = delivered_at or timezone.now()
    key = _dedup_key(
        tenant=tenant,
        item=item,
        rule=rule,
    )
    existing = BillableEvent.objects.filter(tenant=tenant, dedup_key=key).first()
    if existing is not None:
        return cast(BillableEvent, existing)
    event = BillableEvent(
        tenant=tenant,
        batch=batch,
        item=item,
        decision=decision,
        price_rule=rule,
        block=block,
        dedup_key=key,
        delivered_value_fingerprint=delivered_value_fingerprint,
        evidence_status=evidence_status,
        confidence=confidence,
        unit_price_cents=rule.unit_price_cents,
        currency=price_book.currency,
        delivered_at=event_time,
    )
    event.full_clean()
    try:
        with transaction.atomic():
            event.save(force_insert=True)
    except IntegrityError:
        event = BillableEvent.objects.get(tenant=tenant, dedup_key=key)
    refresh_batch_financials(batch.pk)
    return event


@transaction.atomic
def refresh_batch_financials(batch_id: UUID | str) -> None:
    Batch.objects.select_for_update().get(pk=batch_id)
    cost = ProviderCall.objects.filter(batch_id=batch_id).aggregate(
        value=Coalesce(Sum("confirmed_cost_cents"), 0)
    )["value"]
    revenue = BillableEvent.objects.filter(batch_id=batch_id).aggregate(
        value=Coalesce(Sum("unit_price_cents"), 0)
    )["value"]
    Batch.objects.filter(pk=batch_id).update(cost_cents=cost, revenue_cents=revenue)


def financial_summary(*, tenant: Tenant, batch: Batch) -> dict[str, Any]:
    if batch.tenant_id != tenant.pk:
        raise ValidationError("Lote pertence a outro tenant.")
    refresh_batch_financials(batch.pk)
    batch.refresh_from_db(fields=("cost_cents", "revenue_cents"))
    block_revenue = {
        row["block"]: {"delivered": row["delivered"], "revenue_cents": row["revenue"]}
        for row in BillableEvent.objects.filter(batch=batch, tenant=tenant)
        .values("block")
        .annotate(delivered=Count("id"), revenue=Sum("unit_price_cents"))
    }
    block_cost = {
        row["block"]: {"calls": row["calls"], "cost_cents": row["cost"]}
        for row in ProviderCall.objects.filter(batch=batch, tenant=tenant)
        .values("block")
        .annotate(calls=Count("id"), cost=Sum("confirmed_cost_cents"))
    }
    blocks = []
    for block, label in DataBlock.choices:
        revenue_data = block_revenue.get(block, {})
        cost_data = block_cost.get(block, {})
        blocks.append(
            {
                "block": block,
                "block_label": label,
                "delivered": revenue_data.get("delivered", 0),
                "calls": cost_data.get("calls", 0),
                "revenue_cents": revenue_data.get("revenue_cents", 0),
                "cost_cents": cost_data.get("cost_cents", 0),
            }
        )
    provider_rows = (
        ProviderCall.objects.filter(batch=batch, tenant=tenant)
        .values("provider", "status")
        .annotate(calls=Count("id"), cost_cents=Sum("confirmed_cost_cents"))
        .order_by("provider", "status")
    )
    providers = [
        {
            "provider": row["provider"],
            "provider_status": row["status"],
            "calls": row["calls"],
            "cost_cents": row["cost_cents"],
        }
        for row in provider_rows
    ]
    profit = int(batch.revenue_cents) - int(batch.cost_cents)
    margin = round((profit / batch.revenue_cents) * 100, 2) if batch.revenue_cents else 0.0
    delivered_count = BillableEvent.objects.filter(batch=batch, tenant=tenant).count()
    delivered_items = (
        BillableEvent.objects.filter(batch=batch, tenant=tenant)
        .values("item_id")
        .distinct()
        .count()
    )
    coverage = round((delivered_items / batch.total_rows) * 100, 2) if batch.total_rows else 0.0
    return {
        "batch_id": str(batch.pk),
        "currency": "BRL",
        "cost_cents": batch.cost_cents,
        "revenue_cents": batch.revenue_cents,
        "gross_profit_cents": profit,
        "gross_margin_percent": margin,
        "billable_deliveries": delivered_count,
        "coverage_percent": coverage,
        "by_block": blocks,
        "by_provider": providers,
    }


INITIAL_CREDIT_BONUS = 500


def get_or_create_wallet(tenant: Tenant) -> CreditWallet:
    """Obtém ou inicializa a carteira de créditos do tenant.
    Novos tenants recebem 500 créditos de cortesia inicial.
    O tenant interno de administração possui créditos ilimitados.
    """
    with transaction.atomic():
        wallet = (
            CreditWallet.objects.select_for_update()
            .filter(tenant=tenant)
            .first()
        )
        if wallet:
            return wallet

        is_internal = (
            str(tenant.id) == "00000000-0000-4000-8000-000000000001"
            or tenant.slug == "alexandre-leopoldo"
        )
        initial_balance = 0 if is_internal else INITIAL_CREDIT_BONUS

        wallet = CreditWallet.objects.create(
            tenant=tenant,
            balance=initial_balance,
            reserved_balance=0,
            is_unlimited=is_internal,
        )

        if initial_balance > 0:
            CreditTransaction.objects.create(
                tenant=tenant,
                wallet=wallet,
                transaction_type=CreditTransaction.Type.BONUS,
                amount=initial_balance,
                balance_after=initial_balance,
                reference_id="INITIAL_BONUS",
                metadata={"reason": "Boas-vindas ao LeadStream (saldo cortesia)"},
            )

        return wallet


def deposit_credits(
    wallet: CreditWallet,
    amount: int,
    reference_id: str = "",
    metadata: dict[str, Any] | None = None,
) -> CreditTransaction:
    """Adiciona créditos à carteira de forma atômica e registra a transação imutável."""
    if amount <= 0:
        raise ValidationError("O valor do depósito deve ser estritamente positivo.")

    with transaction.atomic():
        locked_wallet = (
            CreditWallet.objects.select_for_update()
            .get(id=wallet.id)
        )
        locked_wallet.balance += amount
        locked_wallet.save(update_fields=["balance", "updated_at"])

        tx = CreditTransaction.objects.create(
            tenant=locked_wallet.tenant,
            wallet=locked_wallet,
            transaction_type=CreditTransaction.Type.DEPOSIT,
            amount=amount,
            balance_after=locked_wallet.balance,
            reference_id=reference_id,
            metadata=metadata or {},
        )
        return tx


def hold_credits(
    wallet: CreditWallet,
    amount: int,
    batch: Batch | None = None,
    description: str = "",
) -> CreditReservation:
    """Reserva créditos para a execução de um lote ou enriquecimento (Hold)."""
    if amount <= 0:
        raise ValidationError("O valor da reserva deve ser estritamente positivo.")

    with transaction.atomic():
        locked_wallet = (
            CreditWallet.objects.select_for_update()
            .get(id=wallet.id)
        )

        if not locked_wallet.is_unlimited and locked_wallet.balance < amount:
            raise ValidationError(
                f"Saldo insuficiente. Disponível: {locked_wallet.balance}, necessário: {amount}."
            )

        if not locked_wallet.is_unlimited:
            locked_wallet.balance -= amount

        locked_wallet.reserved_balance += amount
        locked_wallet.save(update_fields=["balance", "reserved_balance", "updated_at"])

        reservation = CreditReservation.objects.create(
            tenant=locked_wallet.tenant,
            wallet=locked_wallet,
            batch=batch,
            amount=amount,
            status=CreditReservation.Status.ACTIVE,
            description=description,
        )

        CreditTransaction.objects.create(
            tenant=locked_wallet.tenant,
            wallet=locked_wallet,
            reservation=reservation,
            transaction_type=CreditTransaction.Type.HOLD,
            amount=-amount if not locked_wallet.is_unlimited else 0,
            balance_after=locked_wallet.balance,
            reference_id=f"HOLD_{reservation.id}",
            metadata={"batch_id": str(batch.id) if batch else None, "description": description},
        )

        return reservation


def capture_and_release(
    reservation: CreditReservation,
    actual_amount: int,
) -> tuple[CreditTransaction, CreditTransaction | None]:
    """Liquida a reserva (Capture de leads úteis + Release do excedente não utilizado)."""
    if actual_amount < 0:
        raise ValidationError("O valor faturado não pode ser negativo.")

    with transaction.atomic():
        locked_res = (
            CreditReservation.objects.select_for_update()
            .get(id=reservation.id)
        )
        if locked_res.status != CreditReservation.Status.ACTIVE:
            raise ValidationError("Apenas reservas ativas podem ser liquidadas.")

        locked_wallet = (
            CreditWallet.objects.select_for_update()
            .get(id=locked_res.wallet_id)
        )

        reserved = locked_res.amount
        capture_val = min(actual_amount, reserved)
        release_val = max(0, reserved - capture_val)

        locked_wallet.reserved_balance = max(0, locked_wallet.reserved_balance - reserved)
        if not locked_wallet.is_unlimited and release_val > 0:
            locked_wallet.balance += release_val

        locked_wallet.save(update_fields=["balance", "reserved_balance", "updated_at"])

        locked_res.captured_amount = capture_val
        locked_res.released_amount = release_val
        locked_res.status = CreditReservation.Status.SETTLED
        locked_res.save(
            update_fields=["captured_amount", "released_amount", "status", "updated_at"]
        )

        reservation.captured_amount = capture_val
        reservation.released_amount = release_val
        reservation.status = CreditReservation.Status.SETTLED

        capture_tx = CreditTransaction.objects.create(
            tenant=locked_wallet.tenant,
            wallet=locked_wallet,
            reservation=locked_res,
            transaction_type=CreditTransaction.Type.CAPTURE,
            amount=-capture_val if not locked_wallet.is_unlimited else 0,
            balance_after=locked_wallet.balance,
            reference_id=f"CAP_{locked_res.id}",
            metadata={"actual_delivered_credits": capture_val},
        )

        release_tx = None
        if release_val > 0:
            release_tx = CreditTransaction.objects.create(
                tenant=locked_wallet.tenant,
                wallet=locked_wallet,
                reservation=locked_res,
                transaction_type=CreditTransaction.Type.RELEASE,
                amount=release_val if not locked_wallet.is_unlimited else 0,
                balance_after=locked_wallet.balance,
                reference_id=f"REL_{locked_res.id}",
                metadata={"unused_refunded_credits": release_val},
            )

        return capture_tx, release_tx

