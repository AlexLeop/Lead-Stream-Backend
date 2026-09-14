from __future__ import annotations

from typing import Any

from django.core.exceptions import ObjectDoesNotExist
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError
from django.db.models import QuerySet
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.serializers import BaseSerializer
from rest_framework.views import APIView

from leadstream.common.api import reject_tenant_override, resolve_tenant
from leadstream.common.pagination import StandardPagination

from .models import (
    CanonicalDecision,
    Conflict,
    Evidence,
    Observation,
    ProcessingPurpose,
    RetentionPolicy,
    Source,
    SourceRecord,
)
from .serializers import (
    CanonicalDecisionSerializer,
    CanonicalizeInputSerializer,
    ConflictSerializer,
    EvidenceSerializer,
    ObservationSerializer,
    PurposeSerializer,
    RetentionPolicySerializer,
    SourceRecordSerializer,
    SourceSerializer,
)


def _paginated(
    *,
    request: Request,
    view: APIView,
    queryset: QuerySet[Any],
    serializer: type[BaseSerializer[Any]],
) -> Response:
    paginator = StandardPagination()
    page = paginator.paginate_queryset(queryset, request, view=view)
    return paginator.get_paginated_response(serializer(page, many=True).data)


def _save(serializer: BaseSerializer[Any]) -> Response:
    try:
        instance = serializer.save()
    except (DjangoValidationError, IntegrityError, ObjectDoesNotExist) as exc:
        raise ValidationError({"erro": str(exc)}) from exc
    return Response(type(serializer)(instance).data, status=status.HTTP_201_CREATED)


class PurposeCollectionView(APIView):
    @extend_schema(responses=PurposeSerializer(many=True), tags=["Dados — governança"])
    def get(self, request: Request) -> Response:
        queryset = ProcessingPurpose.objects.filter(tenant=resolve_tenant(request)).order_by("code")
        return _paginated(
            request=request, view=self, queryset=queryset, serializer=PurposeSerializer
        )

    @extend_schema(
        request=PurposeSerializer, responses={201: PurposeSerializer}, tags=["Dados — governança"]
    )
    def post(self, request: Request) -> Response:
        reject_tenant_override(request.data)
        serializer = PurposeSerializer(
            data=request.data,
            context={"tenant": resolve_tenant(request)},
        )
        serializer.is_valid(raise_exception=True)
        return _save(serializer)


class RetentionPolicyCollectionView(APIView):
    @extend_schema(responses=RetentionPolicySerializer(many=True), tags=["Dados — governança"])
    def get(self, request: Request) -> Response:
        queryset = RetentionPolicy.objects.filter(tenant=resolve_tenant(request)).order_by("code")
        return _paginated(
            request=request, view=self, queryset=queryset, serializer=RetentionPolicySerializer
        )

    @extend_schema(
        request=RetentionPolicySerializer,
        responses={201: RetentionPolicySerializer},
        tags=["Dados — governança"],
    )
    def post(self, request: Request) -> Response:
        reject_tenant_override(request.data)
        serializer = RetentionPolicySerializer(
            data=request.data, context={"tenant": resolve_tenant(request)}
        )
        serializer.is_valid(raise_exception=True)
        return _save(serializer)


class SourceCollectionView(APIView):
    @extend_schema(responses=SourceSerializer(many=True), tags=["Dados — fontes"])
    def get(self, request: Request) -> Response:
        queryset = Source.objects.filter(tenant=resolve_tenant(request)).order_by(
            "-priority", "name"
        )
        return _paginated(
            request=request, view=self, queryset=queryset, serializer=SourceSerializer
        )

    @extend_schema(
        request=SourceSerializer, responses={201: SourceSerializer}, tags=["Dados — fontes"]
    )
    def post(self, request: Request) -> Response:
        reject_tenant_override(request.data)
        serializer = SourceSerializer(
            data=request.data,
            context={"tenant": resolve_tenant(request)},
        )
        serializer.is_valid(raise_exception=True)
        return _save(serializer)


class SourceRecordCollectionView(APIView):
    @extend_schema(responses=SourceRecordSerializer(many=True), tags=["Dados — fontes"])
    def get(self, request: Request) -> Response:
        queryset = SourceRecord.objects.filter(tenant=resolve_tenant(request)).order_by(
            "-captured_at"
        )
        return _paginated(
            request=request, view=self, queryset=queryset, serializer=SourceRecordSerializer
        )

    @extend_schema(
        request=SourceRecordSerializer,
        responses={201: SourceRecordSerializer},
        tags=["Dados — fontes"],
    )
    def post(self, request: Request) -> Response:
        reject_tenant_override(request.data)
        serializer = SourceRecordSerializer(
            data=request.data, context={"tenant": resolve_tenant(request)}
        )
        serializer.is_valid(raise_exception=True)
        return _save(serializer)


class EvidenceCollectionView(APIView):
    @extend_schema(responses=EvidenceSerializer(many=True), tags=["Dados — evidências"])
    def get(self, request: Request) -> Response:
        queryset = Evidence.objects.filter(tenant=resolve_tenant(request)).order_by("-captured_at")
        return _paginated(
            request=request, view=self, queryset=queryset, serializer=EvidenceSerializer
        )

    @extend_schema(
        request=EvidenceSerializer,
        responses={201: EvidenceSerializer},
        tags=["Dados — evidências"],
    )
    def post(self, request: Request) -> Response:
        reject_tenant_override(request.data)
        serializer = EvidenceSerializer(
            data=request.data, context={"tenant": resolve_tenant(request)}
        )
        serializer.is_valid(raise_exception=True)
        return _save(serializer)


class ObservationCollectionView(APIView):
    @extend_schema(responses=ObservationSerializer(many=True), tags=["Dados — observações"])
    def get(self, request: Request) -> Response:
        queryset = Observation.objects.filter(tenant=resolve_tenant(request)).select_related(
            "source_record__source", "source_record__purpose"
        )
        if target := request.query_params.get("target"):
            queryset = queryset.filter(target_id=target)
        if field_path := request.query_params.get("field_path"):
            queryset = queryset.filter(field_path=field_path)
        return _paginated(
            request=request,
            view=self,
            queryset=queryset.order_by("-observed_at"),
            serializer=ObservationSerializer,
        )

    @extend_schema(
        request=ObservationSerializer,
        responses={201: ObservationSerializer},
        tags=["Dados — observações"],
    )
    def post(self, request: Request) -> Response:
        reject_tenant_override(request.data)
        serializer = ObservationSerializer(
            data=request.data, context={"tenant": resolve_tenant(request)}
        )
        serializer.is_valid(raise_exception=True)
        return _save(serializer)


class CanonicalizeView(APIView):
    @extend_schema(
        request=CanonicalizeInputSerializer,
        responses={201: CanonicalDecisionSerializer},
        tags=["Dados — canonização"],
    )
    def post(self, request: Request) -> Response:
        reject_tenant_override(request.data)
        serializer = CanonicalizeInputSerializer(
            data=request.data, context={"tenant": resolve_tenant(request)}
        )
        serializer.is_valid(raise_exception=True)
        try:
            decision = serializer.save()
        except (DjangoValidationError, ObjectDoesNotExist) as exc:
            raise ValidationError({"erro": str(exc)}) from exc
        return Response(
            CanonicalDecisionSerializer(decision).data,
            status=status.HTTP_201_CREATED,
        )


class CanonicalDecisionCollectionView(APIView):
    @extend_schema(responses=CanonicalDecisionSerializer(many=True), tags=["Dados — canonização"])
    def get(self, request: Request) -> Response:
        queryset = CanonicalDecision.objects.filter(tenant=resolve_tenant(request)).select_related(
            "selected_observation__source_record__source"
        )
        if target := request.query_params.get("target"):
            queryset = queryset.filter(target_id=target)
        if field_path := request.query_params.get("field_path"):
            queryset = queryset.filter(field_path=field_path)
        return _paginated(
            request=request,
            view=self,
            queryset=queryset.order_by("-decided_at"),
            serializer=CanonicalDecisionSerializer,
        )


class ConflictCollectionView(APIView):
    @extend_schema(responses=ConflictSerializer(many=True), tags=["Dados — conflitos"])
    def get(self, request: Request) -> Response:
        queryset = Conflict.objects.filter(tenant=resolve_tenant(request)).order_by("-created_at")
        return _paginated(
            request=request, view=self, queryset=queryset, serializer=ConflictSerializer
        )

    @extend_schema(
        request=ConflictSerializer,
        responses={201: ConflictSerializer},
        tags=["Dados — conflitos"],
    )
    def post(self, request: Request) -> Response:
        reject_tenant_override(request.data)
        serializer = ConflictSerializer(
            data=request.data, context={"tenant": resolve_tenant(request)}
        )
        serializer.is_valid(raise_exception=True)
        return _save(serializer)
