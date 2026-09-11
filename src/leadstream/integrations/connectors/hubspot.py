from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any

import httpx

from .base import BaseCRMConnector, ConnectionTestResult, SyncResult

if TYPE_CHECKING:
    from leadstream.integrations.models import CRMConnection, CRMFieldMapping


class HubSpotConnector(BaseCRMConnector):
    connector_type = "HUBSPOT"
    BASE_URL = "https://api.hubapi.com"

    def _get_headers(self, connection: CRMConnection) -> dict[str, str]:
        token = str(connection.credentials.get("access_token", "")).strip()
        return {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": "LeadStream-HubSpot-Connector/1.0",
        }

    def test_connection(self, connection: CRMConnection) -> ConnectionTestResult:
        token = str(connection.credentials.get("access_token", "")).strip()
        if not token:
            return ConnectionTestResult(
                success=False,
                message="Access Token do HubSpot não informado.",
            )

        start = time.perf_counter()
        headers = self._get_headers(connection)
        try:
            with httpx.Client(timeout=self.timeout) as client:
                resp = client.get(f"{self.BASE_URL}/account-info/v3/details", headers=headers)
                latency = (time.perf_counter() - start) * 1000.0

                if resp.status_code == 200:
                    info = (
                        resp.json()
                        if "application/json" in resp.headers.get("content-type", "")
                        else {}
                    )
                    return ConnectionTestResult(
                        success=True,
                        message=f"Conectado ao HubSpot (Portal ID: {info.get('portalId', 'N/A')}).",
                        remote_account_info=info if isinstance(info, dict) else {},
                        latency_ms=round(latency, 2),
                    )
                err_snippet = resp.text[:60]
                return ConnectionTestResult(
                    success=False,
                    message=f"Falha no HubSpot ({resp.status_code}): {err_snippet}",
                    latency_ms=round(latency, 2),
                )
        except Exception as exc:  # noqa: BLE001
            latency = (time.perf_counter() - start) * 1000.0
            return ConnectionTestResult(
                success=False,
                message=f"Erro de conexão com o HubSpot: {exc}",
                latency_ms=round(latency, 2),
            )

    def sync_company(
        self,
        connection: CRMConnection,
        data: dict[str, Any],
        mapping: list[CRMFieldMapping],
    ) -> SyncResult:
        mapped = self.apply_mapping(data, mapping)
        properties = {
            "name": mapped.get("razao_social") or mapped.get("name", ""),
            "domain": mapped.get("dominio") or mapped.get("domain", ""),
            "city": mapped.get("municipio") or mapped.get("city", ""),
            "state": mapped.get("uf") or mapped.get("state", ""),
            "phone": mapped.get("telefone") or mapped.get("phone", ""),
        }
        # Inclui outros campos mapeados
        for k, v in mapped.items():
            if k not in properties and v is not None:
                properties[k] = str(v)

        return self._post_object(
            connection, "/crm/v3/objects/companies", {"properties": properties}
        )

    def sync_contact(
        self,
        connection: CRMConnection,
        data: dict[str, Any],
        mapping: list[CRMFieldMapping],
    ) -> SyncResult:
        mapped = self.apply_mapping(data, mapping)
        full_name = mapped.get("nome_decisor") or mapped.get("name", "")
        parts = str(full_name).split()
        first_name = parts[0] if parts else ""
        last_name = " ".join(parts[1:]) if len(parts) > 1 else ""

        properties = {
            "email": mapped.get("email_direto") or mapped.get("email", ""),
            "firstname": mapped.get("primeiro_nome") or first_name,
            "lastname": mapped.get("sobrenome") or last_name,
            "phone": mapped.get("telefone_direto") or mapped.get("phone", ""),
            "jobtitle": mapped.get("cargo_observado") or mapped.get("jobtitle", ""),
        }
        for k, v in mapped.items():
            if k not in properties and v is not None:
                properties[k] = str(v)

        return self._post_object(connection, "/crm/v3/objects/contacts", {"properties": properties})

    def _post_object(
        self, connection: CRMConnection, endpoint: str, payload: dict[str, Any]
    ) -> SyncResult:
        headers = self._get_headers(connection)
        url = f"{self.BASE_URL}{endpoint}"
        try:
            with httpx.Client(timeout=self.timeout) as client:
                resp = client.post(url, json=payload, headers=headers)
                if 200 <= resp.status_code < 300:
                    data = (
                        resp.json()
                        if "application/json" in resp.headers.get("content-type", "")
                        else {}
                    )
                    return SyncResult(
                        success=True,
                        status_code=resp.status_code,
                        remote_id=str(data.get("id", "")),
                        response_payload=data if isinstance(data, dict) else {},
                    )

                retry_after: int | None = None
                if resp.status_code == 429:
                    raw_ra = resp.headers.get("Retry-After")
                    if raw_ra and raw_ra.isdigit():
                        retry_after = int(raw_ra)

                return SyncResult(
                    success=False,
                    status_code=resp.status_code,
                    error_code=f"HUBSPOT_{resp.status_code}",
                    error_message=resp.text[:500],
                    retry_after_seconds=retry_after,
                )
        except Exception as exc:  # noqa: BLE001
            return SyncResult(
                success=False,
                status_code=0,
                error_code="NETWORK_ERROR",
                error_message=str(exc),
            )
