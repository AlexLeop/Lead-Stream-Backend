from __future__ import annotations

from .base import BaseCRMConnector, ConnectionTestResult, SyncResult
from .registry import get_connector

__all__ = [
    "BaseCRMConnector",
    "ConnectionTestResult",
    "SyncResult",
    "get_connector",
]
