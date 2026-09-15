from __future__ import annotations

import csv
import io
from collections.abc import Iterable, Iterator
from datetime import datetime
from typing import Any

from django.db.models import Prefetch, QuerySet

from leadstream.entities.models import ContactPoint, Relationship, SocialProfile

from .models import ActivationList, ActivationListMember

EXPORT_COLUMNS = (
    "tipo",
    "nome",
    "empresa",
    "cnpj",
    "cpf_mascarado",
    "cargo_observado",
    "email",
    "status_email",
    "telefone",
    "tipo_telefone",
    "status_telefone",
    "linkedin",
    "exportado_em",
)


def _spreadsheet_safe(value: Any) -> str:
    text = "" if value is None else str(value)
    if text.startswith(("=", "+", "-", "@", "\t", "\r")):
        return f"'{text}"
    return text


def _latest(values: Iterable[Any]) -> Any | None:
    candidates = list(values)
    if not candidates:
        return None
    return max(
        candidates,
        key=lambda item: (item.last_observed_at or item.created_at, item.created_at),
    )


def _usable_contacts(entity: Any, *kinds: str) -> list[ContactPoint]:
    blocked = {
        ContactPoint.Status.INVALID,
        ContactPoint.Status.EXPIRED,
        ContactPoint.Status.SUPPRESSED,
    }
    return [
        contact
        for contact in entity.contact_points.all()
        if contact.kind in kinds and contact.status not in blocked
    ]


def _usable_linkedin(entity: Any) -> SocialProfile | None:
    blocked = {
        ContactPoint.Status.INVALID,
        ContactPoint.Status.EXPIRED,
        ContactPoint.Status.SUPPRESSED,
    }
    return _latest(
        profile
        for profile in entity.social_profiles.all()
        if profile.network == SocialProfile.Network.LINKEDIN and profile.status not in blocked
    )


def _member_row(member: ActivationListMember, *, exported_at: datetime) -> list[str]:
    entity = member.entity
    email = _latest(_usable_contacts(entity, ContactPoint.Kind.EMAIL))
    phone = _latest(
        _usable_contacts(entity, ContactPoint.Kind.WHATSAPP, ContactPoint.Kind.PHONE)
    )
    linkedin = _usable_linkedin(entity)
    person = getattr(entity, "person", None)
    company = getattr(entity, "company", None)
    relationship: Relationship | None = None
    if person is not None:
        relationship = next(
            (item for item in person.relationships.all() if item.ended_on is None),
            None,
        )
        company = relationship.company if relationship else None
    establishment = None
    if company is not None:
        establishments = list(company.establishments.all())
        establishment = next(
            (item for item in establishments if item.is_headquarters),
            establishments[0] if establishments else None,
        )
    return [
        "PF" if person is not None else "PJ",
        (
            person.full_name
            if person is not None
            else (company.trade_name or company.legal_name if company is not None else "")
        ),
        company.legal_name if company is not None else "",
        establishment.cnpj if establishment is not None else "",
        person.cpf_masked if person is not None else "",
        relationship.observed_title if relationship else "",
        email.normalized_value if email else "",
        email.status if email else "ABSENT",
        phone.normalized_value if phone else "",
        phone.kind if phone else "",
        phone.status if phone else "ABSENT",
        linkedin.normalized_url if linkedin else "",
        exported_at.isoformat(),
    ]


def activation_list_members(activation_list: ActivationList) -> QuerySet[ActivationListMember]:
    active_relationships = Relationship.objects.filter(ended_on__isnull=True).select_related(
        "company__entity"
    )
    return (
        activation_list.members.select_related("entity")
        .prefetch_related(
            "entity__contact_points",
            "entity__social_profiles",
            "entity__company__establishments",
            Prefetch("entity__person__relationships", queryset=active_relationships),
        )
        .order_by("added_at")
    )


def _csv_line(values: Iterable[Any]) -> str:
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer, delimiter=";", lineterminator="\r\n")
    writer.writerow([_spreadsheet_safe(value) for value in values])
    return buffer.getvalue()


def stream_activation_list_csv(activation_list: ActivationList) -> Iterator[str]:
    yield "\ufeff" + _csv_line(EXPORT_COLUMNS)
    exported_at = datetime.now().astimezone()
    for member in activation_list_members(activation_list).iterator(chunk_size=500):
        yield _csv_line(_member_row(member, exported_at=exported_at))
