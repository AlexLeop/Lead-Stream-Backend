from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from typing import Any

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from leadstream.batches.models import BatchItem
from leadstream.billing.models import DataBlock
from leadstream.entities.models import Company, ContactPoint, Relationship
from leadstream.entities.normalization import DataValidationError, fingerprint_value
from leadstream.entities.services import (
    create_contact_point,
    create_person,
    create_relationship,
    create_social_profile,
)
from leadstream.evidence.models import (
    Evidence,
    EvidenceStatus,
    Observation,
    ProcessingPurpose,
    RetentionPolicy,
    Source,
    SourceRecord,
)
from leadstream.evidence.services import append_observation, canonicalize
from leadstream.governance.models import Suppression
from leadstream.governance.services import is_suppressed

from .contracts import FieldObservation, PersonCandidate, ProviderResult
from .models import ProviderPolicy


@dataclass(frozen=True)
class BlockQuality:
    status: str
    confidence: int
    fingerprint: str


def _governance(
    item: BatchItem, policy: ProviderPolicy
) -> tuple[Source, ProcessingPurpose, RetentionPolicy]:
    tenant = item.tenant
    category = (
        Source.Category.GOVERNMENT
        if policy.provider == "open-cnpj-bigquery"
        else Source.Category.COMMERCIAL
    )
    source, _ = Source.objects.get_or_create(
        tenant=tenant,
        slug=policy.provider,
        defaults={
            "name": policy.display_name,
            "category": category,
            "priority": max(1, 100 - policy.priority),
        },
    )
    purpose, _ = ProcessingPurpose.objects.get_or_create(
        tenant=tenant,
        code="prospeccao-b2b",
        defaults={
            "name": "Prospecção B2B",
            "description": "Identificação de decisores para relacionamento profissional.",
            "operational_basis": "Legítimo interesse documentado e sujeito a oposição.",
        },
    )
    retention, _ = RetentionPolicy.objects.get_or_create(
        tenant=tenant,
        code="contato-profissional",
        defaults={
            "name": "Contato profissional",
            "stale_after_days": 90,
            "retention_days": 365,
        },
    )
    return source, purpose, retention


def _evidence(
    *,
    record: SourceRecord,
    value: Any,
    method: str,
    source_url: str,
    external_id: str,
    metadata: dict[str, Any] | None = None,
) -> Evidence:
    content_hash = fingerprint_value(value)
    return Evidence.objects.create(
        tenant=record.tenant,
        source_record=record,
        url=source_url,
        external_id=external_id or str(record.pk),
        captured_at=record.captured_at,
        observed_at=record.captured_at,
        method=method,
        excerpt_hash=content_hash,
        content_hash=content_hash,
        metadata=metadata or {},
    )


def _observe(*, record: SourceRecord, target: Any, observation: FieldObservation) -> Observation:
    value_hash = fingerprint_value(observation.value)
    existing: Observation | None = Observation.objects.filter(
        tenant=record.tenant,
        target=target,
        source_record=record,
        field_path=observation.field_path,
        value_fingerprint=value_hash,
    ).first()
    if existing is not None:
        return existing
    evidence = _evidence(
        record=record,
        value=observation.value,
        method=observation.method,
        source_url=observation.source_url,
        external_id=observation.external_id,
        metadata=observation.metadata,
    )
    created = append_observation(
        tenant=record.tenant,
        target=target,
        source_record=record,
        field_path=observation.field_path,
        value=observation.value,
        status=observation.evidence_status,
        confidence=observation.confidence,
        method=observation.method,
        observed_at=observation.observed_at,
        captured_at=record.captured_at,
        evidence_items=(evidence,),
    )
    canonicalize(tenant=record.tenant, target=target, field_path=observation.field_path)
    return created


def _contact_block(kind: str) -> str:
    if kind == ContactPoint.Kind.EMAIL:
        return DataBlock.DIRECT_EMAIL
    if kind == ContactPoint.Kind.WHATSAPP:
        return DataBlock.WHATSAPP
    return DataBlock.DIRECT_PHONE


def _quality_update(
    qualities: dict[str, BlockQuality], block: str, status: str, confidence: int, value: Any
) -> None:
    candidate = BlockQuality(
        status=status,
        confidence=confidence,
        fingerprint=fingerprint_value(value),
    )
    current = qualities.get(block)
    rank: dict[str, int] = {
        EvidenceStatus.OBSERVED: 1,
        EvidenceStatus.INFERRED: 0,
        EvidenceStatus.TECHNICALLY_VALIDATED: 2,
        EvidenceStatus.CONFIRMED: 3,
    }
    if current is None or (rank.get(status, -1), confidence) > (
        rank.get(current.status, -1),
        current.confidence,
    ):
        qualities[block] = candidate


def _choice_key(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    without_accents = "".join(
        character for character in normalized if not unicodedata.combining(character)
    )
    return " ".join(without_accents.casefold().replace("_", "-").split())


def _relationship_qualification(value: str) -> str:
    key = _choice_key(value)
    choices = {choice.casefold(): choice for choice in Relationship.Qualification.values}
    if value.casefold() in choices:
        return choices[value.casefold()]
    if key in {"representante legal", "legal representative"}:
        return Relationship.Qualification.LEGAL_REPRESENTATIVE
    if key in {"administrador", "administradora", "administrator", "socio-administrador"}:
        return Relationship.Qualification.ADMINISTRATOR
    if key in {"socio", "socia", "partner", "owner", "proprietario", "proprietaria"}:
        return Relationship.Qualification.PARTNER
    if key in {"funcionario", "funcionaria", "employee"}:
        return Relationship.Qualification.EMPLOYEE
    return Relationship.Qualification.OTHER


def _relationship_seniority(value: str) -> str:
    key = _choice_key(value)
    choices = {choice.casefold(): choice for choice in Relationship.Seniority.values}
    if value.casefold() in choices:
        return choices[value.casefold()]
    if any(term in key for term in ("owner", "proprietario", "fundador", "founder")):
        return Relationship.Seniority.OWNER
    if any(term in key for term in ("c-level", "ceo", "cfo", "cto", "coo", "presidente")):
        return Relationship.Seniority.C_LEVEL
    if any(term in key for term in ("diretor", "director")):
        return Relationship.Seniority.DIRECTOR
    if any(term in key for term in ("gerente", "manager")):
        return Relationship.Seniority.MANAGER
    if any(term in key for term in ("coordenador", "coordinator")):
        return Relationship.Seniority.COORDINATOR
    return Relationship.Seniority.UNKNOWN if not key else Relationship.Seniority.OTHER


def _persist_person(
    *,
    item: BatchItem,
    company: Company,
    record: SourceRecord,
    candidate: PersonCandidate,
    qualities: dict[str, BlockQuality],
) -> None:
    person = create_person(
        tenant=item.tenant,
        full_name=candidate.full_name,
        external_key=f"{record.source.slug}:{candidate.external_key}",
        hash_key=settings.DATA_HASH_KEY,
    )
    create_relationship(
        tenant=item.tenant,
        person=person,
        company=company,
        qualification=_relationship_qualification(candidate.qualification),
        observed_title=candidate.observed_title,
        seniority=_relationship_seniority(candidate.seniority),
        buying_role=candidate.buying_role,
        buying_role_is_inferred=candidate.buying_role_is_inferred,
    )
    _observe(
        record=record,
        target=person.entity,
        observation=FieldObservation(
            field_path="person.full_name",
            value=candidate.full_name,
            confidence=candidate.confidence,
            evidence_status=candidate.evidence_status,
            method="API" if record.source.category == Source.Category.COMMERCIAL else "DATASET",
            source_url=candidate.source_url,
            external_id=fingerprint_value(candidate.external_key),
        ),
    )
    has_decision_role = (
        candidate.buying_role and not candidate.buying_role_is_inferred
    ) or candidate.qualification.casefold() in {
        "administrador",
        "administradora",
        "administrator",
        "socio-administrador",
        "socio",
        "socia",
        "partner",
        "owner",
        "proprietario",
        "proprietaria",
        "diretor",
        "diretora",
        "director",
        "representante legal",
        "legal representative",
    }
    if has_decision_role:
        _quality_update(
            qualities,
            DataBlock.DECISION_MAKER,
            candidate.evidence_status,
            candidate.confidence,
            (candidate.full_name, candidate.buying_role or candidate.qualification),
        )
    for contact_candidate in candidate.contacts:
        scope = (
            Suppression.Scope.EMAIL
            if contact_candidate.kind == ContactPoint.Kind.EMAIL
            else Suppression.Scope.PHONE
        )
        if is_suppressed(tenant=item.tenant, scope=scope, value=contact_candidate.value):
            continue
        field_path = f"person.contact.{contact_candidate.kind.casefold()}"
        try:
            create_contact_point(
                tenant=item.tenant,
                owner=person.entity,
                kind=contact_candidate.kind,
                value=contact_candidate.value,
            )
            contact_status = contact_candidate.evidence_status
        except DataValidationError:
            contact_status = EvidenceStatus.REJECTED
        _observe(
            record=record,
            target=person.entity,
            observation=FieldObservation(
                field_path=field_path,
                value=contact_candidate.value,
                confidence=contact_candidate.confidence,
                evidence_status=contact_status,
                method="API",
                source_url=contact_candidate.source_url,
                external_id=contact_candidate.external_id,
                metadata=contact_candidate.metadata,
            ),
        )
        if contact_status != EvidenceStatus.REJECTED:
            _quality_update(
                qualities,
                _contact_block(contact_candidate.kind),
                contact_status
                if candidate.evidence_status == EvidenceStatus.CONFIRMED
                else candidate.evidence_status,
                min(contact_candidate.confidence, candidate.confidence),
                contact_candidate.value,
            )
    for social in candidate.socials:
        try:
            create_social_profile(
                tenant=item.tenant,
                owner=person.entity,
                network=social.network,
                profile_url=social.profile_url,
                handle=social.handle,
            )
            social_status = social.evidence_status
        except DataValidationError:
            social_status = EvidenceStatus.REJECTED
        _observe(
            record=record,
            target=person.entity,
            observation=FieldObservation(
                field_path=f"person.social.{social.network.casefold()}",
                value=social.profile_url,
                confidence=social.confidence,
                evidence_status=social_status,
                method="API",
                source_url=social.source_url,
                external_id=social.external_id,
            ),
        )
        if social_status != EvidenceStatus.REJECTED:
            _quality_update(
                qualities,
                DataBlock.SOCIAL_PROFILES,
                social_status
                if candidate.evidence_status == EvidenceStatus.CONFIRMED
                else candidate.evidence_status,
                min(social.confidence, candidate.confidence),
                social.profile_url,
            )


@transaction.atomic
def persist_provider_result(
    *, item: BatchItem, policy: ProviderPolicy, result: ProviderResult, call_id: object
) -> dict[str, BlockQuality]:
    if item.entity_id is None:
        raise DataValidationError("Item sem empresa canônica para enriquecimento.")
    company = Company.objects.get(entity=item.entity, entity__tenant=item.tenant)
    source, purpose, retention = _governance(item, policy)
    source_url = next(
        (obs.source_url for obs in result.observations if obs.source_url),
        next((person.source_url for person in result.people if person.source_url), ""),
    )
    record, _ = SourceRecord.objects.get_or_create(
        tenant=item.tenant,
        source=source,
        external_id=str(call_id),
        defaults={
            "purpose": purpose,
            "retention_policy": retention,
            "source_url": source_url,
            "captured_at": timezone.now(),
            "payload_hash": result.raw_payload_hash,
        },
    )
    qualities: dict[str, BlockQuality] = {}
    normalized_updates: dict[str, Any] = dict(item.normalized_data or {})
    field_to_norm_key = {
        "company.legal_name": "razao_social",
        "company.trade_name": "nome_fantasia",
        "company.registration_status": "situacao_cadastral",
        "company.primary_cnae": "cnae_fiscal",
        "company.secondary_cnaes": "cnaes_secundarios",
        "company.city": "municipio",
        "company.state": "uf",
        "company.tipo_logradouro": "tipo_logradouro",
        "company.logradouro": "logradouro",
        "company.numero": "numero",
        "company.complemento": "complemento",
        "company.bairro": "bairro",
        "company.cep": "cep",
        "company.capital_social": "capital_social",
        "company.porte": "porte",
        "company.natureza_juridica": "natureza_juridica",
        "company.data_inicio_atividade": "data_inicio_atividade",
        "company.data_situacao_cadastral": "data_situacao_cadastral",
        "company.motivo_situacao_cadastral": "motivo_situacao_cadastral",
        "company.codigo_municipio_ibge": "codigo_municipio_ibge",
    }
    for observation in result.observations:
        _observe(record=record, target=item.entity, observation=observation)
        if observation.field_path.startswith("company."):
            _quality_update(
                qualities,
                DataBlock.COMPANY_REGISTRY,
                observation.evidence_status,
                observation.confidence,
                observation.value,
            )
            if observation.field_path == "company.legal_name" and observation.value:
                company.legal_name = str(observation.value)
                company.save(update_fields=["legal_name", "updated_at"])
            elif observation.field_path == "company.trade_name" and observation.value:
                company.trade_name = str(observation.value)
                company.save(update_fields=["trade_name", "updated_at"])
            elif observation.field_path == "company.registration_status" and observation.value:
                company.registration_status = str(observation.value)
                company.save(update_fields=["registration_status", "updated_at"])
            norm_key = field_to_norm_key.get(observation.field_path)
            if norm_key and observation.value not in (None, ""):
                normalized_updates[norm_key] = observation.value

    qsa_list: list[dict[str, Any]] = list(normalized_updates.get("qsa") or [])
    existing_qsa_names = {
        str(entry.get("nome_socio") or entry.get("nome") or "").strip().upper()
        for entry in qsa_list
        if isinstance(entry, dict)
    }
    for candidate in result.people:
        _persist_person(
            item=item,
            company=company,
            record=record,
            candidate=candidate,
            qualities=qualities,
        )
        cand_name = candidate.full_name.strip()
        if cand_name and cand_name.upper() not in existing_qsa_names:
            socio_entry: dict[str, Any] = {
                "nome_socio": cand_name,
                "qualificacao_socio": candidate.qualification,
                "faixa_etaria": None,
            }
            for soc in candidate.socials:
                if soc.network.upper() == "LINKEDIN":
                    socio_entry["linkedin_url"] = soc.profile_url
            for cont in candidate.contacts:
                if (
                    cont.kind == ContactPoint.Kind.EMAIL
                    and "correio_eletronico" not in normalized_updates
                ):
                    normalized_updates["correio_eletronico"] = cont.value
                    normalized_updates["email"] = cont.value
                elif (
                    cont.kind in (ContactPoint.Kind.PHONE, ContactPoint.Kind.WHATSAPP)
                    and "ddd_telefone_1" not in normalized_updates
                ):
                    normalized_updates["ddd_telefone_1"] = cont.value
                    normalized_updates["telefone"] = cont.value
            qsa_list.append(socio_entry)
            existing_qsa_names.add(cand_name.upper())

    if qsa_list:
        normalized_updates["qsa"] = qsa_list

    item.normalized_data = normalized_updates
    item.save(update_fields=["normalized_data", "updated_at"])
    return qualities
