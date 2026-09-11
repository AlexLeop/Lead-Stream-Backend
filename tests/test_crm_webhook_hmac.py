import time

import pytest

from leadstream.integrations.connectors.webhook import (
    WebhookConnector,
    generate_webhook_signature,
    verify_webhook_signature,
)
from leadstream.integrations.models import CRMConnection, CRMConnectorType
from leadstream.tenancy.models import Tenant


@pytest.mark.django_db
class TestCRMWebhookHMAC:
    @pytest.fixture(autouse=True)
    def setup_connection(self):
        self.tenant = Tenant.objects.create(slug="tenant-hmac", name="Tenant HMAC")
        self.secret = "whsec_test_secret_key_123456"
        self.connection = CRMConnection.objects.create(
            tenant=self.tenant,
            name="Webhook Test HMAC",
            connector_type=CRMConnectorType.WEBHOOK_CUSTOM,
            credentials={
                "webhook_url": "https://webhook.example.com/receiver",
                "signing_secret": self.secret,
            },
        )

    def test_generate_and_verify_signature_success(self):
        payload = b'{"lead_id": "123", "cnpj": "00000000000191"}'
        timestamp = int(time.time())

        signature_header = generate_webhook_signature(payload, self.secret, timestamp=timestamp)
        assert signature_header.startswith(f"t={timestamp},v1=")

        is_valid = verify_webhook_signature(
            payload=payload,
            signature_header=signature_header,
            secret=self.secret,
            max_age_seconds=300,
        )
        assert is_valid is True

    def test_verify_signature_fails_on_tampered_payload(self):
        payload = b'{"lead_id": "123"}'
        tampered = b'{"lead_id": "999"}'
        timestamp = int(time.time())

        signature_header = generate_webhook_signature(payload, self.secret, timestamp=timestamp)

        is_valid = verify_webhook_signature(
            payload=tampered,
            signature_header=signature_header,
            secret=self.secret,
        )
        assert is_valid is False

    def test_verify_signature_fails_on_expired_timestamp(self):
        payload = b'{"lead_id": "123"}'
        old_timestamp = int(time.time()) - 600  # 10 min atras

        signature_header = generate_webhook_signature(payload, self.secret, timestamp=old_timestamp)

        is_valid = verify_webhook_signature(
            payload=payload,
            signature_header=signature_header,
            secret=self.secret,
            max_age_seconds=300,
        )
        assert is_valid is False

    def test_connector_headers_contain_standard_signature(self):
        connector = WebhookConnector()
        body = b'{"test": "payload"}'
        headers = connector._get_headers(self.connection, body, "test.event")

        assert "X-LeadStream-Signature" in headers
        assert "X-LeadStream-Signature-V2" in headers
        assert headers["X-LeadStream-Signature"].startswith("sha256=")
        assert "t=" in headers["X-LeadStream-Signature-V2"]
        assert "v1=" in headers["X-LeadStream-Signature-V2"]

        is_valid_v1 = verify_webhook_signature(
            payload=body,
            signature_header=headers["X-LeadStream-Signature"],
            secret=self.secret,
        )
        assert is_valid_v1 is True

        is_valid_v2 = verify_webhook_signature(
            payload=body,
            signature_header=headers["X-LeadStream-Signature-V2"],
            secret=self.secret,
        )
        assert is_valid_v2 is True
