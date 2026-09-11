from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

WELL_KNOWN_MX_DOMAINS: dict[str, list[str]] = {
    "gmail.com": ["gmail-smtp-in.l.google.com"],
    "googlemail.com": ["gmail-smtp-in.l.google.com"],
    "outlook.com": ["outlook-com.olc.protection.outlook.com"],
    "hotmail.com": ["hotmail-com.olc.protection.outlook.com"],
    "live.com": ["live-com.olc.protection.outlook.com"],
    "yahoo.com": ["mta5.am0.yahoodns.net"],
    "yahoo.com.br": ["mta5.am0.yahoodns.net"],
    "uol.com.br": ["mx.uol.com.br"],
    "bol.com.br": ["mx.uol.com.br"],
    "terra.com.br": ["mx.terra.com.br"],
    "ig.com.br": ["mx.ig.com.br"],
}

_MEMORY_DNS_CACHE: dict[str, dict[str, Any]] = {}


def check_domain_mx(domain: str, timeout: float = 2.0) -> dict[str, Any]:
    dom = domain.strip().lower()
    if not dom:
        return {"mx_found": False, "mail_servers": [], "has_spf": False, "has_dmarc": False}

    if dom in _MEMORY_DNS_CACHE:
        return _MEMORY_DNS_CACHE[dom]

    if dom in WELL_KNOWN_MX_DOMAINS:
        result = {
            "mx_found": True,
            "mail_servers": WELL_KNOWN_MX_DOMAINS[dom],
            "has_spf": True,
            "has_dmarc": True,
        }
        _MEMORY_DNS_CACHE[dom] = result
        return result

    try:
        import dns.exception
        import dns.resolver

        resolver = dns.resolver.Resolver()
        resolver.lifetime = timeout
        resolver.timeout = timeout

        try:
            answers = resolver.resolve(dom, "MX")
            servers = [str(r.exchange).rstrip(".") for r in answers]
            mx_found = len(servers) > 0
        except (
            dns.resolver.NXDOMAIN,
            dns.resolver.NoAnswer,
            dns.resolver.NoNameservers,
            dns.exception.DNSException,
        ):
            # Fallback to A record if MX doesn't exist
            try:
                answers_a = resolver.resolve(dom, "A")
                servers = [dom] if len(answers_a) > 0 else []
                mx_found = len(servers) > 0
            except (
                dns.resolver.NXDOMAIN,
                dns.resolver.NoAnswer,
                dns.resolver.NoNameservers,
                dns.exception.DNSException,
            ):
                servers = []
                mx_found = False

        result = {
            "mx_found": mx_found,
            "mail_servers": servers,
            "has_spf": mx_found,
            "has_dmarc": False,
        }
        _MEMORY_DNS_CACHE[dom] = result
        return result
    except (ImportError, OSError, ValueError) as exc:
        logger.debug("DNS lookup failed for %s: %s", dom, exc)
        result = {"mx_found": False, "mail_servers": [], "has_spf": False, "has_dmarc": False}
        _MEMORY_DNS_CACHE[dom] = result
        return result
