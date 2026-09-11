from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any

import httpx

from .base import BaseCRMConnector, ConnectionTestResult, SyncResult

if TYPE_CHECKING:
    from leadstream.integrations.models import CRMConnection, CRMFieldMapping


class RDStationConnector(BaseCRMConnector):
    connector_type = "RD_STATION"
    BASE_URL = "https://crm.rdstation.com/api/v1"

    def _get_token(self, connection: CRMConnection) -> str:
        return str(connection.credentials.get("token", "")).strip()

    def test_connection(self, connection: CRMConnection) -> ConnectionTestResult:
        token = self._get_token(connection)
        if not token:
            return ConnectionTestResult(
                success=False,
                message="Token da API do RD Station não informado.",
            )

        start = time.perf_counter()
        try:
            with httpx.Client(timeout=self.timeout) as client:
                resp = client.get(f"{self.BASE_URL}/users", params={"token": token})
                latency = (time.perf_counter() - start) * 1000.0

                if resp.status_code == 200:
                    return ConnectionTestResult(
                        success=True,
                        message="Conectado com sucesso ao RD Station CRM.",
                        latency_ms=round(latency, 2),
                    )
                err_snippet = resp.text[:60]
                return ConnectionTestResult(
                    success=False,
                    message=f"Falha no RD Station ({resp.status_code}): {err_snippet}",
                    latency_ms=round(latency, 2),
                )
        except Exception as exc:  # noqa: BLE001
            latency = (time.perf_counter() - start) * 1000.0
            return ConnectionTestResult(
                success=False,
                message=f"Erro de conexão com o RD Station: {exc}",
                latency_ms=round(latency, 2),
            )

    def sync_company(
        self,
        connection: CRMConnection,
        data: dict[str, Any],
        mapping: list[CRMFieldMapping],
    ) -> SyncResult:
        mapped = self.apply_mapping(data, mapping)
        org_data = {
            "name": mapped.get("razao_social") or mapped.get("name", "Nova Empresa"),
            "resume": f"CNPJ: {mapped.get('cnpj', '')}",
        }
        for k, v in mapped.items():
            if k not in org_data and v is not None:
                org_data[k] = v

        return self._post_object(connection, "/organizations", {"organization": org_data})

    def sync_contact(
        self,
        connection: CRMConnection,
        data: dict[str, Any],
        mapping: list[CRMFieldMapping],
    ) -> SyncResult:
        mapped = self.apply_mapping(data, mapping)
        email = mapped.get("email_direto") or mapped.get("email")
        phone = mapped.get("telefone_direto") or mapped.get("phone")

        contact_data: dict[str, Any] = {
            "name": mapped.get("nome_decisor") or mapped.get("name", "Novo Contato"),
            "title": mapped.get("cargo_observado") or mapped.get("jobtitle", ""),
        }
        if email:
            contact_data["emails"] = [{"email": str(email)}]
        if phone:
            contact_data["phones"] = [{"phone": str(phone)}]

        for k, v in mapped.items():
            if k not in ["name", "title", "emails", "phones"] and v is not None:
                contact_data[k] = v

        return self._post_object(connection, "/contacts", {"contact": contact_data})

    def _post_object(
        self, connection: CRMConnection, endpoint: str, payload: dict[str, Any]
    ) -> SyncResult:
        token = self._get_token(connection)
        url = f"{self.BASE_URL}{endpoint}"
        try:
            with httpx.Client(timeout=self.timeout) as client:
                resp = client.post(url, json=payload, params={"token": token})
                if 200 <= resp.status_code < 300:
                    res = (
                        resp.json()
                        if "application/json" in resp.headers.get("content-type", "")
                        else {}
                    )
                    return SyncResult(
                        success=True,
                        status_code=resp.status_code,
                        remote_id=str(res.get("id", "") or res.get("_id", "")),
                        response_payload=res if isinstance(res, dict) else {},
                    )

                retry_after: int | None = None
                if resp.status_code == 429:
                    raw_ra = resp.headers.get("Retry-After")
                    if raw_ra and raw_ra.isdigit():
                        retry_after = int(raw_ra)

                return SyncResult(
                    success=False,
                    status_code=resp.status_code,
                    error_code=f"RDSTATION_{resp.status_code}",
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
