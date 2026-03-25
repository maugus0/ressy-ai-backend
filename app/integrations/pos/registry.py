"""
Provider registry for POS integrations.
"""

from __future__ import annotations

from typing import Dict

from app.integrations.pos.base import POSProvider


class POSProviderRegistry:
    """Registry for resolving POS providers by integration type."""

    def __init__(self):
        self._providers: Dict[str, POSProvider] = {}

    def register(self, provider: POSProvider) -> None:
        self._providers[provider.pos_type.upper()] = provider

    def get_provider(self, pos_type: str) -> POSProvider:
        key = (pos_type or "").upper()
        if key not in self._providers:
            raise ValueError(f"Unsupported POS provider: {pos_type}")
        return self._providers[key]


def build_default_pos_provider_registry() -> POSProviderRegistry:
    from app.integrations.pos.square_provider import SquarePOSProvider

    registry = POSProviderRegistry()
    registry.register(SquarePOSProvider())
    return registry
