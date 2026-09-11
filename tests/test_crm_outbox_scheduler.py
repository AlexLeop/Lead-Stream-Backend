from datetime import timedelta

import pytest
from django.conf import settings
from django.contrib.auth.models import User
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from leadstream.integrations.models import (
    CRMConnection,
    CRMConnectorType,
    CRMFieldEntityType,
    CRMOutboxMessage,
    OutboxStatus,
)
from leadstream.security.models import WorkspaceMembership, WorkspaceRole
from leadstream.tenancy.models import Tenant


@pytest.mark.django_db
class TestCRMOutboxSchedulerAndEndpoints:
    @pytest.fixture(autouse=True)
    def setup_environment(self):
        self.tenant = Tenant.objects.create(slug="tenant-outbox", name="Tenant Outbox")
        self.admin_user = User.objects.create_user(
            username="admin_outbox",
            password="SecurePassword123!",
            email="admin@outbox.com",
        )
        self.membership = WorkspaceMembership.objects.create(
            user=self.admin_user,
            tenant=self.tenant,
            role=WorkspaceRole.ADMIN,
        )

        self.operator_user = User.objects.create_user(
            username="operador_outbox",
            password="SecurePassword123!",
            email="op@outbox.com",
        )
        WorkspaceMembership.objects.create(
            user=self.operator_user,
            tenant=self.tenant,
            role=WorkspaceRole.OPERATOR,
        )

        self.connection = CRMConnection.objects.create(
            tenant=self.tenant,
            name="HubSpot Outbox Test",
            connector_type=CRMConnectorType.HUBSPOT,
            credentials={"access_token": "pat-test-123"},
        )

        self.client = APIClient()

    def test_celery_beat_schedule_contains_outbox_task(self):
        schedule = settings.CELERY_BEAT_SCHEDULE
        assert "process-crm-outbox" in schedule
        entry = schedule["process-crm-outbox"]
        assert entry["task"] == "leadstream.integrations.process_crm_outbox_batch"
        assert entry["schedule"] <= 60.0

    def test_outbox_status_endpoint_returns_metrics(self):
        now = timezone.now()
        CRMOutboxMessage.objects.create(
            tenant=self.tenant,
            connection=self.connection,
            entity_type=CRMFieldEntityType.COMPANY,
            idempotency_key="key-1",
            status=OutboxStatus.PENDING,
            created_at=now - timedelta(seconds=45),
        )
        CRMOutboxMessage.objects.create(
            tenant=self.tenant,
            connection=self.connection,
            entity_type=CRMFieldEntityType.COMPANY,
            idempotency_key="key-2",
            status=OutboxStatus.DELIVERED,
        )
        CRMOutboxMessage.objects.create(
            tenant=self.tenant,
            connection=self.connection,
            entity_type=CRMFieldEntityType.COMPANY,
            idempotency_key="key-3",
            status=OutboxStatus.DEAD_LETTER,
        )

        token = RefreshToken.for_user(self.admin_user).access_token
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

        response = self.client.get("/api/v1/integracoes/outbox/status/")
        assert response.status_code == 200
        data = response.json()

        assert data["counts"]["pending"] == 1
        assert data["counts"]["delivered"] == 1
        assert data["counts"]["dead_letter"] == 1
        assert data["is_healthy"] is False  # Tem dead-letter

    def test_outbox_retry_dead_letter_endpoint_as_admin(self):
        from unittest.mock import patch

        msg = CRMOutboxMessage.objects.create(
            tenant=self.tenant,
            connection=self.connection,
            entity_type=CRMFieldEntityType.COMPANY,
            idempotency_key="dl-key-1",
            status=OutboxStatus.DEAD_LETTER,
            retry_count=5,
            error_message="Erro 500 fatal anterior",
        )

        token = RefreshToken.for_user(self.admin_user).access_token
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

        with patch("leadstream.integrations.views.process_crm_outbox_batch.delay") as mock_delay:
            response = self.client.post(
                "/api/v1/integracoes/outbox/retry-dead-letter/",
                {"message_ids": [str(msg.id)]},
                format="json",
            )
            assert response.status_code == 200
            data = response.json()
            assert data["retried_count"] == 1
            assert mock_delay.called

        msg.refresh_from_db()
        assert msg.status == OutboxStatus.PENDING
        assert msg.retry_count == 0
        assert msg.error_message == ""

    def test_outbox_retry_dead_letter_forbidden_for_non_admin(self):
        token = RefreshToken.for_user(self.operator_user).access_token
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

        response = self.client.post(
            "/api/v1/integracoes/outbox/retry-dead-letter/",
            {},
            format="json",
        )
        assert response.status_code == 403
