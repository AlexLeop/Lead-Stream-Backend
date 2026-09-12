import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from leadstream.batches.models import Batch
from leadstream.tenancy.models import Tenant

User = get_user_model()


@pytest.mark.django_db
def test_admin_batches_and_clean_analytics():
    master = User.objects.create_superuser(
        username="master", email="master@example.com", password="pass"
    )
    tenant = Tenant.objects.create(name="Epsilon Corp", slug="epsilon-corp")
    batch = Batch.objects.create(
        tenant=tenant,
        name="Lote 10k SP",
        status=Batch.Status.RUNNING,
        total_rows=10000,
    )

    client = APIClient()
    client.force_authenticate(user=master)

    # 1. Admin Batches
    batch_resp = client.get("/api/v1/admin/batches/")
    assert batch_resp.status_code == 200
    assert len(batch_resp.data["results"]) >= 1

    # 2. Pause Batch
    pause_resp = client.post(f"/api/v1/admin/batches/{batch.id}/pause/")
    assert pause_resp.status_code == 200
    batch.refresh_from_db()
    assert batch.status == Batch.Status.PAUSED

    # 3. Resume Batch
    resume_resp = client.post(f"/api/v1/admin/batches/{batch.id}/resume/")
    assert resume_resp.status_code == 200
    batch.refresh_from_db()
    assert batch.status == Batch.Status.RUNNING

    # 4. Celery Queue telemetry
    queue_resp = client.get("/api/v1/admin/celery/queues/")
    assert queue_resp.status_code == 200

    # 5. Clean Analytics Verification (Zero Fakes)
    Tenant.objects.create(name="Empty Corp", slug="empty-corp")
    client.credentials(HTTP_X_TENANT_SLUG="empty-corp")

    dash_resp = client.get("/api/v1/dashboard/")
    assert dash_resp.status_code == 200
    # Must be real zeros, NOT artificial 120 or 50
    assert dash_resp.data["summary"]["contacts"] == 0
    assert dash_resp.data["summary"]["companies"] == 0

    leads_resp = client.get("/api/v1/leads/")
    assert leads_resp.status_code == 200
    # Must NOT contain "Carlos Eduardo" or fake demo leads
    assert len(leads_resp.data) == 0
