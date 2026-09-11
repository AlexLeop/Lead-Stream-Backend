from __future__ import annotations

from uuid import UUID

from django.core.exceptions import ValidationError as DjangoValidationError
from django.http import FileResponse, Http404, HttpResponse
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from leadstream.common.api import reject_tenant_override, resolve_tenant
from leadstream.common.pagination import StandardPagination
from leadstream.tenancy.services import get_internal_tenant

from .exporter import DEFAULT_EXPORT_COLUMNS, compute_export_hash
from .models import Batch, BatchChunk, BatchExport, BatchItem
from .serializers import (
    BatchChunkSerializer,
    BatchExportRequestSerializer,
    BatchExportSerializer,
    BatchItemSerializer,
    BatchSerializer,
    BatchUploadSerializer,
)
from .services import cancel_batch, create_csv_batch, pause_batch, resume_batch
from .storage import open_export
from .tasks import generate_export_task


def _get_batch(batch_id: UUID, request: Request | None = None) -> Batch:
    tenant = resolve_tenant(request)
    try:
        return Batch.objects.get(pk=batch_id, tenant=tenant)
    except Batch.DoesNotExist as exc:
        raise Http404("Lote não encontrado.") from exc


def _domain_error(exc: DjangoValidationError) -> ValidationError:
    if hasattr(exc, "message_dict"):
        return ValidationError(exc.message_dict)
    return ValidationError({"erro": exc.messages})


class BatchCollectionView(APIView):
    parser_classes = (MultiPartParser, FormParser)

    @extend_schema(responses=BatchSerializer(many=True), tags=["Lotes"])
    def get(self, request: Request) -> Response:
        tenant = resolve_tenant(request)
        queryset = Batch.objects.filter(tenant=tenant)
        requested_status = request.query_params.get("status")
        if requested_status:
            queryset = queryset.filter(status=requested_status)
        paginator = StandardPagination()
        page = paginator.paginate_queryset(queryset, request, view=self)
        return paginator.get_paginated_response(BatchSerializer(page, many=True).data)

    @extend_schema(
        request=BatchUploadSerializer,
        responses={200: BatchSerializer, 202: BatchSerializer},
        parameters=[
            OpenApiParameter(
                "Idempotency-Key",
                str,
                location=OpenApiParameter.HEADER,
                required=True,
                description="Chave estável da operação de upload.",
            )
        ],
        tags=["Lotes"],
    )
    def post(self, request: Request) -> Response:
        reject_tenant_override(request.data)
        serializer = BatchUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        tenant = resolve_tenant(request)

        from leadstream.billing.services import get_or_create_wallet, hold_credits

        wallet = get_or_create_wallet(tenant)
        if not wallet.is_unlimited and wallet.available_balance <= 0:
            raise ValidationError(
                {"carteira": "Saldo insuficiente na carteira. Por favor recarregue seus créditos."}
            )

        try:
            result = create_csv_batch(
                tenant=tenant,
                name=data.get("name", ""),
                upload=data["arquivo"],
                idempotency_key=request.headers.get("Idempotency-Key", ""),
                chunk_size=data["chunk_size"],
            )
        except DjangoValidationError as exc:
            raise _domain_error(exc) from exc

        if result.created and not wallet.is_unlimited:
            estimated_hold = min(
                wallet.available_balance, max(50, int(result.batch.total_rows or 50))
            )
            if estimated_hold > 0:
                try:
                    hold_credits(
                        wallet=wallet,
                        amount=estimated_hold,
                        batch=result.batch,
                        description=f"Reserva para lote {result.batch.name}",
                    )
                except DjangoValidationError:
                    pass

        response_status = status.HTTP_202_ACCEPTED if result.created else status.HTTP_200_OK
        return Response(BatchSerializer(result.batch).data, status=response_status)


class BatchDetailView(APIView):
    @extend_schema(responses=BatchSerializer, tags=["Lotes"])
    def get(self, request: Request, batch_id: UUID) -> Response:
        del request
        return Response(BatchSerializer(_get_batch(batch_id)).data)


class BatchItemsView(APIView):
    @extend_schema(responses=BatchItemSerializer(many=True), tags=["Lotes"])
    def get(self, request: Request, batch_id: UUID) -> Response:
        batch = _get_batch(batch_id)
        queryset = BatchItem.objects.filter(batch=batch, tenant=batch.tenant).order_by("row_number")
        paginator = StandardPagination()
        page = paginator.paginate_queryset(queryset, request, view=self)
        return paginator.get_paginated_response(BatchItemSerializer(page, many=True).data)


class BatchChunksView(APIView):
    @extend_schema(responses=BatchChunkSerializer(many=True), tags=["Lotes"])
    def get(self, request: Request, batch_id: UUID) -> Response:
        batch = _get_batch(batch_id)
        queryset = (
            BatchChunk.objects.filter(batch=batch, tenant=batch.tenant)
            .prefetch_related("attempts")
            .order_by("sequence")
        )
        paginator = StandardPagination()
        page = paginator.paginate_queryset(queryset, request, view=self)
        return paginator.get_paginated_response(BatchChunkSerializer(page, many=True).data)


class PauseBatchView(APIView):
    @extend_schema(request=None, responses=BatchSerializer, tags=["Lotes — comandos"])
    def post(self, request: Request, batch_id: UUID) -> Response:
        del request
        try:
            batch = pause_batch(tenant=get_internal_tenant(), batch_id=batch_id)
        except DjangoValidationError as exc:
            raise _domain_error(exc) from exc
        return Response(BatchSerializer(batch).data)


class ResumeBatchView(APIView):
    @extend_schema(request=None, responses=BatchSerializer, tags=["Lotes — comandos"])
    def post(self, request: Request, batch_id: UUID) -> Response:
        del request
        try:
            batch = resume_batch(tenant=get_internal_tenant(), batch_id=batch_id)
        except DjangoValidationError as exc:
            raise _domain_error(exc) from exc
        return Response(BatchSerializer(batch).data)


class CancelBatchView(APIView):
    @extend_schema(request=None, responses=BatchSerializer, tags=["Lotes — comandos"])
    def post(self, request: Request, batch_id: UUID) -> Response:
        del request
        batch = cancel_batch(tenant=get_internal_tenant(), batch_id=batch_id)
        return Response(BatchSerializer(batch).data)


class BatchExportCreateView(APIView):
    @extend_schema(
        request=BatchExportRequestSerializer,
        responses={200: BatchExportSerializer, 202: BatchExportSerializer},
        tags=["Lotes — exportação"],
    )
    def post(self, request: Request, batch_id: UUID) -> Response:
        batch = _get_batch(batch_id)
        serializer = BatchExportRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        columns = list(data.get("columns") or DEFAULT_EXPORT_COLUMNS)
        statuses = list(data.get("statuses") or [])
        lead_level = str(data.get("lead_level") or "DECISION_MAKER")

        export_hash = compute_export_hash(
            batch_id=batch.id,
            columns=columns,
            statuses=statuses,
            lead_level=lead_level,
            updated_at=batch.updated_at.isoformat(),
        )

        cached = BatchExport.objects.filter(
            tenant=batch.tenant,
            batch=batch,
            export_hash=export_hash,
            status=BatchExport.Status.COMPLETED,
        ).first()
        if cached:
            return Response(BatchExportSerializer(cached).data, status=status.HTTP_200_OK)

        export = BatchExport.objects.create(
            tenant=batch.tenant,
            batch=batch,
            status=BatchExport.Status.PENDING,
            selected_columns=columns,
            selected_statuses=statuses,
            lead_level=lead_level,
            export_hash=export_hash,
        )

        generate_export_task.delay(str(export.id))
        return Response(BatchExportSerializer(export).data, status=status.HTTP_202_ACCEPTED)


class BatchExportListView(APIView):
    @extend_schema(responses=BatchExportSerializer(many=True), tags=["Lotes — exportação"])
    def get(self, request: Request, batch_id: UUID) -> Response:
        batch = _get_batch(batch_id)
        queryset = BatchExport.objects.filter(batch=batch, tenant=batch.tenant).order_by(
            "-created_at"
        )
        paginator = StandardPagination()
        page = paginator.paginate_queryset(queryset, request, view=self)
        return paginator.get_paginated_response(BatchExportSerializer(page, many=True).data)


class ExportDetailView(APIView):
    @extend_schema(responses=BatchExportSerializer, tags=["Exportações"])
    def get(self, request: Request, export_id: UUID) -> Response:
        del request
        try:
            export = BatchExport.objects.get(pk=export_id, tenant=get_internal_tenant())
        except BatchExport.DoesNotExist as exc:
            raise Http404("Exportação não encontrada.") from exc
        return Response(BatchExportSerializer(export).data)


class ExportDownloadView(APIView):
    @extend_schema(
        responses={
            (200, "text/csv"): OpenApiResponse(
                description="Arquivo CSV em pt-BR com dados comerciais completos."
            )
        },
        tags=["Exportações"],
    )
    def get(self, request: Request, export_id: UUID) -> HttpResponse | FileResponse:

        del request
        try:
            export = BatchExport.objects.get(pk=export_id, tenant=get_internal_tenant())
        except BatchExport.DoesNotExist as exc:
            raise Http404("Exportação não encontrada.") from exc

        if export.status != BatchExport.Status.COMPLETED:
            raise ValidationError({"erro": "Exportação ainda não foi concluída."})

        file_obj = open_export(export.file_backend, export.file_key)
        response: HttpResponse | FileResponse
        if isinstance(file_obj, bytes):
            response = HttpResponse(file_obj, content_type=export.content_type)
        else:
            response = FileResponse(file_obj, content_type=export.content_type)

        response["Content-Disposition"] = f'attachment; filename="{export.file_name}"'
        response["X-Content-Type-Options"] = "nosniff"
        response["Cache-Control"] = "private, no-transform"
        return response
