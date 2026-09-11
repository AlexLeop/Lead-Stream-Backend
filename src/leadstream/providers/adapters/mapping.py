from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from typing import Any

from leadstream.entities.models import ContactPoint, SocialProfile
from leadstream.entities.normalization import normalize_linkedin_url
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
                clean_url = (
                    normalize_linkedin_url(url)
                    if network == SocialProfile.Network.LINKEDIN
                    else url
                )
                socials.append(
                    SocialCandidate(
                        network=network,
                        profile_url=clean_url,
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


def google_serp_linkedin_candidates(
    payload: Any,
    *,
    source_url: str,
    confidence: int = 75,
    evidence_status: str = EvidenceStatus.OBSERVED,
    expected_names: Iterable[str] = (),
) -> tuple[PersonCandidate, ...]:
    people: list[PersonCandidate] = []
    seen_urls: set[str] = set()
    normalized_expected = {
        normalized_key(str(name)) for name in expected_names if name and str(name).strip()
    }

    organic_list: list[dict[str, Any]] = []
    if isinstance(payload, list):
        for item in payload:
            if isinstance(item, dict):
                if "organicResults" in item and isinstance(item["organicResults"], list):
                    organic_list.extend(
                        res for res in item["organicResults"] if isinstance(res, dict)
                    )
                elif "url" in item and "linkedin.com" in str(item.get("url", "")):
                    organic_list.append(item)
    elif isinstance(payload, dict):
        if "organicResults" in payload and isinstance(payload["organicResults"], list):
            organic_list.extend(
                res for res in payload["organicResults"] if isinstance(res, dict)
            )

    for record in organic_list:
        url = str(record.get("url") or "").strip()
        if not url or "linkedin.com/in/" not in url:
            continue
        clean_url = normalize_linkedin_url(url)
        if not clean_url or clean_url in seen_urls:
            continue
        seen_urls.add(clean_url)

        title = str(record.get("title") or "").strip()
        snippet = str(record.get("description") or "").strip()

        clean_title = re.sub(r"\s*\|\s*LinkedIn.*$", "", title, flags=re.IGNORECASE).strip()
        parts = re.split(r"\s+[-\u2013\u2014]\s+", clean_title)
        extracted_name = parts[0].strip() if parts else clean_title
        extracted_role = parts[1].strip() if len(parts) > 1 else (snippet[:100] or "Decisor")
        if re.search(r"LinkedIn", extracted_role, flags=re.IGNORECASE):
            extracted_role = "Decisor"

        if not extracted_name:
            continue

        item_confidence = confidence
        norm_extracted = normalized_key(extracted_name)

        if normalized_expected:
            is_match = False
            for exp in normalized_expected:
                if exp == norm_extracted or exp in norm_extracted or norm_extracted in exp:
                    is_match = True
                    break
                tokens_exp = {t for t in exp.split() if len(t) > 2}
                tokens_ext = {t for t in norm_extracted.split() if len(t) > 2}
                if tokens_exp and tokens_ext and len(tokens_exp.intersection(tokens_ext)) >= 2:
                    is_match = True
                    break
            if is_match:
                item_confidence = max(confidence, 85)
            else:
                item_confidence = max(confidence - 15, 50)

        socials = (
            SocialCandidate(
                network=SocialProfile.Network.LINKEDIN,
                profile_url=clean_url,
                confidence=item_confidence,
                evidence_status=evidence_status,
                source_url=source_url,
                external_id=clean_url,
            ),
        )

        people.append(
            PersonCandidate(
                full_name=extracted_name,
                external_key=clean_url,
                qualification=extracted_role[:80],
                observed_title=extracted_role[:160],
                buying_role="Decisor potencial",
                buying_role_is_inferred=True,
                confidence=item_confidence,
                evidence_status=evidence_status,
                contacts=(),
                socials=socials,
                source_url=source_url,
            )
        )

    return tuple(people)

