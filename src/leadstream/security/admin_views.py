from __future__ import annotations

from typing import Any, ClassVar

from django.contrib.auth import get_user_model
from django.db import transaction
from rest_framework import serializers, status
from rest_framework.permissions import IsAdminUser
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from leadstream.security.authentication import CombinedAuthentication
from leadstream.security.crypto import generate_api_key
from leadstream.security.models import APIKey, WorkspaceMembership, WorkspaceRole
from leadstream.tenancy.models import Tenant

User = get_user_model()


class AdminUserMembershipSerializer(serializers.ModelSerializer[WorkspaceMembership]):
    tenant_slug = serializers.CharField(source="tenant.slug", read_only=True)
    tenant_name = serializers.CharField(source="tenant.name", read_only=True)

    class Meta:
        model = WorkspaceMembership
        fields: ClassVar[list[str]] = [
            "id",
            "tenant_id",
            "tenant_slug",
            "tenant_name",
            "role",
            "is_active",
            "created_at",
        ]


class AdminUserSerializer(serializers.ModelSerializer[Any]):
    memberships = AdminUserMembershipSerializer(
        source="workspace_memberships", many=True, read_only=True
    )

    class Meta:
        model = User
        fields: ClassVar[list[str]] = [
            "id",
            "username",
            "email",
            "first_name",
            "last_name",
            "is_active",
            "is_staff",
            "is_superuser",
            "date_joined",
            "memberships",
        ]


class AdminUserListView(APIView):
    """Listagem e cadastro administrativo de usuários e vínculos de workspace."""

    authentication_classes = (CombinedAuthentication,)
    permission_classes = (IsAdminUser,)

    def get(self, request: Request) -> Response:
        users = User.objects.all().prefetch_related(
            "workspace_memberships__tenant"
        ).order_by("-date_joined")
        search = request.query_params.get("search", "").strip()
        if search:
            users = users.filter(username__icontains=search) | users.filter(email__icontains=search)

        serializer = AdminUserSerializer(users, many=True)
        return Response({"results": serializer.data, "count": len(serializer.data)})

    def post(self, request: Request) -> Response:
        payload: dict[str, Any] = request.data if isinstance(request.data, dict) else {}
        username = payload.get("username", "").strip()
        email = payload.get("email", "").strip()
        password = payload.get("password", "").strip()
        tenant_id = payload.get("tenant_id", "").strip()
        role = payload.get("role", WorkspaceRole.OPERATOR)

        if not username or not email:
            return Response(
                {"detail": "Os campos 'username' e 'email' são obrigatórios."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if User.objects.filter(username=username).exists():
            return Response(
                {"detail": f"Usuário com username '{username}' já existe."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        with transaction.atomic():
            user = User.objects.create_user(
                username=username,
                email=email,
                password=password or None,
            )

            if tenant_id:
                try:
                    tenant = Tenant.objects.get(id=tenant_id)
                    WorkspaceMembership.objects.create(
                        user=user,
                        tenant=tenant,
                        role=role if role in WorkspaceRole.values else WorkspaceRole.OPERATOR,
                        is_active=True,
                    )
                except (Tenant.DoesNotExist, ValueError):
                    pass

        serializer = AdminUserSerializer(user)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class AdminUserDetailView(APIView):
    """Consulta e alteração de papel e status de usuário."""

    authentication_classes = (CombinedAuthentication,)
    permission_classes = (IsAdminUser,)

    def get(self, request: Request, user_id: str) -> Response:
        try:
            user = User.objects.get(id=user_id)
        except (User.DoesNotExist, ValueError):
            return Response({"detail": "Usuário não encontrado."}, status=status.HTTP_404_NOT_FOUND)
        serializer = AdminUserSerializer(user)
        return Response(serializer.data)

    def patch(self, request: Request, user_id: str) -> Response:
        try:
            user = User.objects.get(id=user_id)
        except (User.DoesNotExist, ValueError):
            return Response({"detail": "Usuário não encontrado."}, status=status.HTTP_404_NOT_FOUND)

        payload: dict[str, Any] = request.data if isinstance(request.data, dict) else {}
        if "is_active" in payload:
            user.is_active = bool(payload["is_active"])
        if payload.get("password"):
            user.set_password(payload["password"])
        if "is_staff" in payload:
            user.is_staff = bool(payload["is_staff"])
        user.save()

        # Atualiza papel no tenant se especificado
        role = payload.get("role")
        tenant_id = payload.get("tenant_id")
        if role and role in WorkspaceRole.values:
            membership_qs = WorkspaceMembership.objects.filter(user=user)
            if tenant_id:
                membership_qs = membership_qs.filter(tenant_id=tenant_id)
            membership_qs.update(role=role)

        serializer = AdminUserSerializer(user)
        return Response(serializer.data, status=status.HTTP_200_OK)


class AdminAPIKeySerializer(serializers.ModelSerializer[APIKey]):
    tenant_slug = serializers.CharField(source="tenant.slug", read_only=True)
    tenant_name = serializers.CharField(source="tenant.name", read_only=True)

    class Meta:
        model = APIKey
        fields: ClassVar[list[str]] = [
            "id",
            "tenant_id",
            "tenant_slug",
            "tenant_name",
            "name",
            "prefix",
            "role",
            "scopes",
            "is_active",
            "expires_at",
            "last_used_at",
            "created_at",
        ]


class AdminAPIKeyListView(APIView):
    """Listagem e emissão de chaves criptográficas de API multi-tenant."""

    authentication_classes = (CombinedAuthentication,)
    permission_classes = (IsAdminUser,)

    def get(self, request: Request) -> Response:
        keys = APIKey.objects.all().select_related("tenant").order_by("-created_at")
        tenant_id = request.query_params.get("tenant_id", "").strip()
        if tenant_id:
            keys = keys.filter(tenant_id=tenant_id)

        serializer = AdminAPIKeySerializer(keys, many=True)
        return Response({"results": serializer.data, "count": len(serializer.data)})

    def post(self, request: Request) -> Response:
        payload: dict[str, Any] = request.data if isinstance(request.data, dict) else {}
        tenant_id = payload.get("tenant_id", "").strip()
        name = payload.get("name", "Chave de Integração").strip()
        role = payload.get("role", WorkspaceRole.OPERATOR)
        scopes = payload.get("scopes", [])

        try:
            tenant = Tenant.objects.get(id=tenant_id)
        except (Tenant.DoesNotExist, ValueError):
            return Response({"detail": "Tenant não encontrado."}, status=status.HTTP_404_NOT_FOUND)

        api_key_obj, raw_key = generate_api_key(
            tenant=tenant,
            name=name,
            role=role,
            scopes=scopes if isinstance(scopes, list) else [],
        )

        data = AdminAPIKeySerializer(api_key_obj).data
        data["raw_key"] = raw_key
        return Response(data, status=status.HTTP_201_CREATED)


class AdminAPIKeyDetailView(APIView):
    """Revogação de chave de API."""

    authentication_classes = (CombinedAuthentication,)
    permission_classes = (IsAdminUser,)

    def delete(self, request: Request, key_id: str) -> Response:
        try:
            key = APIKey.objects.get(id=key_id)
        except (APIKey.DoesNotExist, ValueError):
            return Response({"detail": "Chave não encontrada."}, status=status.HTTP_404_NOT_FOUND)

        key.is_active = False
        key.save(update_fields=["is_active"])
        return Response(
            {"detail": f"Chave '{key.name}' ({key.prefix}...) revogada com sucesso."},
            status=status.HTTP_200_OK,
        )
