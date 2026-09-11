from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any

import httpx

from .base import BaseCRMConnector, ConnectionTestResult, SyncResult

if TYPE_CHECKING:
    from leadstream.integrations.models import CRMConnection, CRMFieldMapping


class PloomesConnector(BaseCRMConnector):
    connector_type = "PLOOMES"
    BASE_URL = "https://api2.ploomes.com"

    def _get_headers(self, connection: CRMConnection) -> dict[str, str]:
        user_key = str(connection.credentials.get("user_key", "")).strip()
        return {
            "User-Key": user_key,
            "Content-Type": "application/json",
            "User-Agent": "LeadStream-Ploomes-Connector/1.0",
        }

    def test_connection(self, connection: CRMConnection) -> ConnectionTestResult:
        user_key = str(connection.credentials.get("user_key", "")).strip()
        if not user_key:
            return ConnectionTestResult(
                success=False,
                message="User-Key do Ploomes não informada.",
            )

        start = time.perf_counter()
        headers = self._get_headers(connection)
        try:
            with httpx.Client(timeout=10.0) as client:
                resp = client.get(f"{self.BASE_URL}/Self", headers=headers)
                latency = (time.perf_counter() - start) * 1000.0

                if resp.status_code == 200:
                    data = resp.json().get("value", [{}])
                    user_info = data[0] if isinstance(data, list) and data else {}
                    return ConnectionTestResult(
                        success=True,
                        message=f"Conectado ao Ploomes CRM ({user_info.get('Name', 'Usuário')}).",
                        remote_account_info=user_info if isinstance(user_info, dict) else {},
                        latency_ms=round(latency, 2),
                    )
                err_snippet = resp.text[:60]
                return ConnectionTestResult(
                    success=False,
                    message=f"Falha no Ploomes ({resp.status_code}): {err_snippet}",
                    latency_ms=round(latency, 2),
                )
        except Exception as exc:  # noqa: BLE001
            latency = (time.perf_counter() - start) * 1000.0
            return ConnectionTestResult(
                success=False,
                message=f"Erro de conexão com o Ploomes: {exc}",
                latency_ms=round(latency, 2),
            )

    def sync_company(
        self,
        connection: CRMConnection,
        data: dict[str, Any],
        mapping: list[CRMFieldMapping],
    ) -> SyncResult:
        mapped = self.apply_mapping(data, mapping)
        payload: dict[str, Any] = {
            "TypeId": 1,  # 1 = Empresa (Pessoa Jurídica) no Ploomes
            "Name": mapped.get("razao_social") or mapped.get("name", "Nova Empresa"),
            "CNPJ": mapped.get("cnpj", ""),
            "StreetAddress": mapped.get("logradouro") or mapped.get("address", ""),
        }
        for k, v in mapped.items():
            if k not in payload and v is not None:
                payload[k] = v

        return self._post_object(connection, "/Contacts", payload)

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
            "TypeId": 2,  # 2 = Pessoa Física no Ploomes
            "Name": mapped.get("nome_decisor") or mapped.get("name", "Novo Contato"),
            "Email": str(email) if email else None,
        }
        if phone:
            payload["Phones"] = [{"PhoneNumber": str(phone), "TypeId": 1}]

        for k, v in mapped.items():
            if k not in ["TypeId", "Name", "Email", "Phones"] and v is not None:
                payload[k] = v

        return self._post_object(connection, "/Contacts", payload)

    def _post_object(
        self, connection: CRMConnection, endpoint: str, payload: dict[str, Any]
    ) -> SyncResult:
        headers = self._get_headers(connection)
        url = f"{self.BASE_URL}{endpoint}"
        try:
            with httpx.Client(timeout=15.0) as client:
                resp = client.post(url, json=payload, headers=headers)
                if 200 <= resp.status_code < 300:
                    res = resp.json()
                    item = (
                        res.get("value", [{}])[0]
                        if isinstance(res.get("value"), list) and res.get("value")
                        else res
                    )
                    return SyncResult(
                        success=True,
                        status_code=resp.status_code,
                        remote_id=str(item.get("Id", "") or item.get("id", "")),
                        response_payload=item if isinstance(item, dict) else {},
                    )

                retry_after: int | None = None
                if resp.status_code == 429:
                    raw_ra = resp.headers.get("Retry-After")
                    if raw_ra and raw_ra.isdigit():
                        retry_after = int(raw_ra)

                return SyncResult(
                    success=False,
                    status_code=resp.status_code,
                    error_code=f"PLOOMES_{resp.status_code}",
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
