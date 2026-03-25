"""
Abstract base classes for POS provider adapters.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

from app.integrations.pos.models import (
    POSCatalogAvailabilitySnapshot,
    POSCatalogSnapshot,
    POSOrderCancellationResult,
    POSOrderSubmissionResult,
    POSSubmitOrderRequest,
)


class POSProvider(ABC):
    """Provider adapter interface for POS systems."""

    provider_name: str
    pos_type: str

    @abstractmethod
    def fetch_catalog(self, integration: Dict[str, Any]) -> POSCatalogSnapshot:
        """Fetch and normalize the provider catalog into the internal POS DTOs."""

    @abstractmethod
    def fetch_availability_updates(
        self,
        integration: Dict[str, Any],
        *,
        begin_time: str | None = None,
    ) -> POSCatalogAvailabilitySnapshot:
        """Fetch current provider availability updates for mapped items/customizations."""

    @abstractmethod
    def submit_pickup_order(
        self,
        integration: Dict[str, Any],
        request: POSSubmitOrderRequest,
        *,
        idempotency_key: str,
    ) -> POSOrderSubmissionResult:
        """Submit a pickup order to the provider."""

    @abstractmethod
    def cancel_pickup_order(
        self,
        integration: Dict[str, Any],
        *,
        external_order_id: str,
        external_payment_id: Optional[str] = None,
        idempotency_key: str,
        reason: Optional[str] = None,
    ) -> POSOrderCancellationResult:
        """Cancel a previously submitted pickup order in the provider."""
