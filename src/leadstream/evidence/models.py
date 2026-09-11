from __future__ import annotations

import uuid
from collections.abc import Iterable
from typing import Any, ClassVar, NoReturn

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.db.models.base import ModelBase

from leadstream.entities.models import Entity
from leadstream.tenancy.models import TenantOwnedModel


class EvidenceStatus(models.TextChoices):
    ABSENT = "ABSENT", "Ausente"
    OBSERVED = "OBSERVED", "Observado"
    INFERRED = "INFERRED", "Inferido"
    TECHNICALLY_VALIDATED = "TECHNICALLY_VALIDATED", "Validado tecnicamente"
    CONFIRMED = "CONFIRMED", "Confirmado"
    CONFLICTING = "CONFLICTING", "Conflitante"
    REJECTED = "REJECTED", "Rejeitado"


class CaptureMethod(models.TextChoices):
    API = "API", "API"
    DATASET = "DATASET", "Base de dados"
    WEB_PAGE = "WEB_PAGE", "Página pública"
    SEARCH = "SEARCH", "Busca pública"
    TECHNICAL_CHECK = "TECHNICAL_CHECK", "Validação técnica"
    INFERENCE = "INFERENCE", "Inferência"
    MANUAL = "MANUAL", "Registro manual"


class ProcessingPurpose(TenantOwnedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.SlugField(max_length=80)
    name = models.CharField(max_length=160)
    description = models.TextField()
    operational_basis = models.CharField(max_length=255)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "leadstream_processing_purpose"
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.UniqueConstraint(fields=("tenant", "code"), name="purpose_tenant_code_uniq")
        ]

    def __str__(self) -> str:
        return self.name


class RetentionPolicy(TenantOwnedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.SlugField(max_length=80)
    name = models.CharField(max_length=160)
    stale_after_days = models.PositiveIntegerField()
    retention_days = models.PositiveIntegerField()
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "leadstream_retention_policy"
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.UniqueConstraint(fields=("tenant", "code"), name="retention_tenant_code_uniq"),
            models.CheckConstraint(
                condition=Q(retention_days__gte=models.F("stale_after_days")),
                name="retention_after_stale",
            ),
        ]

    def __str__(self) -> str:
        return self.name


class Source(TenantOwnedModel):
    class Category(models.TextChoices):
        GOVERNMENT = "GOVERNMENT", "Governamental"
        COMMERCIAL = "COMMERCIAL", "Comercial"
        PUBLIC_WEB = "PUBLIC_WEB", "Web pública"
        INTERNAL = "INTERNAL", "Interna"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    slug = models.SlugField(max_length=80)
    name = models.CharField(max_length=160)
    category = models.CharField(max_length=24, choices=Category.choices)
    priority = models.PositiveSmallIntegerField(default=50)
    terms_url = models.URLField(max_length=1024, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "leadstream_source"
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.UniqueConstraint(fields=("tenant", "slug"), name="source_tenant_slug_uniq")
        ]

    def __str__(self) -> str:
        return self.name


class SourceRecord(TenantOwnedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    source = models.ForeignKey(Source, on_delete=models.PROTECT, related_name="records")
    purpose = models.ForeignKey(
        ProcessingPurpose, on_delete=models.PROTECT, related_name="source_records"
    )
    retention_policy = models.ForeignKey(
        RetentionPolicy, on_delete=models.PROTECT, related_name="source_records"
    )
    external_id = models.CharField(max_length=255)
    source_url = models.URLField(max_length=2048, blank=True)
    captured_at = models.DateTimeField()
    payload_hash = models.CharField(max_length=64, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "leadstream_source_record"
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.UniqueConstraint(
                fields=("tenant", "source", "external_id"), name="source_record_identity_uniq"
            )
        ]
        indexes: ClassVar[list[models.Index]] = [
            models.Index(fields=("tenant", "source", "captured_at"), name="source_record_time_idx")
        ]

    def __str__(self) -> str:
        return f"{self.source.slug}:{self.external_id}"

    def clean(self) -> None:
        references = (
            self.source.tenant_id,
            self.purpose.tenant_id,
            self.retention_policy.tenant_id,
        )
        if any(tenant_id != self.tenant_id for tenant_id in references):
            raise ValidationError("Origem, finalidade e retenção devem pertencer ao mesmo tenant.")


class Evidence(TenantOwnedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    source_record = models.ForeignKey(
        SourceRecord, on_delete=models.PROTECT, related_name="evidence_items"
    )
    url = models.URLField(max_length=2048, blank=True)
    external_id = models.CharField(max_length=255, blank=True)
    captured_at = models.DateTimeField()
    observed_at = models.DateTimeField(null=True, blank=True)
    method = models.CharField(max_length=32, choices=CaptureMethod.choices)
    excerpt = models.TextField(blank=True)
    excerpt_hash = models.CharField(max_length=64, blank=True)
    content_hash = models.CharField(max_length=64)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "leadstream_evidence"
        indexes: ClassVar[list[models.Index]] = [
            models.Index(fields=("tenant", "captured_at"), name="evidence_captured_idx")
        ]

    def __str__(self) -> str:
        return self.content_hash

    def clean(self) -> None:
        if self.source_record.tenant_id != self.tenant_id:
            raise ValidationError(
                {"source_record": "Evidência e registro de origem devem pertencer ao mesmo tenant."}
            )
        if not (self.url or self.external_id or self.excerpt or self.excerpt_hash):
            raise ValidationError("Evidência exige URL, identificador, trecho ou hash do trecho.")


class ImmutableQuerySet(models.QuerySet[Any]):
    def update(self, **kwargs: Any) -> NoReturn:
        del kwargs
        raise ValidationError("Registros de auditoria são append-only.")

    def delete(self) -> NoReturn:
        raise ValidationError("Registros de auditoria são append-only.")


class Observation(TenantOwnedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    target = models.ForeignKey(Entity, on_delete=models.PROTECT, related_name="observations")
    source_record = models.ForeignKey(
        SourceRecord, on_delete=models.PROTECT, related_name="observations"
    )
    field_path = models.CharField(max_length=255)
    value = models.JSONField(null=True, blank=True)
    value_fingerprint = models.CharField(max_length=64)
    status = models.CharField(max_length=32, choices=EvidenceStatus.choices)
    confidence = models.PositiveSmallIntegerField()
    method = models.CharField(max_length=32, choices=CaptureMethod.choices)
    observed_at = models.DateTimeField()
    captured_at = models.DateTimeField()
    expires_at = models.DateTimeField(null=True, blank=True)
    supersedes = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.PROTECT, related_name="superseded_by"
    )
    evidence = models.ManyToManyField(Evidence, through="ObservationEvidence")
    created_at = models.DateTimeField(auto_now_add=True)

    objects = ImmutableQuerySet.as_manager()

    class Meta:
        db_table = "leadstream_observation"
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.CheckConstraint(
                condition=Q(confidence__gte=0) & Q(confidence__lte=100),
                name="observation_confidence_range",
            )
        ]
        indexes: ClassVar[list[models.Index]] = [
            models.Index(fields=("tenant", "target", "field_path"), name="observation_field_idx"),
            models.Index(fields=("tenant", "status", "expires_at"), name="observation_status_idx"),
            models.Index(fields=("value_fingerprint",), name="observation_value_hash_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.target_id}:{self.field_path}:{self.status}"

    def clean(self) -> None:
        errors: dict[str, str] = {}
        if self.target.tenant_id != self.tenant_id:
            errors["target"] = "Observação e entidade devem pertencer ao mesmo tenant."
        if self.source_record.tenant_id != self.tenant_id:
            errors["source_record"] = "Observação e origem devem pertencer ao mesmo tenant."
        if self.supersedes_id and self.supersedes:
            if self.supersedes.tenant_id != self.tenant_id:
                errors["supersedes"] = "A observação anterior pertence a outro tenant."
            if (
                self.supersedes.target_id != self.target_id
                or self.supersedes.field_path != self.field_path
            ):
                errors["supersedes"] = "A observação anterior deve tratar a mesma entidade e campo."
        if errors:
            raise ValidationError(errors)

    def save(
        self,
        *,
        force_insert: bool | tuple[ModelBase, ...] = False,
        force_update: bool = False,
        using: str | None = None,
        update_fields: Iterable[str] | None = None,
    ) -> None:
        if not self._state.adding or force_update or update_fields:
            raise ValidationError("Observações são append-only; crie uma nova observação.")
        super().save(
            force_insert=force_insert,
            force_update=force_update,
            using=using,
            update_fields=update_fields,
        )

    def delete(self, using: str | None = None, keep_parents: bool = False) -> NoReturn:
        del using, keep_parents
        raise ValidationError("Observações são append-only e não podem ser excluídas.")


class ObservationEvidence(models.Model):
    observation = models.ForeignKey(Observation, on_delete=models.PROTECT)
    evidence = models.ForeignKey(Evidence, on_delete=models.PROTECT)

    class Meta:
        db_table = "leadstream_observation_evidence"
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.UniqueConstraint(
                fields=("observation", "evidence"), name="observation_evidence_uniq"
            )
        ]

    def __str__(self) -> str:
        return f"{self.observation_id}:{self.evidence_id}"


class Conflict(TenantOwnedModel):
    class Status(models.TextChoices):
        OPEN = "OPEN", "Aberto"
        RESOLVED = "RESOLVED", "Resolvido"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    target = models.ForeignKey(Entity, on_delete=models.PROTECT, related_name="conflicts")
    field_path = models.CharField(max_length=255)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.OPEN)
    reason = models.TextField(blank=True)
    observations = models.ManyToManyField(Observation, through="ConflictParticipant")
    resolved_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "leadstream_conflict"
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.UniqueConstraint(
                fields=("tenant", "target", "field_path"),
                condition=Q(status="OPEN"),
                name="conflict_one_open_per_field",
            )
        ]

    def __str__(self) -> str:
        return f"{self.target_id}:{self.field_path}:{self.status}"


class ConflictParticipant(models.Model):
    conflict = models.ForeignKey(Conflict, on_delete=models.PROTECT)
    observation = models.ForeignKey(Observation, on_delete=models.PROTECT)

    class Meta:
        db_table = "leadstream_conflict_participant"
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.UniqueConstraint(
                fields=("conflict", "observation"), name="conflict_participant_uniq"
            )
        ]

    def __str__(self) -> str:
        return f"{self.conflict_id}:{self.observation_id}"


class CanonicalDecision(TenantOwnedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    target = models.ForeignKey(Entity, on_delete=models.PROTECT, related_name="canonical_decisions")
    field_path = models.CharField(max_length=255)
    version = models.PositiveIntegerField()
    policy_version = models.CharField(max_length=64)
    selected_observation = models.ForeignKey(
        Observation,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="canonical_selections",
    )
    decision_status = models.CharField(max_length=32, choices=EvidenceStatus.choices)
    reason = models.TextField()
    decided_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    objects = ImmutableQuerySet.as_manager()

    class Meta:
        db_table = "leadstream_canonical_decision"
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.UniqueConstraint(
                fields=("tenant", "target", "field_path", "version"),
                name="canonical_decision_version_uniq",
            )
        ]
        indexes: ClassVar[list[models.Index]] = [
            models.Index(
                fields=("tenant", "target", "field_path", "-version"),
                name="canonical_current_idx",
            )
        ]

    def __str__(self) -> str:
        return f"{self.target_id}:{self.field_path}:v{self.version}"

    def clean(self) -> None:
        errors: dict[str, str] = {}
        if self.target.tenant_id != self.tenant_id:
            errors["target"] = "Decisão e entidade devem pertencer ao mesmo tenant."
        if self.selected_observation:
            selected = self.selected_observation
            if selected.tenant_id != self.tenant_id:
                errors["selected_observation"] = "A observação selecionada pertence a outro tenant."
            if selected.target_id != self.target_id or selected.field_path != self.field_path:
                errors["selected_observation"] = "A observação selecionada trata outro campo."
            if selected.status != self.decision_status:
                errors["decision_status"] = "A decisão deve preservar o estado da observação."
        elif self.decision_status != EvidenceStatus.ABSENT:
            errors["decision_status"] = "Decisão sem observação deve registrar ausência."
        if errors:
            raise ValidationError(errors)

    def save(
        self,
        *,
        force_insert: bool | tuple[ModelBase, ...] = False,
        force_update: bool = False,
        using: str | None = None,
        update_fields: Iterable[str] | None = None,
    ) -> None:
        if not self._state.adding or force_update or update_fields:
            raise ValidationError("Decisões canônicas são versionadas e append-only.")
        super().save(
            force_insert=force_insert,
            force_update=force_update,
            using=using,
            update_fields=update_fields,
        )

    def delete(self, using: str | None = None, keep_parents: bool = False) -> NoReturn:
        del using, keep_parents
        raise ValidationError("Decisões canônicas são append-only e não podem ser excluídas.")
