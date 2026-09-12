from __future__ import annotations

from typing import Any, ClassVar

from rest_framework import permissions, serializers, status
from rest_framework.permissions import AllowAny, IsAdminUser
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from leadstream.security.authentication import CombinedAuthentication
from leadstream.tenancy.branding_models import PlatformBranding


class PlatformBrandingSerializer(serializers.ModelSerializer[PlatformBranding]):
    class Meta:
        model = PlatformBranding
        fields: ClassVar[list[str]] = [
            "platform_name",
            "logo_url_dark",
            "logo_url_light",
            "favicon_url",
            "accent_color",
            "support_email",
            "terms_url",
            "privacy_url",
        ]


class BrandingView(APIView):
    """Retorna e permite atualização da configuração White-Label da plataforma."""

    authentication_classes = (CombinedAuthentication,)

    def get_permissions(self) -> list[permissions.BasePermission]:
        if self.request.method == "GET":
            return [AllowAny()]
        return [IsAdminUser()]

    def get(self, request: Request) -> Response:
        branding = PlatformBranding.get_active()
        serializer = PlatformBrandingSerializer(branding)
        return Response(serializer.data)

    def patch(self, request: Request) -> Response:
        branding = PlatformBranding.get_active()
        data: dict[str, Any] = request.data if isinstance(request.data, dict) else {}
        serializer = PlatformBrandingSerializer(branding, data=data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_200_OK)
