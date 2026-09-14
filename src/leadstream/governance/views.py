from __future__ import annotations

from django.core.exceptions import ValidationError as DjangoValidationError
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from leadstream.common.api import reject_tenant_override, resolve_tenant
from leadstream.common.pagination import StandardPagination

from .models import Suppression
from .serializers import (
    ApplyRetentionSerializer,
    RetentionRunSerializer,
    SuppressionCreateSerializer,
    SuppressionReadSerializer,
)


class SuppressionCollectionView(APIView):
    @extend_schema(responses=SuppressionReadSerializer(many=True), tags=["Dados — supressão"])
    def get(self, request: Request) -> Response:
        queryset = Suppression.objects.filter(tenant=resolve_tenant(request)).order_by(
            "-created_at"
        )
        paginator = StandardPagination()
        page = paginator.paginate_queryset(queryset, request, view=self)
        return paginator.get_paginated_response(SuppressionReadSerializer(page, many=True).data)

    @extend_schema(
        request=SuppressionCreateSerializer,
        responses={201: SuppressionReadSerializer},
        tags=["Dados — supressão"],
    )
    def post(self, request: Request) -> Response:
        reject_tenant_override(request.data)
        tenant = resolve_tenant(request)
        serializer = SuppressionCreateSerializer(data=request.data, context={"tenant": tenant})
        serializer.is_valid(raise_exception=True)
        try:
            suppression = serializer.save()
        except (ValueError, DjangoValidationError) as exc:
            raise ValidationError({"erro": str(exc)}) from exc
        return Response(
            SuppressionReadSerializer(suppression).data,
            status=status.HTTP_201_CREATED,
        )


class ApplyRetentionView(APIView):
    @extend_schema(
        request=ApplyRetentionSerializer,
        responses={201: RetentionRunSerializer},
        tags=["Dados — retenção"],
    )
    def post(self, request: Request) -> Response:
        reject_tenant_override(request.data)
        tenant = resolve_tenant(request)
        serializer = ApplyRetentionSerializer(data=request.data, context={"tenant": tenant})
        serializer.is_valid(raise_exception=True)
        try:
            run = serializer.save()
        except DjangoValidationError as exc:
            raise ValidationError({"erro": str(exc)}) from exc
        return Response(RetentionRunSerializer(run).data, status=status.HTTP_201_CREATED)
