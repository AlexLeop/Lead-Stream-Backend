from __future__ import annotations

import hashlib
import hmac
import re
import unicodedata
import uuid
from dataclasses import dataclass
from datetime import date
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from django.core.exceptions import ValidationError
from django.db import transaction

from leadstream.tenancy.models import Tenant

from .models import (
    Company,
    ContactPoint,
    Entity,
    Establishment,
    Person,
    Relationship,
    SocialProfile,
)
from .normalization import (
    DataValidationError,
    cnpj_root,
    normalize_cnpj,
    normalize_email,
    normalize_linkedin_url,
    normalize_phone_br,
    only_digits,
)


@dataclass(frozen=True)
class CompanyIdentity:
    company: Company
    establishment: Establishment


def _normalize_name(value: str) -> str:
    compact = " ".join((value or "").split())
    if not compact:
        raise DataValidationError("Nome é obrigatório.")
    decomposed = unicodedata.normalize("NFKD", compact)
    normalized = "".join(
        character for character in decomposed if not unicodedata.combining(character)
    )
    return normalized.casefold()


def _normalize_social_url(value: str) -> str:
    candidate = (value or "").strip()
    if "linkedin.com" in candidate.casefold():
        norm = normalize_linkedin_url(candidate)
        if norm:
            return norm
    parsed = urlsplit(candidate)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise DataValidationError("URL de perfil social inválida.")
    host = parsed.hostname.encode("idna").decode("ascii").casefold()
    port = f":{parsed.port}" if parsed.port else ""
    path = parsed.path.rstrip("/") or "/"
    return urlunsplit(("https", f"{host}{port}", path, parsed.query, ""))


def _cpf_digest(cpf: str, hash_key: str) -> tuple[str, str]:
    digits = only_digits(cpf)
    if len(digits) != 11 or len(set(digits)) == 1:
        raise DataValidationError("CPF inválido para correlação.")

    def check_digit(base: str, initial_weight: int) -> str:
        total = sum(
            int(number) * weight
            for number, weight in zip(base, range(initial_weight, 1, -1), strict=True)
        )
        result = 11 - total % 11
        return "0" if result >= 10 else str(result)

    first = check_digit(digits[:9], 10)
    second = check_digit(digits[:9] + first, 11)
    if digits[-2:] != first + second:
        raise DataValidationError("CPF inválido para correlação.")
    if not hash_key:
        raise DataValidationError("Chave de correlação é obrigatória para tratar CPF.")
    digest = hmac.new(hash_key.encode(), digits.encode(), hashlib.sha256).hexdigest()
    return f"***.{digits[3:6]}.{digits[6:9]}-**", digest


def _ensure_tenant(tenant: Tenant, *entities: Entity) -> None:
    if any(entity.tenant_id != tenant.pk for entity in entities):
        raise ValidationError("Todas as referências devem pertencer ao mesmo tenant.")


@transaction.atomic
def create_company(
    *,
    tenant: Tenant,
    cnpj: str,
    legal_name: str,
    trade_name: str = "",
    registration_status: str = "",
    is_headquarters: bool | None = None,
) -> CompanyIdentity:
    normalized_cnpj = normalize_cnpj(cnpj)
    root = cnpj_root(normalized_cnpj)
    company_entity, _ = Entity.objects.get_or_create(
        tenant=tenant,
        kind=Entity.Kind.COMPANY,
        natural_key=root,
    )
    company, _ = Company.objects.get_or_create(
        entity=company_entity,
        defaults={
            "cnpj_root": root,
            "legal_name": " ".join(legal_name.split()),
            "trade_name": " ".join(trade_name.split()),
            "registration_status": registration_status,
        },
    )
    establishment_entity, _ = Entity.objects.get_or_create(
        tenant=tenant,
        kind=Entity.Kind.ESTABLISHMENT,
        natural_key=normalized_cnpj,
    )
    establishment, _ = Establishment.objects.get_or_create(
        entity=establishment_entity,
        defaults={
            "company": company,
            "cnpj": normalized_cnpj,
            "is_headquarters": is_headquarters
            if is_headquarters is not None
            else normalized_cnpj[8:12] == "0001",
            "registration_status": registration_status,
        },
    )
    company.full_clean()
    establishment.full_clean()
    return CompanyIdentity(company=company, establishment=establishment)


@transaction.atomic
def create_person(
    *,
    tenant: Tenant,
    full_name: str,
    external_key: str | None = None,
    cpf: str | None = None,
    hash_key: str | None = None,
) -> Person:
    normalized_name = _normalize_name(full_name)
    cpf_masked = ""
    cpf_hash = ""
    if cpf is not None:
        cpf_masked, cpf_hash = _cpf_digest(cpf, hash_key or "")
    natural_key = f"cpf:{cpf_hash}" if cpf_hash else f"person:{external_key or uuid.uuid4()}"
    entity, _ = Entity.objects.get_or_create(
        tenant=tenant,
        kind=Entity.Kind.PERSON,
        natural_key=natural_key,
    )
    person, _ = Person.objects.get_or_create(
        entity=entity,
        defaults={
            "full_name": " ".join(full_name.split()),
            "normalized_name": normalized_name,
            "cpf_masked": cpf_masked,
            "cpf_hash": cpf_hash,
        },
    )
    person.full_clean()
    return person


@transaction.atomic
def create_relationship(
    *,
    tenant: Tenant,
    person: Person,
    company: Company,
    qualification: str,
    observed_title: str = "",
    normalized_title: str = "",
    seniority: str = Relationship.Seniority.UNKNOWN,
    buying_role: str = "",
    buying_role_is_inferred: bool = False,
    started_on: date | None = None,
    ended_on: date | None = None,
) -> Relationship:
    _ensure_tenant(tenant, person.entity, company.entity)
    relationship, _ = Relationship.objects.get_or_create(
        tenant=tenant,
        person=person,
        company=company,
        qualification=qualification,
        started_on=started_on,
        defaults={
            "observed_title": observed_title,
            "normalized_title": normalized_title,
            "seniority": seniority,
            "buying_role": buying_role,
            "buying_role_is_inferred": buying_role_is_inferred,
            "ended_on": ended_on,
        },
    )
    relationship.full_clean()
    return relationship


@transaction.atomic
def create_contact_point(
    *,
    tenant: Tenant,
    owner: Entity,
    kind: str,
    value: str,
    status: str = ContactPoint.Status.OBSERVED,
    capabilities: dict[str, Any] | None = None,
) -> ContactPoint:
    _ensure_tenant(tenant, owner)
    if kind == ContactPoint.Kind.EMAIL:
        normalized = normalize_email(value)
    elif kind in {ContactPoint.Kind.PHONE, ContactPoint.Kind.WHATSAPP}:
        normalized = normalize_phone_br(value)
    else:
        raise DataValidationError("Tipo de contato inválido.")
    contact, _ = ContactPoint.objects.get_or_create(
        tenant=tenant,
        owner=owner,
        kind=kind,
        normalized_value=normalized,
        defaults={
            "scope": owner.kind,
            "original_value": value,
            "status": status,
            "capabilities": capabilities or {},
        },
    )
    contact.full_clean()
    return contact


@transaction.atomic
def create_social_profile(
    *,
    tenant: Tenant,
    owner: Entity,
    network: str,
    profile_url: str,
    handle: str = "",
) -> SocialProfile:
    _ensure_tenant(tenant, owner)
    normalized_url = _normalize_social_url(profile_url)
    clean_profile_url = normalized_url if network == SocialProfile.Network.LINKEDIN else profile_url
    profile, _ = SocialProfile.objects.get_or_create(
        tenant=tenant,
        owner=owner,
        network=network,
        normalized_url=normalized_url,
        defaults={
            "profile_url": clean_profile_url,
            "handle": re.sub(r"^@", "", handle.strip()),
        },
    )
    profile.full_clean()
    return profile
