from __future__ import annotations

from drf_spectacular.utils import extend_schema
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from leadstream.common.api import resolve_tenant

from .serializers import WorkspaceSerializer


class WorkspaceView(APIView):
    @extend_schema(
        operation_id="consultar_workspace_atual",
        summary="Consultar workspace atual",
        description="Retorna somente o workspace autenticado na requisição.",
        responses={200: WorkspaceSerializer},
        tags=["Workspace"],
    )
    def get(self, request: Request) -> Response:
        tenant = resolve_tenant(request)
        return Response(WorkspaceSerializer(tenant).data)
