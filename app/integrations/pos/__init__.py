"""
Provider-agnostic POS integration layer.
"""

from app.integrations.pos.base import POSProvider
from app.integrations.pos.registry import POSProviderRegistry, build_default_pos_provider_registry

__all__ = ["POSProvider", "POSProviderRegistry", "build_default_pos_provider_registry"]
