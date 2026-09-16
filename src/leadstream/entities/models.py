from __future__ import annotations

import uuid
from typing import ClassVar

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q

from leadstream.tenancy.models import TenantOwnedModel


class Entity(TenantOwnedModel):
    class Kind(models.TextChoices):
        COMPANY = "COMPANY", "Empresa"
        ESTABLISHMENT = "ESTABLISHMENT", "Estabelecimento"
        PERSON = "PERSON", "Pessoa"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    kind = models.CharField(max_length=24, choices=Kind.choices)
    natural_key = models.CharField(max_length=160)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "leadstream_entity"
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.UniqueConstraint(
                fields=("tenant", "kind", "natural_key"), name="entity_tenant_kind_natural_uniq"
            )
        ]
        indexes: ClassVar[list[models.Index]] = [
            models.Index(fields=("tenant", "kind", "natural_key"), name="entity_lookup_idx"),
            models.Index(fields=("tenant", "kind", "updated_at"), name="entity_tenant_recent_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.kind}:{self.natural_key}"


class Company(models.Model):
    entity = models.OneToOneField(
        Entity,
        primary_key=True,
        on_delete=models.PROTECT,
        related_name="company",
        limit_choices_to={"kind": Entity.Kind.COMPANY},
    )
    cnpj_root = models.CharField(max_length=8)
    legal_name = models.CharField(max_length=255)
    trade_name = models.CharField(max_length=255, blank=True)
    registration_status = models.CharField(max_length=32, blank=True)
    opened_on = models.DateField(null=True, blank=True)
    legal_nature = models.CharField(max_length=255, blank=True)
    company_size = models.CharField(max_length=80, blank=True)
    share_capital = models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True)
    primary_cnae = models.CharField(max_length=16, blank=True)
    primary_cnae_description = models.CharField(max_length=500, blank=True)
    secondary_cnaes = models.JSONField(default=list, blank=True)
    simple_national = models.BooleanField(null=True, blank=True)
    mei = models.BooleanField(null=True, blank=True)
    registry_source = models.CharField(max_length=160, blank=True)
    registry_observed_at = models.DateTimeField(null=True, blank=True)
    government_risk = models.JSONField(default=dict, blank=True)
    government_risk_observed_at = models.DateTimeField(null=True, blank=True)
    public_sector_profile = models.JSONField(default=dict, blank=True)
    public_sector_observed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "leadstream_company"
        indexes: ClassVar[list[models.Index]] = [
            models.Index(fields=("primary_cnae",), name="company_cnae_idx"),
            models.Index(fields=("company_size",), name="company_size_idx"),
            models.Index(fields=("registration_status",), name="company_status_idx"),
        ]

    def __str__(self) -> str:
        return self.legal_name

    @property
    def tenant_id(self) -> uuid.UUID:
        return self.entity.tenant_id

    def clean(self) -> None:
        if self.entity.kind != Entity.Kind.COMPANY:
            raise ValidationError({"entity": "A entidade deve ser do tipo empresa."})
        if self.entity.natural_key != self.cnpj_root:
            raise ValidationError({"cnpj_root": "A raiz do CNPJ diverge da identidade da empresa."})


class Establishment(models.Model):
    entity = models.OneToOneField(
        Entity,
        primary_key=True,
        on_delete=models.PROTECT,
        related_name="establishment",
        limit_choices_to={"kind": Entity.Kind.ESTABLISHMENT},
    )
    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name="establishments")
    cnpj = models.CharField(max_length=14)
    is_headquarters = models.BooleanField(default=False)
    registration_status = models.CharField(max_length=32, blank=True)
    street_type = models.CharField(max_length=80, blank=True)
    street = models.CharField(max_length=255, blank=True)
    number = models.CharField(max_length=40, blank=True)
    complement = models.CharField(max_length=255, blank=True)
    district = models.CharField(max_length=160, blank=True)
    city = models.CharField(max_length=160, blank=True)
    state = models.CharField(max_length=2, blank=True)
    postal_code = models.CharField(max_length=8, blank=True)
    municipality_ibge_code = models.CharField(max_length=16, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "leadstream_establishment"
        indexes: ClassVar[list[models.Index]] = [
            models.Index(fields=("company", "is_headquarters"), name="estab_company_hq_idx"),
            models.Index(fields=("state", "city"), name="estab_location_idx"),
        ]

    def __str__(self) -> str:
        return self.cnpj

    @property
    def tenant_id(self) -> uuid.UUID:
        return self.entity.tenant_id

    def clean(self) -> None:
        errors: dict[str, str] = {}
        if self.entity.kind != Entity.Kind.ESTABLISHMENT:
            errors["entity"] = "A entidade deve ser do tipo estabelecimento."
        if self.entity.natural_key != self.cnpj:
            errors["cnpj"] = "O CNPJ diverge da identidade do estabelecimento."
        if self.company.entity.tenant_id != self.entity.tenant_id:
            errors["company"] = "Empresa e estabelecimento devem pertencer ao mesmo tenant."
        if self.cnpj[:8] != self.company.cnpj_root:
            errors["cnpj"] = "O CNPJ do estabelecimento não pertence à raiz da empresa."
        if errors:
            raise ValidationError(errors)


class Person(models.Model):
    entity = models.OneToOneField(
        Entity,
        primary_key=True,
        on_delete=models.PROTECT,
        related_name="person",
        limit_choices_to={"kind": Entity.Kind.PERSON},
    )
    full_name = models.CharField(max_length=255)
    normalized_name = models.CharField(max_length=255)
    cpf_masked = models.CharField(max_length=14, blank=True)
    cpf_hash = models.CharField(max_length=64, blank=True)
    government_profile = models.JSONField(default=dict, blank=True)
    government_profile_observed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "leadstream_person"
        indexes: ClassVar[list[models.Index]] = [
            models.Index(fields=("normalized_name",), name="person_name_idx")
        ]

    def __str__(self) -> str:
        return self.full_name

    @property
    def tenant_id(self) -> uuid.UUID:
        return self.entity.tenant_id

    def clean(self) -> None:
        if self.entity.kind != Entity.Kind.PERSON:
            raise ValidationError({"entity": "A entidade deve ser do tipo pessoa."})
        if self.cpf_masked and "*" not in self.cpf_masked:
            raise ValidationError({"cpf_masked": "CPF deve permanecer mascarado."})


class Relationship(TenantOwnedModel):
    class Qualification(models.TextChoices):
        LEGAL_REPRESENTATIVE = "LEGAL_REPRESENTATIVE", "Representante legal"
        PARTNER = "PARTNER", "Sócio"
        ADMINISTRATOR = "ADMINISTRATOR", "Administrador"
        EMPLOYEE = "EMPLOYEE", "Funcionário"
        OTHER = "OTHER", "Outro"

    class Seniority(models.TextChoices):
        OWNER = "OWNER", "Proprietário"
        C_LEVEL = "C_LEVEL", "C-Level"
        DIRECTOR = "DIRECTOR", "Diretor"
        MANAGER = "MANAGER", "Gerente"
        COORDINATOR = "COORDINATOR", "Coordenador"
        OTHER = "OTHER", "Outro"
        UNKNOWN = "UNKNOWN", "Não informado"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    person = models.ForeignKey(Person, on_delete=models.PROTECT, related_name="relationships")
    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name="relationships")
    qualification = models.CharField(max_length=32, choices=Qualification.choices)
    observed_title = models.CharField(max_length=255, blank=True)
    normalized_title = models.CharField(max_length=255, blank=True)
    seniority = models.CharField(
        max_length=24, choices=Seniority.choices, default=Seniority.UNKNOWN
    )
    buying_role = models.CharField(max_length=120, blank=True)
    buying_role_is_inferred = models.BooleanField(default=False)
    started_on = models.DateField(null=True, blank=True)
    ended_on = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "leadstream_relationship"
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.CheckConstraint(
                condition=Q(ended_on__isnull=True)
                | Q(started_on__isnull=True)
                | Q(ended_on__gte=models.F("started_on")),
                name="relationship_dates_valid",
            ),
            models.UniqueConstraint(
                fields=("tenant", "person", "company", "qualification", "started_on"),
                name="relationship_identity_uniq",
                nulls_distinct=False,
            ),
        ]
        indexes: ClassVar[list[models.Index]] = [
            models.Index(fields=("tenant", "company", "ended_on"), name="relationship_company_idx"),
            models.Index(fields=("tenant", "person", "ended_on"), name="relationship_person_idx"),
        ]

    def clean(self) -> None:
        if self.person.entity.tenant_id != self.tenant_id:
            raise ValidationError({"person": "Pessoa e vínculo devem pertencer ao mesmo tenant."})
        if self.company.entity.tenant_id != self.tenant_id:
            raise ValidationError({"company": "Empresa e vínculo devem pertencer ao mesmo tenant."})


class ContactPoint(TenantOwnedModel):
    class Kind(models.TextChoices):
        EMAIL = "EMAIL", "E-mail"
        PHONE = "PHONE", "Telefone"
        WHATSAPP = "WHATSAPP", "WhatsApp"

    class Scope(models.TextChoices):
        PERSON = "PERSON", "Pessoa"
        COMPANY = "COMPANY", "Empresa"
        ESTABLISHMENT = "ESTABLISHMENT", "Estabelecimento"

    class Status(models.TextChoices):
        OBSERVED = "OBSERVED", "Observado"
        INVALID = "INVALID", "Inválido"
        DOMAIN_VALID = "DOMAIN_VALID", "Domínio validado"
        CAPABILITY_VALID = "CAPABILITY_VALID", "Capacidade técnica validada"
        CONFIRMED = "CONFIRMED", "Confirmado"
        STALE = "STALE", "Desatualizado"
        EXPIRED = "EXPIRED", "Expirado"
        SUPPRESSED = "SUPPRESSED", "Suprimido"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(Entity, on_delete=models.PROTECT, related_name="contact_points")
    kind = models.CharField(max_length=16, choices=Kind.choices)
    scope = models.CharField(max_length=20, choices=Scope.choices)
    original_value = models.CharField(max_length=512)
    normalized_value = models.CharField(max_length=512)
    status = models.CharField(max_length=32, choices=Status.choices, default=Status.OBSERVED)
    capabilities = models.JSONField(default=dict, blank=True)
    last_observed_at = models.DateTimeField(null=True, blank=True)
    stale_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "leadstream_contact_point"
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.UniqueConstraint(
                fields=("tenant", "owner", "kind", "normalized_value"),
                name="contact_identity_uniq",
            )
        ]
        indexes: ClassVar[list[models.Index]] = [
            models.Index(fields=("tenant", "kind", "status"), name="contact_status_idx"),
            models.Index(fields=("tenant", "normalized_value"), name="contact_value_idx"),
        ]

    def clean(self) -> None:
        errors: dict[str, str] = {}
        if self.owner.tenant_id != self.tenant_id:
            errors["owner"] = "Contato e proprietário devem pertencer ao mesmo tenant."
        if self.scope != self.owner.kind:
            errors["scope"] = "O escopo do contato deve corresponder ao proprietário."
        if errors:
            raise ValidationError(errors)


class SocialProfile(TenantOwnedModel):
    class Network(models.TextChoices):
        LINKEDIN = "LINKEDIN", "LinkedIn"
        INSTAGRAM = "INSTAGRAM", "Instagram"
        FACEBOOK = "FACEBOOK", "Facebook"
        X = "X", "X"
        OTHER = "OTHER", "Outra"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(Entity, on_delete=models.PROTECT, related_name="social_profiles")
    network = models.CharField(max_length=20, choices=Network.choices)
    profile_url = models.URLField(max_length=1024)
    normalized_url = models.URLField(max_length=1024)
    handle = models.CharField(max_length=255, blank=True)
    status = models.CharField(
        max_length=32, choices=ContactPoint.Status.choices, default=ContactPoint.Status.OBSERVED
    )
    last_observed_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "leadstream_social_profile"
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.UniqueConstraint(
                fields=("tenant", "owner", "network", "normalized_url"),
                name="social_profile_identity_uniq",
            )
        ]
        indexes: ClassVar[list[models.Index]] = [
            models.Index(fields=("tenant", "network", "status"), name="social_profile_status_idx")
        ]

    def clean(self) -> None:
        if self.owner.tenant_id != self.tenant_id:
            raise ValidationError(
                {"owner": "Perfil social e proprietário devem pertencer ao mesmo tenant."}
            )


CONTACT_POINT_STATUS_CHOICES = ContactPoint.Status.choices
CONTACT_POINT_SCOPE_CHOICES = ContactPoint.Scope.choices
