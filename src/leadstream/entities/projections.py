from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from django.db import transaction
from django.utils import timezone

from .models import Company
from .normalization import only_digits


def _date(value: Any) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value or "").strip()
    for pattern in ("%Y-%m-%d", "%d/%m/%Y", "%Y%m%d"):
        try:
            return datetime.strptime(text, pattern).date()
        except ValueError:
            continue
    return None


def _decimal(value: Any) -> Decimal | None:
    if value in (None, ""):
        return None
    try:
        if isinstance(value, str):
            text = value.strip()
            if "," in text and "." in text:
                text = text.replace(".", "").replace(",", ".")
            elif "," in text:
                text = text.replace(",", ".")
            return Decimal(text)
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return None


def _optional_bool(value: Any) -> bool | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return value
    normalized = str(value).strip().casefold()
    if normalized in {"1", "true", "sim", "s", "yes"}:
        return True
    if normalized in {"0", "false", "não", "nao", "n", "no"}:
        return False
    return None


def _set_if_present(
    instance: Any,
    updates: set[str],
    field: str,
    data: dict[str, Any],
    key: str,
    transform: Any = str,
) -> None:
    if key not in data or data[key] in (None, ""):
        return
    value = transform(data[key])
    if value is None:
        return
    setattr(instance, field, value)
    updates.add(field)


@transaction.atomic
def update_company_registry_projection(
    *,
    company: Company,
    data: dict[str, Any],
    source: str,
    observed_at: datetime | None = None,
) -> Company:
    """Atualiza somente valores observados em uma fonte cadastral identificada."""
    company_updates: set[str] = set()
    _set_if_present(company, company_updates, "legal_name", data, "legal_name")
    _set_if_present(company, company_updates, "trade_name", data, "trade_name")
    _set_if_present(
        company,
        company_updates,
        "registration_status",
        data,
        "registration_status",
    )
    _set_if_present(company, company_updates, "opened_on", data, "opened_on", _date)
    _set_if_present(company, company_updates, "legal_nature", data, "legal_nature")
    _set_if_present(company, company_updates, "company_size", data, "company_size")
    _set_if_present(company, company_updates, "share_capital", data, "share_capital", _decimal)
    _set_if_present(company, company_updates, "primary_cnae", data, "primary_cnae")
    _set_if_present(
        company,
        company_updates,
        "primary_cnae_description",
        data,
        "primary_cnae_description",
    )
    if "secondary_cnaes" in data and isinstance(data["secondary_cnaes"], list):
        company.secondary_cnaes = data["secondary_cnaes"]
        company_updates.add("secondary_cnaes")
    for key, field in (("simple_national", "simple_national"), ("mei", "mei")):
        if key in data:
            bool_value = _optional_bool(data[key])
            if bool_value is not None:
                setattr(company, field, bool_value)
                company_updates.add(field)
    company.registry_source = source[:160]
    company.registry_observed_at = observed_at or timezone.now()
    company_updates.update(("registry_source", "registry_observed_at", "updated_at"))
    company.save(update_fields=company_updates)

    establishment = company.establishments.order_by("-is_headquarters", "created_at").first()
    if establishment is None:
        return company
    establishment_updates: set[str] = set()
    address_mapping = {
        "street_type": "street_type",
        "street": "street",
        "number": "number",
        "complement": "complement",
        "district": "district",
        "city": "city",
        "state": "state",
        "postal_code": "postal_code",
        "municipality_ibge_code": "municipality_ibge_code",
    }
    for key, field in address_mapping.items():
        if key not in data or data[key] in (None, ""):
            continue
        address_value = str(data[key]).strip()
        if field == "state":
            address_value = address_value.upper()[:2]
        elif field == "postal_code":
            address_value = only_digits(address_value)[:8]
        setattr(establishment, field, address_value)
        establishment_updates.add(field)
    if establishment_updates:
        establishment_updates.add("updated_at")
        establishment.save(update_fields=establishment_updates)
    return company
