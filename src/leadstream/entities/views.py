from __future__ import annotations

from uuid import UUID

from django.core.exceptions import ValidationError as DjangoValidationError
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from leadstream.common.api import reject_tenant_override, resolve_tenant
from leadstream.common.pagination import StandardPagination

from .models import Company, ContactPoint, Establishment, Person, Relationship, SocialProfile
from .normalization import DataValidationError
from .serializers import (
    CompanyCreateSerializer,
    CompanyReadSerializer,
    ContactPointSerializer,
    EstablishmentSerializer,
    PersonCreateSerializer,
    PersonReadSerializer,
    RelationshipSerializer,
    SocialProfileSerializer,
)


def _domain_error(exc: Exception) -> ValidationError:
    return ValidationError({"erro": str(exc)})


class CompanyCollectionView(APIView):
    @extend_schema(responses=CompanyReadSerializer(many=True), tags=["Dados — empresas"])
    def get(self, request: Request) -> Response:
        tenant = resolve_tenant(request)
        queryset = Company.objects.filter(entity__tenant=tenant).prefetch_related("establishments")
        cnpj_root = request.query_params.get("cnpj_root")
        if cnpj_root:
            queryset = queryset.filter(cnpj_root=cnpj_root)
        paginator = StandardPagination()
        page = paginator.paginate_queryset(queryset.order_by("legal_name"), request, view=self)
        return paginator.get_paginated_response(CompanyReadSerializer(page, many=True).data)

    @extend_schema(
        request=CompanyCreateSerializer,
        responses={201: CompanyReadSerializer},
        tags=["Dados — empresas"],
    )
    def post(self, request: Request) -> Response:
        reject_tenant_override(request.data)
        tenant = resolve_tenant(request)
        serializer = CompanyCreateSerializer(data=request.data, context={"tenant": tenant})
        serializer.is_valid(raise_exception=True)
        try:
            company = serializer.save()
        except (DataValidationError, DjangoValidationError) as exc:
            raise _domain_error(exc) from exc
        return Response(CompanyReadSerializer(company).data, status=status.HTTP_201_CREATED)


class EstablishmentCollectionView(APIView):
    @extend_schema(responses=EstablishmentSerializer(many=True), tags=["Dados — empresas"])
    def get(self, request: Request) -> Response:
        queryset = Establishment.objects.filter(entity__tenant=resolve_tenant(request))
        paginator = StandardPagination()
        page = paginator.paginate_queryset(queryset.order_by("cnpj"), request, view=self)
        return paginator.get_paginated_response(EstablishmentSerializer(page, many=True).data)


class PersonCollectionView(APIView):
    @extend_schema(responses=PersonReadSerializer(many=True), tags=["Dados — pessoas"])
    def get(self, request: Request) -> Response:
        queryset = Person.objects.filter(entity__tenant=resolve_tenant(request))
        name = request.query_params.get("nome")
        if name:
            queryset = queryset.filter(normalized_name__icontains=name)
        paginator = StandardPagination()
        page = paginator.paginate_queryset(queryset.order_by("full_name"), request, view=self)
        return paginator.get_paginated_response(PersonReadSerializer(page, many=True).data)

    @extend_schema(
        request=PersonCreateSerializer,
        responses={201: PersonReadSerializer},
        tags=["Dados — pessoas"],
    )
    def post(self, request: Request) -> Response:
        reject_tenant_override(request.data)
        tenant = resolve_tenant(request)
        serializer = PersonCreateSerializer(data=request.data, context={"tenant": tenant})
        serializer.is_valid(raise_exception=True)
        try:
            person = serializer.save()
        except (DataValidationError, DjangoValidationError) as exc:
            raise _domain_error(exc) from exc
        return Response(PersonReadSerializer(person).data, status=status.HTTP_201_CREATED)


class RelationshipCollectionView(APIView):
    @extend_schema(responses=RelationshipSerializer(many=True), tags=["Dados — vínculos"])
    def get(self, request: Request) -> Response:
        queryset = Relationship.objects.filter(tenant=resolve_tenant(request))
        company_id = request.query_params.get("empresa")
        if company_id:
            try:
                queryset = queryset.filter(company_id=UUID(company_id))
            except ValueError as exc:
                raise ValidationError({"empresa": "Identificador de empresa inválido."}) from exc
        paginator = StandardPagination()
        page = paginator.paginate_queryset(queryset.order_by("-created_at"), request, view=self)
        return paginator.get_paginated_response(RelationshipSerializer(page, many=True).data)

    @extend_schema(
        request=RelationshipSerializer,
        responses={201: RelationshipSerializer},
        tags=["Dados — vínculos"],
    )
    def post(self, request: Request) -> Response:
        reject_tenant_override(request.data)
        tenant = resolve_tenant(request)
        serializer = RelationshipSerializer(data=request.data, context={"tenant": tenant})
        serializer.is_valid(raise_exception=True)
        try:
            relationship = serializer.save()
        except DjangoValidationError as exc:
            raise _domain_error(exc) from exc
        return Response(RelationshipSerializer(relationship).data, status=status.HTTP_201_CREATED)


class ContactCollectionView(APIView):
    @extend_schema(responses=ContactPointSerializer(many=True), tags=["Dados — contatos"])
    def get(self, request: Request) -> Response:
        queryset = ContactPoint.objects.filter(tenant=resolve_tenant(request))
        kind = request.query_params.get("tipo")
        if kind:
            queryset = queryset.filter(kind=kind)
        paginator = StandardPagination()
        page = paginator.paginate_queryset(queryset.order_by("-created_at"), request, view=self)
        return paginator.get_paginated_response(ContactPointSerializer(page, many=True).data)

    @extend_schema(
        request=ContactPointSerializer,
        responses={201: ContactPointSerializer},
        tags=["Dados — contatos"],
    )
    def post(self, request: Request) -> Response:
        reject_tenant_override(request.data)
        tenant = resolve_tenant(request)
        serializer = ContactPointSerializer(data=request.data, context={"tenant": tenant})
        serializer.is_valid(raise_exception=True)
        try:
            contact = serializer.save()
        except (DataValidationError, DjangoValidationError) as exc:
            raise _domain_error(exc) from exc
        return Response(ContactPointSerializer(contact).data, status=status.HTTP_201_CREATED)


class SocialProfileCollectionView(APIView):
    @extend_schema(responses=SocialProfileSerializer(many=True), tags=["Dados — perfis sociais"])
    def get(self, request: Request) -> Response:
        queryset = SocialProfile.objects.filter(tenant=resolve_tenant(request))
        network = request.query_params.get("rede")
        if network:
            queryset = queryset.filter(network=network)
        paginator = StandardPagination()
        page = paginator.paginate_queryset(queryset.order_by("-created_at"), request, view=self)
        return paginator.get_paginated_response(SocialProfileSerializer(page, many=True).data)

    @extend_schema(
        request=SocialProfileSerializer,
        responses={201: SocialProfileSerializer},
        tags=["Dados — perfis sociais"],
    )
    def post(self, request: Request) -> Response:
        reject_tenant_override(request.data)
        tenant = resolve_tenant(request)
        serializer = SocialProfileSerializer(data=request.data, context={"tenant": tenant})
        serializer.is_valid(raise_exception=True)
        try:
            profile = serializer.save()
        except (DataValidationError, DjangoValidationError) as exc:
            raise _domain_error(exc) from exc
        return Response(SocialProfileSerializer(profile).data, status=status.HTTP_201_CREATED)
