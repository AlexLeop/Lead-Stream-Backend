from __future__ import annotations

from typing import TYPE_CHECKING

from .base import BaseCRMConnector
from .hubspot import HubSpotConnector
from .pipedrive import PipedriveConnector
from .ploomes import PloomesConnector
from .rdstation import RDStationConnector
from .salesforce import SalesforceConnector
from .webhook import WebhookConnector

if TYPE_CHECKING:
    from leadstream.integrations.models import CRMConnection

_REGISTRY: dict[str, type[BaseCRMConnector]] = {
    "WEBHOOK_CUSTOM": WebhookConnector,
    "WEBHOOK_N8N": WebhookConnector,
    "WEBHOOK_ZAPIER": WebhookConnector,
    "WEBHOOK_MAKE": WebhookConnector,
    "HUBSPOT": HubSpotConnector,
    "PIPEDRIVE": PipedriveConnector,
    "RD_STATION": RDStationConnector,
    "SALESFORCE": SalesforceConnector,
    "PLOOMES": PloomesConnector,
}


def get_connector(connector_type: str) -> BaseCRMConnector:
    """Retorna uma instância do conector adequado para o tipo informado.

    Se o tipo for desconhecido ou webhook, utiliza WebhookConnector como fallback universal.
    """
    cls = _REGISTRY.get(connector_type, WebhookConnector)
    return cls()


def get_connector_for_connection(connection: CRMConnection) -> BaseCRMConnector:
    """Obtém o conector associado a uma CRMConnection."""
    return get_connector(connection.connector_type)
