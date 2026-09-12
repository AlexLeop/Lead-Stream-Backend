import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

User = get_user_model()


@pytest.mark.django_db
def test_public_branding_get():
    client = APIClient()
    response = client.get("/api/v1/system/branding/")
    assert response.status_code == 200
    assert response.data["platform_name"] == "LeadStream"
    assert response.data["accent_color"] == "#10B981"


@pytest.mark.django_db
def test_branding_patch_unauthorized():
    client = APIClient()
    response = client.patch("/api/v1/system/branding/", {"platform_name": "Custom Leads"})
    assert response.status_code in [401, 403]


@pytest.mark.django_db
def test_branding_patch_superuser():
    user = User.objects.create_superuser(
        username="admin_branding", email="admin_b@example.com", password="password123"
    )
    client = APIClient()
    client.force_authenticate(user=user)
    response = client.patch(
        "/api/v1/system/branding/",
        {
            "platform_name": "UltraLead Enterprise",
            "accent_color": "#3B82F6",
            "support_email": "suporte@ultralead.com.br",
        },
    )
    assert response.status_code == 200
    assert response.data["platform_name"] == "UltraLead Enterprise"
    assert response.data["accent_color"] == "#3B82F6"
    assert response.data["support_email"] == "suporte@ultralead.com.br"
