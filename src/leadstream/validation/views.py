from __future__ import annotations

from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from leadstream.validation.email_check import validate_email_technical
from leadstream.validation.serializers import (
    EmailValidationRequestSerializer,
    EmailValidationResultSerializer,
)
from leadstream.validation.smtp_probe import verify_email_smtp_deep


class EmailValidationView(APIView):
    """Validação atômica e verificação profunda de entregabilidade de e-mail (Zero-Bounce)."""

    @extend_schema(
        request=EmailValidationRequestSerializer,
        responses={200: EmailValidationResultSerializer(many=True)},
        tags=["Validação & Entregabilidade"],
        summary="Verificar Entregabilidade de E-mail em Tempo Real",
    )
    def post(self, request: Request) -> Response:
        serializer = EmailValidationRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        target_emails: list[str] = []
        if data.get("email"):
            target_emails.append(str(data["email"]).strip())
        if data.get("emails"):
            for e in data["emails"]:
                clean = str(e).strip()
                if clean and clean not in target_emails:
                    target_emails.append(clean)

        deep_smtp = bool(data.get("deep_smtp", True))

        results = []
        for em in target_emails[:50]:  # Limite de segurança para 50 por request síncrono
            if deep_smtp:
                res = verify_email_smtp_deep(em)
            else:
                res = validate_email_technical(em, deep_smtp=False)
                res["is_deliverable"] = res["status"] in ("ENTREGAVEL", "ENTREGAVEL_VALIDADO")
                res["is_catch_all"] = False
                res["is_disposable"] = res["tipo"] == "DESCARTAVEL"
                res["mx_server"] = None
                res["details"] = "Verificação estática DNS/Sintaxe."
            results.append(res)

        if len(target_emails) == 1 and data.get("email") and not data.get("emails"):
            return Response(results[0], status=status.HTTP_200_OK)

        return Response(
            {"count": len(results), "results": results},
            status=status.HTTP_200_OK,
        )
