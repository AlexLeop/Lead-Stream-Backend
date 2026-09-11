from __future__ import annotations

from uuid import UUID

from django.core.exceptions import ValidationError as DjangoValidationError
from django.http import Http404
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from leadstream.batches.models import Batch
from leadstream.common.api import reject_tenant_override, resolve_tenant
from leadstream.tenancy.services import get_internal_tenant

from .models import CreditTransaction, PriceBook
from .serializers import (
    CreditDepositRequestSerializer,
    CreditDepositResponseSerializer,
    CreditTransactionSerializer,
    CreditWalletSerializer,
    FinancialSummarySerializer,
    PriceBookInputSerializer,
    PriceBookSerializer,
)
from .services import (
    create_price_book,
    deposit_credits,
    ensure_default_price_book,
    financial_summary,
    get_or_create_wallet,
)


def _domain_error(exc: DjangoValidationError) -> ValidationError:
    if hasattr(exc, "message_dict"):
        return ValidationError(exc.message_dict)
    return ValidationError({"erro": exc.messages})


class PriceBookCollectionView(APIView):
    @extend_schema(responses=PriceBookSerializer(many=True), tags=["Financeiro — preços"])
    def get(self, request: Request) -> Response:
        del request
        tenant = get_internal_tenant()
        ensure_default_price_book(tenant)
        queryset = PriceBook.objects.filter(tenant=tenant).prefetch_related("rules")
        return Response(PriceBookSerializer(queryset, many=True).data)

    @extend_schema(
        request=PriceBookInputSerializer,
        responses={201: PriceBookSerializer},
        tags=["Financeiro — preços"],
    )
    def post(self, request: Request) -> Response:
        reject_tenant_override(request.data)
        serializer = PriceBookInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            price_book = create_price_book(
                tenant=get_internal_tenant(), **serializer.validated_data
            )
        except DjangoValidationError as exc:
            raise _domain_error(exc) from exc
        price_book = PriceBook.objects.prefetch_related("rules").get(pk=price_book.pk)
        return Response(PriceBookSerializer(price_book).data, status=status.HTTP_201_CREATED)


class BatchFinancialSummaryView(APIView):
    @extend_schema(responses=FinancialSummarySerializer, tags=["Financeiro — lotes"])
    def get(self, request: Request, batch_id: UUID) -> Response:
        del request
        tenant = get_internal_tenant()
        try:
            batch = Batch.objects.get(pk=batch_id, tenant=tenant)
        except Batch.DoesNotExist as exc:
            raise Http404("Lote não encontrado.") from exc
        return Response(financial_summary(tenant=tenant, batch=batch))


class CreditWalletDetailView(APIView):
    @extend_schema(responses=CreditWalletSerializer, tags=["Financeiro — carteira"])
    def get(self, request: Request) -> Response:
        tenant = resolve_tenant(request)
        wallet = get_or_create_wallet(tenant)
        serializer = CreditWalletSerializer(wallet)
        return Response(serializer.data, status=status.HTTP_200_OK)


class CreditTransactionListView(APIView):
    @extend_schema(responses=CreditTransactionSerializer(many=True), tags=["Financeiro — carteira"])
    def get(self, request: Request) -> Response:
        tenant = resolve_tenant(request)
        wallet = get_or_create_wallet(tenant)
        txs = CreditTransaction.objects.filter(wallet=wallet).order_by("-created_at")[:100]
        serializer = CreditTransactionSerializer(txs, many=True)
        return Response(
            {"count": txs.count(), "results": serializer.data},
            status=status.HTTP_200_OK,
        )


class CreditDepositView(APIView):
    @extend_schema(
        request=CreditDepositRequestSerializer,
        responses={200: CreditDepositResponseSerializer},
        tags=["Financeiro — carteira"],
    )
    def post(self, request: Request) -> Response:
        reject_tenant_override(request.data)
        serializer = CreditDepositRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        tenant = resolve_tenant(request)
        wallet = get_or_create_wallet(tenant)
        data = serializer.validated_data
        try:
            tx = deposit_credits(
                wallet=wallet,
                amount=data["amount"],
                reference_id=data.get("reference_id", ""),
                metadata=data.get("metadata", {}),
            )
        except DjangoValidationError as exc:
            raise _domain_error(exc) from exc

        wallet.refresh_from_db()
        return Response(
            {
                "message": f"Depósito de {data['amount']} créditos realizado com sucesso.",
                "balance": wallet.balance,
                "transaction": CreditTransactionSerializer(tx).data,
            },
            status=status.HTTP_200_OK,
        )
