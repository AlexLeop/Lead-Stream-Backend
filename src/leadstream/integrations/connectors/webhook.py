from __future__ import annotations

import hashlib
import hmac
import json
import time
from typing import TYPE_CHECKING, Any

import httpx
from django.utils import timezone

from .base import BaseCRMConnector, ConnectionTestResult, SyncResult

if TYPE_CHECKING:
    from leadstream.integrations.models import CRMConnection, CRMFieldMapping


class WebhookConnector(BaseCRMConnector):
    connector_type = "WEBHOOK_CUSTOM"

    def _sign_payload(self, body_bytes: bytes, secret: str) -> str:
        if not secret:
            return ""
        return hmac.new(secret.encode("utf-8"), body_bytes, hashlib.sha256).hexdigest()

    def _get_headers(
        self, connection: CRMConnection, body_bytes: bytes, event_name: str
    ) -> dict[str, str]:
        secret = str(connection.credentials.get("signing_secret", "")).strip()
        signature = self._sign_payload(body_bytes, secret)
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "LeadStream-Webhook-Delivery/1.0",
            "X-LeadStream-Event": event_name,
            "X-LeadStream-Timestamp": timezone.now().isoformat(),
            "X-LeadStream-Tenant": str(connection.tenant_id),
        }
        if signature:
            headers["X-LeadStream-Signature"] = f"sha256={signature}"
        # Suporte a headers customizados definidos pelo tenant nas settings
        custom_headers = connection.settings.get("custom_headers", {})
        if isinstance(custom_headers, dict):
            for k, v in custom_headers.items():
                headers[str(k)] = str(v)
        return headers

    def test_connection(self, connection: CRMConnection) -> ConnectionTestResult:
        webhook_url = str(connection.credentials.get("webhook_url", "")).strip()
        if not webhook_url:
            return ConnectionTestResult(
                success=False,
                message="URL do Webhook não configurada.",
                latency_ms=0.0,
            )

        start = time.perf_counter()
        body = json.dumps(
            {"event": "leadstream.ping", "timestamp": timezone.now().isoformat()}
        ).encode("utf-8")
        headers = self._get_headers(connection, body, "leadstream.ping")

        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.post(webhook_url, content=body, headers=headers)
                latency = (time.perf_counter() - start) * 1000.0

                if 200 <= response.status_code < 300:
                    return ConnectionTestResult(
                        success=True,
                        message=f"Webhook respondeu com status {response.status_code}.",
                        remote_account_info={"status_code": response.status_code},
                        latency_ms=round(latency, 2),
                    )
                err_snippet = response.text[:60]
                return ConnectionTestResult(
                    success=False,
                    message=f"Webhook rejeitou o ping ({response.status_code}): {err_snippet}",
                    remote_account_info={"status_code": response.status_code},
                    latency_ms=round(latency, 2),
                )
        except Exception as exc:  # noqa: BLE001
            latency = (time.perf_counter() - start) * 1000.0
            return ConnectionTestResult(
                success=False,
                message=f"Erro de conexão com o Webhook: {exc}",
                latency_ms=round(latency, 2),
            )

    def sync_company(
        self,
        connection: CRMConnection,
        data: dict[str, Any],
        mapping: list[CRMFieldMapping],
    ) -> SyncResult:
        return self._dispatch(connection, data, mapping, "company.enriched", "COMPANY")

    def sync_contact(
        self,
        connection: CRMConnection,
        data: dict[str, Any],
        mapping: list[CRMFieldMapping],
    ) -> SyncResult:
        return self._dispatch(connection, data, mapping, "contact.enriched", "CONTACT")

    def _dispatch(
        self,
        connection: CRMConnection,
        data: dict[str, Any],
        mapping: list[CRMFieldMapping],
        event_name: str,
        entity_type: str,
    ) -> SyncResult:
        webhook_url = str(connection.credentials.get("webhook_url", "")).strip()
        if not webhook_url:
            return SyncResult(
                success=False,
                status_code=400,
                error_code="CONFIG_ERROR",
                error_message="URL do Webhook não informada nas credenciais.",
            )

        mapped_data = self.apply_mapping(data, mapping)
        payload = {
            "event": event_name,
            "entity_type": entity_type,
            "timestamp": timezone.now().isoformat(),
            "data": mapped_data,
        }
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers = self._get_headers(connection, body, event_name)

        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.post(webhook_url, content=body, headers=headers)

                if 200 <= response.status_code < 300:
                    resp_json = (
                        response.json()
                        if "application/json" in response.headers.get("content-type", "")
                        else {}
                    )
                    return SyncResult(
                        success=True,
                        status_code=response.status_code,
                        remote_id=str(resp_json.get("id", "") or resp_json.get("event_id", "")),
                        response_payload=resp_json if isinstance(resp_json, dict) else {},
                    )

                retry_after: int | None = None
                if response.status_code == 429:
                    raw_ra = response.headers.get("Retry-After")
                    if raw_ra and raw_ra.isdigit():
                        retry_after = int(raw_ra)

                return SyncResult(
                    success=False,
                    status_code=response.status_code,
                    error_code=f"HTTP_{response.status_code}",
                    error_message=response.text[:500],
                    retry_after_seconds=retry_after,
                )
        except Exception as exc:  # noqa: BLE001
            return SyncResult(
                success=False,
                status_code=0,
                error_code="NETWORK_ERROR",
                error_message=str(exc),
            )
