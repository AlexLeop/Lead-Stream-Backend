from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Protocol

from leadstream.batches.models import Batch, BatchItem
from leadstream.tenancy.models import Tenant


@dataclass(frozen=True)
class ContactCandidate:
    kind: str
    value: str
    confidence: int
    evidence_status: str = "OBSERVED"
    source_url: str = ""
    external_id: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SocialCandidate:
    network: str
    profile_url: str
    confidence: int
    evidence_status: str = "OBSERVED"
    handle: str = ""
    source_url: str = ""
    external_id: str = ""


@dataclass(frozen=True)
class PersonCandidate:
    full_name: str
    external_key: str
    qualification: str
    observed_title: str = ""
    seniority: str = "UNKNOWN"
    buying_role: str = ""
    buying_role_is_inferred: bool = False
    confidence: int = 70
    evidence_status: str = "OBSERVED"
    contacts: tuple[ContactCandidate, ...] = ()
    socials: tuple[SocialCandidate, ...] = ()
    source_url: str = ""


@dataclass(frozen=True)
class FieldObservation:
    field_path: str
    value: Any
    confidence: int
    evidence_status: str
    method: str
    source_url: str = ""
    external_id: str = ""
    observed_at: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ProviderContext:
    tenant: Tenant
    batch: Batch
    item: BatchItem
    cnpj: str
    missing_blocks: frozenset[str]
    call_id: str | None = None
    execution_token: str = ""


@dataclass(frozen=True)
class ProviderQuota:
    """Quota externa compartilhada, medida em requisições reais ao provedor."""

    scope: str
    requests_per_minute: int
    units: int = 1


@dataclass(frozen=True)
class ProviderResult:
    outcome: str
    confirmed_cost_cents: int
    observations: tuple[FieldObservation, ...] = ()
    people: tuple[PersonCandidate, ...] = ()
    company_contacts: tuple[ContactCandidate, ...] = ()
    delivered_blocks: frozenset[str] = frozenset()
    external_request_id: str = ""
    raw_payload_hash: str = ""


class ProviderAdapter(Protocol):
    slug: str

    def is_configured(self) -> bool: ...

    def enrich(self, context: ProviderContext) -> ProviderResult: ...
