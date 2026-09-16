from __future__ import annotations

import uuid
from collections.abc import Iterable
from typing import Any, ClassVar, NoReturn

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.db.models.base import ModelBase

from leadstream.batches.models import Batch, BatchItem
from leadstream.evidence.models import CanonicalDecision
from leadstream.tenancy.models import TenantOwnedModel


class DataBlock(models.TextChoices):
    COMPANY_REGISTRY = "COMPANY_REGISTRY", "Dados cadastrais"
    HYGIENE = "HYGIENE", "Higienização"
    DECISION_MAKER = "DECISION_MAKER", "Decisor"
    DIRECT_EMAIL = "DIRECT_EMAIL", "E-mail direto"
    DIRECT_PHONE = "DIRECT_PHONE", "Telefone direto"
    WHATSAPP = "WHATSAPP", "WhatsApp validado"
    SOCIAL_PROFILES = "SOCIAL_PROFILES", "Redes sociais"
    BANKING = "BANKING", "Instituição bancária"
    GOVERNMENT_RISK = "GOVERNMENT_RISK", "Risco governamental"
    PUBLIC_SECTOR = "PUBLIC_SECTOR", "Atuação no setor público"


class PriceBook(TenantOwnedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    version = models.PositiveIntegerField()
    name = models.CharField(max_length=160)
    currency = models.CharField(max_length=3, default="BRL")
    effective_at = models.DateTimeField()
    retired_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "leadstream_price_book"
        ordering: ClassVar[list[str]] = ["-version"]
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.UniqueConstraint(fields=("tenant", "version"), name="price_book_version_uniq")
        ]


class PriceRule(TenantOwnedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    price_book = models.ForeignKey(PriceBook, on_delete=models.PROTECT, related_name="rules")
    block = models.CharField(max_length=32, choices=DataBlock.choices)
    unit_price_cents = models.PositiveIntegerField()
    minimum_confidence = models.PositiveSmallIntegerField(default=80)
    refresh_window_days = models.PositiveIntegerField(default=30)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "leadstream_price_rule"
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.UniqueConstraint(
                fields=("price_book", "block"), name="price_rule_book_block_uniq"
            ),
            models.CheckConstraint(
                condition=Q(minimum_confidence__lte=100), name="price_rule_confidence_max"
            ),
            models.CheckConstraint(
                condition=Q(refresh_window_days__gte=1), name="price_rule_refresh_positive"
            ),
        ]

    def clean(self) -> None:
        if self.price_book.tenant_id != self.tenant_id:
            raise ValidationError({"price_book": "Regra e tabela devem pertencer ao mesmo tenant."})


class ProviderCall(TenantOwnedModel):
    class Status(models.TextChoices):
        REQUESTED = "REQUESTED", "Solicitada"
        SUCCEEDED = "SUCCEEDED", "Concluída"
        ABSENT = "ABSENT", "Sem resultado"
        FAILED = "FAILED", "Falhou"
        BLOCKED_BUDGET = "BLOCKED_BUDGET", "Bloqueada por orçamento"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    batch = models.ForeignKey(Batch, on_delete=models.PROTECT, related_name="provider_calls")
    item = models.ForeignKey(
        BatchItem, on_delete=models.PROTECT, null=True, blank=True, related_name="provider_calls"
    )
    provider = models.CharField(max_length=80)
    operation = models.CharField(max_length=120)
    block = models.CharField(max_length=32, choices=DataBlock.choices)
    idempotency_key = models.CharField(max_length=160)
    status = models.CharField(max_length=24, choices=Status.choices, default=Status.REQUESTED)
    estimated_cost_cents = models.PositiveIntegerField(default=0)
    confirmed_cost_cents = models.PositiveIntegerField(default=0)
    currency = models.CharField(max_length=3, default="BRL")
    external_request_id = models.CharField(max_length=255, blank=True)
    error_code = models.CharField(max_length=64, blank=True)
    latency_ms = models.PositiveIntegerField(default=0)
    delivered_blocks = models.JSONField(default=list, blank=True)
    execution_token = models.CharField(max_length=36, blank=True)
    leased_until = models.DateTimeField(null=True, blank=True)
    next_poll_at = models.DateTimeField(null=True, blank=True)
    provider_state = models.JSONField(default=dict, blank=True)
    started_at = models.DateTimeField()
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "leadstream_provider_call"
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.UniqueConstraint(
                fields=("tenant", "idempotency_key"), name="provider_call_idempotency_uniq"
            )
        ]
        indexes: ClassVar[list[models.Index]] = [
            models.Index(fields=("tenant", "provider", "status"), name="provider_call_status_idx"),
            models.Index(fields=("tenant", "batch", "block"), name="provider_call_batch_idx"),
        ]

    def clean(self) -> None:
        errors: dict[str, str] = {}
        if self.batch.tenant_id != self.tenant_id:
            errors["batch"] = "Chamada e lote devem pertencer ao mesmo tenant."
        if (
            self.item_id
            and self.item
            and (self.item.tenant_id != self.tenant_id or self.item.batch_id != self.batch_id)
        ):
            errors["item"] = "Item não pertence ao mesmo tenant e lote."
        if errors:
            raise ValidationError(errors)


class ImmutableLedgerQuerySet(models.QuerySet[Any]):
    def update(self, **kwargs: Any) -> NoReturn:
        del kwargs
        raise ValidationError("Eventos financeiros são append-only.")

    def delete(self) -> NoReturn:
        raise ValidationError("Eventos financeiros são append-only.")


class BillableEvent(TenantOwnedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    batch = models.ForeignKey(Batch, on_delete=models.PROTECT, related_name="billable_events")
    item = models.ForeignKey(BatchItem, on_delete=models.PROTECT, related_name="billable_events")
    decision = models.ForeignKey(
        CanonicalDecision,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="billable_events",
    )
    price_rule = models.ForeignKey(PriceRule, on_delete=models.PROTECT, related_name="events")
    block = models.CharField(max_length=32, choices=DataBlock.choices)
    dedup_key = models.CharField(max_length=64)
    delivered_value_fingerprint = models.CharField(max_length=64)
    evidence_status = models.CharField(max_length=32)
    confidence = models.PositiveSmallIntegerField()
    unit_price_cents = models.PositiveIntegerField()
    currency = models.CharField(max_length=3)
    delivered_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    objects = ImmutableLedgerQuerySet.as_manager()

    class Meta:
        db_table = "leadstream_billable_event"
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.UniqueConstraint(
                fields=("tenant", "dedup_key"), name="billable_event_dedup_uniq"
            ),
            models.CheckConstraint(
                condition=Q(confidence__lte=100), name="billable_event_confidence_max"
            ),
        ]
        indexes: ClassVar[list[models.Index]] = [
            models.Index(fields=("tenant", "batch", "block"), name="billable_batch_block_idx")
        ]

    def clean(self) -> None:
        references = {
            self.batch.tenant_id,
            self.item.tenant_id,
            self.price_rule.tenant_id,
        }
        if self.decision_id and self.decision:
            references.add(self.decision.tenant_id)
        if references != {self.tenant_id} or self.item.batch_id != self.batch_id:
            raise ValidationError("Evento faturável contém referências de outro tenant ou lote.")

    def save(
        self,
        *,
        force_insert: bool | tuple[ModelBase, ...] = False,
        force_update: bool = False,
        using: str | None = None,
        update_fields: Iterable[str] | None = None,
    ) -> None:
        if not self._state.adding or force_update or update_fields:
            raise ValidationError("Eventos faturáveis são append-only.")
        super().save(
            force_insert=force_insert,
            force_update=force_update,
            using=using,
            update_fields=update_fields,
        )

    def delete(self, using: str | None = None, keep_parents: bool = False) -> NoReturn:
        del using, keep_parents
        raise ValidationError("Eventos faturáveis são append-only.")


DATA_BLOCK_CHOICES = DataBlock.choices
PROVIDER_CALL_STATUS_CHOICES = ProviderCall.Status.choices


class CreditWallet(TenantOwnedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    balance = models.IntegerField(default=0)
    reserved_balance = models.IntegerField(default=0)
    is_unlimited = models.BooleanField(default=False)
    auto_recharge = models.BooleanField(default=False)
    recharge_threshold = models.IntegerField(default=100)
    updated_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "leadstream_credit_wallet"
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.UniqueConstraint(fields=("tenant",), name="credit_wallet_tenant_uniq"),
            models.CheckConstraint(
                condition=Q(balance__gte=0) | Q(is_unlimited=True),
                name="credit_wallet_balance_positive",
            ),
            models.CheckConstraint(
                condition=Q(reserved_balance__gte=0),
                name="credit_wallet_reserved_positive",
            ),
        ]

    @property
    def available_balance(self) -> int:
        return self.balance


class CreditReservation(TenantOwnedModel):
    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", "Ativa"
        SETTLED = "SETTLED", "Liquidada"
        CANCELLED = "CANCELLED", "Cancelada"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    wallet = models.ForeignKey(CreditWallet, on_delete=models.PROTECT, related_name="reservations")
    batch = models.ForeignKey(
        Batch,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="credit_reservations",
    )
    amount = models.PositiveIntegerField()
    captured_amount = models.PositiveIntegerField(default=0)
    released_amount = models.PositiveIntegerField(default=0)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE)
    description = models.CharField(max_length=255, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "leadstream_credit_reservation"
        indexes: ClassVar[list[models.Index]] = [
            models.Index(fields=("tenant", "status"), name="credit_res_status_idx"),
            models.Index(fields=("wallet", "status"), name="credit_res_wallet_idx"),
        ]


class CreditTransaction(TenantOwnedModel):
    class Type(models.TextChoices):
        DEPOSIT = "DEPOSIT", "Depósito / Recarga"
        HOLD = "HOLD", "Reserva de lote"
        CAPTURE = "CAPTURE", "Captura / Cobrança de lead útil"
        RELEASE = "RELEASE", "Liberação / Estorno de excedente"
        BONUS = "BONUS", "Crédito bônus inicial"
        ADJUSTMENT = "ADJUSTMENT", "Ajuste manual administrativo"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    wallet = models.ForeignKey(CreditWallet, on_delete=models.PROTECT, related_name="transactions")
    reservation = models.ForeignKey(
        CreditReservation,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="transactions",
    )
    transaction_type = models.CharField(max_length=20, choices=Type.choices)
    amount = models.IntegerField()
    balance_after = models.IntegerField()
    reference_id = models.CharField(max_length=160, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = ImmutableLedgerQuerySet.as_manager()

    class Meta:
        db_table = "leadstream_credit_transaction"
        ordering: ClassVar[list[str]] = ["-created_at"]
        indexes: ClassVar[list[models.Index]] = [
            models.Index(fields=("wallet", "-created_at"), name="credit_tx_wallet_idx"),
            models.Index(fields=("tenant", "-created_at"), name="credit_tx_tenant_idx"),
        ]

    def save(
        self,
        *,
        force_insert: bool | tuple[ModelBase, ...] = False,
        force_update: bool = False,
        using: str | None = None,
        update_fields: Iterable[str] | None = None,
    ) -> None:
        if not self._state.adding or force_update or update_fields:
            raise ValidationError("Eventos de transação de crédito são append-only.")
        super().save(
            force_insert=force_insert,
            force_update=force_update,
            using=using,
            update_fields=update_fields,
        )

    def delete(self, using: str | None = None, keep_parents: bool = False) -> NoReturn:
        del using, keep_parents
        raise ValidationError("Eventos de transação de crédito são append-only.")
