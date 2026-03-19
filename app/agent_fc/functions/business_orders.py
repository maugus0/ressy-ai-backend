"""Business order-related function implementations wired to application services."""

from __future__ import annotations

import asyncio
import inspect
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.agent_fc.functions.common_business import load_business
from app.agent_fc.functions.function_context import (
    NoArgs,
    context_customer_contact,
    context_order_session_state,
    context_business_id,
    split_call_context,
)
from app.config import settings
from app.models.order_models import OrderItemOptionGroupSelection
from app.repositories.mysql_catalogue_repo import MySQLCatalogueRepository
from app.repositories.mysql_business_order_item_repo import MySQLOrderItemRepository
from app.repositories.mysql_business_order_repo import MySQLOrderRepository
from app.repositories.mysql_user_repo import MySQLUserRepository
from app.repositories.mysql_user_business_metadata_repo import (
    MySQLUserRestaurantMetadataRepository,
)
from app.services.business_activity_history_service import BusinessActivityHistoryService
from app.services.business_notification_service import BusinessNotificationService
from app.services.business_order_customization_service import BusinessOrderCustomizationService
from app.services.sse_service import OrderEventSubtype, SSEService
from app.utils.business_hours import format_operating_window, is_business_open_now
from app.utils.timezone import coerce_datetime

logger = logging.getLogger(__name__)


class OrderItem(BaseModel):
    model_config = ConfigDict(extra="allow")

    # Positive values map to known menu items. `0` is allowed for custom/freeform items.
    item_id: int = Field(ge=0)
    name: str
    quantity: int = 1
    price: Optional[float] = None
    instructions: Optional[str] = None
    options: List[OrderItemOptionGroupSelection] = Field(default_factory=list)

    @field_validator("options", mode="before")
    @classmethod
    def _normalize_options(cls, value: Any) -> List[OrderItemOptionGroupSelection]:
        if value is None:
            return []
        if isinstance(value, list):
            return value
        if isinstance(value, dict):
            normalized: List[OrderItemOptionGroupSelection] = []
            for group_id, selections in value.items():
                if selections is None:
                    continue
                normalized.append(
                    OrderItemOptionGroupSelection.model_validate({"group_id": int(group_id), "selections": selections})
                )
            return normalized
        return []


class CreateOrderArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    customer_name: Optional[str] = None
    pickup_time_iso: Optional[str] = None
    items: List[OrderItem]
    notes: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class LookupOrderByIdArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    order_id: int


class CheckItemsAvailabilityArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: List[OrderItem]
    location: Optional[str] = None


class UpdateOrderDetailsArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    customer_name: Optional[str] = None  # Allow updating customer name during order update
    items: List[OrderItem]
    customization: Dict[str, Any] = Field(default_factory=dict)
    total_amount: Optional[float] = None
    notes: Optional[str] = None
    status: Optional[str] = None  # Allow status changes (e.g., "cancelled") within update window


# ---------- Repository/Service Factory Functions ----------
# Create fresh instances per function call to ensure up-to-date data
# during active voice calls. This fixes mid-call updates not being detected.


def _get_order_repo() -> MySQLOrderRepository:
    """Create fresh order repository instance per function call."""
    return MySQLOrderRepository()


def _get_user_repo() -> MySQLUserRepository:
    """Create fresh user repository instance per function call."""
    return MySQLUserRepository()


def _get_menu_repo() -> MySQLCatalogueRepository:
    """Create fresh menu repository instance per function call."""
    return MySQLCatalogueRepository()


def _get_order_item_repo() -> MySQLOrderItemRepository:
    """Create fresh order item repository instance per function call."""
    return MySQLOrderItemRepository()


def _get_metadata_repo() -> MySQLUserRestaurantMetadataRepository:
    """Create fresh metadata repository instance per function call."""
    return MySQLUserRestaurantMetadataRepository()


def _get_history_service() -> BusinessActivityHistoryService:
    """Create fresh history service instance per function call."""
    return BusinessActivityHistoryService()


def _get_sse_service() -> SSEService:
    """Create fresh SSE service instance per function call."""
    return SSEService()


def _get_customization_service() -> BusinessOrderCustomizationService:
    """Create fresh customization service per function call."""
    return BusinessOrderCustomizationService()


async def _emit_order_sse_event(
    business_id: int,
    order_id: int,
    subtype: OrderEventSubtype,
    data: Dict[str, Any],
) -> None:
    """
    Emit SSE order event AND persist notification. Non-blocking, failure-tolerant.
    """
    try:
        sse_service = _get_sse_service()
        await sse_service.emit_order_event(
            business_id=business_id,
            order_id=order_id,
            subtype=subtype,
            data=data,
        )
    except Exception as sse_error:
        logger.error("[SSE] Order event emission failed for order %s (%s): %s", order_id, subtype.value, sse_error)

    try:
        notification_service = BusinessNotificationService()
        notification_service.create_notification(
            business_id=business_id,
            type="order",
            subtype=subtype.value if hasattr(subtype, "value") else subtype,
            data={"order_id": order_id, **(data or {})},
            entity_id=order_id,
        )
    except Exception as e:
        logger.error("[Notification] Order notification persistence failed for order %s: %s", order_id, e)


async def _send_voice_order_sms(
    business: Dict[str, Any],
    order_id: int,
    customer_phone: str,
) -> None:
    """Send SMS notification for voice-agent-created order.

    This is a fire-and-forget background task - SMS failures should not
    affect the voice call or order creation.
    """
    import json

    try:
        twilio_number = (business.get("twilio_phone_number") or "").strip()
        if not twilio_number:
            logger.debug("No Twilio number configured for business %s", business.get("id"))
            return

        twilio_details = business.get("twilio_details") or {}
        if isinstance(twilio_details, str):
            try:
                twilio_details = json.loads(twilio_details) if twilio_details else {}
            except json.JSONDecodeError as e:
                logger.warning(
                    "Invalid JSON in twilio_details for business %s: %s",
                    business.get("id"),
                    e,
                )
                twilio_details = {}
            except Exception as e:
                logger.warning(
                    "Unexpected error parsing twilio_details for business %s: %s",
                    business.get("id"),
                    e,
                )
                twilio_details = {}

        sid = twilio_details.get("account_sid") or twilio_details.get("TWILIO_ACCOUNT_SID")
        token = twilio_details.get("auth_token") or twilio_details.get("TWILIO_AUTH_TOKEN")

        notification_service = BusinessNotificationService()
        await notification_service.send_order_notification(
            business_id=business.get("id"),
            order_id=order_id,
            new_status="pending",  # Voice-created orders start as pending
            recipient_phone=customer_phone,
            business_name=business.get("name") or "",
            business_twilio_number=twilio_number,
            twilio_account_sid=sid,
            twilio_auth_token=token,
        )
        logger.info("SMS sent for voice order %s", order_id)
    except Exception as e:
        # Don't fail the voice call if SMS fails - just log
        logger.warning("Failed to send SMS for voice order %s: %s", order_id, e)


def _normalize_boolean(value: Any) -> bool:
    """
    Normalize a value to a boolean, handling MySQL TINYINT (0/1) and Python booleans.

    Handles:
    - True/False (Python boolean)
    - 0/1 (MySQL TINYINT)
    - None (defaults to False)
    - Other types (safely defaults to False)

    Args:
        value: The value to normalize (can be bool, int, None, or other)

    Returns:
        bool: Normalized boolean value
    """
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    try:
        # Handle MySQL TINYINT (0/1) and other numeric types
        return int(value) == 1
    except (TypeError, ValueError):
        # Handle edge cases (non-numeric strings, etc.) - default to False
        return False


async def _run_service_call(func, *args, **kwargs):
    if inspect.iscoroutinefunction(func):
        return await func(*args, **kwargs)
    return await asyncio.to_thread(func, *args, **kwargs)


def _summarize_items(items: List[OrderItem]) -> List[Dict[str, Any]]:
    return [
        {
            "name": item.name,
            "quantity": item.quantity,
            "item_id": item.item_id,
            "instructions": item.instructions,
            "options": [option.model_dump() for option in item.options],
        }
        for item in items
    ]


def _calculate_total(items: List[OrderItem]) -> float:
    """Compute total from item prices * quantities; treats missing prices as 0 after any lookups."""
    total = 0.0
    for item in items:
        price = item.price if item.price is not None else 0.0
        qty = max(item.quantity, 1)
        try:
            total += float(price) * qty
        except (TypeError, ValueError):
            continue
    return round(total, 2)


def _has_catalogue_item_id(item_id: Optional[int]) -> bool:
    try:
        return int(item_id) > 0
    except (TypeError, ValueError):
        return False


def _coerce_positive_int(value: Any) -> Optional[int]:
    try:
        normalized = int(value)
    except (TypeError, ValueError):
        return None
    return normalized if normalized > 0 else None


def _snapshot_catalogue_item_id(item_id: Optional[int]) -> Optional[int]:
    if not _has_catalogue_item_id(item_id):
        return None
    return int(item_id)


async def _validate_and_price_items(
    items: List[OrderItem],
) -> Tuple[List[Dict[str, Any]], Optional[List[Dict[str, Any]]]]:
    """
    Validate customization selections and compute pricing snapshots.
    """
    customization_service = _get_customization_service()
    priced_items: List[Dict[str, Any]] = []
    issues: List[Dict[str, Any]] = []

    for item in items:
        base_price = float(item.price or 0)
        if not _has_catalogue_item_id(item.item_id):
            if item.options:
                issues.append(
                    {
                        "item_id": item.item_id,
                        "item_name": item.name,
                        "issues": [
                            {
                                "issue_code": "INVALID_OPTION",
                                "message": "Customizations require a known menu item.",
                            }
                        ],
                    }
                )
                continue
            option_total = 0.0
            final_unit_price = base_price
            total_price = round(final_unit_price * max(item.quantity, 1), 2)
            priced_items.append(
                {
                    "option_total": option_total,
                    "final_unit_price": final_unit_price,
                    "total_price": total_price,
                    "option_snapshots": [],
                }
            )
            continue

        validation = await _run_service_call(customization_service.validate_item_options, item.item_id, item.options)
        if not validation.is_valid:
            issues.append(
                {
                    "item_id": item.item_id,
                    "item_name": item.name,
                    "issues": [issue.model_dump() for issue in validation.issues],
                }
            )
            continue

        item.options = validation.normalized_options
        priced = await _run_service_call(
            customization_service.price_item,
            item.item_id,
            base_price,
            item.quantity,
            validation.normalized_options,
        )
        priced_items.append(
            {
                "option_total": priced.option_total,
                "final_unit_price": priced.final_unit_price,
                "total_price": priced.total_price,
                "option_snapshots": priced.option_snapshots,
            }
        )

    if issues:
        return [], issues
    return priced_items, None


async def _populate_missing_prices(business_id: int, items: List[OrderItem]) -> None:
    """Fill in missing item prices by looking up the business menu."""
    missing_prices = [item for item in items if item.price is None]
    if not missing_prices:
        return

    try:
        menu_repo = _get_menu_repo()
        menu_items = await _run_service_call(menu_repo.get_available_items_by_business, business_id)
    except Exception as exc:  # noqa: BLE001 - defensive for agent calls
        logger.warning("Unable to fetch menu for price lookup business_id=%s: %s", business_id, exc)
        return

    price_by_id: Dict[int, Any] = {}
    price_by_name: Dict[str, Any] = {}
    for menu_item in menu_items or []:
        try:
            item_id = int(menu_item.get("id"))
            price_by_id[item_id] = menu_item.get("price")
        except (TypeError, ValueError, AttributeError):
            # Skip malformed menu rows; price lookup will continue by name if available.
            pass
        name = menu_item.get("item_name") or menu_item.get("name")
        if name:
            price_by_name[str(name).lower()] = menu_item.get("price")

    for item in items:
        if item.price is not None:
            continue

        lookup_price = None
        if item.item_id is not None:
            try:
                lookup_price = price_by_id.get(int(item.item_id))
            except (TypeError, ValueError):
                lookup_price = None
        if lookup_price is None and item.name:
            lookup_price = price_by_name.get(item.name.lower())

        if lookup_price is None:
            continue

        try:
            item.price = float(lookup_price)
        except (TypeError, ValueError):
            continue


async def create_order(**kwargs) -> Dict[str, Any]:
    context, model_kwargs = split_call_context(kwargs, CreateOrderArgs)
    args = CreateOrderArgs.model_validate(model_kwargs)
    call_sid = context.get("call_sid")
    business_id = context_business_id(context)
    customer_contact = context_customer_contact(context)
    order_session_state = context_order_session_state(context)
    if business_id is None:
        return {"status": "FAILED", "message": "Missing business context."}
    if not customer_contact:
        return {"status": "FAILED", "message": "Missing caller contact context."}
    business = await load_business(business_id)
    if not business:
        return {
            "status": "FAILED",
            "message": "Unable to load business information right now. Please try again shortly.",
        }
    if not is_business_open_now(business):
        return {
            "status": "CLOSED",
            "message": (
                "The business is currently closed. Please place your order during operating hours "
                f"({format_operating_window(business)})."
            ),
        }
    await _populate_missing_prices(business_id, args.items)
    priced_items, validation_issues = await _validate_and_price_items(args.items)
    if validation_issues:
        return {
            "status": "CUSTOMIZATION_INVALID",
            "message": "Some customizations need clarification.",
            "issues": validation_issues,
        }

    total_amount = round(sum(item["total_price"] for item in priced_items), 2)
    logger.info(
        "create_order invoked customer_contact=%s items=%s call_sid=%s active_order_id=%s",
        customer_contact,
        len(args.items),
        call_sid,
        order_session_state.get("active_order_id"),
    )

    def _upsert():
        # Create fresh repository instances for this operation
        user_repo = _get_user_repo()
        metadata_repo = _get_metadata_repo()
        order_repo = _get_order_repo()
        order_item_repo = _get_order_item_repo()

        # Ensure user exists/updated
        user_id = user_repo.create_or_update_user(
            {
                "name": args.customer_name,
                "phone_number": customer_contact,
                "email": None,
                "address": None,
                "is_spam": False,
                "credit_card": None,
            }
        )

        # Create user-business metadata mapping (for dashboard user visibility)
        if business_id:
            try:
                metadata_repo.create_mapping(
                    user_id=user_id,
                    business_id=business_id,
                    source="order",
                    notes="Created via voice agent order",
                )
            except Exception as meta_err:
                # Log but don't fail order creation if metadata mapping fails
                logger.warning("Failed to create user-business metadata call_sid=%s: %s", call_sid, meta_err)

        order_details = [item.model_dump() for item in args.items]
        customization_payload = args.metadata.get("customization", {})

        # Guardrail: if this call already has an active order, update it in-place
        # instead of creating a duplicate order record.
        active_order_id = _coerce_positive_int(order_session_state.get("active_order_id"))
        if active_order_id is not None:
            active_order = order_repo.get_order_by_id_with_verification(active_order_id, business_id, user_id)
            if active_order:
                previous_data = {
                    "status": active_order.get("status"),
                    "order_details": active_order.get("order_details"),
                    "customization": active_order.get("customization"),
                    "total_amount": active_order.get("total_amount"),
                }
                order_repo.update_order_details(active_order_id, order_details, customization_payload, total_amount)
                order_item_repo.delete_order_items_by_order(active_order_id)
                for item, pricing in zip(args.items, priced_items):
                    order_item_id = order_item_repo.create_order_item(
                        active_order_id,
                        {
                            "catalogue_item_id": _snapshot_catalogue_item_id(item.item_id),
                            "item_name_snapshot": item.name,
                            "base_price_snapshot": float(item.price or 0),
                            "quantity": item.quantity,
                            "instructions": item.instructions,
                            "final_unit_price_snapshot": pricing["final_unit_price"],
                            "option_total_snapshot": pricing["option_total"],
                            "total_price_snapshot": pricing["total_price"],
                        },
                    )
                    order_item_repo.create_order_item_options(order_item_id, pricing["option_snapshots"])
                updated_order = order_repo.get_order_by_id(active_order_id)
                return {
                    "mode": "updated",
                    "order_id": active_order_id,
                    "user_id": user_id,
                    "updated_order": updated_order,
                    "previous_data": previous_data,
                }

        order_payload = {
            "business_id": business_id,
            "status": "pending",
            "total_amount": total_amount,
            "order_details": order_details,
            "customization": customization_payload,
        }
        order_id = order_repo.create_order(user_id, order_payload)
        # Store detail rows for relational table
        for item in args.items:
            item_id = item.item_id
            if _has_catalogue_item_id(item_id):
                for _ in range(max(item.quantity, 1)):
                    order_repo.create_order_details(order_id, item_id)
        # Store order item snapshots and options
        for item, pricing in zip(args.items, priced_items):
            order_item_id = order_item_repo.create_order_item(
                order_id,
                {
                    "catalogue_item_id": _snapshot_catalogue_item_id(item.item_id),
                    "item_name_snapshot": item.name,
                    "base_price_snapshot": float(item.price or 0),
                    "quantity": item.quantity,
                    "instructions": item.instructions,
                    "final_unit_price_snapshot": pricing["final_unit_price"],
                    "option_total_snapshot": pricing["option_total"],
                    "total_price_snapshot": pricing["total_price"],
                },
            )
            order_item_repo.create_order_item_options(order_item_id, pricing["option_snapshots"])
        return {"mode": "created", "order_id": order_id, "user_id": user_id}

    upsert_result = await _run_service_call(_upsert)
    mode = upsert_result["mode"]
    order_id = upsert_result["order_id"]
    user_id = upsert_result["user_id"]
    order_session_state["active_order_id"] = order_id

    if mode == "updated":
        logger.warning(
            "create_order updated existing active order instead of creating a new one call_sid=%s order_id=%s",
            call_sid,
            order_id,
        )
        updated_order = upsert_result["updated_order"]
        previous_data = upsert_result["previous_data"]

        def _log_update_history():
            try:
                if business_id:
                    logger.debug(
                        "[DEBUG] Logging guarded create-as-update history: order_id=%s, business_id=%s",
                        order_id,
                        business_id,
                    )
                    history_service = _get_history_service()
                    new_data = {
                        "status": updated_order.get("status"),
                        "order_details": updated_order.get("order_details"),
                        "customization": updated_order.get("customization"),
                        "total_amount": updated_order.get("total_amount"),
                    }
                    if args.customer_name:
                        new_data["customer_name"] = args.customer_name
                    history_id = history_service.log_order_updated(
                        order_id=order_id,
                        business_id=int(business_id),
                        previous_data=previous_data or {},
                        new_data=new_data,
                        user_id=updated_order.get("user_id"),
                    )
                    logger.info("Activity history logged for guarded create update: history_id=%s", history_id)
            except Exception as history_error:
                logger.exception(
                    "[ERROR] Failed to log history for guarded create update call_sid=%s: %s",
                    call_sid,
                    history_error,
                )

        await _run_service_call(_log_update_history)
        if business_id:
            asyncio.create_task(
                _emit_order_sse_event(
                    business_id=int(business_id),
                    order_id=order_id,
                    subtype=OrderEventSubtype.ORDER_UPDATED,
                    data={
                        "order_id": order_id,
                        "status": updated_order.get("status"),
                        "total_amount": updated_order.get("total_amount"),
                    },
                )
            )
        return {
            "status": "UPDATED",
            "message": "Order updated",
            "order_id": order_id,
            "user_id": user_id,
            "business_id": business_id,
            "items": _summarize_items(args.items),
            "total_amount": total_amount,
            "order": updated_order,
        }

    # Log activity history for voice agent order creation (run in thread since it's a DB operation)
    def _log_create_history():
        try:
            if business_id:
                logger.debug(
                    "[DEBUG] Logging order creation history: order_id=%s, business_id=%s",
                    order_id,
                    business_id,
                )
                history_service = _get_history_service()
                history_id = history_service.log_order_created(
                    order_id=order_id,
                    business_id=business_id,
                    order_data={
                        "status": "pending",
                        "total_amount": total_amount,
                        "customer_name": args.customer_name,
                        "order_details": _summarize_items(args.items),
                    },
                    user_id=user_id,
                )
                logger.info("Activity history logged for order creation: history_id=%s", history_id)
            else:
                logger.warning(
                    "Cannot log history - business_id is None for order %s call_sid=%s", order_id, call_sid
                )
        except Exception as history_error:
            logger.exception(
                "[ERROR] Failed to log history for voice agent order creation call_sid=%s: %s",
                call_sid,
                history_error,
            )

    await _run_service_call(_log_create_history)

    # Emit SSE event for new order (background task)
    if business_id:
        asyncio.create_task(
            _emit_order_sse_event(
                business_id=business_id,
                order_id=order_id,
                subtype=OrderEventSubtype.NEW_ORDER,
                data={
                    "order_id": order_id,
                    "status": "pending",
                    "total_amount": total_amount,
                    "customer_name": args.customer_name,
                },
            )
        )

        # Send SMS notification for voice-created order (background task)
        if customer_contact:
            asyncio.create_task(
                _send_voice_order_sms(
                    business=business,
                    order_id=order_id,
                    customer_phone=customer_contact,
                )
            )

    return {
        "status": "CREATED",
        "message": "Order created",
        "order_id": order_id,
        "user_id": user_id,
        "business_id": business_id,
        "items": _summarize_items(args.items),
        "total_amount": total_amount,
    }


async def lookup_order(**kwargs) -> Dict[str, Any]:
    context, model_kwargs = split_call_context(kwargs, NoArgs)
    NoArgs.model_validate(model_kwargs)
    call_sid = context.get("call_sid")
    business_id = context_business_id(context)
    customer_contact = context_customer_contact(context)
    if business_id is None:
        return {"status": "FAILED", "message": "Missing business context."}
    if not customer_contact:
        return {"status": "FAILED", "message": "Missing caller contact context."}
    logger.info("lookup_order invoked customer_contact=%s call_sid=%s", customer_contact, call_sid)

    def _lookup():
        user_repo = _get_user_repo()
        order_repo = _get_order_repo()
        user_id = user_repo.get_user_id_by_phone_or_email(customer_contact, None)
        if not user_id:
            return None
        return order_repo.get_latest_order_by_user(user_id, business_id)

    order = await _run_service_call(_lookup)
    if not order:
        return {
            "status": "NOT_FOUND",
            "message": "Sorry, no order found for your phone number at this business.",
        }
    return {"status": "FOUND", "order": order}


async def lookup_order_by_id(**kwargs) -> Dict[str, Any]:
    """
    Look up a specific order by order ID, verifying it belongs to the caller and business.

    This function requires order_id argument and business/caller context defaults
    to match, ensuring no private data is leaked. The order will only be returned if:
    - The order_id exists
    - The order belongs to the context business_id
    - The order belongs to the user associated with context customer_contact (phone number)
    """
    context, model_kwargs = split_call_context(kwargs, LookupOrderByIdArgs)
    args = LookupOrderByIdArgs.model_validate(model_kwargs)
    call_sid = context.get("call_sid")
    business_id = context_business_id(context)
    customer_contact = context_customer_contact(context)
    if business_id is None:
        return {"status": "FAILED", "message": "Missing business context."}
    if not customer_contact:
        return {"status": "FAILED", "message": "Missing caller contact context."}
    logger.info(
        "lookup_order_by_id invoked order_id=%s customer_contact=%s business_id=%s call_sid=%s",
        args.order_id,
        customer_contact,
        business_id,
        call_sid,
    )

    def _lookup():
        user_repo = _get_user_repo()
        order_repo = _get_order_repo()

        # First, get user_id from phone number
        user_id = user_repo.get_user_id_by_phone_or_email(customer_contact, None)
        if not user_id:
            return None

        # Then verify order belongs to this user, business, and matches the order_id
        return order_repo.get_order_by_id_with_verification(args.order_id, business_id, user_id)

    order = await _run_service_call(_lookup)
    if not order:
        return {
            "status": "NOT_FOUND",
            "message": "Sorry, no order found with that ID for your phone number at this business.",
        }
    return {"status": "FOUND", "order": order}


def _flatten_menu_items(menus: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return menus


def _match_menu_item(menu_items: List[Dict[str, Any]], request_item: OrderItem) -> Optional[Dict[str, Any]]:
    """Match a requested item against menu items by ID or name."""
    for item in menu_items:
        # Match by item_id if provided
        if _has_catalogue_item_id(request_item.item_id) and item.get("id") == request_item.item_id:
            return item
        # Match by name (check both "item_name" and "name" fields)
        item_name = item.get("item_name") or item.get("name")
        if item_name and request_item.name:
            if str(item_name).lower() == str(request_item.name).lower():
                return item
    return None


async def check_items_availability(**kwargs) -> Dict[str, Any]:
    """
    Check availability of menu items.

    Returns only item availability buckets:
    - available_items
    - unavailable_items
    - unknown_items
    """
    context, model_kwargs = split_call_context(kwargs, CheckItemsAvailabilityArgs)
    args = CheckItemsAvailabilityArgs.model_validate(model_kwargs)
    call_sid = context.get("call_sid")
    business_id = context_business_id(context)
    if business_id is None:
        return {"status": "FAILED", "message": "Missing business context."}
    logger.info(
        "check_items_availability invoked business_id=%s item_count=%s call_sid=%s",
        business_id,
        len(args.items),
        call_sid,
    )
    business = await load_business(business_id)
    if not business:
        return {
            "status": "FAILED",
            "message": "Unable to load business information right now. Please try again shortly.",
        }
    if not is_business_open_now(business):
        return {
            "status": "CLOSED",
            "message": (
                "The business is currently closed. Please check back during operating hours "
                f"({format_operating_window(business)})."
            ),
        }
    menu_repo = _get_menu_repo()
    # Get ALL items (both available and unavailable) to properly check status
    all_menu_items = await _run_service_call(menu_repo.get_menus_by_business, business_id)
    all_menu_items = _flatten_menu_items(all_menu_items)
    available_items: List[Dict[str, Any]] = []
    unavailable_items: List[Dict[str, Any]] = []
    unknown_items: List[Dict[str, Any]] = []
    for requested in args.items:
        match = _match_menu_item(all_menu_items, requested)
        if match:
            # Normalize availability to boolean (handles MySQL TINYINT 0/1 and Python booleans)
            is_available_bool = _normalize_boolean(match.get("is_available"))
            item_ref = {"item_id": match.get("id"), "requested_item": requested.name}

            if is_available_bool:
                available_items.append(item_ref)
            else:
                unavailable_items.append(item_ref)
        else:
            unknown_items.append({"requested_item": requested.name})

    return {
        "business_id": business_id,
        "available_items": available_items,
        "unavailable_items": unavailable_items,
        "unknown_items": unknown_items,
    }


def _is_within_update_window(created_at: Any) -> bool:
    """
    Check if an order/reservation is within the allowed update window.

    Args:
        created_at: The created_at timestamp (datetime or string)

    Returns:
        True if the order/reservation can still be updated, False otherwise
    """
    if created_at is None:
        return False

    now = datetime.now(timezone.utc)
    update_window_seconds = settings.AGENT_UPDATE_WINDOW_SECONDS

    # Handle different formats of created_at
    created_at = coerce_datetime(created_at)
    if created_at is None:
        return False

    elapsed_seconds = (now - created_at).total_seconds()
    return elapsed_seconds <= update_window_seconds


async def update_order_details(**kwargs) -> Dict[str, Any]:
    context, model_kwargs = split_call_context(kwargs, UpdateOrderDetailsArgs)
    args = UpdateOrderDetailsArgs.model_validate(model_kwargs)
    call_sid = context.get("call_sid")
    business_id = context_business_id(context)
    customer_contact = context_customer_contact(context)
    order_session_state = context_order_session_state(context)
    active_order_id = _coerce_positive_int(order_session_state.get("active_order_id"))
    if business_id is None:
        return {"status": "FAILED", "message": "Missing business context."}
    if not customer_contact:
        return {"status": "FAILED", "message": "Missing caller contact context."}
    business = await load_business(business_id)
    if not business:
        return {
            "status": "FAILED",
            "message": "Unable to load business information right now. Please try again shortly.",
        }
    if not is_business_open_now(business):
        return {
            "status": "CLOSED",
            "message": (
                "The business is currently closed. Order updates are only available during operating hours "
                f"({format_operating_window(business)})."
            ),
        }
    await _populate_missing_prices(business_id, args.items)
    priced_items, validation_issues = await _validate_and_price_items(args.items)
    if validation_issues:
        return {
            "status": "CUSTOMIZATION_INVALID",
            "message": "Some customizations need clarification.",
            "issues": validation_issues,
        }

    logger.info(
        "update_order_details invoked customer_contact=%s call_sid=%s active_order_id=%s",
        customer_contact,
        call_sid,
        active_order_id,
    )

    def _update():
        user_repo = _get_user_repo()
        order_repo = _get_order_repo()
        order_item_repo = _get_order_item_repo()

        user_id = user_repo.get_user_id_by_phone_or_email(customer_contact, None)
        if not user_id:
            return None, None, None, None, None

        order = None
        if active_order_id is not None:
            order = order_repo.get_order_by_id_with_verification(active_order_id, business_id, user_id)
        if not order:
            order = order_repo.get_latest_order_by_user(user_id, business_id)
        if not order:
            return None, None, None, None, None
        order_id = order.get("id")
        if not order_id:
            return None, None, None, None, None

        # Check if order is within the allowed update window
        created_at = order.get("created_at")
        if not _is_within_update_window(created_at):
            return "UPDATE_WINDOW_EXPIRED", None, None, order, order_id

        # Update user's name if provided (consistent with create_order behavior)
        # Only update after validation to ensure it only executes when order update will succeed
        if args.customer_name:
            user_repo.create_or_update_user(
                {
                    "name": args.customer_name,
                    "phone_number": customer_contact,
                    "email": None,
                    "address": None,
                    "is_spam": False,
                    "credit_card": None,
                }
            )

        # Capture previous state for activity history
        previous_data = {
            "status": order.get("status"),
            "order_details": order.get("order_details"),
            "customization": order.get("customization"),
            "total_amount": order.get("total_amount"),
        }

        order_details = [item.model_dump() for item in args.items]
        total_amount = round(sum(item["total_price"] for item in priced_items), 2)
        order_repo.update_order_details(order_id, order_details, args.customization, total_amount)
        order_item_repo.delete_order_items_by_order(order_id)
        for item, pricing in zip(args.items, priced_items):
            order_item_id = order_item_repo.create_order_item(
                order_id,
                {
                    "catalogue_item_id": _snapshot_catalogue_item_id(item.item_id),
                    "item_name_snapshot": item.name,
                    "base_price_snapshot": float(item.price or 0),
                    "quantity": item.quantity,
                    "instructions": item.instructions,
                    "final_unit_price_snapshot": pricing["final_unit_price"],
                    "option_total_snapshot": pricing["option_total"],
                    "total_price_snapshot": pricing["total_price"],
                },
            )
            order_item_repo.create_order_item_options(order_item_id, pricing["option_snapshots"])

        # Update status if provided (e.g., cancellation within update window)
        if args.status:
            order_repo.update_order_status(order_id, args.status)

        updated = order_repo.get_order_by_id(order_id)

        return updated, previous_data, order.get("business_id"), order, order_id

    result, previous_data, business_id, original_order, resolved_order_id = await _run_service_call(_update)
    business_id = business_id or context_business_id(context)

    # Handle update window expired
    if result == "UPDATE_WINDOW_EXPIRED":
        window_minutes = settings.AGENT_UPDATE_WINDOW_SECONDS // 60
        return {
            "status": "UPDATE_WINDOW_EXPIRED",
            "message": (
                f"This order was placed more than {window_minutes} minutes ago "
                "and can no longer be modified. Please contact the business directly "
                "for any changes."
            ),
        }

    if not result:
        return {
            "status": "NOT_FOUND",
            "message": "Sorry, no order found for your phone number at this business.",
        }

    updated_order = result
    if resolved_order_id:
        order_session_state["active_order_id"] = resolved_order_id

    # Log activity history for voice agent order update (run in thread since it's a DB operation)
    def _log_history():
        try:
            if business_id:
                logger.debug(
                    "[DEBUG] Logging order update history: order_id=%s, business_id=%s",
                    updated_order.get("id"),
                    business_id,
                )
                history_service = _get_history_service()
                new_data = {
                    "status": updated_order.get("status"),
                    "order_details": updated_order.get("order_details"),
                    "customization": updated_order.get("customization"),
                    "total_amount": updated_order.get("total_amount"),
                }
                # Include customer_name if it was updated
                if args.customer_name:
                    new_data["customer_name"] = args.customer_name
                history_id = history_service.log_order_updated(
                    order_id=updated_order.get("id"),
                    business_id=int(business_id),
                    previous_data=previous_data or {},
                    new_data=new_data,
                    user_id=updated_order.get("user_id"),
                )
                logger.info("Activity history logged for order update: history_id=%s", history_id)
            else:
                logger.warning(
                    "Cannot log history - business_id is None for order %s call_sid=%s",
                    updated_order.get("id"),
                    call_sid,
                )
        except Exception as history_error:
            logger.exception(
                "[ERROR] Failed to log history for voice agent order update call_sid=%s: %s",
                call_sid,
                history_error,
            )

    await _run_service_call(_log_history)

    # Emit SSE event for order update (background task)
    if business_id:
        new_status = updated_order.get("status", "")
        event_subtype = (
            OrderEventSubtype.ORDER_CANCELLED if new_status.lower() == "cancelled" else OrderEventSubtype.ORDER_UPDATED
        )
        asyncio.create_task(
            _emit_order_sse_event(
                business_id=int(business_id),
                order_id=updated_order.get("id"),
                subtype=event_subtype,
                data={
                    "order_id": updated_order.get("id"),
                    "status": new_status,
                    "total_amount": updated_order.get("total_amount"),
                },
            )
        )

    return {"status": "UPDATED", "order": updated_order}
