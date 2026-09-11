from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any

import httpx

from .base import BaseCRMConnector, ConnectionTestResult, SyncResult

if TYPE_CHECKING:
    from leadstream.integrations.models import CRMConnection, CRMFieldMapping


class SalesforceConnector(BaseCRMConnector):
    connector_type = "SALESFORCE"

    def _get_base_url(self, connection: CRMConnection) -> str:
        url = str(connection.credentials.get("instance_url", "")).strip()
        return url.rstrip("/")

    def _get_headers(self, connection: CRMConnection) -> dict[str, str]:
        token = str(connection.credentials.get("access_token", "")).strip()
        return {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": "LeadStream-Salesforce-Connector/1.0",
        }

    def test_connection(self, connection: CRMConnection) -> ConnectionTestResult:
        base_url = self._get_base_url(connection)
        if not base_url:
            return ConnectionTestResult(
                success=False,
                message="Instance URL do Salesforce não informada.",
            )

        start = time.perf_counter()
        headers = self._get_headers(connection)
        try:
            with httpx.Client(timeout=self.timeout) as client:
                resp = client.get(f"{base_url}/services/data/v59.0/limits", headers=headers)
                latency = (time.perf_counter() - start) * 1000.0

                if resp.status_code == 200:
                    calls = resp.json().get("DailyApiRequests", {})
                    rem = calls.get("Remaining", "N/A")
                    max_req = calls.get("Max", "N/A")
                    return ConnectionTestResult(
                        success=True,
                        message=f"Conectado ao Salesforce. Requisições: {rem}/{max_req}.",
                        remote_account_info=calls if isinstance(calls, dict) else {},
                        latency_ms=round(latency, 2),
                    )
                err_snippet = resp.text[:60]
                return ConnectionTestResult(
                    success=False,
                    message=f"Falha no Salesforce ({resp.status_code}): {err_snippet}",
                    latency_ms=round(latency, 2),
                )
        except Exception as exc:  # noqa: BLE001
            latency = (time.perf_counter() - start) * 1000.0
            return ConnectionTestResult(
                success=False,
                message=f"Erro ao conectar com Salesforce: {exc}",
                latency_ms=round(latency, 2),
            )

    def sync_company(
        self,
        connection: CRMConnection,
        data: dict[str, Any],
        mapping: list[CRMFieldMapping],
    ) -> SyncResult:
        mapped = self.apply_mapping(data, mapping)
        payload = {
            "Name": mapped.get("razao_social") or mapped.get("name", "Nova Conta"),
            "Phone": mapped.get("telefone") or mapped.get("phone", ""),
            "BillingCity": mapped.get("municipio") or mapped.get("city", ""),
            "BillingState": mapped.get("uf") or mapped.get("state", ""),
        }
        for k, v in mapped.items():
            if k not in payload and v is not None:
                payload[k] = str(v)

        return self._post_object(connection, "/services/data/v59.0/sobjects/Account", payload)

    def sync_contact(
        self,
        connection: CRMConnection,
        data: dict[str, Any],
        mapping: list[CRMFieldMapping],
    ) -> SyncResult:
        mapped = self.apply_mapping(data, mapping)
        full_name = mapped.get("nome_decisor") or mapped.get("name", "Contato")
        parts = str(full_name).split()
        first_name = parts[0] if parts else ""
        last_name = " ".join(parts[1:]) if len(parts) > 1 else (parts[0] if parts else "Lead")

        payload = {
            "FirstName": mapped.get("primeiro_nome") or first_name,
            "LastName": mapped.get("sobrenome") or last_name,
            "Email": mapped.get("email_direto") or mapped.get("email", ""),
            "Phone": mapped.get("telefone_direto") or mapped.get("phone", ""),
            "Title": mapped.get("cargo_observado") or mapped.get("jobtitle", ""),
        }
        for k, v in mapped.items():
            if k not in payload and v is not None:
                payload[k] = str(v)

        return self._post_object(connection, "/services/data/v59.0/sobjects/Contact", payload)

    def _post_object(
        self, connection: CRMConnection, endpoint: str, payload: dict[str, Any]
    ) -> SyncResult:
        base_url = self._get_base_url(connection)
        headers = self._get_headers(connection)
        url = f"{base_url}{endpoint}"
        try:
            with httpx.Client(timeout=self.timeout) as client:
                resp = client.post(url, json=payload, headers=headers)
                if 200 <= resp.status_code < 300:
                    res = (
                        resp.json()
                        if "application/json" in resp.headers.get("content-type", "")
                        else {}
                    )
                    return SyncResult(
                        success=True,
                        status_code=resp.status_code,
                        remote_id=str(res.get("id", "")),
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
                    error_code=f"SALESFORCE_{resp.status_code}",
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
