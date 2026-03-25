"""
Square SDK-backed client wrapper.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from square import Square
from square.core.api_error import ApiError
from square.environment import SquareEnvironment

from app.config import settings
from app.utils.logging_config import get_logger

logger = get_logger(__name__)


class SquareClient:
    """Thin wrapper around the official Square Python SDK."""

    def __init__(self, access_token: str, base_url: Optional[str] = None):
        self.access_token = access_token
        self.base_url = (base_url or settings.SQUARE_API_BASE_URL or "").rstrip("/")
        self._client = self._build_client()

    def _resolve_environment(self) -> Tuple[SquareEnvironment, Optional[str]]:
        if "squareupsandbox.com" in self.base_url:
            return SquareEnvironment.SANDBOX, None
        if self.base_url in {"", "https://connect.squareup.com"}:
            return SquareEnvironment.PRODUCTION, None
        return SquareEnvironment.PRODUCTION, self.base_url or None

    def _build_client(self) -> Square:
        environment, custom_base_url = self._resolve_environment()
        client_kwargs: Dict[str, Any] = {
            "environment": environment,
            "token": self.access_token,
        }
        if custom_base_url:
            client_kwargs["base_url"] = custom_base_url
        return Square(**client_kwargs)

    def _serialize(self, value: Any) -> Any:
        if value is None:
            return None
        if isinstance(value, list):
            return [self._serialize(item) for item in value]
        if isinstance(value, dict):
            return {key: self._serialize(item) for key, item in value.items() if item is not None}
        if hasattr(value, "model_dump"):
            return value.model_dump(mode="json", by_alias=True, exclude_none=True)
        return value

    @staticmethod
    def _log_api_error(operation: str, error: ApiError) -> None:
        logger.error("[Square API] %s failed with status=%s body=%s", operation, error.status_code, error.body)

    def create_order(self, location_id: str, order_data: Dict[str, Any], idempotency_key: str) -> Dict[str, Any]:
        order_payload = {
            "location_id": location_id,
            "line_items": order_data.get("line_items", []),
        }
        if order_data.get("discounts"):
            order_payload["discounts"] = order_data["discounts"]
        if order_data.get("fulfillments"):
            order_payload["fulfillments"] = order_data["fulfillments"]
        if order_data.get("reference_id"):
            order_payload["reference_id"] = order_data["reference_id"]

        logger.info(
            "[Square API] Creating order location_id=%s idempotency_key=%s line_items=%s",
            location_id,
            idempotency_key,
            len(order_payload.get("line_items", [])),
        )
        try:
            response = self._client.orders.create(order=order_payload, idempotency_key=idempotency_key)
            return self._serialize(response) or {}
        except ApiError as error:
            self._log_api_error("CreateOrder", error)
            raise

    def get_order(self, order_id: str) -> Dict[str, Any]:
        logger.info("[Square API] Retrieving order order_id=%s", order_id)
        try:
            response = self._client.orders.get(order_id)
            return self._serialize(response) or {}
        except ApiError as error:
            self._log_api_error("GetOrder", error)
            raise

    def update_order(
        self,
        order_id: str,
        *,
        order_data: Dict[str, Any],
        idempotency_key: str,
        fields_to_clear: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        logger.info(
            "[Square API] Updating order order_id=%s idempotency_key=%s fields_to_clear=%s",
            order_id,
            idempotency_key,
            fields_to_clear or [],
        )
        try:
            response = self._client.orders.update(
                order_id,
                order=order_data,
                fields_to_clear=fields_to_clear,
                idempotency_key=idempotency_key,
            )
            return self._serialize(response) or {}
        except ApiError as error:
            self._log_api_error("UpdateOrder", error)
            raise

    def list_catalog(self, types: Optional[List[str]] = None) -> Dict[str, Any]:
        type_filter = ",".join(types) if types else None
        logger.info("[Square API] Listing catalog types=%s", type_filter or "default")
        try:
            pager = self._client.catalog.list(types=type_filter)
            objects = [self._serialize(obj) for obj in pager]
            return {"objects": objects}
        except ApiError as error:
            self._log_api_error("ListCatalog", error)
            raise

    def list_locations(self) -> Dict[str, Any]:
        logger.info("[Square API] Listing locations")
        try:
            response = self._client.locations.list()
            return self._serialize(response) or {}
        except ApiError as error:
            self._log_api_error("ListLocations", error)
            raise

    def search_catalog_objects(
        self,
        *,
        object_types: Optional[List[str]] = None,
        begin_time: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> Dict[str, Any]:
        logger.info(
            "[Square API] Searching catalog objects object_types=%s begin_time=%s limit=%s",
            object_types or ["default"],
            begin_time,
            limit,
        )
        try:
            cursor: Optional[str] = None
            objects: List[Dict[str, Any]] = []
            related_objects: List[Dict[str, Any]] = []
            response_payload: Dict[str, Any] = {}

            while True:
                response = self._client.catalog.search(
                    cursor=cursor,
                    object_types=object_types,
                    begin_time=begin_time,
                    limit=limit,
                )
                serialized = self._serialize(response) or {}
                response_payload = serialized
                objects.extend(serialized.get("objects") or [])
                related_objects.extend(serialized.get("related_objects") or [])
                cursor = serialized.get("cursor")
                if not cursor:
                    break

            response_payload["objects"] = objects
            if related_objects:
                response_payload["related_objects"] = related_objects
            else:
                response_payload.pop("related_objects", None)
            response_payload.pop("cursor", None)
            return response_payload
        except ApiError as error:
            self._log_api_error("SearchCatalogObjects", error)
            raise

    def create_payment(self, order_id: str, amount: float, currency: str, idempotency_key: str) -> Dict[str, Any]:
        amount_cents = int(round(amount * 100))
        logger.info(
            "[Square API] Creating cash payment order_id=%s amount_cents=%s currency=%s idempotency_key=%s",
            order_id,
            amount_cents,
            currency,
            idempotency_key,
        )
        try:
            response = self._client.payments.create(
                source_id="CASH",
                idempotency_key=idempotency_key,
                order_id=order_id,
                amount_money={"amount": amount_cents, "currency": currency},
                cash_details={
                    "buyer_supplied_money": {
                        "amount": amount_cents,
                        "currency": currency,
                    }
                },
            )
            return self._serialize(response) or {}
        except ApiError as error:
            self._log_api_error("CreatePayment", error)
            raise

    def refund_payment(
        self,
        *,
        payment_id: str,
        amount_cents: int,
        currency: str,
        idempotency_key: str,
        reason: Optional[str] = None,
    ) -> Dict[str, Any]:
        logger.info(
            "[Square API] Refunding payment payment_id=%s amount_cents=%s currency=%s idempotency_key=%s",
            payment_id,
            amount_cents,
            currency,
            idempotency_key,
        )
        try:
            response = self._client.refunds.refund_payment(
                idempotency_key=idempotency_key,
                payment_id=payment_id,
                amount_money={"amount": amount_cents, "currency": currency},
                reason=reason,
            )
            return self._serialize(response) or {}
        except ApiError as error:
            self._log_api_error("RefundPayment", error)
            raise

    def pay_order(
        self,
        order_id: str,
        payment_ids: List[str],
        idempotency_key: str,
        order_version: Optional[int] = None,
    ) -> Dict[str, Any]:
        logger.info(
            "[Square API] Paying order order_id=%s payment_ids=%s idempotency_key=%s",
            order_id,
            payment_ids,
            idempotency_key,
        )
        try:
            response = self._client.orders.pay(
                order_id,
                idempotency_key=idempotency_key,
                payment_ids=payment_ids,
                order_version=order_version,
            )
            return self._serialize(response) or {}
        except ApiError as error:
            self._log_api_error("PayOrder", error)
            raise
