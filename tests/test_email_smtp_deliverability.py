from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from leadstream.validation.smtp_probe import (
    DeliverabilityStatus,
    clear_smtp_cache,
    verify_email_smtp_deep,
)


@pytest.fixture(autouse=True)
def _clear_cache():
    clear_smtp_cache()
    yield
    clear_smtp_cache()


def test_verify_email_invalid_syntax():
    res = verify_email_smtp_deep("email-invalido@")
    assert res["status"] == DeliverabilityStatus.INVALID_SYNTAX
    assert res["is_deliverable"] is False
    assert res["score_confiabilidade"] == 0.0


def test_verify_email_disposable():
    res = verify_email_smtp_deep("teste@tempmail.com")
    assert res["status"] == DeliverabilityStatus.DISPOSABLE
    assert res["is_deliverable"] is False
    assert res["is_disposable"] is True


@patch("leadstream.validation.smtp_probe.check_domain_mx")
def test_verify_email_no_mx(mock_mx):
    mock_mx.return_value = {"mx_found": False, "mail_servers": []}
    res = verify_email_smtp_deep("contato@dominio-inexistente-xyz.com.br")
    assert res["status"] == DeliverabilityStatus.NO_MX
    assert res["is_deliverable"] is False


@patch("leadstream.validation.smtp_probe.check_domain_mx")
@patch("leadstream.validation.smtp_probe.smtplib.SMTP")
def test_verify_email_smtp_deliverable(mock_smtp_cls, mock_mx):
    mock_mx.return_value = {"mx_found": True, "mail_servers": ["mx.empresa.com.br"]}
    mock_client = MagicMock()
    mock_smtp_cls.return_value.__enter__.return_value = mock_client

    mock_client.ehlo.return_value = (250, b"OK")
    mock_client.mail.return_value = (250, b"OK")
    # Canary 550 (rejeitado), Target 250 (aceito)
    mock_client.rcpt.side_effect = [
        (550, b"User unknown"),  # canary
        (250, b"Recipient OK"),  # target
    ]

    res = verify_email_smtp_deep("ceo@empresa.com.br")
    assert res["status"] == DeliverabilityStatus.DELIVERABLE
    assert res["is_deliverable"] is True
    assert res["is_catch_all"] is False
    assert res["score_confiabilidade"] >= 0.95


@patch("leadstream.validation.smtp_probe.check_domain_mx")
@patch("leadstream.validation.smtp_probe.smtplib.SMTP")
def test_verify_email_smtp_catch_all(mock_smtp_cls, mock_mx):
    mock_mx.return_value = {"mx_found": True, "mail_servers": ["mx.empresa.com.br"]}
    mock_client = MagicMock()
    mock_smtp_cls.return_value.__enter__.return_value = mock_client

    mock_client.ehlo.return_value = (250, b"OK")
    mock_client.mail.return_value = (250, b"OK")
    # Ambos aceitos -> Catch-All
    mock_client.rcpt.side_effect = [
        (250, b"OK"),  # canary
        (250, b"OK"),  # target
    ]

    res = verify_email_smtp_deep("diretor@empresa.com.br")
    assert res["status"] == DeliverabilityStatus.RISKY_CATCH_ALL
    assert res["is_deliverable"] is False
    assert res["is_catch_all"] is True


@patch("leadstream.validation.smtp_probe.check_domain_mx")
@patch("leadstream.validation.smtp_probe.smtplib.SMTP")
def test_verify_email_smtp_mailbox_not_found(mock_smtp_cls, mock_mx):
    mock_mx.return_value = {"mx_found": True, "mail_servers": ["mx.empresa.com.br"]}
    mock_client = MagicMock()
    mock_smtp_cls.return_value.__enter__.return_value = mock_client

    mock_client.ehlo.return_value = (250, b"OK")
    mock_client.mail.return_value = (250, b"OK")
    # Canary 550, Target 550 (mailbox not found)
    mock_client.rcpt.side_effect = [
        (550, b"User unknown"),  # canary
        (550, b"Mailbox not found"),  # target
    ]

    res = verify_email_smtp_deep("fantasma@empresa.com.br")
    assert res["status"] == DeliverabilityStatus.UNDELIVERABLE_MAILBOX_NOT_FOUND
    assert res["is_deliverable"] is False
