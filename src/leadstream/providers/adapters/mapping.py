from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from typing import Any

from leadstream.entities.models import ContactPoint, SocialProfile
from leadstream.evidence.models import EvidenceStatus
from leadstream.providers.contracts import ContactCandidate, PersonCandidate, SocialCandidate


def normalized_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.casefold())


def pick(data: Mapping[str, Any], *keys: str, default: Any = "") -> Any:
    lookup = {normalized_key(str(key)): value for key, value in data.items()}
    for key in keys:
        normalized = normalized_key(key)
        if normalized in lookup and lookup[normalized] not in (None, "", []):
            return lookup[normalized]
    return default


def dictionaries(value: Any) -> Iterable[dict[str, Any]]:
    if isinstance(value, dict):
        yield value
        for nested in value.values():
            yield from dictionaries(nested)
    elif isinstance(value, list):
        for item in value:
            yield from dictionaries(item)


def strings(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        return (value,) if value.strip() else ()
    if isinstance(value, list):
        return tuple(str(item) for item in value if str(item).strip())
    return (str(value),)


def person_candidates(
    payload: Any,
    *,
    source_url: str,
    confidence: int = 75,
    evidence_status: str = EvidenceStatus.OBSERVED,
) -> tuple[PersonCandidate, ...]:
    people: list[PersonCandidate] = []
    seen: set[tuple[str, str]] = set()
    for index, record in enumerate(dictionaries(payload)):
        name = str(pick(record, "full_name", "fullname", "nome_completo", "name", "nome")).strip()
        role = str(
            pick(record, "qualification", "qualificacao", "title", "cargo", "position", "role")
        ).strip()
        if not name or not role:
            continue
        external_key = str(
            pick(record, "external_id", "id", "linkedin_url", default=f"{name}:{role}:{index}")
        )
        identity = (name.casefold(), external_key)
        if identity in seen:
            continue
        seen.add(identity)
        contacts: list[ContactCandidate] = []
        for email in strings(pick(record, "emails", "email", "personal_email", default=[])):
            contacts.append(
                ContactCandidate(
                    kind=ContactPoint.Kind.EMAIL,
                    value=email,
                    confidence=confidence,
                    evidence_status=evidence_status,
                    source_url=source_url,
                    external_id=external_key,
                )
            )
        for phone in strings(pick(record, "phones", "phone", "telefone", "celular", default=[])):
            contacts.append(
                ContactCandidate(
                    kind=ContactPoint.Kind.PHONE,
                    value=phone,
                    confidence=confidence,
                    evidence_status=evidence_status,
                    source_url=source_url,
                    external_id=external_key,
                )
            )
        for phone in strings(pick(record, "whatsapp", "whatsapps", default=[])):
            contacts.append(
                ContactCandidate(
                    kind=ContactPoint.Kind.WHATSAPP,
                    value=phone,
                    confidence=confidence,
                    evidence_status=evidence_status,
                    source_url=source_url,
                    external_id=external_key,
                    metadata={"explicit_whatsapp_field": True},
                )
            )
        socials: list[SocialCandidate] = []
        networks = (
            (SocialProfile.Network.LINKEDIN, ("linkedin", "linkedin_url", "linkedinurl")),
            (SocialProfile.Network.INSTAGRAM, ("instagram", "instagram_url")),
            (SocialProfile.Network.FACEBOOK, ("facebook", "facebook_url")),
        )
        for network, aliases in networks:
            for url in strings(pick(record, *aliases, default=[])):
                socials.append(
                    SocialCandidate(
                        network=network,
                        profile_url=url,
                        confidence=confidence,
                        evidence_status=evidence_status,
                        source_url=source_url,
                        external_id=external_key,
                    )
                )
        people.append(
            PersonCandidate(
                full_name=name,
                external_key=external_key,
                qualification=role[:80],
                observed_title=role[:160],
                buying_role="Decisor potencial",
                buying_role_is_inferred=True,
                confidence=confidence,
                evidence_status=evidence_status,
                contacts=tuple(contacts),
                socials=tuple(socials),
                source_url=source_url,
            )
        )
    return tuple(people)
