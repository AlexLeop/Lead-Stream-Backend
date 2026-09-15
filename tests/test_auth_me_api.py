import pytest
from django.contrib.auth.models import User
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from leadstream.security.crypto import generate_api_key
from leadstream.security.models import WorkspaceMembership, WorkspaceRole
from leadstream.tenancy.models import Tenant


@pytest.mark.django_db
class TestAuthMeAndSwitchWorkspaceAPI:
    @pytest.fixture(autouse=True)
    def setup_entities(self):
        self.tenant_a = Tenant.objects.create(slug="workspace-a", name="Workspace Alpha")
        self.tenant_b = Tenant.objects.create(slug="workspace-b", name="Workspace Beta")

        self.user = User.objects.create_user(
            username="analista",
            email="analista@leadstream.com.br",
            password="SecurePassword123!",
            first_name="Carlos",
            last_name="Silva",
        )
        self.membership_a = WorkspaceMembership.objects.create(
            user=self.user,
            tenant=self.tenant_a,
            role=WorkspaceRole.OPERATOR,
        )

        self.superuser = User.objects.create_superuser(
            username="admin_global",
            email="admin@leadstream.com.br",
            password="AdminPassword123!",
            first_name="Admin",
            last_name="Master",
        )

        self.client = APIClient()

    def test_auth_me_unauthenticated_returns_401(self):
        response = self.client.get("/api/v1/auth/me/")
        assert response.status_code == 401

    def test_auth_me_with_jwt_returns_profile_and_active_workspace(self):
        token = RefreshToken.for_user(self.user).access_token
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

        response = self.client.get("/api/v1/auth/me/")
        assert response.status_code == 200
        data = response.json()

        assert data["user"]["username"] == "analista"
        assert data["user"]["email"] == "analista@leadstream.com.br"
        assert data["user"]["first_name"] == "Carlos"
        assert data["auth_type"] == "JWT"

        assert data["active_workspace"]["id"] == str(self.tenant_a.id)
        assert data["active_workspace"]["slug"] == "workspace-a"
        assert data["active_workspace"]["role"] == "OPERATOR"

        assert len(data["workspaces"]) == 1
        assert data["workspaces"][0]["slug"] == "workspace-a"
        assert "batches:view" in data["permissions"]

    def test_auth_me_with_api_key_returns_machine_profile(self):
        _api_key, raw_key = generate_api_key(
            tenant=self.tenant_a,
            name="CI Integration Key",
            role=WorkspaceRole.ADMIN,
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {raw_key}")

        response = self.client.get("/api/v1/auth/me/")
        assert response.status_code == 200
        data = response.json()

        assert data["auth_type"] == "API_KEY"
        assert data["active_workspace"]["slug"] == "workspace-a"
        assert data["active_workspace"]["role"] == "ADMIN"
        assert "security:manage_keys" in data["permissions"]

    def test_switch_workspace_success_when_user_has_membership(self):
        # Concede acesso ao Workspace B como ADMIN
        WorkspaceMembership.objects.create(
            user=self.user,
            tenant=self.tenant_b,
            role=WorkspaceRole.ADMIN,
        )

        token = RefreshToken.for_user(self.user).access_token
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

        # Troca para Workspace B
        response = self.client.post(
            "/api/v1/auth/switch-workspace/",
            {"workspace_id": str(self.tenant_b.id)},
            format="json",
        )
        assert response.status_code == 200
        data = response.json()
        assert data["active_workspace"]["id"] == str(self.tenant_b.id)
        assert data["active_workspace"]["role"] == "ADMIN"
        assert "access" in data
        assert "refresh" not in data
        assert self.client.cookies["leadstream_refresh"]["httponly"] is True

        # O tenant selecionado permanece no token, sem depender de header controlado pelo cliente.
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {data['access']}")
        me_response = self.client.get("/api/v1/auth/me/")
        assert me_response.status_code == 200
        assert me_response.json()["active_workspace"]["id"] == str(self.tenant_b.id)

    def test_switch_workspace_denied_when_user_has_no_membership(self):
        token = RefreshToken.for_user(self.user).access_token
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

        # Tenta alternar para Workspace B sem ter membership
        response = self.client.post(
            "/api/v1/auth/switch-workspace/",
            {"workspace_id": str(self.tenant_b.id)},
            format="json",
        )
        assert response.status_code == 403
        data = response.json()
        assert data["code"] == "WORKSPACE_ACCESS_DENIED"

    def test_switch_workspace_allowed_for_superuser_anywhere(self):
        token = RefreshToken.for_user(self.superuser).access_token
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

        response = self.client.post(
            "/api/v1/auth/switch-workspace/",
            {"workspace_id": str(self.tenant_b.id)},
            format="json",
        )
        assert response.status_code == 200
        data = response.json()
        assert data["active_workspace"]["id"] == str(self.tenant_b.id)

    def test_auth_me_with_superuser_returns_super_admin(self):
        token = RefreshToken.for_user(self.superuser).access_token
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

        response = self.client.get("/api/v1/auth/me/")
        assert response.status_code == 200
        data = response.json()
        assert data["user"]["username"] == "admin_global"
        assert data["user"]["is_superuser"] is True
        assert data["active_workspace"]["role"] == "SUPER_ADMIN"
        assert data["active_workspace"]["is_owner"] is True
