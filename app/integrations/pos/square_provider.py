"""
Square implementation of the provider-agnostic POS adapter.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from square.core.api_error import ApiError

from app.config import settings
from app.integrations.pos.base import POSProvider
from app.integrations.pos.models import (
    POSCatalogAvailabilityItem,
    POSCatalogAvailabilityOptionValue,
    POSCatalogAvailabilitySnapshot,
    POSCatalogIssue,
    POSCatalogMenuItem,
    POSCatalogOptionGroup,
    POSCatalogOptionGroupAttachment,
    POSCatalogOptionValue,
    POSCatalogSnapshot,
    POSOrderCancellationResult,
    POSOrderSubmissionResult,
    POSSubmitOrderRequest,
)
from app.integrations.square_client import SquareClient
from app.utils.logging_config import get_logger

logger = get_logger(__name__)


class SquarePOSProvider(POSProvider):
    """Square provider adapter."""

    provider_name = "Square"
    pos_type = "SQUARE"

    def _get_credentials(self, integration: Dict[str, Any]) -> Dict[str, Any]:
        credentials = integration.get("credentials") or {}
        if isinstance(credentials, str):
            try:
                credentials = json.loads(credentials)
            except (TypeError, json.JSONDecodeError):
                credentials = {}
        return credentials

    def _get_access_token(self, integration: Dict[str, Any]) -> str:
        credentials = self._get_credentials(integration)
        access_token = credentials.get("access_token") or settings.SQUARE_ACCESS_TOKEN
        if not access_token:
            raise ValueError("Square access token not configured")
        return access_token

    def _get_client(self, integration: Dict[str, Any]) -> SquareClient:
        return SquareClient(self._get_access_token(integration))

    @staticmethod
    def _normalize_selection_type(value: Optional[str]) -> str:
        text = str(value or "MULTIPLE").strip().upper()
        return "single" if text == "SINGLE" else "multiple"

    @staticmethod
    def _normalize_selection_bound(value: Any, *, default: Optional[int]) -> Optional[int]:
        if value is None:
            return default
        try:
            normalized = int(value)
        except (TypeError, ValueError):
            return default
        if normalized < 0:
            return default
        return normalized

    @staticmethod
    def _resolve_square_bool_override(override_value: Any, base_value: Any) -> bool:
        text = str(override_value or "").strip().upper()
        if text == "YES":
            return True
        if text == "NO":
            return False
        if text == "NOT_SET":
            override_value = None
        return bool(base_value) if override_value is None else bool(override_value)

    @staticmethod
    def _normalize_display_name(item_name: str, variation_name: str) -> str:
        if not variation_name or variation_name.strip().lower() in {"regular", "default"}:
            return item_name
        if variation_name.strip().lower() == item_name.strip().lower():
            return item_name
        return f"{item_name} - {variation_name}"

    @staticmethod
    def _get_location_override(overrides: Any, location_id: Optional[str]) -> Dict[str, Any]:
        if not location_id or not isinstance(overrides, list):
            return {}
        for override in overrides:
            if not isinstance(override, dict):
                continue
            if str(override.get("location_id") or "") == str(location_id):
                return override
        return {}

    @staticmethod
    def _build_object_map(catalog_objects: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        object_map: Dict[str, Dict[str, Any]] = {}
        for obj in catalog_objects:
            object_id = obj.get("id")
            if object_id:
                object_map[str(object_id)] = obj
        return object_map

    @staticmethod
    def _normalize_begin_time(begin_time: Optional[str]) -> Optional[str]:
        if not begin_time:
            return None
        try:
            parsed = datetime.fromisoformat(str(begin_time).replace("Z", "+00:00"))
        except (TypeError, ValueError):
            return begin_time
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        normalized = parsed.astimezone(timezone.utc)
        adjusted = normalized.timestamp() - 1
        return datetime.fromtimestamp(max(adjusted, 0), tz=timezone.utc).isoformat().replace("+00:00", "Z")

    @staticmethod
    def _is_currently_sold_out(override: Dict[str, Any]) -> bool:
        if not override:
            return False
        if not bool(override.get("sold_out", False)):
            return False
        sold_out_valid_until = override.get("sold_out_valid_until")
        if not sold_out_valid_until:
            return True
        try:
            valid_until = datetime.fromisoformat(str(sold_out_valid_until).replace("Z", "+00:00"))
        except (TypeError, ValueError):
            return True
        if valid_until.tzinfo is None:
            valid_until = valid_until.replace(tzinfo=timezone.utc)
        return valid_until > datetime.now(timezone.utc)

    def _is_variation_available(self, variation_data: Dict[str, Any], location_id: Optional[str]) -> bool:
        if not bool(variation_data.get("sellable", True)):
            return False
        location_override = self._get_location_override(variation_data.get("location_overrides"), location_id)
        return not self._is_currently_sold_out(location_override)

    def _is_modifier_available(
        self,
        *,
        modifier_data: Dict[str, Any],
        override: Dict[str, Any],
        location_id: Optional[str],
    ) -> bool:
        hidden_online = self._resolve_square_bool_override(
            override.get("hidden_online_override"),
            modifier_data.get("hidden_online", False),
        )
        if hidden_online:
            return False
        location_override = self._get_location_override(modifier_data.get("location_overrides"), location_id)
        return not self._is_currently_sold_out(location_override)

    @staticmethod
    def _build_category_map(catalog_objects: List[Dict[str, Any]]) -> Dict[str, str]:
        categories: Dict[str, str] = {}
        for obj in catalog_objects:
            if obj.get("type") != "CATEGORY" or obj.get("is_deleted"):
                continue
            category_data = obj.get("category_data") or {}
            category_name = category_data.get("name")
            category_id = obj.get("id")
            if category_id and category_name:
                categories[str(category_id)] = category_name
        return categories

    @staticmethod
    def _build_modifier_list_map(catalog_objects: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        modifier_lists: Dict[str, Dict[str, Any]] = {}
        for obj in catalog_objects:
            if obj.get("type") != "MODIFIER_LIST" or obj.get("is_deleted"):
                continue
            modifier_lists[str(obj.get("id"))] = obj
        return modifier_lists

    @staticmethod
    def _get_item_category_name(item_data: Dict[str, Any], category_map: Dict[str, str]) -> Optional[str]:
        category_id = item_data.get("category_id")
        if category_id and str(category_id) in category_map:
            return category_map[str(category_id)]

        categories = item_data.get("categories") or []
        for category in categories:
            if isinstance(category, dict):
                category_id = category.get("id") or category.get("category_id")
            else:
                category_id = category
            if category_id and str(category_id) in category_map:
                return category_map[str(category_id)]
        return None

    def _build_option_group(
        self,
        modifier_list_id: str,
        modifier_list_obj: Dict[str, Any],
        modifier_list_info: Dict[str, Any],
        sort_order: int,
        location_id: Optional[str],
        modifier_object_map: Optional[Dict[str, Dict[str, Any]]] = None,
    ) -> POSCatalogOptionGroup:
        modifier_list_data = modifier_list_obj.get("modifier_list_data") or {}
        modifier_type = str(modifier_list_data.get("modifier_type") or "LIST").upper()
        input_type = "TEXT" if modifier_type == "TEXT" else "SELECT"
        selection_type = self._normalize_selection_type(
            modifier_list_data.get("selection_type") or ("SINGLE" if input_type == "TEXT" else "MULTIPLE")
        )
        min_select = self._normalize_selection_bound(
            modifier_list_info.get("min_selected_modifiers"),
            default=0,
        )
        max_select_default = 1 if input_type == "TEXT" else None
        max_select = self._normalize_selection_bound(
            modifier_list_info.get("max_selected_modifiers"),
            default=max_select_default,
        )
        text_required = bool(modifier_list_data.get("text_required")) if input_type == "TEXT" else False
        effective_selection_type = self._normalize_selection_type(
            modifier_list_info.get("selection_type") or selection_type
        )
        effective_allows_quantity = bool(
            modifier_list_info.get("allow_quantities", modifier_list_data.get("allow_quantities", False))
        )

        modifier_overrides = {
            str(override.get("modifier_id")): override
            for override in (modifier_list_info.get("modifier_overrides") or [])
            if override.get("modifier_id")
        }

        values: List[POSCatalogOptionValue] = []
        for value_sort_order, modifier in enumerate(modifier_list_data.get("modifiers") or []):
            if modifier.get("type") != "MODIFIER" or modifier.get("is_deleted"):
                continue
            modifier_id = modifier.get("id")
            if not modifier_id:
                continue
            modifier_source = (modifier_object_map or {}).get(str(modifier_id), modifier)
            modifier_data = modifier_source.get("modifier_data") or modifier.get("modifier_data") or {}

            override = modifier_overrides.get(str(modifier_id), {})
            price_money = modifier_data.get("price_money") or {}
            values.append(
                POSCatalogOptionValue(
                    external_id=str(modifier_id),
                    external_group_id=modifier_list_id,
                    name=modifier_data.get("name") or "",
                    price_delta=float(price_money.get("amount", 0)) / 100.0,
                    is_default=bool(
                        override.get(
                            "on_by_default_override",
                            override.get("on_by_default", modifier_data.get("on_by_default", False)),
                        )
                    ),
                    is_available=self._is_modifier_available(
                        modifier_data=modifier_data,
                        override=override,
                        location_id=location_id,
                    ),
                    sort_order=value_sort_order,
                    external_object_type=modifier_source.get("type", modifier.get("type", "MODIFIER")),
                    external_version=(
                        str(modifier_source.get("version"))
                        if modifier_source.get("version") is not None
                        else (str(modifier.get("version")) if modifier.get("version") is not None else None)
                    ),
                    source_name=modifier_data.get("name"),
                    metadata={"raw_modifier_data": modifier_data},
                )
            )

        return POSCatalogOptionGroup(
            external_id=modifier_list_id,
            name=modifier_list_data.get("name") or "",
            description=None,
            selection_type=selection_type,
            min_select=0,
            max_select=1 if input_type == "TEXT" else None,
            free_allowance=0,
            free_allowance_strategy="HIGHEST_PRICE_FIRST",
            allows_quantity=(
                bool(modifier_list_data.get("allow_quantities", False)) if input_type == "SELECT" else False
            ),
            max_quantity_per_option=None,
            prompt_style="ASK_IF_MENTIONED",
            is_required=False,
            is_available=not self._resolve_square_bool_override(
                modifier_list_info.get("hidden_from_customer_override"),
                modifier_list_data.get("hidden_from_customer", False),
            ),
            sort_order=sort_order,
            input_type=input_type,
            text_required=text_required,
            max_text_length=modifier_list_data.get("max_length"),
            values=values if input_type == "SELECT" else [],
            external_parent_id=modifier_list_info.get("item_id"),
            external_object_type=modifier_list_obj.get("type", "MODIFIER_LIST"),
            external_version=(
                str(modifier_list_obj.get("version")) if modifier_list_obj.get("version") is not None else None
            ),
            source_name=modifier_list_data.get("name"),
            attachment=POSCatalogOptionGroupAttachment(
                selection_type=effective_selection_type,
                min_select=min_select,
                max_select=max_select,
                free_allowance=0,
                allows_quantity=effective_allows_quantity if input_type == "SELECT" else False,
                max_quantity_per_option=None,
                is_required=min_select > 0,
                sort_order=sort_order,
                metadata={"raw_modifier_list_info": modifier_list_info},
            ),
            metadata={"raw_modifier_list_info": modifier_list_info},
        )

    def _search_availability_objects(
        self,
        integration: Dict[str, Any],
        *,
        begin_time: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        client = self._get_client(integration)
        normalized_begin_time = self._normalize_begin_time(begin_time)
        response = client.search_catalog_objects(
            object_types=["ITEM_VARIATION", "MODIFIER"],
            begin_time=normalized_begin_time,
            limit=1000,
        )
        return response.get("objects") or []

    def fetch_catalog(self, integration: Dict[str, Any]) -> POSCatalogSnapshot:
        client = self._get_client(integration)
        location_id = integration.get("location_id")
        try:
            locations_response = client.list_locations()
            locations = locations_response.get("locations") or []
        except ApiError as error:
            logger.warning(
                "[Square API] ListLocations failed during catalog import; continuing without account metadata: %s",
                error,
            )
            locations = []
        availability_objects = self._search_availability_objects(integration)
        availability_object_map = self._build_object_map(availability_objects)
        matched_location = next(
            (location for location in locations if str(location.get("id") or "") == str(location_id or "")),
            None,
        )
        response = client.list_catalog(types=["CATEGORY", "ITEM", "MODIFIER_LIST"])
        catalog_objects = response.get("objects", [])
        category_map = self._build_category_map(catalog_objects)
        modifier_list_map = self._build_modifier_list_map(catalog_objects)

        items: List[POSCatalogMenuItem] = []
        issues: List[POSCatalogIssue] = []
        catalog_versions: List[str] = []

        for obj in catalog_objects:
            if obj.get("type") != "ITEM" or obj.get("is_deleted"):
                continue

            item_id = obj.get("id")
            item_data = obj.get("item_data") or {}
            item_name = item_data.get("buyer_facing_name") or item_data.get("name") or ""
            source_item_name = item_data.get("name") or item_name
            source_description = item_data.get("description_plaintext") or item_data.get("description")
            category_name = self._get_item_category_name(item_data, category_map)

            modifier_groups: List[POSCatalogOptionGroup] = []
            for group_sort_order, modifier_list_info in enumerate(item_data.get("modifier_list_info") or []):
                modifier_list_id = modifier_list_info.get("modifier_list_id")
                if not modifier_list_id:
                    continue
                modifier_list_obj = modifier_list_map.get(str(modifier_list_id))
                if not modifier_list_obj:
                    issues.append(
                        POSCatalogIssue(
                            scope="OPTION_GROUP",
                            issue_type="MISSING_EXTERNAL_REFERENCE",
                            title="Modifier list reference missing from Square catalog payload",
                            external_object_id=str(modifier_list_id),
                            external_parent_id=str(item_id) if item_id is not None else None,
                            details=f"Item '{source_item_name}' references modifier list '{modifier_list_id}' which was not returned by Square.",
                        )
                    )
                    continue
                modifier_groups.append(
                    self._build_option_group(
                        str(modifier_list_id),
                        modifier_list_obj,
                        modifier_list_info,
                        group_sort_order,
                        str(location_id) if location_id is not None else None,
                        availability_object_map,
                    )
                )

            variations = item_data.get("variations") or []
            valid_variation_count = 0
            for variation in variations:
                if variation.get("type") != "ITEM_VARIATION" or variation.get("is_deleted"):
                    continue
                variation_id = variation.get("id")
                if not variation_id:
                    continue

                variation_source = availability_object_map.get(str(variation_id), variation)
                variation_data = (
                    variation_source.get("item_variation_data") or variation.get("item_variation_data") or {}
                )
                price_money = variation_data.get("price_money") or {}
                price_amount = price_money.get("amount")
                if price_amount is None:
                    issues.append(
                        POSCatalogIssue(
                            scope="ITEM",
                            issue_type="MISSING_PRICE",
                            title="Square variation is missing a fixed price",
                            external_object_id=str(variation_id),
                            external_parent_id=str(item_id) if item_id is not None else None,
                            details=f"Variation '{variation_data.get('name') or source_item_name}' does not have price_money.amount.",
                        )
                    )
                    continue

                valid_variation_count += 1
                variation_name = variation_data.get("name") or ""
                items.append(
                    POSCatalogMenuItem(
                        external_id=str(variation_id),
                        external_parent_id=str(item_id) if item_id is not None else None,
                        external_object_type=variation_source.get("type", variation.get("type", "ITEM_VARIATION")),
                        external_version=(
                            str(variation_source.get("version"))
                            if variation_source.get("version") is not None
                            else (str(variation.get("version")) if variation.get("version") is not None else None)
                        ),
                        name=self._normalize_display_name(item_name, variation_name),
                        description=source_description,
                        price=float(price_amount) / 100.0,
                        category=category_name,
                        sub_category=None,
                        is_available=self._is_variation_available(
                            variation_data,
                            str(location_id) if location_id is not None else None,
                        ),
                        is_active=not bool(variation.get("is_deleted", False)),
                        option_groups=modifier_groups,
                        source_name=source_item_name,
                        source_description=source_description,
                        source_category=category_name,
                        source_sub_category=None,
                        metadata={
                            "square_item_id": item_id,
                            "square_variation_name": variation_name,
                            "sku": variation_data.get("sku"),
                        },
                    )
                )
                if variation.get("version") is not None:
                    catalog_versions.append(str(variation.get("version")))

            if valid_variation_count == 0:
                issues.append(
                    POSCatalogIssue(
                        scope="ITEM",
                        issue_type="UNSUPPORTED_ITEM",
                        title="Square item has no sellable fixed-price variations",
                        external_object_id=str(item_id) if item_id is not None else None,
                        details=f"Item '{source_item_name}' could not be imported because no supported variation was found.",
                    )
                )

        catalog_version = max(catalog_versions) if catalog_versions else None
        return POSCatalogSnapshot(
            items=items,
            catalog_version=catalog_version,
            issues=issues,
            metadata={
                "object_count": len(catalog_objects),
                "external_account_id": matched_location.get("merchant_id") if matched_location else None,
                "location_currency": matched_location.get("currency") if matched_location else None,
            },
        )

    def fetch_availability_updates(
        self,
        integration: Dict[str, Any],
        *,
        begin_time: str | None = None,
    ) -> POSCatalogAvailabilitySnapshot:
        location_id = integration.get("location_id")
        if not location_id:
            return POSCatalogAvailabilitySnapshot()

        availability_objects = self._search_availability_objects(integration, begin_time=begin_time)
        item_updates: List[POSCatalogAvailabilityItem] = []
        option_value_updates: List[POSCatalogAvailabilityOptionValue] = []

        for obj in availability_objects:
            object_type = str(obj.get("type") or "").upper()
            object_id = obj.get("id")
            if not object_id:
                continue
            if object_type == "ITEM_VARIATION":
                variation_data = obj.get("item_variation_data") or {}
                item_updates.append(
                    POSCatalogAvailabilityItem(
                        external_id=str(object_id),
                        is_available=self._is_variation_available(variation_data, str(location_id)),
                        metadata={"raw_item_variation_data": variation_data},
                    )
                )
            elif object_type == "MODIFIER":
                modifier_data = obj.get("modifier_data") or {}
                option_value_updates.append(
                    POSCatalogAvailabilityOptionValue(
                        external_id=str(object_id),
                        external_group_id=modifier_data.get("modifier_list_id"),
                        is_available=self._is_modifier_available(
                            modifier_data=modifier_data,
                            override={},
                            location_id=str(location_id),
                        ),
                        metadata={"raw_modifier_data": modifier_data},
                    )
                )

        return POSCatalogAvailabilitySnapshot(
            items=item_updates,
            option_values=option_value_updates,
            metadata={"begin_time": begin_time},
        )

    @staticmethod
    def _build_pickup_details(request: POSSubmitOrderRequest) -> Dict[str, Any]:
        pickup_details: Dict[str, Any] = {}
        recipient: Dict[str, Any] = {}
        if request.customer_phone:
            recipient["phone_number"] = request.customer_phone
        if request.customer_name:
            recipient["display_name"] = request.customer_name
        if recipient:
            pickup_details["recipient"] = recipient
        if request.pickup_at:
            pickup_details["pickup_at"] = request.pickup_at
        return pickup_details

    @staticmethod
    def _compute_total_amount(request: POSSubmitOrderRequest) -> float:
        total = 0.0
        for line_item in request.line_items:
            unit_total = float(line_item.price)
            for modifier in line_item.modifiers:
                unit_total += float(modifier.price_delta) * max(modifier.quantity, 1)
            total += unit_total * max(line_item.quantity, 1)
        return round(total, 2)

    def _build_order_payload(self, request: POSSubmitOrderRequest) -> Dict[str, Any]:
        line_items: List[Dict[str, Any]] = []
        for line_item in request.line_items:
            square_line_item: Dict[str, Any] = {
                "catalog_object_id": line_item.external_item_id,
                "quantity": str(max(line_item.quantity, 1)),
            }
            if line_item.note:
                square_line_item["note"] = line_item.note[:500]

            modifiers: List[Dict[str, Any]] = []
            for modifier in line_item.modifiers:
                modifier_payload: Dict[str, Any] = {
                    "quantity": str(max(modifier.quantity, 1)),
                }
                if modifier.external_value_id:
                    modifier_payload["catalog_object_id"] = modifier.external_value_id
                else:
                    modifier_payload["name"] = (modifier.free_text_value or modifier.name or "Custom").strip()[:255]
                    if modifier.price_delta:
                        modifier_payload["base_price_money"] = {
                            "amount": int(round(float(modifier.price_delta) * 100)),
                            "currency": request.currency,
                        }
                modifiers.append(modifier_payload)

            if modifiers:
                square_line_item["modifiers"] = modifiers
            line_items.append(square_line_item)

        return {
            "line_items": line_items,
            "fulfillments": [{"type": "PICKUP", "pickup_details": self._build_pickup_details(request)}],
            "reference_id": request.reference_id,
        }

    @staticmethod
    def _is_square_error_like(error: ApiError, needle: str) -> bool:
        errors = error.body.get("errors") if isinstance(error.body, dict) else None
        return any(needle in str(item.get("detail", "")).lower() for item in (errors or []) if isinstance(item, dict))

    @staticmethod
    def _extract_order_money(order_data: Dict[str, Any], fallback_currency: str) -> tuple[int, str]:
        money = order_data.get("total_money") or order_data.get("net_amount_due_money") or {}
        amount = int(money.get("amount") or 0)
        currency = str(money.get("currency") or fallback_currency or "USD")
        return amount, currency

    def submit_pickup_order(
        self,
        integration: Dict[str, Any],
        request: POSSubmitOrderRequest,
        *,
        idempotency_key: str,
    ) -> POSOrderSubmissionResult:
        client = self._get_client(integration)
        order_payload = self._build_order_payload(request)
        order_response = client.create_order(
            request.location_id,
            order_payload,
            idempotency_key=idempotency_key,
        )

        order_data = order_response.get("order") or {}
        external_order_id = order_data.get("id")
        payload: Dict[str, Any] = {"order_response": order_response}

        payment_id: Optional[str] = None
        if external_order_id:
            payment_response = client.create_payment(
                order_id=external_order_id,
                amount=self._compute_total_amount(request),
                currency=request.currency,
                idempotency_key=f"{idempotency_key}-payment",
            )
            payload["payment_response"] = payment_response
            payment = payment_response.get("payment") or {}
            payment_id = payment.get("id")
            if payment_id:
                try:
                    pay_order_response = client.pay_order(
                        order_id=external_order_id,
                        payment_ids=[payment_id],
                        idempotency_key=f"{idempotency_key}-pay",
                    )
                    payload["pay_order_response"] = pay_order_response
                except ApiError as error:
                    errors = error.body.get("errors") if isinstance(error.body, dict) else None
                    already_paid = any(
                        str(item.get("code")) == "BAD_REQUEST" and "already paid" in str(item.get("detail", "")).lower()
                        for item in (errors or [])
                        if isinstance(item, dict)
                    )
                    if already_paid:
                        payload["pay_order_response"] = {
                            "status": "ALREADY_PAID",
                            "errors": errors or [],
                        }
                    else:
                        raise

        return POSOrderSubmissionResult(
            external_order_id=external_order_id,
            external_payment_id=payment_id,
            status="CONFIRMED" if external_order_id else "FAILED",
            payload=payload,
        )

    def cancel_pickup_order(
        self,
        integration: Dict[str, Any],
        *,
        external_order_id: str,
        external_payment_id: Optional[str] = None,
        idempotency_key: str,
        reason: Optional[str] = None,
    ) -> POSOrderCancellationResult:
        client = self._get_client(integration)
        order_response = client.get_order(external_order_id)
        order_data = order_response.get("order") or {}
        location_id = order_data.get("location_id") or integration.get("location_id")
        version = order_data.get("version")
        if version is None:
            raise ValueError(f"Square order {external_order_id} is missing version for cancellation.")

        fulfillments = order_data.get("fulfillments") or []
        if not fulfillments:
            raise ValueError(f"Square order {external_order_id} has no fulfillments to cancel.")

        pickup_found = False
        needs_cancel = False
        updated_fulfillments: List[Dict[str, Any]] = []
        for fulfillment in fulfillments:
            normalized = dict(fulfillment)
            if str(normalized.get("type") or "").upper() == "PICKUP":
                pickup_found = True
                if str(normalized.get("state") or "").upper() != "CANCELED":
                    normalized["state"] = "CANCELED"
                    needs_cancel = True
            updated_fulfillments.append(normalized)

        if not pickup_found:
            raise ValueError(f"Square order {external_order_id} does not have a pickup fulfillment.")

        payload: Dict[str, Any] = {"order_response": order_response}
        if needs_cancel:
            update_order_response = client.update_order(
                external_order_id,
                order_data={
                    "location_id": location_id,
                    "version": version,
                    "fulfillments": updated_fulfillments,
                },
                idempotency_key=f"{idempotency_key}-cancel",
            )
            payload["update_order_response"] = update_order_response
        else:
            payload["update_order_response"] = {"status": "ALREADY_CANCELLED"}

        refund_response: Optional[Dict[str, Any]] = None
        if external_payment_id:
            amount_cents, currency = self._extract_order_money(order_data, str(integration.get("currency") or "USD"))
            if amount_cents > 0:
                try:
                    refund_response = client.refund_payment(
                        payment_id=external_payment_id,
                        amount_cents=amount_cents,
                        currency=currency,
                        idempotency_key=f"{idempotency_key}-refund",
                        reason=reason,
                    )
                except ApiError as error:
                    if self._is_square_error_like(error, "already refunded") or self._is_square_error_like(
                        error, "has already been refunded"
                    ):
                        refund_response = {
                            "status": "ALREADY_REFUNDED",
                            "errors": error.body.get("errors") if isinstance(error.body, dict) else [],
                        }
                    else:
                        raise
                payload["refund_response"] = refund_response

        return POSOrderCancellationResult(
            external_order_id=external_order_id,
            external_payment_id=external_payment_id,
            status="CANCELLED",
            payload=payload,
        )
