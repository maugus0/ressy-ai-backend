import json
import re
import uuid
from collections import defaultdict
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import httpx
from square.core.api_error import ApiError

from app.config import settings
from app.integrations.pos import build_default_pos_provider_registry
from app.integrations.pos.models import (
    POSOrderCancellationResult,
    POSOrderLineItem,
    POSOrderModifierSelection,
    POSOrderSubmissionResult,
    POSSubmitOrderRequest,
)
from app.repositories.mysql_menu_repo import MySQLMenuRepository
from app.repositories.mysql_order_item_repo import MySQLOrderItemRepository
from app.repositories.mysql_order_pos_sync_repo import MySQLOrderPOSSyncRepository
from app.repositories.mysql_order_repo import MySQLOrderRepository
from app.repositories.mysql_pos_integration_repo import MySQLPOSIntegrationRepository
from app.repositories.mysql_pos_menu_item_mapping_repo import MySQLPOSMenuItemMappingRepository
from app.repositories.mysql_pos_option_group_mapping_repo import MySQLPOSOptionGroupMappingRepository
from app.repositories.mysql_pos_option_value_mapping_repo import MySQLPOSOptionValueMappingRepository
from app.utils.logging_config import get_logger

logger = get_logger(__name__)


class POSService:
    def __init__(self):
        self.pos_integration_repo = MySQLPOSIntegrationRepository()
        self.order_sync_repo = MySQLOrderPOSSyncRepository()
        self.order_repo = MySQLOrderRepository()
        self.order_item_repo = MySQLOrderItemRepository()
        self.menu_repo = MySQLMenuRepository()
        self.pos_menu_item_mapping_repo = MySQLPOSMenuItemMappingRepository()
        self.pos_option_group_mapping_repo = MySQLPOSOptionGroupMappingRepository()
        self.pos_option_value_mapping_repo = MySQLPOSOptionValueMappingRepository()
        self.provider_registry = build_default_pos_provider_registry()

    @staticmethod
    def _is_retryable_sync_error(error: Exception) -> bool:
        if isinstance(error, ApiError):
            status_code = getattr(error, "status_code", None)
            return bool(status_code in {408, 429} or (isinstance(status_code, int) and status_code >= 500))
        return isinstance(error, (httpx.HTTPError, TimeoutError, ConnectionError, OSError))

    def _build_order_submission_context(
        self,
        order_id: int,
    ) -> tuple[Optional[Dict[str, Any]], Dict[str, Any], Dict[str, Any]]:
        order = self.order_repo.get_order_with_user(order_id)
        if not order:
            return None, {}, {}

        order_details = order.get("order_details", [])
        if isinstance(order_details, str):
            try:
                order_details = json.loads(order_details)
            except (json.JSONDecodeError, TypeError):
                order_details = []

        customization = order.get("customization", {})
        if isinstance(customization, str):
            try:
                customization = json.loads(customization)
            except (json.JSONDecodeError, TypeError):
                customization = {}

        customer_name = order.get("customer_name") or customization.get("customer_name") or ""
        customer_phone = order.get("customer_phone") or customization.get("customer_phone") or ""
        customer_email = order.get("customer_email") or customization.get("customer_email") or ""

        order_data = {
            "order_details": order_details,
            "customer_name": customer_name,
            "customer_phone": customer_phone,
            "customer_email": customer_email,
        }
        return order, order_data, customization

    def _process_integration_submission(
        self,
        *,
        sync_id: int,
        order_id: int,
        restaurant_id: int,
        pos_integration: Dict[str, Any],
        order: Dict[str, Any],
        order_data: Dict[str, Any],
        customization: Dict[str, Any],
        idempotency_key: str,
        attempt_count: int,
        schedule_retry_on_failure: bool = True,
    ) -> Dict[str, Any]:
        pos_type = pos_integration.get("pos_type")
        integration_id = pos_integration.get("id")
        enabled = pos_integration.get("enabled")
        location_id = pos_integration.get("location_id")

        logger.info(
            "[POS Sync] Processing %s integration: id=%s, enabled=%s, location_id=%s",
            pos_type,
            integration_id,
            enabled,
            location_id,
        )
        logger.info(
            "[POS Sync] Syncing order %s to %s POS (integration_id: %s, idempotency_key: %s)",
            order_id,
            pos_type,
            integration_id,
            idempotency_key,
        )

        if pos_type != "SQUARE":
            error_msg = f"Unsupported POS type: {pos_type}"
            logger.warning(error_msg)
            self.order_sync_repo.update_sync_status(
                sync_id,
                status="FAILED",
                error=error_msg,
                attempts=attempt_count,
                request_payload=order_data,
            )
            return {
                "success": False,
                "status": "FAILED",
                "sync_id": sync_id,
                "integration_id": integration_id,
                "pos_type": pos_type,
                "retry_scheduled": False,
                "retryable": False,
                "error": error_msg,
            }

        try:
            if not location_id or str(location_id).strip() == "":
                raise ValueError(
                    "Square location_id not configured. Please configure location_id in POS integration settings."
                )

            logger.info("[POS Sync] Processing Square sync for order %s, location_id: %s", order_id, location_id)
            logger.info(
                "[POS Sync] Order data: %s items, customer: %s",
                len(order_data.get("order_details", [])),
                order_data.get("customer_name", "N/A"),
            )
            result = self._sync_to_square(order_id, pos_integration, order_data, idempotency_key, order, customization)
            external_order_id = result.external_order_id
            self.order_sync_repo.update_sync_status(
                sync_id,
                status=result.status,
                external_order_id=external_order_id,
                external_payment_id=result.external_payment_id,
                attempts=attempt_count,
                response_payload=result.payload,
            )
            logger.info(
                "[POS Sync] Updated sync record %s to %s for order %s",
                sync_id,
                result.status,
                order_id,
            )
            return {
                "success": True,
                "status": result.status,
                "sync_id": sync_id,
                "integration_id": integration_id,
                "pos_type": pos_type,
                "retry_scheduled": False,
                "retryable": False,
                "external_order_id": external_order_id,
                "payload": result.payload,
                "external_payment_id": result.external_payment_id,
            }
        except Exception as error:
            error_msg = str(error)
            retryable = self._is_retryable_sync_error(error)
            logger.error(
                "POS sync failed for order %s, POS %s (integration_id: %s): %s",
                order_id,
                pos_type,
                integration_id,
                error_msg,
            )
            logger.exception("Exception details for order %s POS sync failure:", order_id)

            if retryable and schedule_retry_on_failure:
                retry_minutes = settings.POS_RETRY_BASE_MINUTES * (2 ** max(attempt_count - 1, 0))
                next_retry = datetime.now() + timedelta(minutes=retry_minutes)
                self.order_sync_repo.update_sync_status(
                    sync_id,
                    status="PENDING",
                    error=error_msg,
                    attempts=attempt_count,
                    next_retry_at=next_retry,
                    request_payload=order_data,
                )
                logger.info("Scheduled retry for order %s POS sync at %s", order_id, next_retry)
            else:
                self.order_sync_repo.update_sync_status(
                    sync_id,
                    status="FAILED",
                    error=error_msg,
                    attempts=attempt_count,
                    request_payload=order_data,
                )

            return {
                "success": False,
                "status": "PENDING" if retryable and schedule_retry_on_failure else "FAILED",
                "sync_id": sync_id,
                "integration_id": integration_id,
                "pos_type": pos_type,
                "retry_scheduled": retryable and schedule_retry_on_failure,
                "retryable": retryable,
                "error": error_msg,
            }

    @staticmethod
    def _choose_snapshot_integration(integrations: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        for integration in integrations:
            if str(integration.get("pos_type") or "").upper() == "SQUARE":
                return integration
        return integrations[0] if integrations else None

    @staticmethod
    def _build_snapshot_items_with_options(
        items: List[Dict[str, Any]],
        options: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        options_by_item: Dict[int, List[Dict[str, Any]]] = defaultdict(list)
        for option in options:
            order_item_id = option.get("order_item_id")
            if order_item_id is None:
                continue
            options_by_item[int(order_item_id)].append(dict(option))

        snapshot_items: List[Dict[str, Any]] = []
        for item in items:
            normalized_item = dict(item)
            item_id = normalized_item.get("id")
            normalized_item["option_snapshots"] = options_by_item.get(int(item_id), []) if item_id is not None else []
            snapshot_items.append(normalized_item)
        return snapshot_items

    def capture_order_state(self, order_id: int) -> Optional[Dict[str, Any]]:
        order = self.order_repo.get_order_with_user(order_id)
        if not order:
            return None
        order_details = order.get("order_details", [])
        if isinstance(order_details, str):
            try:
                order_details = json.loads(order_details)
            except (json.JSONDecodeError, TypeError):
                order_details = []
        customization = order.get("customization", {})
        if isinstance(customization, str):
            try:
                customization = json.loads(customization)
            except (json.JSONDecodeError, TypeError):
                customization = {}
        snapshot_items = self._build_snapshot_items_with_options(
            self.order_item_repo.list_order_items(order_id),
            self.order_item_repo.list_order_item_options(order_id),
        )
        return {
            "order_id": order_id,
            "status": order.get("status"),
            "total_amount": order.get("total_amount"),
            "order_details": order_details,
            "customization": customization,
            "snapshot_items": snapshot_items,
        }

    def restore_order_state(self, order_id: int, state: Dict[str, Any]) -> None:
        self.order_repo.update_order(
            order_id=order_id,
            status=state.get("status"),
            total_amount=state.get("total_amount"),
            order_details=state.get("order_details"),
            customization=state.get("customization"),
        )
        self.order_item_repo.replace_order_item_snapshots(order_id, state.get("snapshot_items", []))

    def has_confirmed_sync(self, order_id: int) -> bool:
        return bool(self.order_sync_repo.get_latest_confirmed_syncs(order_id))

    def attach_external_snapshot_ids(
        self,
        restaurant_id: Optional[int],
        priced_items: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        if not restaurant_id or not priced_items:
            return deepcopy(priced_items)

        integration = self._choose_snapshot_integration(
            self.pos_integration_repo.get_enabled_integrations(int(restaurant_id))
        )
        if not integration:
            return deepcopy(priced_items)

        integration_id = int(integration["id"])
        enriched_items: List[Dict[str, Any]] = []
        menu_mapping_cache: Dict[int, Optional[Dict[str, Any]]] = {}
        group_mapping_cache: Dict[int, Optional[Dict[str, Any]]] = {}
        value_mapping_cache: Dict[int, Optional[Dict[str, Any]]] = {}

        for item in priced_items:
            enriched_item = deepcopy(item)
            menu_item_id = enriched_item.get("menu_item_id")
            if menu_item_id is not None:
                normalized_menu_item_id = int(menu_item_id)
                if normalized_menu_item_id not in menu_mapping_cache:
                    menu_mapping_cache[normalized_menu_item_id] = self.pos_menu_item_mapping_repo.get_by_internal_item(
                        normalized_menu_item_id,
                        integration_id,
                    )
                menu_mapping = menu_mapping_cache[normalized_menu_item_id]
                if menu_mapping and menu_mapping.get("external_item_id"):
                    enriched_item["external_item_id_snapshot"] = str(menu_mapping["external_item_id"])

            option_snapshots: List[Dict[str, Any]] = []
            for option in enriched_item.get("option_snapshots", []):
                enriched_option = deepcopy(option)
                option_group_id = enriched_option.get("option_group_id")
                option_value_id = enriched_option.get("option_value_id")
                if option_group_id is not None:
                    normalized_group_id = int(option_group_id)
                    if normalized_group_id not in group_mapping_cache:
                        group_mapping_cache[normalized_group_id] = (
                            self.pos_option_group_mapping_repo.get_by_internal_group(
                                normalized_group_id,
                                integration_id,
                            )
                        )
                    group_mapping = group_mapping_cache[normalized_group_id]
                    if group_mapping and group_mapping.get("external_group_id"):
                        enriched_option["external_group_id_snapshot"] = str(group_mapping["external_group_id"])
                if option_value_id is not None:
                    normalized_value_id = int(option_value_id)
                    if normalized_value_id not in value_mapping_cache:
                        value_mapping_cache[normalized_value_id] = (
                            self.pos_option_value_mapping_repo.get_by_internal_value(
                                normalized_value_id,
                                integration_id,
                            )
                        )
                    value_mapping = value_mapping_cache[normalized_value_id]
                    if value_mapping:
                        if value_mapping.get("external_group_id"):
                            enriched_option["external_group_id_snapshot"] = str(value_mapping["external_group_id"])
                        if value_mapping.get("external_value_id"):
                            enriched_option["external_value_id_snapshot"] = str(value_mapping["external_value_id"])
                option_snapshots.append(enriched_option)

            enriched_item["option_snapshots"] = option_snapshots
            enriched_items.append(enriched_item)

        return enriched_items

    def _get_item_price(self, item: Dict, menu_repo: MySQLMenuRepository) -> float:
        # Priority 1: Use price from order_details (actual price at time of order)
        if item.get("price") is not None:
            price = float(item["price"])
            logger.debug(f"Using price from order_details for '{item.get('name')}': ${price:.2f}")
            return price
        # Priority 2: Lookup from menu if item_id exists
        if item.get("item_id"):
            menu_item = menu_repo.get_by_id(item["item_id"])
            if menu_item:
                price = float(menu_item.get("price", 0))
                logger.debug(
                    f"Using price from menu lookup for '{item.get('name')}' (item_id={item.get('item_id')}): ${price:.2f}"
                )
                return price
        # Priority 3: Fallback to 0.00 (should not happen in normal flow)
        logger.warning(f"No price found for item: {item.get('name')} (item_id={item.get('item_id')}), using $0.00")
        return 0.00

    @staticmethod
    def _normalize_customer_phone(customer_phone: str) -> str:
        customer_phone = (customer_phone or "").strip()
        if customer_phone and not customer_phone.startswith("+"):
            digits_only = re.sub(r"[^\d]", "", customer_phone)
            if len(digits_only) == 10:
                customer_phone = f"+1{digits_only}"
            elif len(digits_only) == 11 and digits_only.startswith("1"):
                customer_phone = f"+{digits_only}"
            elif digits_only:
                customer_phone = f"+{digits_only}"
        return customer_phone

    def _calculate_pickup_time_iso(
        self,
        order_data: Dict[str, Any],
        order: Optional[Dict[str, Any]],
        customization: Optional[Dict[str, Any]],
    ) -> Optional[str]:
        pickup_time_iso = None
        if customization and isinstance(customization, dict):
            pickup_time_iso = customization.get("pickup_time_iso") or customization.get("pickup_time")
        if pickup_time_iso or not order:
            return pickup_time_iso

        order_created_at = order.get("created_at")
        if isinstance(order_created_at, str):
            try:
                order_created_at = datetime.fromisoformat(order_created_at.replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                order_created_at = None

        if not isinstance(order_created_at, datetime):
            order_created_at = datetime.now(timezone.utc)

        total_prep_minutes = 0.0
        item_count = 0
        for item in order_data.get("order_details", []):
            item_id = item.get("item_id")
            quantity = int(item.get("quantity", 1) or 1)
            if not item_id:
                continue
            menu_item = self.menu_repo.get_by_id(item_id)
            if menu_item and menu_item.get("avg_prep_time"):
                prep_time = float(menu_item.get("avg_prep_time", 0))
                total_prep_minutes += prep_time * quantity
                item_count += quantity

        default_prep_minutes = settings.DEFAULT_PREP_TIME_MINUTES
        avg_prep_minutes = (
            default_prep_minutes if total_prep_minutes == 0 or item_count == 0 else total_prep_minutes / item_count
        )
        pickup_datetime = order_created_at + timedelta(minutes=avg_prep_minutes)
        if pickup_datetime.tzinfo is None:
            pickup_datetime = pickup_datetime.replace(tzinfo=timezone.utc)
        else:
            pickup_datetime = pickup_datetime.astimezone(timezone.utc)
        return pickup_datetime.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"

    def _build_provider_order_request(
        self,
        *,
        order_id: int,
        pos_integration: Dict[str, Any],
        order_data: Dict[str, Any],
        order: Optional[Dict[str, Any]],
        customization: Optional[Dict[str, Any]],
    ) -> POSSubmitOrderRequest:
        pos_integration_id = int(pos_integration["id"])
        currency = (pos_integration.get("currency") or "USD").strip() or "USD"
        location_id = (pos_integration.get("location_id") or "").strip()
        if not location_id:
            raise ValueError(
                "Square location_id not configured. Please configure location_id in POS integration settings."
            )

        order_items = self.order_item_repo.list_order_items(order_id)
        order_item_options = self.order_item_repo.list_order_item_options(order_id)
        options_by_order_item = defaultdict(list)
        for option in order_item_options:
            order_item_id = option.get("order_item_id")
            if order_item_id is not None:
                options_by_order_item[int(order_item_id)].append(option)

        line_items = []
        if order_items:
            for order_item in order_items:
                menu_item_id = order_item.get("menu_item_id")
                if menu_item_id is None:
                    raise ValueError(f"Order item snapshot {order_item.get('id')} is missing menu_item_id")
                menu_mapping = self.pos_menu_item_mapping_repo.get_by_internal_item(
                    int(menu_item_id), pos_integration_id
                )
                external_item_id = None
                if menu_mapping and menu_mapping.get("is_active") and menu_mapping.get("external_item_id"):
                    external_item_id = str(menu_mapping["external_item_id"])
                elif order_item.get("external_item_id_snapshot"):
                    external_item_id = str(order_item["external_item_id_snapshot"])
                if not external_item_id:
                    raise ValueError(
                        f"No active POS mapping found for menu_item_id={menu_item_id} on integration_id={pos_integration_id}"
                    )

                modifiers = []
                for option in options_by_order_item.get(int(order_item["id"]), []):
                    free_text_value = option.get("free_text_value")
                    option_value_id = option.get("option_value_id")
                    option_group_id = option.get("option_group_id")
                    option_mapping = None
                    group_mapping = None
                    if option_value_id is not None:
                        option_mapping = self.pos_option_value_mapping_repo.get_by_internal_value(
                            int(option_value_id),
                            pos_integration_id,
                        )
                        if option_mapping and not option_mapping.get("is_active"):
                            option_mapping = None
                        if not option_mapping and not option.get("external_value_id_snapshot"):
                            raise ValueError(
                                f"No active POS option mapping found for option_value_id={option_value_id} "
                                f"on integration_id={pos_integration_id}"
                            )
                    elif option_group_id is not None:
                        group_mapping = self.pos_option_group_mapping_repo.get_by_internal_group(
                            int(option_group_id),
                            pos_integration_id,
                        )
                        if group_mapping and not group_mapping.get("is_active"):
                            group_mapping = None
                        if not group_mapping and not option.get("external_group_id_snapshot"):
                            raise ValueError(
                                f"No active POS option group mapping found for option_group_id={option_group_id} "
                                f"on integration_id={pos_integration_id}"
                            )

                    external_group_id = None
                    if option_mapping and option_mapping.get("external_group_id"):
                        external_group_id = str(option_mapping["external_group_id"])
                    elif group_mapping and group_mapping.get("external_group_id"):
                        external_group_id = str(group_mapping["external_group_id"])
                    elif option.get("external_group_id_snapshot"):
                        external_group_id = str(option["external_group_id_snapshot"])

                    external_value_id = None
                    if option_mapping and option_mapping.get("external_value_id"):
                        external_value_id = str(option_mapping["external_value_id"])
                    elif option.get("external_value_id_snapshot"):
                        external_value_id = str(option["external_value_id_snapshot"])

                    modifiers.append(
                        POSOrderModifierSelection(
                            external_group_id=external_group_id,
                            external_value_id=external_value_id,
                            name=option.get("option_value_name_snapshot") or free_text_value or "Custom",
                            quantity=int(option.get("quantity", 1) or 1),
                            price_delta=float(option.get("price_delta_snapshot") or 0),
                            free_text_value=free_text_value,
                        )
                    )

                line_items.append(
                    POSOrderLineItem(
                        external_item_id=external_item_id,
                        name=order_item.get("item_name_snapshot") or "Unknown Item",
                        quantity=int(order_item.get("quantity", 1) or 1),
                        price=float(order_item.get("base_price_snapshot") or 0),
                        note=order_item.get("instructions"),
                        modifiers=modifiers,
                    )
                )
        else:
            for item in order_data.get("order_details", []):
                menu_item_id = item.get("item_id")
                if menu_item_id is None:
                    raise ValueError(
                        f"Order {order_id} contains an item without item_id; POS sync requires mapped items."
                    )
                menu_mapping = self.pos_menu_item_mapping_repo.get_by_internal_item(
                    int(menu_item_id), pos_integration_id
                )
                external_item_id = None
                if menu_mapping and menu_mapping.get("is_active") and menu_mapping.get("external_item_id"):
                    external_item_id = str(menu_mapping["external_item_id"])
                elif item.get("external_item_id_snapshot"):
                    external_item_id = str(item["external_item_id_snapshot"])
                if not external_item_id:
                    raise ValueError(
                        f"No active POS mapping found for menu_item_id={menu_item_id} on integration_id={pos_integration_id}"
                    )
                line_items.append(
                    POSOrderLineItem(
                        external_item_id=external_item_id,
                        name=item.get("name") or "Unknown Item",
                        quantity=int(item.get("quantity", 1) or 1),
                        price=float(self._get_item_price(item, self.menu_repo)),
                        note=item.get("instructions"),
                    )
                )

        if not line_items:
            raise ValueError("No mapped menu items found for POS order submission")

        customer_phone = self._normalize_customer_phone(order_data.get("customer_phone", ""))
        return POSSubmitOrderRequest(
            restaurant_id=int(order.get("restaurant_id") if order else pos_integration.get("restaurant_id")),
            location_id=location_id,
            currency=currency,
            reference_id=f"RESSY-{order_id}",
            customer_name=(order_data.get("customer_name") or "").strip() or None,
            customer_phone=customer_phone or None,
            customer_email=(order_data.get("customer_email") or "").strip() or None,
            pickup_at=self._calculate_pickup_time_iso(order_data, order, customization),
            line_items=line_items,
            metadata={"order_id": order_id},
        )

    def _sync_to_square(
        self,
        order_id: int,
        pos_integration: Dict,
        order_data: Dict,
        idempotency_key: str,
        order: Optional[Dict] = None,
        customization: Optional[Dict] = None,
    ) -> POSOrderSubmissionResult:
        logger.info("[POS Sync] Syncing order %s to Square integration_id=%s", order_id, pos_integration.get("id"))
        request = self._build_provider_order_request(
            order_id=order_id,
            pos_integration=pos_integration,
            order_data=order_data,
            order=order,
            customization=customization,
        )
        provider = self.provider_registry.get_provider("SQUARE")
        result = provider.submit_pickup_order(
            pos_integration,
            request,
            idempotency_key=idempotency_key,
        )
        logger.info(
            "[POS Sync] Square sync completed for order %s external_order_id=%s",
            order_id,
            result.external_order_id,
        )
        return result

    def submit_order_to_pos(
        self,
        order_id: int,
        restaurant_id: int,
        *,
        schedule_retry_on_failure: bool = True,
    ) -> Dict[str, Any]:
        try:
            logger.info("Starting POS sync for order %s, restaurant %s", order_id, restaurant_id)
            order, order_data, customization = self._build_order_submission_context(order_id)
            if not order:
                error_msg = f"Order {order_id} not found for POS sync"
                logger.error(error_msg)
                return {
                    "required": False,
                    "success": False,
                    "status": "FAILED",
                    "retry_scheduled": False,
                    "error": error_msg,
                    "results": [],
                }

            logger.info("[POS Sync] Fetching enabled POS integrations for restaurant %s", restaurant_id)
            pos_integrations = self.pos_integration_repo.get_enabled_integrations(restaurant_id)
            logger.info("[POS Sync] Found %s existing enabled integration(s) in database", len(pos_integrations))

            if not pos_integrations:
                logger.info(
                    "[POS Sync] No enabled POS integrations found for restaurant %s, order %s. POS sync skipped.",
                    restaurant_id,
                    order_id,
                )
                return {
                    "required": False,
                    "success": True,
                    "status": "SKIPPED",
                    "retry_scheduled": False,
                    "results": [],
                }

            logger.info(
                "[POS Sync] Processing %s POS integration(s) for restaurant %s",
                len(pos_integrations),
                restaurant_id,
            )
            results = []

            for pos_integration in pos_integrations:
                integration_id = pos_integration.get("id")
                idempotency_key = f"{order_id}-{integration_id}-{uuid.uuid4().hex[:8]}"
                sync_id = self.order_sync_repo.create_sync_record(
                    order_id, restaurant_id, integration_id, idempotency_key
                )
                results.append(
                    self._process_integration_submission(
                        sync_id=sync_id,
                        order_id=order_id,
                        restaurant_id=restaurant_id,
                        pos_integration=pos_integration,
                        order=order,
                        order_data=order_data,
                        customization=customization,
                        idempotency_key=idempotency_key,
                        attempt_count=1,
                        schedule_retry_on_failure=schedule_retry_on_failure,
                    )
                )

            success = all(result.get("success") for result in results)
            retry_scheduled = any(result.get("retry_scheduled") for result in results)
            logger.info("[POS Sync] Completed POS sync processing for order %s", order_id)
            return {
                "required": True,
                "success": success,
                "status": "CONFIRMED" if success else ("TEMPORARY_FAILURE" if retry_scheduled else "FAILED"),
                "retry_scheduled": retry_scheduled,
                "results": results,
                "error": next(
                    (result.get("error") for result in results if result.get("error")),
                    None,
                ),
            }
        except Exception as e:
            logger.exception(f"[POS Sync] Error in sync_order_to_pos for order {order_id}: {e}")
            logger.error(
                f"[POS Sync] POS sync failed completely for order {order_id}, restaurant {restaurant_id}: {str(e)}"
            )
            return {
                "required": True,
                "success": False,
                "status": "FAILED",
                "retry_scheduled": False,
                "results": [],
                "error": str(e),
            }

    def sync_order_to_pos(self, order_id: int, restaurant_id: int) -> Dict[str, Any]:
        return self.submit_order_to_pos(order_id, restaurant_id)

    @staticmethod
    def _latest_confirmed_syncs_by_integration(sync_records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        latest_by_integration: Dict[int, Dict[str, Any]] = {}
        for record in sync_records:
            integration_id = record.get("pos_integration_id")
            if integration_id is None:
                continue
            normalized_id = int(integration_id)
            if normalized_id not in latest_by_integration:
                latest_by_integration[normalized_id] = record
        return list(latest_by_integration.values())

    def _cancel_square_order(
        self,
        *,
        order_id: int,
        restaurant_id: int,
        pos_integration: Dict[str, Any],
        confirmed_sync: Dict[str, Any],
        reason: Optional[str],
    ) -> Dict[str, Any]:
        integration_id = int(pos_integration["id"])
        idempotency_key = f"{order_id}-{integration_id}-cancel-{uuid.uuid4().hex[:8]}"
        sync_id = self.order_sync_repo.create_sync_record(order_id, restaurant_id, integration_id, idempotency_key)
        provider = self.provider_registry.get_provider("SQUARE")
        external_order_id = confirmed_sync.get("external_order_id")
        external_payment_id = (
            str(confirmed_sync["external_payment_id"]) if confirmed_sync.get("external_payment_id") else None
        )

        try:
            if not external_order_id:
                raise ValueError(f"No external order ID found for confirmed POS sync on order {order_id}")

            result: POSOrderCancellationResult = provider.cancel_pickup_order(
                pos_integration,
                external_order_id=str(external_order_id),
                external_payment_id=external_payment_id,
                idempotency_key=idempotency_key,
                reason=reason,
            )
            self.order_sync_repo.update_sync_status(
                sync_id,
                status=result.status,
                external_order_id=result.external_order_id,
                external_payment_id=result.external_payment_id,
                attempts=1,
                response_payload=result.payload,
            )
            return {
                "success": result.status == "CANCELLED",
                "status": result.status,
                "sync_id": sync_id,
                "integration_id": integration_id,
                "pos_type": "SQUARE",
                "external_order_id": result.external_order_id,
                "external_payment_id": result.external_payment_id,
                "payload": result.payload,
            }
        except Exception as error:
            self.order_sync_repo.update_sync_status(
                sync_id,
                status="FAILED",
                external_order_id=str(external_order_id) if external_order_id else None,
                external_payment_id=external_payment_id,
                attempts=1,
                error=str(error),
            )
            raise

    def cancel_order_in_pos(
        self,
        order_id: int,
        restaurant_id: int,
        *,
        reason: Optional[str] = None,
    ) -> Dict[str, Any]:
        confirmed_syncs = self._latest_confirmed_syncs_by_integration(
            self.order_sync_repo.get_latest_confirmed_syncs(order_id)
        )
        if not confirmed_syncs:
            return {
                "required": False,
                "success": True,
                "status": "SKIPPED",
                "results": [],
            }

        results: List[Dict[str, Any]] = []
        for confirmed_sync in confirmed_syncs:
            integration_id = confirmed_sync.get("pos_integration_id")
            pos_integration = self.pos_integration_repo.get_by_id(int(integration_id)) if integration_id else None
            if not pos_integration:
                error_msg = f"POS integration not found for sync record {confirmed_sync.get('id')}"
                results.append(
                    {
                        "success": False,
                        "status": "FAILED",
                        "integration_id": integration_id,
                        "error": error_msg,
                    }
                )
                continue
            try:
                if str(pos_integration.get("pos_type") or "").upper() != "SQUARE":
                    raise ValueError(f"Unsupported POS type for cancellation: {pos_integration.get('pos_type')}")
                results.append(
                    self._cancel_square_order(
                        order_id=order_id,
                        restaurant_id=restaurant_id,
                        pos_integration=pos_integration,
                        confirmed_sync=confirmed_sync,
                        reason=reason,
                    )
                )
            except Exception as error:
                results.append(
                    {
                        "success": False,
                        "status": "FAILED",
                        "integration_id": integration_id,
                        "pos_type": pos_integration.get("pos_type"),
                        "error": str(error),
                    }
                )

        success = all(result.get("success") for result in results)
        return {
            "required": True,
            "success": success,
            "status": "CANCELLED" if success else "FAILED",
            "results": results,
            "error": next((result.get("error") for result in results if result.get("error")), None),
        }

    def replace_order_after_internal_update(
        self,
        order_id: int,
        restaurant_id: int,
        *,
        previous_state: Dict[str, Any],
        reason: Optional[str] = None,
    ) -> Dict[str, Any]:
        confirmed_syncs = self._latest_confirmed_syncs_by_integration(
            self.order_sync_repo.get_latest_confirmed_syncs(order_id)
        )
        if not confirmed_syncs:
            return {
                "required": False,
                "success": True,
                "status": "SKIPPED",
                "results": [],
                "rollback_performed": False,
                "rollback_success": True,
            }

        cancel_result = self.cancel_order_in_pos(order_id, restaurant_id, reason=reason)
        if not cancel_result.get("success"):
            self.restore_order_state(order_id, previous_state)
            return {
                "required": True,
                "success": False,
                "status": "FAILED",
                "error": cancel_result.get("error") or "Failed to cancel existing POS order.",
                "cancel_result": cancel_result,
                "rollback_performed": True,
                "rollback_success": True,
            }

        submit_result = self.submit_order_to_pos(order_id, restaurant_id, schedule_retry_on_failure=False)
        if submit_result.get("success"):
            return {
                **submit_result,
                "cancel_result": cancel_result,
                "rollback_performed": False,
                "rollback_success": True,
            }

        rollback_success = False
        rollback_result: Dict[str, Any] | None = None
        restore_error: Optional[str] = None
        try:
            self.restore_order_state(order_id, previous_state)
            rollback_result = self.submit_order_to_pos(order_id, restaurant_id, schedule_retry_on_failure=False)
            rollback_success = bool(rollback_result.get("success"))
        except Exception as error:
            restore_error = str(error)

        error_message = submit_result.get("error") or "Failed to submit updated POS order."
        if not rollback_success and restore_error:
            error_message = f"{error_message} Rollback also failed: {restore_error}"
        elif not rollback_success and rollback_result and rollback_result.get("error"):
            error_message = f"{error_message} Rollback also failed: {rollback_result.get('error')}"

        return {
            "required": True,
            "success": False,
            "status": "FAILED",
            "error": error_message,
            "cancel_result": cancel_result,
            "submit_result": submit_result,
            "rollback_performed": True,
            "rollback_success": rollback_success,
            "rollback_result": rollback_result,
        }
