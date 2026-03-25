"""Order-related function implementations wired to application services."""

from __future__ import annotations

import asyncio
import inspect
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.agent_fc.functions.common_restaurant import load_restaurant
from app.agent_fc.functions.function_context import (
    NoArgs,
    context_customer_contact,
    context_order_session_state,
    context_restaurant_id,
    split_call_context,
)
from app.agent_fc.responses import AgentFunctionResult, AgentSideEffect
from app.config import settings
from app.models.order_models import OrderItemOptionGroupSelection
from app.repositories.mysql_menu_repo import MySQLMenuRepository
from app.repositories.mysql_order_item_repo import MySQLOrderItemRepository
from app.repositories.mysql_order_repo import MySQLOrderRepository
from app.repositories.mysql_user_repo import MySQLUserRepository
from app.repositories.mysql_user_restaurant_metadata_repo import (
    MySQLUserRestaurantMetadataRepository,
)
from app.services.activity_history_service import ActivityHistoryService
from app.services.call_service import CallService
from app.services.escalation_service import EscalationService
from app.services.notification_service import NotificationService
from app.services.order_customization_service import OrderCustomizationService
from app.services.pos_service import POSService
from app.services.sse_service import OrderEventSubtype, SSEService
from app.utils.restaurant_hours import format_operating_window, is_restaurant_open_now
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


def _get_menu_repo() -> MySQLMenuRepository:
    """Create fresh menu repository instance per function call."""
    return MySQLMenuRepository()


def _get_order_item_repo() -> MySQLOrderItemRepository:
    """Create fresh order item repository instance per function call."""
    return MySQLOrderItemRepository()


def _get_metadata_repo() -> MySQLUserRestaurantMetadataRepository:
    """Create fresh metadata repository instance per function call."""
    return MySQLUserRestaurantMetadataRepository()


def _get_history_service() -> ActivityHistoryService:
    """Create fresh history service instance per function call."""
    return ActivityHistoryService()


def _get_pos_service() -> POSService:
    """Create fresh POS service instance per function call."""
    return POSService()


def _get_sse_service() -> SSEService:
    """Create fresh SSE service instance per function call."""
    return SSEService()


def _get_customization_service() -> OrderCustomizationService:
    """Create fresh customization service per function call."""
    return OrderCustomizationService()


async def _emit_order_sse_event(
    restaurant_id: int,
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
            restaurant_id=restaurant_id,
            order_id=order_id,
            subtype=subtype,
            data=data,
        )
    except Exception as sse_error:
        logger.error("[SSE] Order event emission failed for order %s (%s): %s", order_id, subtype.value, sse_error)

    try:
        from app.services.notification_persistence_service import NotificationPersistenceService

        notification_service = NotificationPersistenceService()
        notification_service.create_notification(
            restaurant_id=restaurant_id,
            type="order",
            subtype=subtype.value if hasattr(subtype, "value") else subtype,
            data={"order_id": order_id, **(data or {})},
            entity_id=order_id,
        )
    except Exception as e:
        logger.error("[Notification] Order notification persistence failed for order %s: %s", order_id, e)


async def _send_voice_order_sms(
    restaurant: Dict[str, Any],
    order_id: int,
    customer_phone: str,
) -> None:
    """Send SMS notification for voice-agent-created order.

    This is a fire-and-forget background task - SMS failures should not
    affect the voice call or order creation.
    """
    import json

    try:
        twilio_number = (restaurant.get("twilio_phone_number") or "").strip()
        if not twilio_number:
            logger.debug("No Twilio number configured for restaurant %s", restaurant.get("id"))
            return

        twilio_details = restaurant.get("twilio_details") or {}
        if isinstance(twilio_details, str):
            try:
                twilio_details = json.loads(twilio_details) if twilio_details else {}
            except json.JSONDecodeError as e:
                logger.warning(
                    "Invalid JSON in twilio_details for restaurant %s: %s",
                    restaurant.get("id"),
                    e,
                )
                twilio_details = {}
            except Exception as e:
                logger.warning(
                    "Unexpected error parsing twilio_details for restaurant %s: %s",
                    restaurant.get("id"),
                    e,
                )
                twilio_details = {}

        sid = twilio_details.get("account_sid") or twilio_details.get("TWILIO_ACCOUNT_SID")
        token = twilio_details.get("auth_token") or twilio_details.get("TWILIO_AUTH_TOKEN")

        notification_service = NotificationService()
        await notification_service.send_order_notification(
            restaurant_id=restaurant.get("id"),
            order_id=order_id,
            new_status="pending",  # Voice-created orders start as pending
            recipient_phone=customer_phone,
            restaurant_name=restaurant.get("name") or "",
            restaurant_twilio_number=twilio_number,
            twilio_account_sid=sid,
            twilio_auth_token=token,
        )
        logger.info("SMS sent for voice order %s", order_id)
    except Exception as e:
        # Don't fail the voice call if SMS fails - just log
        logger.warning("Failed to send SMS for voice order %s: %s", order_id, e)


async def _emit_pos_failure_escalation_event(
    *,
    restaurant_id: int,
    call_id: Optional[int],
    caller_phone: Optional[str],
    error_message: str,
    order_id: int,
    escalation_id: Optional[int],
) -> None:
    try:
        sse_service = _get_sse_service()
        await sse_service.emit_escalation_server_error(
            restaurant_id=restaurant_id,
            call_id=str(call_id) if call_id is not None else None,
            error_message=error_message,
            error_code="POS_ORDER_CONFIRMATION_FAILED",
            data={
                "caller_phone": caller_phone,
                "order_id": order_id,
                "escalation_id": escalation_id,
            },
        )
    except Exception as exc:  # noqa: BLE001 - defensive
        logger.warning("Failed to emit POS failure escalation SSE event order_id=%s: %s", order_id, exc)

    try:
        from app.services.notification_persistence_service import NotificationPersistenceService

        NotificationPersistenceService().create_notification(
            restaurant_id=restaurant_id,
            type="escalation",
            subtype="internal_server_error",
            data={
                "caller_phone": caller_phone,
                "order_id": order_id,
                "error_message": error_message,
                "escalation_id": escalation_id,
            },
            entity_id=escalation_id or order_id,
        )
    except Exception as exc:  # noqa: BLE001 - defensive
        logger.warning("Failed to persist POS failure escalation notification order_id=%s: %s", order_id, exc)


def _should_forward_escalation(restaurant: Optional[Dict[str, Any]]) -> tuple[bool, Optional[str]]:
    if not restaurant:
        return False, None

    escalation_phone_number = restaurant.get("escalation_phone_number")
    if not (_normalize_boolean(restaurant.get("forward_escalations")) and escalation_phone_number):
        return False, escalation_phone_number

    escalation_mode = str(restaurant.get("escalation_mode") or "always").strip().lower()
    if escalation_mode == "open_hours_only" and not is_restaurant_open_now(restaurant):
        return False, escalation_phone_number

    return True, escalation_phone_number


async def _handle_voice_pos_failure(
    *,
    order_id: int,
    user_id: int,
    restaurant_id: int,
    restaurant: Dict[str, Any],
    customer_contact: str,
    call_sid: Optional[str],
    call_id: Optional[int],
    pos_result: Dict[str, Any],
) -> Dict[str, Any] | AgentFunctionResult:
    error_message = (
        str(pos_result.get("error") or "").strip() or "The restaurant system could not confirm the order right now."
    )

    def _soft_delete_order() -> None:
        _get_order_repo().soft_delete_order(order_id)

    await _run_service_call(_soft_delete_order)

    should_forward, escalation_phone_number = _should_forward_escalation(restaurant)
    escalation_id: Optional[int] = None

    def _create_escalation() -> Optional[int]:
        return EscalationService().create_escalation(
            {
                "call_id": call_id,
                "user_id": user_id,
                "restaurant_id": str(restaurant_id),
                "twilio_call_sid": call_sid,
                "caller_phone": customer_contact,
                "escalation_phone_number": escalation_phone_number,
                "urgency": "high",
                "reason": f"POS order confirmation failed after retry: {error_message}",
                "status": "raised",
            }
        )

    try:
        created_escalation_id = await _run_service_call(_create_escalation)
        escalation_id = int(created_escalation_id) if created_escalation_id is not None else None
    except Exception as exc:  # noqa: BLE001 - defensive
        logger.warning("Failed to create POS failure escalation call_sid=%s order_id=%s: %s", call_sid, order_id, exc)

    if call_id:
        try:
            await _run_service_call(CallService().mark_escalated, call_id)
        except Exception as exc:  # noqa: BLE001 - defensive
            logger.warning("Failed to mark call escalated call_id=%s call_sid=%s: %s", call_id, call_sid, exc)

    asyncio.create_task(
        _emit_pos_failure_escalation_event(
            restaurant_id=restaurant_id,
            call_id=call_id,
            caller_phone=customer_contact,
            error_message=error_message,
            order_id=order_id,
            escalation_id=escalation_id,
        )
    )

    content = {
        "status": "FAILED",
        "message": "I couldn't complete the order with the restaurant system right now.",
        "order_id": order_id,
        "user_id": user_id,
        "restaurant_id": restaurant_id,
        "forwarding": should_forward,
        "escalated": True,
        "error": error_message,
    }
    if should_forward:
        content["instruction"] = "Already spoken via injected message. Do NOT repeat or rephrase it."
        return AgentFunctionResult(
            content=content,
            side_effects=[
                AgentSideEffect(
                    {
                        "type": "InjectAgentMessage",
                        "message": (
                            "I'm sorry, I couldn't confirm your order with the restaurant system right now, "
                            "so I'll connect you to the restaurant directly."
                        ),
                    }
                ),
                AgentSideEffect({"type": "close"}, delay_seconds=0.5),
            ],
        )

    return content


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


def _has_menu_item_id(item_id: Optional[int]) -> bool:
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


def _snapshot_menu_item_id(item_id: Optional[int]) -> Optional[int]:
    if not _has_menu_item_id(item_id):
        return None
    return int(item_id)


async def _validate_and_price_items(
    items: List[OrderItem],
) -> Tuple[List[Dict[str, Any]], Optional[List[Dict[str, Any]]]]:
    """
    Validate customization selections and compute pricing snapshots.
    """
    customization_service = _get_customization_service()
    menu_repo = _get_menu_repo()
    priced_items: List[Dict[str, Any]] = []
    issues: List[Dict[str, Any]] = []
    menu_item_ids = sorted({int(item.item_id) for item in items if _has_menu_item_id(item.item_id)})
    menu_items_by_id: Dict[int, Dict[str, Any]] = {}
    if menu_item_ids:
        menu_items_by_id = await _run_service_call(menu_repo.get_by_ids, menu_item_ids)

    for item in items:
        base_price = float(item.price or 0)
        if not _has_menu_item_id(item.item_id):
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

        menu_item = menu_items_by_id.get(int(item.item_id))
        if not menu_item:
            issues.append(
                {
                    "item_id": item.item_id,
                    "item_name": item.name,
                    "issues": [
                        {
                            "issue_code": "INVALID_ITEM",
                            "message": "This item is no longer available.",
                        }
                    ],
                }
            )
            continue

        if not _normalize_boolean(menu_item.get("is_active")) or not _normalize_boolean(menu_item.get("is_available")):
            issues.append(
                {
                    "item_id": item.item_id,
                    "item_name": item.name,
                    "issues": [
                        {
                            "issue_code": "UNAVAILABLE_ITEM",
                            "message": "This item is currently unavailable.",
                        }
                    ],
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


async def _populate_missing_prices(restaurant_id: int, items: List[OrderItem]) -> None:
    """Fill in missing item prices by looking up the restaurant menu."""
    missing_prices = [item for item in items if item.price is None]
    if not missing_prices:
        return

    try:
        menu_repo = _get_menu_repo()
        menu_items = await _run_service_call(menu_repo.get_available_items_by_restaurant, restaurant_id)
    except Exception as exc:  # noqa: BLE001 - defensive for agent calls
        logger.warning("Unable to fetch menu for price lookup restaurant_id=%s: %s", restaurant_id, exc)
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
    call_id = _coerce_positive_int(context.get("call_id"))
    restaurant_id = context_restaurant_id(context)
    customer_contact = context_customer_contact(context)
    order_session_state = context_order_session_state(context)
    if restaurant_id is None:
        return {"status": "FAILED", "message": "Missing restaurant context."}
    if not customer_contact:
        return {"status": "FAILED", "message": "Missing caller contact context."}
    restaurant = await load_restaurant(restaurant_id)
    if not restaurant:
        return {
            "status": "FAILED",
            "message": "Unable to load restaurant information right now. Please try again shortly.",
        }
    if not is_restaurant_open_now(restaurant):
        return {
            "status": "CLOSED",
            "message": (
                "The restaurant is currently closed. Please place your order during operating hours "
                f"({format_operating_window(restaurant)})."
            ),
        }
    await _populate_missing_prices(restaurant_id, args.items)
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
        pos_service = _get_pos_service()

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

        # Create user-restaurant metadata mapping (for dashboard user visibility)
        if restaurant_id:
            try:
                metadata_repo.create_mapping(
                    user_id=user_id,
                    restaurant_id=restaurant_id,
                    source="order",
                    notes="Created via voice agent order",
                )
            except Exception as meta_err:
                # Log but don't fail order creation if metadata mapping fails
                logger.warning("Failed to create user-restaurant metadata call_sid=%s: %s", call_sid, meta_err)

        order_details = [item.model_dump() for item in args.items]
        customization_payload = args.metadata.get("customization", {})
        enriched_priced_items = pos_service.attach_external_snapshot_ids(restaurant_id, priced_items)

        # Guardrail: if this call already has an active order, update it in-place
        # instead of creating a duplicate order record.
        active_order_id = _coerce_positive_int(order_session_state.get("active_order_id"))
        if active_order_id is not None:
            active_order = order_repo.get_order_by_id_with_verification(active_order_id, restaurant_id, user_id)
            if active_order:
                previous_pos_state = pos_service.capture_order_state(active_order_id)
                previous_data = {
                    "status": active_order.get("status"),
                    "order_details": active_order.get("order_details"),
                    "customization": active_order.get("customization"),
                    "total_amount": active_order.get("total_amount"),
                }
                order_repo.update_order_details(active_order_id, order_details, customization_payload, total_amount)
                order_item_repo.delete_order_items_by_order(active_order_id)
                for item, pricing in zip(args.items, enriched_priced_items):
                    order_item_id = order_item_repo.create_order_item(
                        active_order_id,
                        {
                            "menu_item_id": _snapshot_menu_item_id(item.item_id),
                            "external_item_id_snapshot": pricing.get("external_item_id_snapshot"),
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
                    "previous_pos_state": previous_pos_state,
                }

        order_payload = {
            "restaurant_id": restaurant_id,
            "status": "pending",
            "total_amount": total_amount,
            "order_details": order_details,
            "customization": customization_payload,
        }
        order_id = order_repo.create_order(user_id, order_payload)
        # Store detail rows for relational table
        for item in args.items:
            item_id = item.item_id
            if _has_menu_item_id(item_id):
                for _ in range(max(item.quantity, 1)):
                    order_repo.create_order_details(order_id, item_id)
        # Store order item snapshots and options
        for item, pricing in zip(args.items, enriched_priced_items):
            order_item_id = order_item_repo.create_order_item(
                order_id,
                {
                    "menu_item_id": _snapshot_menu_item_id(item.item_id),
                    "external_item_id_snapshot": pricing.get("external_item_id_snapshot"),
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

    if mode == "updated":
        order_session_state["active_order_id"] = order_id
        logger.warning(
            "create_order updated existing active order instead of creating a new one call_sid=%s order_id=%s",
            call_sid,
            order_id,
        )
        updated_order = upsert_result["updated_order"]
        previous_data = upsert_result["previous_data"]
        previous_pos_state = upsert_result.get("previous_pos_state")

        pos_result = {"required": False, "success": True, "status": "SKIPPED", "retry_scheduled": False}
        if restaurant_id and previous_pos_state:

            def _replace_pos_after_guarded_update():
                pos_service = _get_pos_service()
                if not pos_service.has_confirmed_sync(order_id):
                    return {
                        "required": False,
                        "success": True,
                        "status": "SKIPPED",
                        "retry_scheduled": False,
                    }
                return pos_service.replace_order_after_internal_update(
                    order_id,
                    int(restaurant_id),
                    previous_state=previous_pos_state,
                    reason="Voice caller updated an active order",
                )

            pos_result = await _run_service_call(_replace_pos_after_guarded_update)
            if pos_result.get("required") and not pos_result.get("success"):
                return {
                    "status": "FAILED",
                    "message": "I couldn't confirm the updated order with the restaurant system right now.",
                    "order_id": order_id,
                    "user_id": user_id,
                    "restaurant_id": restaurant_id,
                }

        def _log_update_history():
            try:
                if restaurant_id:
                    logger.debug(
                        "[DEBUG] Logging guarded create-as-update history: order_id=%s, restaurant_id=%s",
                        order_id,
                        restaurant_id,
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
                        restaurant_id=int(restaurant_id),
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
        if restaurant_id:
            asyncio.create_task(
                _emit_order_sse_event(
                    restaurant_id=int(restaurant_id),
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
            "restaurant_id": restaurant_id,
            "items": _summarize_items(args.items),
            "total_amount": total_amount,
            "order": updated_order,
        }

    pos_result = {"required": False, "success": True, "status": "SKIPPED", "retry_scheduled": False}
    if restaurant_id:

        def _submit_pos():
            logger.info("Submitting order %s to POS before returning create_order response", order_id)
            pos_service = _get_pos_service()
            return pos_service.submit_order_to_pos(
                order_id,
                int(restaurant_id),
                schedule_retry_on_failure=False,
                immediate_retry_attempts=1,
            )

        pos_result = await _run_service_call(_submit_pos)
        if pos_result.get("required") and not pos_result.get("success"):
            logger.warning(
                "create_order POS submission failed call_sid=%s order_id=%s status=%s retryable=%s",
                call_sid,
                order_id,
                pos_result.get("status"),
                pos_result.get("retryable"),
            )
            return await _handle_voice_pos_failure(
                order_id=order_id,
                user_id=user_id,
                restaurant_id=int(restaurant_id),
                restaurant=restaurant,
                customer_contact=customer_contact,
                call_sid=call_sid,
                call_id=call_id,
                pos_result=pos_result,
            )

    # Log activity history for voice agent order creation (run in thread since it's a DB operation)
    def _log_create_history():
        try:
            if restaurant_id:
                logger.debug(
                    "[DEBUG] Logging order creation history: order_id=%s, restaurant_id=%s",
                    order_id,
                    restaurant_id,
                )
                history_service = _get_history_service()
                history_id = history_service.log_order_created(
                    order_id=order_id,
                    restaurant_id=restaurant_id,
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
                    "Cannot log history - restaurant_id is None for order %s call_sid=%s", order_id, call_sid
                )
        except Exception as history_error:
            logger.exception(
                "[ERROR] Failed to log history for voice agent order creation call_sid=%s: %s",
                call_sid,
                history_error,
            )

    await _run_service_call(_log_create_history)
    order_session_state["active_order_id"] = order_id

    if restaurant_id:
        asyncio.create_task(
            _emit_order_sse_event(
                restaurant_id=restaurant_id,
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

        if customer_contact:
            asyncio.create_task(
                _send_voice_order_sms(
                    restaurant=restaurant,
                    order_id=order_id,
                    customer_phone=customer_contact,
                )
            )

    return {
        "status": "CONFIRMED" if pos_result.get("required") else "CREATED",
        "message": "Order confirmed" if pos_result.get("required") else "Order created",
        "order_id": order_id,
        "user_id": user_id,
        "restaurant_id": restaurant_id,
        "items": _summarize_items(args.items),
        "total_amount": total_amount,
    }


async def lookup_order(**kwargs) -> Dict[str, Any]:
    context, model_kwargs = split_call_context(kwargs, NoArgs)
    NoArgs.model_validate(model_kwargs)
    call_sid = context.get("call_sid")
    restaurant_id = context_restaurant_id(context)
    customer_contact = context_customer_contact(context)
    if restaurant_id is None:
        return {"status": "FAILED", "message": "Missing restaurant context."}
    if not customer_contact:
        return {"status": "FAILED", "message": "Missing caller contact context."}
    logger.info("lookup_order invoked customer_contact=%s call_sid=%s", customer_contact, call_sid)

    def _lookup():
        user_repo = _get_user_repo()
        order_repo = _get_order_repo()
        user_id = user_repo.get_user_id_by_phone_or_email(customer_contact, None)
        if not user_id:
            return None
        return order_repo.get_latest_order_by_user(user_id, restaurant_id)

    order = await _run_service_call(_lookup)
    if not order:
        return {
            "status": "NOT_FOUND",
            "message": "Sorry, no order found for your phone number at this restaurant.",
        }
    return {"status": "FOUND", "order": order}


async def lookup_order_by_id(**kwargs) -> Dict[str, Any]:
    """
    Look up a specific order by order ID, verifying it belongs to the caller and restaurant.

    This function requires order_id argument and restaurant/caller context defaults
    to match, ensuring no private data is leaked. The order will only be returned if:
    - The order_id exists
    - The order belongs to the context restaurant_id
    - The order belongs to the user associated with context customer_contact (phone number)
    """
    context, model_kwargs = split_call_context(kwargs, LookupOrderByIdArgs)
    args = LookupOrderByIdArgs.model_validate(model_kwargs)
    call_sid = context.get("call_sid")
    restaurant_id = context_restaurant_id(context)
    customer_contact = context_customer_contact(context)
    if restaurant_id is None:
        return {"status": "FAILED", "message": "Missing restaurant context."}
    if not customer_contact:
        return {"status": "FAILED", "message": "Missing caller contact context."}
    logger.info(
        "lookup_order_by_id invoked order_id=%s customer_contact=%s restaurant_id=%s call_sid=%s",
        args.order_id,
        customer_contact,
        restaurant_id,
        call_sid,
    )

    def _lookup():
        user_repo = _get_user_repo()
        order_repo = _get_order_repo()

        # First, get user_id from phone number
        user_id = user_repo.get_user_id_by_phone_or_email(customer_contact, None)
        if not user_id:
            return None

        # Then verify order belongs to this user, restaurant, and matches the order_id
        return order_repo.get_order_by_id_with_verification(args.order_id, restaurant_id, user_id)

    order = await _run_service_call(_lookup)
    if not order:
        return {
            "status": "NOT_FOUND",
            "message": "Sorry, no order found with that ID for your phone number at this restaurant.",
        }
    return {"status": "FOUND", "order": order}


def _flatten_menu_items(menus: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return menus


def _match_menu_item(menu_items: List[Dict[str, Any]], request_item: OrderItem) -> Optional[Dict[str, Any]]:
    """Match a requested item against menu items by ID or name."""
    for item in menu_items:
        # Match by item_id if provided
        if _has_menu_item_id(request_item.item_id) and item.get("id") == request_item.item_id:
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
    restaurant_id = context_restaurant_id(context)
    if restaurant_id is None:
        return {"status": "FAILED", "message": "Missing restaurant context."}
    logger.info(
        "check_items_availability invoked restaurant_id=%s item_count=%s call_sid=%s",
        restaurant_id,
        len(args.items),
        call_sid,
    )
    restaurant = await load_restaurant(restaurant_id)
    if not restaurant:
        return {
            "status": "FAILED",
            "message": "Unable to load restaurant information right now. Please try again shortly.",
        }
    if not is_restaurant_open_now(restaurant):
        return {
            "status": "CLOSED",
            "message": (
                "The restaurant is currently closed. Please check back during operating hours "
                f"({format_operating_window(restaurant)})."
            ),
        }
    menu_repo = _get_menu_repo()
    # Get all active items, then split matches by current availability.
    all_menu_items = await _run_service_call(menu_repo.get_menus_by_restaurant, restaurant_id, True)
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
        "restaurant_id": restaurant_id,
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
    restaurant_id = context_restaurant_id(context)
    customer_contact = context_customer_contact(context)
    order_session_state = context_order_session_state(context)
    active_order_id = _coerce_positive_int(order_session_state.get("active_order_id"))
    if restaurant_id is None:
        return {"status": "FAILED", "message": "Missing restaurant context."}
    if not customer_contact:
        return {"status": "FAILED", "message": "Missing caller contact context."}
    restaurant = await load_restaurant(restaurant_id)
    if not restaurant:
        return {
            "status": "FAILED",
            "message": "Unable to load restaurant information right now. Please try again shortly.",
        }
    if not is_restaurant_open_now(restaurant):
        return {
            "status": "CLOSED",
            "message": (
                "The restaurant is currently closed. Order updates are only available during operating hours "
                f"({format_operating_window(restaurant)})."
            ),
        }
    await _populate_missing_prices(restaurant_id, args.items)
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
        pos_service = _get_pos_service()

        user_id = user_repo.get_user_id_by_phone_or_email(customer_contact, None)
        if not user_id:
            return None, None, None, None, None, None

        order = None
        if active_order_id is not None:
            order = order_repo.get_order_by_id_with_verification(active_order_id, restaurant_id, user_id)
        if not order:
            order = order_repo.get_latest_order_by_user(user_id, restaurant_id)
        if not order:
            return None, None, None, None, None, None
        order_id = order.get("id")
        if not order_id:
            return None, None, None, None, None, None

        # Check if order is within the allowed update window
        created_at = order.get("created_at")
        if not _is_within_update_window(created_at):
            return "UPDATE_WINDOW_EXPIRED", None, None, order, order_id, None

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
        previous_pos_state = pos_service.capture_order_state(order_id)

        order_details = [item.model_dump() for item in args.items]
        total_amount = round(sum(item["total_price"] for item in priced_items), 2)
        enriched_priced_items = pos_service.attach_external_snapshot_ids(restaurant_id, priced_items)
        order_repo.update_order_details(order_id, order_details, args.customization, total_amount)
        order_item_repo.delete_order_items_by_order(order_id)
        for item, pricing in zip(args.items, enriched_priced_items):
            order_item_id = order_item_repo.create_order_item(
                order_id,
                {
                    "menu_item_id": _snapshot_menu_item_id(item.item_id),
                    "external_item_id_snapshot": pricing.get("external_item_id_snapshot"),
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

        return updated, previous_data, order.get("restaurant_id"), order, order_id, previous_pos_state

    result, previous_data, restaurant_id, original_order, resolved_order_id, previous_pos_state = (
        await _run_service_call(_update)
    )
    restaurant_id = restaurant_id or context_restaurant_id(context)

    # Handle update window expired
    if result == "UPDATE_WINDOW_EXPIRED":
        window_minutes = settings.AGENT_UPDATE_WINDOW_SECONDS // 60
        return {
            "status": "UPDATE_WINDOW_EXPIRED",
            "message": (
                f"This order was placed more than {window_minutes} minutes ago "
                "and can no longer be modified. Please contact the restaurant directly "
                "for any changes."
            ),
        }

    if not result:
        return {
            "status": "NOT_FOUND",
            "message": "Sorry, no order found for your phone number at this restaurant.",
        }

    updated_order = result
    if resolved_order_id:
        order_session_state["active_order_id"] = resolved_order_id

    pos_result = {"required": False, "success": True, "status": "SKIPPED", "retry_scheduled": False}
    if restaurant_id and resolved_order_id and previous_pos_state:

        def _sync_updated_order_to_pos():
            pos_service = _get_pos_service()
            if not pos_service.has_confirmed_sync(resolved_order_id):
                return {
                    "required": False,
                    "success": True,
                    "status": "SKIPPED",
                    "retry_scheduled": False,
                }
            if (args.status or "").strip().lower() == "cancelled":
                pos_result_inner = pos_service.cancel_order_in_pos(
                    resolved_order_id,
                    int(restaurant_id),
                    reason="Voice caller cancelled order",
                )
                if not pos_result_inner.get("success"):
                    pos_service.restore_order_state(resolved_order_id, previous_pos_state)
                return pos_result_inner
            return pos_service.replace_order_after_internal_update(
                resolved_order_id,
                int(restaurant_id),
                previous_state=previous_pos_state,
                reason="Voice caller updated order",
            )

        pos_result = await _run_service_call(_sync_updated_order_to_pos)
        if pos_result.get("required") and not pos_result.get("success"):
            failed_status = "FAILED"
            return {
                "status": failed_status,
                "message": (
                    "I couldn't confirm the order cancellation with the restaurant system right now."
                    if (args.status or "").strip().lower() == "cancelled"
                    else "I couldn't confirm the updated order with the restaurant system right now."
                ),
                "order_id": resolved_order_id,
                "restaurant_id": restaurant_id,
            }

    # Log activity history for voice agent order update (run in thread since it's a DB operation)
    def _log_history():
        try:
            if restaurant_id:
                logger.debug(
                    "[DEBUG] Logging order update history: order_id=%s, restaurant_id=%s",
                    updated_order.get("id"),
                    restaurant_id,
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
                    restaurant_id=int(restaurant_id),
                    previous_data=previous_data or {},
                    new_data=new_data,
                    user_id=updated_order.get("user_id"),
                )
                logger.info("Activity history logged for order update: history_id=%s", history_id)
            else:
                logger.warning(
                    "Cannot log history - restaurant_id is None for order %s call_sid=%s",
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
    if restaurant_id:
        new_status = updated_order.get("status", "")
        event_subtype = (
            OrderEventSubtype.ORDER_CANCELLED if new_status.lower() == "cancelled" else OrderEventSubtype.ORDER_UPDATED
        )
        asyncio.create_task(
            _emit_order_sse_event(
                restaurant_id=int(restaurant_id),
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
