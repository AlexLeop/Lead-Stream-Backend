from __future__ import annotations

import uuid
from typing import Any, ClassVar

from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone
from rest_framework import serializers, status
from rest_framework.permissions import IsAdminUser
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from leadstream.billing.models import (
    CreditTransaction,
    CreditWallet,
    DataBlock,
    PriceBook,
    PriceRule,
)
from leadstream.security.authentication import CombinedAuthentication
from leadstream.security.models import WorkspaceMembership, WorkspaceRole
from leadstream.tenancy.models import Tenant

User = get_user_model()


class AdminTenantSerializer(serializers.ModelSerializer[Tenant]):
    wallet_balance = serializers.SerializerMethodField()
    members_count = serializers.SerializerMethodField()

    class Meta:
        model = Tenant
        fields: ClassVar[list[str]] = [
            "id",
            "slug",
            "name",
            "is_active",
            "max_batch_size",
            "rate_limit_per_minute",
            "max_concurrency",
            "wallet_balance",
            "members_count",
            "created_at",
            "updated_at",
        ]

    def get_wallet_balance(self, obj: Tenant) -> int:
        wallet = CreditWallet.objects.filter(tenant=obj).first()
        return wallet.balance if wallet else 0

    def get_members_count(self, obj: Tenant) -> int:
        return WorkspaceMembership.objects.filter(tenant=obj).count()


class AdminTenantListCreateView(APIView):
    """Listagem e criação administrativa de clientes/tenants."""

    authentication_classes = (CombinedAuthentication,)
    permission_classes = (IsAdminUser,)

    def get(self, request: Request) -> Response:
        tenants = Tenant.objects.all().order_by("-created_at")
        search = request.query_params.get("search", "").strip()
        if search:
            tenants = tenants.filter(name__icontains=search) | tenants.filter(
                slug__icontains=search
            )

        serializer = AdminTenantSerializer(tenants, many=True)
        return Response({"results": serializer.data, "count": len(serializer.data)})

    def post(self, request: Request) -> Response:
        payload: dict[str, Any] = request.data if isinstance(request.data, dict) else {}
        name = payload.get("name", "").strip()
        slug = payload.get("slug", "").strip()
        if not name or not slug:
            return Response(
                {"detail": "Os campos 'name' e 'slug' são obrigatórios."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if Tenant.objects.filter(slug=slug).exists():
            return Response(
                {"detail": f"Já existe um cliente com o slug '{slug}'."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        max_batch_size = int(payload.get("max_batch_size", 100000))
        rate_limit = int(payload.get("rate_limit_per_minute", 60))
        max_concurrency = int(payload.get("max_concurrency", 4))
        initial_credits = int(payload.get("initial_credits", 0))
        admin_email = payload.get("admin_email", "").strip()

        with transaction.atomic():
            tenant = Tenant.objects.create(
                name=name,
                slug=slug,
                max_batch_size=max_batch_size,
                rate_limit_per_minute=rate_limit,
                max_concurrency=max_concurrency,
            )

            # Inicializa carteira contábil
            wallet = CreditWallet.objects.create(tenant=tenant, balance=initial_credits)
            if initial_credits > 0:
                CreditTransaction.objects.create(
                    tenant=tenant,
                    wallet=wallet,
                    transaction_type=CreditTransaction.Type.BONUS,
                    amount=initial_credits,
                    balance_after=initial_credits,
                    reference_id="initial_bonus",
                    metadata={
                        "reason": "Crédito bônus inicial concedido no provisionamento do cliente"
                    },
                )

            # Inicializa PriceBook padrão com regras de bloco
            book = PriceBook.objects.create(
                tenant=tenant,
                version=1,
                name="Tabela Padrão",
                effective_at=timezone.now(),
            )
            default_block_prices = {
                DataBlock.COMPANY_REGISTRY: 10,
                DataBlock.HYGIENE: 5,
                DataBlock.DECISION_MAKER: 25,
                DataBlock.DIRECT_EMAIL: 20,
                DataBlock.DIRECT_PHONE: 20,
                DataBlock.WHATSAPP: 30,
                DataBlock.SOCIAL_PROFILES: 15,
                DataBlock.BANKING: 15,
                DataBlock.GOVERNMENT_RISK: 0,
                DataBlock.PUBLIC_SECTOR: 0,
            }
            for block, price in default_block_prices.items():
                PriceRule.objects.create(
                    tenant=tenant,
                    price_book=book,
                    block=block,
                    unit_price_cents=price,
                    minimum_confidence=80,
                    refresh_window_days=30,
                )

            # Se e-mail do admin for informado, cria/associa usuário
            if admin_email:
                user = User.objects.filter(email=admin_email).first()
                if not user:
                    username = admin_email.split("@")[0] + "_" + uuid.uuid4().hex[:4]
                    user = User.objects.create_user(username=username, email=admin_email)
                WorkspaceMembership.objects.get_or_create(
                    user=user,
                    tenant=tenant,
                    defaults={"role": WorkspaceRole.ADMIN, "is_active": True},
                )

        serializer = AdminTenantSerializer(tenant)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class AdminTenantUpdateSerializer(serializers.ModelSerializer[Tenant]):
    class Meta:
        model = Tenant
        fields: ClassVar[list[str]] = [
            "name",
            "is_active",
            "max_batch_size",
            "rate_limit_per_minute",
            "max_concurrency",
        ]


class AdminTenantDetailView(APIView):
    """Consulta e atualização de limites e status de um tenant."""

    authentication_classes = (CombinedAuthentication,)
    permission_classes = (IsAdminUser,)

    def get(self, request: Request, tenant_id: str) -> Response:
        try:
            tenant = Tenant.objects.get(id=tenant_id)
        except (Tenant.DoesNotExist, ValueError):
            return Response({"detail": "Tenant não encontrado."}, status=status.HTTP_404_NOT_FOUND)
        serializer = AdminTenantSerializer(tenant)
        return Response(serializer.data)

    def patch(self, request: Request, tenant_id: str) -> Response:
        try:
            tenant = Tenant.objects.get(id=tenant_id)
        except (Tenant.DoesNotExist, ValueError):
            return Response({"detail": "Tenant não encontrado."}, status=status.HTTP_404_NOT_FOUND)

        payload: dict[str, Any] = request.data if isinstance(request.data, dict) else {}
        serializer = AdminTenantUpdateSerializer(tenant, data=payload, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(AdminTenantSerializer(tenant).data, status=status.HTTP_200_OK)


class AdminTenantImpersonateView(APIView):
    """Gera contexto de personificação imediata para superadministrador."""

    authentication_classes = (CombinedAuthentication,)
    permission_classes = (IsAdminUser,)

    def post(self, request: Request, tenant_id: str) -> Response:
        try:
            tenant = Tenant.objects.get(id=tenant_id)
        except (Tenant.DoesNotExist, ValueError):
            return Response({"detail": "Tenant não encontrado."}, status=status.HTTP_404_NOT_FOUND)

        return Response(
            {
                "tenant": {
                    "id": str(tenant.id),
                    "slug": tenant.slug,
                    "name": tenant.name,
                    "is_active": tenant.is_active,
                },
                "tenant_slug": tenant.slug,
                "message": f"Contexto de governança chaveado para '{tenant.name}'.",
            },
            status=status.HTTP_200_OK,
        )
