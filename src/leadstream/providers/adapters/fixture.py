from __future__ import annotations

from collections.abc import Callable

from leadstream.providers.contracts import ProviderContext, ProviderResult


class FixtureProviderAdapter:
    def __init__(self, slug: str, handler: Callable[[ProviderContext], ProviderResult]) -> None:
        self.slug = slug
        self._handler = handler

    def is_configured(self) -> bool:
        return True

    def enrich(self, context: ProviderContext) -> ProviderResult:
        return self._handler(context)
