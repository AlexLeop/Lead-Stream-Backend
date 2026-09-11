from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from leadstream.integrations.models import CRMConnection, CRMFieldMapping


@dataclass(frozen=True)
class ConnectionTestResult:
    success: bool
    message: str
    remote_account_info: dict[str, Any] = field(default_factory=dict)
    latency_ms: float = 0.0


@dataclass(frozen=True)
class SyncResult:
    success: bool
    remote_id: str = ""
    status_code: int = 200
    error_code: str = ""
    error_message: str = ""
    retry_after_seconds: int | None = None
    response_payload: dict[str, Any] = field(default_factory=dict)


class BaseCRMConnector(ABC):
    connector_type: str

    @property
    def timeout(self) -> float:
        from django.conf import settings

        return float(getattr(settings, "CRM_CONNECTOR_DEFAULT_TIMEOUT_SECONDS", 10))

    def apply_mapping(
        self,
        data: dict[str, Any],
        mapping: list[CRMFieldMapping],
    ) -> dict[str, Any]:
        """Aplica as regras de mapeamento configuradas pelo tenant.

        Se não houver mapeamento específico para um campo, o valor original é mantido.
        """
        if not mapping:
            return dict(data)

        mapped: dict[str, Any] = {}
        # Primeiro, popula os campos mapeados explicitamente
        source_map = {m.source_field: m for m in mapping}
        for source_key, value in data.items():
            if source_key in source_map:
                m = source_map[source_key]
                val = self._transform_value(value, m.transformation)
                mapped[m.target_field] = val
            else:
                mapped[source_key] = value

        return mapped

    @staticmethod
    def _transform_value(val: Any, transformation: str) -> Any:
        if val is None:
            return None
        text = str(val)
        match transformation:
            case "LOWER":
                return text.lower()
            case "UPPER":
                return text.upper()
            case "DIGITS_ONLY":
                return "".join(c for c in text if c.isdigit())
            case "FIRST_NAME":
                return text.split()[0] if text.split() else text
            case "LAST_NAME":
                parts = text.split()
                return " ".join(parts[1:]) if len(parts) > 1 else ""
            case _:
                return val

    @abstractmethod
    def test_connection(self, connection: CRMConnection) -> ConnectionTestResult:
        """Valida credenciais e conectividade com a API externa."""

    @abstractmethod
    def sync_company(
        self,
        connection: CRMConnection,
        data: dict[str, Any],
        mapping: list[CRMFieldMapping],
    ) -> SyncResult:
        """Envia ou atualiza dados da empresa no CRM."""

    @abstractmethod
    def sync_contact(
        self,
        connection: CRMConnection,
        data: dict[str, Any],
        mapping: list[CRMFieldMapping],
    ) -> SyncResult:
        """Envia ou atualiza dados do decisor/contato no CRM."""

    def sync_deal(
        self,
        connection: CRMConnection,
        data: dict[str, Any],
        mapping: list[CRMFieldMapping],
    ) -> SyncResult:
        """Opcional: Abre oportunidade/negócio no funil do CRM."""
        del connection, data, mapping
        return SyncResult(
            success=True,
            remote_id="",
        )
