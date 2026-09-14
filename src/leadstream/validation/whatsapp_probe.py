from __future__ import annotations

import logging
from typing import Any

import httpx
from django.conf import settings
from django.utils import timezone

from leadstream.common.redaction import mask_phone

logger = logging.getLogger(__name__)


def clean_digits(value: str) -> str:
    return "".join(c for c in str(value or "") if c.isdigit())


def format_e164_whatsapp_br(phone: str, ddd: str = "") -> str:
    """Normaliza o telefone para o padrão do WhatsApp no Brasil (DDI 55 + DDD + dígitos)."""
    digits = clean_digits(phone)
    clean_ddd = clean_digits(ddd)

    if not digits:
        return ""

    # Remove DDI 55 se já estiver no início
    if digits.startswith("55") and len(digits) in (12, 13):
        digits = digits[2:]

    # Remove 0 inicial no DDD ou número
    if clean_ddd.startswith("0") and len(clean_ddd) == 3:
        clean_ddd = clean_ddd[1:]
    if digits.startswith("0") and len(digits) in (11, 12):
        digits = digits[1:]

    if len(digits) in (10, 11):
        detected_ddd = digits[:2]
        number_part = digits[2:]
    elif len(digits) in (8, 9):
        detected_ddd = clean_ddd
        number_part = digits
    else:
        detected_ddd = clean_ddd
        number_part = digits

    if detected_ddd and number_part:
        return f"55{detected_ddd}{number_part}"
    return digits


def format_display_phone_br(e164_digits: str) -> str:
    """Converte dígitos E.164 (5511999999999) em formato legível '(11) 99999-9999'."""
    d = clean_digits(e164_digits)
    if d.startswith("55") and len(d) in (12, 13):
        d = d[2:]
    if len(d) == 11:
        return f"({d[:2]}) {d[2:7]}-{d[7:]}"
    if len(d) == 10:
        return f"({d[:2]}) {d[2:6]}-{d[6:]}"
    return e164_digits


def is_whatsapp_probe_configured() -> bool:
    """Verifica se o gateway de WhatsApp (Evolution API / WPPConnect) está configurado."""
    probe_url = getattr(settings, "WHATSAPP_PROBE_URL", None)
    probe_key = getattr(settings, "WHATSAPP_PROBE_API_KEY", None)
    return bool(probe_url and probe_key)


def check_evolution_api(
    base_url: str,
    api_key: str,
    instance: str,
    phone_e164: str,
    timeout: float,
    client: httpx.Client | None = None,
) -> dict[str, Any]:
    """Consulta de verificação de número na Evolution API / EvolutionGo."""
    url = f"{base_url.rstrip('/')}/chat/whatsappNumbers/{instance}"
    headers = {
        "apikey": api_key,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    payload = {"numbers": [phone_e164]}

    http_client = client or httpx.Client(timeout=timeout)
    try:
        response = http_client.post(url, headers=headers, json=payload)
        response.raise_for_status()
        data = response.json()
    finally:
        if client is None:
            http_client.close()

    # O retorno comum é uma lista de objetos: [{"exists": true, "jid": "...", "number": "..."}]
    item: dict[str, Any] = {}
    if isinstance(data, list) and data:
        first = data[0]
        if isinstance(first, dict):
            item = first
    elif isinstance(data, dict):
        if "exists" in data:
            item = data
        elif isinstance(data.get("response"), list) and data["response"]:
            first = data["response"][0]
            if isinstance(first, dict):
                item = first

    exists = bool(item.get("exists", False))
    jid = str(item.get("jid") or item.get("id") or "")
    if not jid and exists:
        jid = f"{phone_e164}@s.whatsapp.net"

    is_business = bool(item.get("isBusiness", False))

    profile_pic = None
    # Se existe, tenta buscar a foto de perfil
    if exists:
        try:
            pic_url = f"{base_url.rstrip('/')}/chat/fetchProfilePictureUrl/{instance}"
            pic_client = client or httpx.Client(timeout=5.0)
            try:
                pic_res = pic_client.post(pic_url, headers=headers, json={"number": phone_e164})
                if pic_res.status_code == 200:
                    pic_data = pic_res.json()
                    profile_pic = (
                        pic_data.get("profilePictureUrl")
                        or pic_data.get("url")
                        or pic_data.get("picture")
                    )
            finally:
                if client is None:
                    pic_client.close()
        except Exception as exc:  # noqa: BLE001
            logger.debug(
                "Não foi possível obter foto de perfil para %s: %s",
                mask_phone(phone_e164),
                exc.__class__.__name__,
            )

    return {
        "exists": exists,
        "jid": jid if exists else None,
        "is_business": is_business,
        "profile_pic": profile_pic,
    }


def check_wppconnect(
    base_url: str,
    api_key: str,
    session: str,
    phone_e164: str,
    timeout: float,
    client: httpx.Client | None = None,
) -> dict[str, Any]:
    """Consulta de verificação de número no WPPConnect Server."""
    url = f"{base_url.rstrip('/')}/api/{session}/check-number-status/{phone_e164}"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    http_client = client or httpx.Client(timeout=timeout)
    try:
        response = http_client.get(url, headers=headers)
        response.raise_for_status()
        data = response.json()
    finally:
        if client is None:
            http_client.close()

    resp_obj = data.get("response", {}) if isinstance(data, dict) else {}
    exists = bool(resp_obj.get("numberExists") or resp_obj.get("canReceiveMessage"))
    raw_id = resp_obj.get("id")
    jid = raw_id.get("_serialized") if isinstance(raw_id, dict) else str(raw_id or "")

    return {
        "exists": exists,
        "jid": jid if exists else None,
        "is_business": bool(resp_obj.get("isBusiness", False)),
        "profile_pic": None,
    }


def verify_whatsapp_active(
    phone: str,
    ddd: str = "",
    client: httpx.Client | None = None,
) -> dict[str, Any]:
    """Executa a verificação técnica ativa e em tempo real da existência de conta no WhatsApp.

    IMPORTANTE: Não utiliza dados simulados/fictícios. Caso o gateway de WhatsApp
    não esteja configurado ou esteja inacessível, retorna status explícito de indisponibilidade.
    """
    e164 = format_e164_whatsapp_br(phone, ddd=ddd)
    display_phone = format_display_phone_br(e164)

    if len(e164) < 12 or len(e164) > 13:
        return {
            "configurado": True,
            "disponivel": True,
            "sucesso": False,
            "status": "NUMERO_INVALIDO",
            "tem_whatsapp": False,
            "tipo_conta": "NENHUMA",
            "jid": None,
            "numero_e164": e164,
            "numero_formatado": display_phone,
            "foto_perfil": None,
            "recado": None,
            "provedor": None,
            "verificado_em": timezone.now().isoformat(),
            "detalhes": f"Número '{phone}' não corresponde ao padrão telefônico brasileiro.",
        }

    if not is_whatsapp_probe_configured():
        return {
            "configurado": False,
            "disponivel": False,
            "sucesso": False,
            "status": "INDISPONIVEL",
            "tem_whatsapp": False,
            "tipo_conta": "DESCONHECIDA",
            "jid": None,
            "numero_e164": e164,
            "numero_formatado": display_phone,
            "foto_perfil": None,
            "recado": None,
            "provedor": None,
            "verificado_em": timezone.now().isoformat(),
            "detalhes": (
                "Gateway de WhatsApp (Evolution API / WPPConnect) não está configurado. "
                "Defina WHATSAPP_PROBE_URL e WHATSAPP_PROBE_API_KEY no ambiente."
            ),
        }

    provider = getattr(settings, "WHATSAPP_PROBE_PROVIDER", "evolution").lower()
    base_url = getattr(settings, "WHATSAPP_PROBE_URL", "")
    api_key = getattr(settings, "WHATSAPP_PROBE_API_KEY", "")
    instance = getattr(settings, "WHATSAPP_PROBE_INSTANCE", "leadstream")
    timeout = float(getattr(settings, "WHATSAPP_PROBE_TIMEOUT_SECONDS", 10))

    try:
        if "wppconnect" in provider:
            res = check_wppconnect(
                base_url=base_url,
                api_key=api_key,
                session=instance,
                phone_e164=e164,
                timeout=timeout,
                client=client,
            )
            provedor_label = "WPPConnect Server"
        else:
            res = check_evolution_api(
                base_url=base_url,
                api_key=api_key,
                instance=instance,
                phone_e164=e164,
                timeout=timeout,
                client=client,
            )
            provedor_label = "Evolution API (EvolutionGo)"

        exists = res["exists"]
        is_business = res["is_business"]
        if is_business:
            tipo_conta = "WHATSAPP_BUSINESS"
        elif exists:
            tipo_conta = "WHATSAPP_PESSOAL"
        else:
            tipo_conta = "NENHUMA"

        return {
            "configurado": True,
            "disponivel": True,
            "sucesso": True,
            "status": "VALIDADO_ATIVO" if exists else "SEM_CONTA_WHATSAPP",
            "tem_whatsapp": exists,
            "tipo_conta": tipo_conta,
            "jid": res["jid"],
            "numero_e164": e164,
            "numero_formatado": display_phone,
            "foto_perfil": res["profile_pic"],
            "recado": None,
            "provedor": provedor_label,
            "verificado_em": timezone.now().isoformat(),
            "detalhes": (
                "Conta ativa e confirmada diretamente na rede do WhatsApp."
                if exists
                else "Número não possui conta ativa registrada no WhatsApp."
            ),
        }

    except httpx.TimeoutException:
        logger.warning("Timeout ao consultar probe de WhatsApp para o número %s", mask_phone(e164))
        return {
            "configurado": True,
            "disponivel": False,
            "sucesso": False,
            "status": "TIMEOUT",
            "tem_whatsapp": False,
            "tipo_conta": "DESCONHECIDA",
            "jid": None,
            "numero_e164": e164,
            "numero_formatado": display_phone,
            "foto_perfil": None,
            "recado": None,
            "provedor": provider,
            "verificado_em": timezone.now().isoformat(),
            "detalhes": f"Tempo limite de {timeout}s excedido ao consultar o gateway de WhatsApp.",
        }
    except httpx.HTTPStatusError as exc:
        logger.error("Erro HTTP %s no gateway de WhatsApp: %s", exc.response.status_code, exc)
        return {
            "configurado": True,
            "disponivel": False,
            "sucesso": False,
            "status": "ERRO_GATEWAY",
            "tem_whatsapp": False,
            "tipo_conta": "DESCONHECIDA",
            "jid": None,
            "numero_e164": e164,
            "numero_formatado": display_phone,
            "foto_perfil": None,
            "recado": None,
            "provedor": provider,
            "verificado_em": timezone.now().isoformat(),
            "detalhes": f"Falha na comunicação com o gateway (HTTP {exc.response.status_code}).",
        }
    except Exception as exc:
        logger.exception(
            "Falha inesperada no probe de WhatsApp para %s: %s",
            mask_phone(e164),
            exc.__class__.__name__,
        )
        return {
            "configurado": True,
            "disponivel": False,
            "sucesso": False,
            "status": "FALHA_CONEXAO",
            "tem_whatsapp": False,
            "tipo_conta": "DESCONHECIDA",
            "jid": None,
            "numero_e164": e164,
            "numero_formatado": display_phone,
            "foto_perfil": None,
            "recado": None,
            "provedor": provider,
            "verificado_em": timezone.now().isoformat(),
            "detalhes": f"Erro de conexão com o gateway de WhatsApp: {exc}",
        }
