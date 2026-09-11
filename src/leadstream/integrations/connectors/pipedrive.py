from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any

import httpx

from .base import BaseCRMConnector, ConnectionTestResult, SyncResult

if TYPE_CHECKING:
    from leadstream.integrations.models import CRMConnection, CRMFieldMapping


class PipedriveConnector(BaseCRMConnector):
    connector_type = "PIPEDRIVE"
    BASE_URL = "https://api.pipedrive.com/v1"

    def _get_token(self, connection: CRMConnection) -> str:
        return str(connection.credentials.get("api_token", "")).strip()

    def test_connection(self, connection: CRMConnection) -> ConnectionTestResult:
        token = self._get_token(connection)
        if not token:
            return ConnectionTestResult(
                success=False,
                message="API Token do Pipedrive não informado.",
            )

        start = time.perf_counter()
        try:
            with httpx.Client(timeout=self.timeout) as client:
                resp = client.get(f"{self.BASE_URL}/users/me", params={"api_token": token})
                latency = (time.perf_counter() - start) * 1000.0

                if resp.status_code == 200:
                    data = resp.json().get("data", {})
                    return ConnectionTestResult(
                        success=True,
                        message=f"Conectado ao Pipedrive (Usuário: {data.get('name', 'N/A')}).",
                        remote_account_info=data if isinstance(data, dict) else {},
                        latency_ms=round(latency, 2),
                    )
                err_snippet = resp.text[:60]
                return ConnectionTestResult(
                    success=False,
                    message=f"Falha no Pipedrive ({resp.status_code}): {err_snippet}",
                    latency_ms=round(latency, 2),
                )
        except Exception as exc:  # noqa: BLE001
            latency = (time.perf_counter() - start) * 1000.0
            return ConnectionTestResult(
                success=False,
                message=f"Erro de conexão com o Pipedrive: {exc}",
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
            "name": mapped.get("razao_social") or mapped.get("name", "Nova Empresa"),
            "address": mapped.get("logradouro") or mapped.get("address", ""),
        }
        for k, v in mapped.items():
            if k not in payload and v is not None:
                payload[k] = v

        return self._post_object(connection, "/organizations", payload)

    def sync_contact(
        self,
        connection: CRMConnection,
        data: dict[str, Any],
        mapping: list[CRMFieldMapping],
    ) -> SyncResult:
        mapped = self.apply_mapping(data, mapping)
        email = mapped.get("email_direto") or mapped.get("email")
        phone = mapped.get("telefone_direto") or mapped.get("phone")

        payload: dict[str, Any] = {
            "name": mapped.get("nome_decisor") or mapped.get("name", "Novo Contato"),
        }
        if email:
            payload["email"] = [{"value": str(email), "primary": True}]
        if phone:
            payload["phone"] = [{"value": str(phone), "primary": True}]

        for k, v in mapped.items():
            if k not in ["name", "email", "phone"] and v is not None:
                payload[k] = v

        return self._post_object(connection, "/persons", payload)

    def _post_object(
        self, connection: CRMConnection, endpoint: str, payload: dict[str, Any]
    ) -> SyncResult:
        token = self._get_token(connection)
        url = f"{self.BASE_URL}{endpoint}"
        try:
            with httpx.Client(timeout=self.timeout) as client:
                resp = client.post(url, json=payload, params={"api_token": token})
                if 200 <= resp.status_code < 300:
                    res = resp.json().get("data", {})
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
                    error_code=f"PIPEDRIVE_{resp.status_code}",
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
