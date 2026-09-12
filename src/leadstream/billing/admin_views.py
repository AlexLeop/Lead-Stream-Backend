from __future__ import annotations

from typing import Any, ClassVar

from django.db import transaction
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
from leadstream.tenancy.models import Tenant


class AdminPriceRuleSerializer(serializers.ModelSerializer[PriceRule]):
    class Meta:
        model = PriceRule
        fields: ClassVar[list[str]] = [
            "id",
            "block",
            "unit_price_cents",
            "minimum_confidence",
            "refresh_window_days",
        ]


class AdminPriceBookSerializer(serializers.ModelSerializer[PriceBook]):
    tenant_slug = serializers.CharField(source="tenant.slug", read_only=True)
    tenant_name = serializers.CharField(source="tenant.name", read_only=True)
    rules = AdminPriceRuleSerializer(many=True, read_only=True)

    class Meta:
        model = PriceBook
        fields: ClassVar[list[str]] = [
            "id",
            "tenant_id",
            "tenant_slug",
            "tenant_name",
            "version",
            "name",
            "currency",
            "effective_at",
            "retired_at",
            "rules",
            "created_at",
        ]


class AdminPricingListView(APIView):
    """Listagem de tabelas de preços e regras de bloco."""

    authentication_classes = (CombinedAuthentication,)
    permission_classes = (IsAdminUser,)

    def get(self, request: Request) -> Response:
        books = PriceBook.objects.all().prefetch_related("rules", "tenant").order_by("-created_at")
        tenant_id = request.query_params.get("tenant_id", "").strip()
        if tenant_id:
            books = books.filter(tenant_id=tenant_id)

        serializer = AdminPriceBookSerializer(books, many=True)
        return Response({"results": serializer.data, "count": len(serializer.data)})


class AdminPriceBookUpdateView(APIView):
    """Atualização em lote das regras de preço por bloco de dados."""

    authentication_classes = (CombinedAuthentication,)
    permission_classes = (IsAdminUser,)

    def put(self, request: Request, book_id: str) -> Response:
        try:
            book = PriceBook.objects.get(id=book_id)
        except (PriceBook.DoesNotExist, ValueError):
            return Response(
                {"detail": "PriceBook não encontrado."},
                status=status.HTTP_404_NOT_FOUND,
            )

        payload: dict[str, Any] = request.data if isinstance(request.data, dict) else {}
        rules_data = payload.get("rules", [])
        if not isinstance(rules_data, list):
            return Response(
                {"detail": "O campo 'rules' deve ser uma lista."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        with transaction.atomic():
            for item in rules_data:
                block = item.get("block")
                if not block or block not in DataBlock.values:
                    continue
                unit_price_cents = int(item.get("unit_price_cents", 10))
                min_confidence = int(item.get("minimum_confidence", 80))
                refresh_days = int(item.get("refresh_window_days", 30))

                PriceRule.objects.update_or_create(
                    price_book=book,
                    block=block,
                    defaults={
                        "tenant": book.tenant,
                        "unit_price_cents": unit_price_cents,
                        "minimum_confidence": min_confidence,
                        "refresh_window_days": refresh_days,
                    },
                )

        serializer = AdminPriceBookSerializer(book)
        return Response(serializer.data, status=status.HTTP_200_OK)


class AdminWalletSerializer(serializers.ModelSerializer[CreditWallet]):
    tenant_slug = serializers.CharField(source="tenant.slug", read_only=True)
    tenant_name = serializers.CharField(source="tenant.name", read_only=True)

    class Meta:
        model = CreditWallet
        fields: ClassVar[list[str]] = [
            "id",
            "tenant_id",
            "tenant_slug",
            "tenant_name",
            "balance",
            "reserved_balance",
            "available_balance",
            "is_unlimited",
            "auto_recharge",
            "recharge_threshold",
            "updated_at",
            "created_at",
        ]


class AdminWalletListView(APIView):
    """Consulta de saldos de carteiras de todos os clientes."""

    authentication_classes = (CombinedAuthentication,)
    permission_classes = (IsAdminUser,)

    def get(self, request: Request) -> Response:
        wallets = CreditWallet.objects.all().select_related("tenant").order_by("-balance")
        serializer = AdminWalletSerializer(wallets, many=True)
        return Response({"results": serializer.data, "count": len(serializer.data)})


class AdminWalletCreditInjectionView(APIView):
    """Injeção ou ajuste manual de créditos com registro imutável no livro-razão."""

    authentication_classes = (CombinedAuthentication,)
    permission_classes = (IsAdminUser,)

    def post(self, request: Request, tenant_id: str) -> Response:
        try:
            tenant = Tenant.objects.get(id=tenant_id)
        except (Tenant.DoesNotExist, ValueError):
            return Response({"detail": "Tenant não encontrado."}, status=status.HTTP_404_NOT_FOUND)

        payload: dict[str, Any] = request.data if isinstance(request.data, dict) else {}
        amount = int(payload.get("amount", 0))
        reason = payload.get("reason", "").strip()

        if amount <= 0:
            return Response(
                {"detail": "O valor de crédito ('amount') deve ser positivo."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not reason:
            return Response(
                {"detail": "A justificativa ('reason') é estritamente obrigatória para auditoria."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        with transaction.atomic():
            wallet, _ = CreditWallet.objects.get_or_create(tenant=tenant)
            new_balance = wallet.balance + amount
            wallet.balance = new_balance
            wallet.save(update_fields=["balance", "updated_at"])

            username = request.user.get_username() if request.user else "master_admin"
            CreditTransaction.objects.create(
                tenant=tenant,
                wallet=wallet,
                transaction_type=CreditTransaction.Type.DEPOSIT,
                amount=amount,
                balance_after=new_balance,
                reference_id="admin_manual_deposit",
                metadata={"reason": reason, "injected_by": username},
            )

        serializer = AdminWalletSerializer(wallet)
        return Response(serializer.data, status=status.HTTP_200_OK)


class AdminCreditTransactionSerializer(serializers.ModelSerializer[CreditTransaction]):
    class Meta:
        model = CreditTransaction
        fields: ClassVar[list[str]] = [
            "id",
            "transaction_type",
            "amount",
            "balance_after",
            "reference_id",
            "metadata",
            "created_at",
        ]


class AdminWalletTransactionsView(APIView):
    """Histórico de transações contábeis do cliente."""

    authentication_classes = (CombinedAuthentication,)
    permission_classes = (IsAdminUser,)

    def get(self, request: Request, tenant_id: str) -> Response:
        try:
            tenant = Tenant.objects.get(id=tenant_id)
        except (Tenant.DoesNotExist, ValueError):
            return Response({"detail": "Tenant não encontrado."}, status=status.HTTP_404_NOT_FOUND)

        transactions = CreditTransaction.objects.filter(tenant=tenant).order_by("-created_at")
        serializer = AdminCreditTransactionSerializer(transactions, many=True)
        return Response({"results": serializer.data, "count": len(serializer.data)})
