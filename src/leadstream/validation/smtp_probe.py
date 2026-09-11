from __future__ import annotations

import logging
import smtplib
import uuid
from typing import Any

from leadstream.validation.dns_mx import check_domain_mx
from leadstream.validation.email_check import is_disposable_domain, validate_email_syntax

logger = logging.getLogger(__name__)


class DeliverabilityStatus:
    DELIVERABLE = "DELIVERABLE"
    RISKY_CATCH_ALL = "RISKY_CATCH_ALL"
    UNDELIVERABLE_MAILBOX_NOT_FOUND = "UNDELIVERABLE_MAILBOX_NOT_FOUND"
    NO_MX = "NO_MX"
    DISPOSABLE = "DISPOSABLE"
    INVALID_SYNTAX = "INVALID_SYNTAX"
    CONNECTION_ERROR = "CONNECTION_ERROR"


_SMTP_CACHE: dict[str, dict[str, Any]] = {}


def clear_smtp_cache() -> None:
    _SMTP_CACHE.clear()


def verify_email_smtp_deep(
    email: str,
    timeout: float = 3.0,
    check_catch_all: bool = True,
    sender_email: str = "verify@leadstream.com.br",
) -> dict[str, Any]:
    """Executa verificação em 5 etapas de entregabilidade atômica:
    1. Sintaxe RFC 5322
    2. Domínio descartável
    3. Registros DNS MX
    4. Handshake SMTP (EHLO/MAIL FROM/RCPT TO)
    5. Teste canário de servidor Catch-All
    """
    clean_email = (email or "").strip().lower()

    if not validate_email_syntax(clean_email):
        return {
            "endereco": clean_email,
            "status": DeliverabilityStatus.INVALID_SYNTAX,
            "is_deliverable": False,
            "is_catch_all": False,
            "is_disposable": False,
            "mx_server": None,
            "score_confiabilidade": 0.0,
            "details": "Sintaxe do e-mail não obedece ao padrão RFC 5322.",
        }

    _, domain = clean_email.split("@", 1)

    if is_disposable_domain(domain):
        return {
            "endereco": clean_email,
            "status": DeliverabilityStatus.DISPOSABLE,
            "is_deliverable": False,
            "is_catch_all": False,
            "is_disposable": True,
            "mx_server": None,
            "score_confiabilidade": 0.0,
            "details": "Domínio temporário/descartável identificado.",
        }

    if clean_email in _SMTP_CACHE:
        return _SMTP_CACHE[clean_email]

    mx_info = check_domain_mx(domain, timeout=timeout)
    if not mx_info.get("mx_found") or not mx_info.get("mail_servers"):
        result = {
            "endereco": clean_email,
            "status": DeliverabilityStatus.NO_MX,
            "is_deliverable": False,
            "is_catch_all": False,
            "is_disposable": False,
            "mx_server": None,
            "score_confiabilidade": 0.0,
            "details": "Nenhum servidor MX ou registro A encontrado para este domínio.",
        }
        _SMTP_CACHE[clean_email] = result
        return result

    mail_servers = mx_info["mail_servers"]
    chosen_server = mail_servers[0]

    try:
        with smtplib.SMTP(chosen_server, port=25, timeout=timeout) as smtp:
            smtp.ehlo_or_helo_if_needed()
            smtp.mail(sender_email)

            is_catch_all = False
            if check_catch_all:
                canary_mailbox = f"canary_probe_{uuid.uuid4().hex[:8]}@{domain}"
                canary_code, _ = smtp.rcpt(canary_mailbox)
                # Se aceitar 250 para um endereço aleatório inexistente, o servidor é catch-all
                if canary_code in (250, 251):
                    is_catch_all = True

            target_code, target_msg = smtp.rcpt(clean_email)
            if isinstance(target_msg, bytes):
                target_msg_str = target_msg.decode("utf-8", errors="ignore")
            else:
                target_msg_str = str(target_msg)

            smtp.rset()
            smtp.quit()

            if target_code in (250, 251):
                if is_catch_all:
                    status = DeliverabilityStatus.RISKY_CATCH_ALL
                    is_deliverable = False
                    score = 0.60
                    details = "Servidor aceita todos os e-mails (Catch-All). Risco de bounce."
                else:
                    status = DeliverabilityStatus.DELIVERABLE
                    is_deliverable = True
                    score = 0.98
                    details = "Caixa postal verificada e confirmada via SMTP."
            elif target_code in (550, 551, 552, 553, 554):
                status = DeliverabilityStatus.UNDELIVERABLE_MAILBOX_NOT_FOUND
                is_deliverable = False
                score = 0.0
                details = (
                    f"Caixa postal inexistente rejeitada pelo servidor "
                    f"(Código {target_code}: {target_msg_str})."
                )
            else:
                status = DeliverabilityStatus.CONNECTION_ERROR
                is_deliverable = False
                score = 0.40
                details = f"Resposta ambígua do servidor (Código {target_code}: {target_msg_str})."

            result = {
                "endereco": clean_email,
                "status": status,
                "is_deliverable": is_deliverable,
                "is_catch_all": is_catch_all,
                "is_disposable": False,
                "mx_server": chosen_server,
                "score_confiabilidade": score,
                "details": details,
            }
            _SMTP_CACHE[clean_email] = result
            return result

    except (smtplib.SMTPException, OSError) as exc:
        logger.debug(
            "Falha na sonda SMTP para %s no servidor %s: %s",
            clean_email,
            chosen_server,
            exc,
        )
        result = {
            "endereco": clean_email,
            "status": DeliverabilityStatus.CONNECTION_ERROR,
            "is_deliverable": False,
            "is_catch_all": False,
            "is_disposable": False,
            "mx_server": chosen_server,
            "score_confiabilidade": 0.40,
            "details": f"Não foi possível conectar ao servidor de e-mail ({chosen_server}): {exc}",
        }
        return result
