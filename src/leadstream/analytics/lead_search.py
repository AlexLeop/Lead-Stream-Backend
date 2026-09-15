from __future__ import annotations

import math
import uuid
from dataclasses import dataclass
from typing import Any

from django.db.models import Count, Prefetch, Q, QuerySet

from leadstream.entities.models import (
    ContactPoint,
    Entity,
    Establishment,
    Relationship,
    SocialProfile,
)
from leadstream.tenancy.models import Tenant

EXCLUDED_CONTACT_STATUSES = (
    ContactPoint.Status.SUPPRESSED,
    ContactPoint.Status.EXPIRED,
)
VALIDATED_CONTACT_STATUSES = (
    ContactPoint.Status.CAPABILITY_VALID,
    ContactPoint.Status.CONFIRMED,
)


@dataclass(frozen=True)
class LeadPage:
    entities: tuple[Entity, ...]
    count: int
    page: int
    page_size: int
    total_pages: int
    next_page: int | None
    previous_page: int | None
    pj_count: int
    pf_count: int


def _boolean(value: str | None) -> bool | None:
    if value is None or value == "":
        return None
    normalized = value.strip().casefold()
    if normalized in {"1", "true", "sim", "yes"}:
        return True
    if normalized in {"0", "false", "não", "nao", "no"}:
        return False
    raise ValueError("Use true ou false nos filtros booleanos.")


def _entity_query(tenant: Tenant, params: Any) -> QuerySet[Entity]:
    query = Entity.objects.filter(
        tenant=tenant,
        kind__in=(Entity.Kind.COMPANY, Entity.Kind.PERSON),
    )
    lead_type = str(params.get("lead_type") or params.get("type") or "").strip().upper()
    if lead_type:
        kind_by_type = {"PJ": Entity.Kind.COMPANY, "PF": Entity.Kind.PERSON}
        if lead_type not in kind_by_type:
            raise ValueError("lead_type deve ser PJ ou PF.")
        query = query.filter(kind=kind_by_type[lead_type])

    text = str(params.get("q") or "").strip()
    if text:
        digits = "".join(character for character in text if character.isdigit())
        text_filter = (
            Q(company__legal_name__icontains=text)
            | Q(company__trade_name__icontains=text)
            | Q(person__full_name__icontains=text)
            | Q(person__normalized_name__icontains=text)
            | Q(person__relationships__observed_title__icontains=text)
            | Q(person__relationships__company__legal_name__icontains=text)
        )
        if digits:
            text_filter |= Q(natural_key__icontains=digits) | Q(
                person__cpf_masked__icontains=digits
            )
        query = query.filter(text_filter)

    state = str(params.get("uf") or params.get("state") or "").strip().upper()
    if state:
        query = query.filter(
            Q(company__establishments__state=state)
            | Q(person__relationships__company__establishments__state=state)
        )
    city = str(params.get("city") or "").strip()
    if city:
        query = query.filter(
            Q(company__establishments__city__icontains=city)
            | Q(person__relationships__company__establishments__city__icontains=city)
        )
    cnae = "".join(character for character in str(params.get("cnae") or "") if character.isdigit())
    if cnae:
        query = query.filter(
            Q(company__primary_cnae__startswith=cnae)
            | Q(person__relationships__company__primary_cnae__startswith=cnae)
        )
    company_size = str(params.get("company_size") or "").strip()
    if company_size:
        query = query.filter(
            Q(company__company_size__iexact=company_size)
            | Q(person__relationships__company__company_size__iexact=company_size)
        )
    registration_status = str(params.get("registration_status") or "").strip()
    if registration_status:
        query = query.filter(
            Q(company__registration_status__iexact=registration_status)
            | Q(person__relationships__company__registration_status__iexact=registration_status)
        )
    seniority = str(params.get("seniority") or "").strip().upper()
    if seniority:
        query = query.filter(person__relationships__seniority=seniority)
    title = str(params.get("title") or "").strip()
    if title:
        query = query.filter(person__relationships__observed_title__icontains=title)

    has_email = _boolean(params.get("has_email"))
    if has_email is not None:
        email_filter = Q(contact_points__kind=ContactPoint.Kind.EMAIL) & ~Q(
            contact_points__status__in=EXCLUDED_CONTACT_STATUSES
        )
        query = query.filter(email_filter) if has_email else query.exclude(email_filter)
    has_phone = _boolean(params.get("has_phone"))
    if has_phone is not None:
        phone_filter = Q(
            contact_points__kind__in=(ContactPoint.Kind.PHONE, ContactPoint.Kind.WHATSAPP)
        ) & ~Q(contact_points__status__in=EXCLUDED_CONTACT_STATUSES)
        query = query.filter(phone_filter) if has_phone else query.exclude(phone_filter)

    email_status = str(params.get("email_status") or "").strip().casefold()
    if email_status == "verified":
        query = query.filter(
            contact_points__kind=ContactPoint.Kind.EMAIL,
            contact_points__status__in=VALIDATED_CONTACT_STATUSES,
        )
    elif email_status == "catchall":
        query = query.filter(
            contact_points__kind=ContactPoint.Kind.EMAIL,
            contact_points__capabilities__catch_all=True,
        )
    elif email_status == "invalid":
        query = query.filter(
            contact_points__kind=ContactPoint.Kind.EMAIL,
            contact_points__status=ContactPoint.Status.INVALID,
        )
    elif email_status and email_status != "all":
        raise ValueError("email_status deve ser verified, catchall, invalid ou all.")

    dataset_id = str(params.get("dataset_id") or "").strip()
    if dataset_id:
        try:
            query = query.filter(batch_items__batch_id=uuid.UUID(dataset_id))
        except ValueError as exc:
            raise ValueError("dataset_id inválido.") from exc
    return query.distinct().order_by("-updated_at", "-id")


def _hydrated_entities(ids: list[uuid.UUID]) -> tuple[Entity, ...]:
    if not ids:
        return ()
    contacts = ContactPoint.objects.exclude(status__in=EXCLUDED_CONTACT_STATUSES).order_by(
        "-last_observed_at", "-created_at"
    )
    socials = SocialProfile.objects.exclude(status__in=EXCLUDED_CONTACT_STATUSES).order_by(
        "-last_observed_at", "-created_at"
    )
    establishments = Establishment.objects.order_by("-is_headquarters", "created_at")
    relationships = (
        Relationship.objects.filter(ended_on__isnull=True)
        .select_related("company__entity")
        .prefetch_related(
            Prefetch(
                "company__establishments",
                queryset=establishments,
                to_attr="_lead_establishments",
            )
        )
        .order_by("-updated_at")
    )
    hydrated = (
        Entity.objects.filter(pk__in=ids)
        .select_related("company", "person")
        .prefetch_related(
            Prefetch("contact_points", queryset=contacts, to_attr="_lead_contacts"),
            Prefetch("social_profiles", queryset=socials, to_attr="_lead_socials"),
            Prefetch(
                "company__establishments",
                queryset=establishments,
                to_attr="_lead_establishments",
            ),
            Prefetch(
                "person__relationships",
                queryset=relationships,
                to_attr="_lead_relationships",
            ),
        )
    )
    by_id = {entity.id: entity for entity in hydrated}
    return tuple(by_id[entity_id] for entity_id in ids if entity_id in by_id)


def search_leads(*, tenant: Tenant, params: Any, page: int, page_size: int) -> LeadPage:
    query = _entity_query(tenant, params)
    count = query.count()
    total_pages = math.ceil(count / page_size) if count else 0
    offset = (page - 1) * page_size
    ids = list(query.values_list("id", flat=True)[offset : offset + page_size])
    counts = Entity.objects.filter(
        tenant=tenant,
        kind__in=(Entity.Kind.COMPANY, Entity.Kind.PERSON),
    ).aggregate(
        pj=Count("id", filter=Q(kind=Entity.Kind.COMPANY)),
        pf=Count("id", filter=Q(kind=Entity.Kind.PERSON)),
    )
    return LeadPage(
        entities=_hydrated_entities(ids),
        count=count,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
        next_page=page + 1 if page < total_pages else None,
        previous_page=page - 1 if page > 1 and count else None,
        pj_count=int(counts["pj"] or 0),
        pf_count=int(counts["pf"] or 0),
    )
