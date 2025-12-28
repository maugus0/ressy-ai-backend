"""Order-related function implementations wired to application services."""

from __future__ import annotations

import asyncio
import inspect
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.config import settings
from app.repositories.mysql_menu_repo import MySQLMenuRepository
from app.repositories.mysql_order_repo import MySQLOrderRepository
from app.repositories.mysql_user_repo import MySQLUserRepository
from app.repositories.mysql_user_restaurant_metadata_repo import (
    MySQLUserRestaurantMetadataRepository,
)
from app.services.activity_history_service import ActivityHistoryService
from app.services.sse_service import OrderEventSubtype, SSEService

logger = logging.getLogger(__name__)


class OrderItem(BaseModel):
    model_config = ConfigDict(extra="allow")

    item_id: int
    name: str
    quantity: int = 1
    price: Optional[float] = None
    instructions: Optional[str] = None
    options: Dict[str, Any] = Field(default_factory=dict)


class CreateOrderArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    restaurant_id: int
    customer_name: Optional[str] = None
    customer_contact: str
    pickup_time_iso: Optional[str] = None
    items: List[OrderItem]
    notes: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class LookupOrderArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    customer_contact: str
    restaurant_id: int


class CheckItemsAvailabilityArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    restaurant_id: int
    items: List[OrderItem]
    location: Optional[str] = None


class UpdateOrderDetailsArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    customer_contact: str
    restaurant_id: int
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


def _get_metadata_repo() -> MySQLUserRestaurantMetadataRepository:
    """Create fresh metadata repository instance per function call."""
    return MySQLUserRestaurantMetadataRepository()


def _get_history_service() -> ActivityHistoryService:
    """Create fresh history service instance per function call."""
    return ActivityHistoryService()


def _get_sse_service() -> SSEService:
    """Create fresh SSE service instance per function call."""
    return SSEService()


async def _emit_order_sse_event(
    restaurant_id: int,
    order_id: int,
    subtype: OrderEventSubtype,
    data: Dict[str, Any],
) -> None:
    """
    Background task to emit SSE order events.
    Logs errors but does not raise exceptions to avoid affecting other operations.
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
        logger.error(f"Failed to emit SSE event for order {order_id} ({subtype.value}): {sse_error}")


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
            "options": item.options,
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
    args = CreateOrderArgs.model_validate(kwargs)
    await _populate_missing_prices(args.restaurant_id, args.items)
    total_amount = _calculate_total(args.items)
    logger.info("create_order invoked customer_contact=%s items=%s", args.customer_contact, len(args.items))

    def _create():
        # Create fresh repository instances for this operation
        user_repo = _get_user_repo()
        metadata_repo = _get_metadata_repo()
        order_repo = _get_order_repo()

        # Ensure user exists/updated
        user_id = user_repo.create_or_update_user(
            {
                "name": args.customer_name,
                "phone_number": args.customer_contact,
                "email": None,
                "address": None,
                "is_spam": False,
                "credit_card": None,
            }
        )

        # Create user-restaurant metadata mapping (for dashboard user visibility)
        if args.restaurant_id:
            try:
                metadata_repo.create_mapping(
                    user_id=user_id,
                    restaurant_id=int(args.restaurant_id),
                    source="order",
                    notes="Created via voice agent order",
                )
            except Exception as meta_err:
                # Log but don't fail order creation if metadata mapping fails
                logger.warning("Failed to create user-restaurant metadata: %s", meta_err)

        order_payload = {
            "restaurant_id": int(args.restaurant_id) if args.restaurant_id else None,
            "status": "pending",
            "total_amount": total_amount,
            "order_details": [item.model_dump() for item in args.items],
            "customization": args.metadata.get("customization", {}),
        }
        order_id = order_repo.create_order(user_id, order_payload)
        # Store detail rows for relational table
        for item in args.items:
            item_id = item.item_id
            if item_id:
                for _ in range(max(item.quantity, 1)):
                    order_repo.create_order_details(order_id, item_id)
        return order_id, user_id

    order_id, user_id = await _run_service_call(_create)

    # Log activity history for voice agent order creation (run in thread since it's a DB operation)
    def _log_history():
        try:
            if args.restaurant_id:
                logger.debug(
                    "[DEBUG] Logging order creation history: order_id=%s, restaurant_id=%s",
                    order_id,
                    args.restaurant_id,
                )
                history_service = _get_history_service()
                history_id = history_service.log_order_created(
                    order_id=order_id,
                    restaurant_id=int(args.restaurant_id),
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
                logger.warning("Cannot log history - restaurant_id is None for order %s", order_id)
        except Exception as history_error:
            logger.exception("[ERROR] Failed to log history for voice agent order creation: %s", history_error)

    await _run_service_call(_log_history)

    # Emit SSE event for new order (background task)
    if args.restaurant_id:
        asyncio.create_task(
            _emit_order_sse_event(
                restaurant_id=int(args.restaurant_id),
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

    return {
        "status": "CREATED",
        "message": "Order created",
        "order_id": order_id,
        "user_id": user_id,
        "restaurant_id": args.restaurant_id,
        "items": _summarize_items(args.items),
        "total_amount": total_amount,
    }


async def lookup_order(**kwargs) -> Dict[str, Any]:
    args = LookupOrderArgs.model_validate(kwargs)
    logger.info("lookup_order invoked customer_contact=%s", args.customer_contact)

    def _lookup():
        user_repo = _get_user_repo()
        order_repo = _get_order_repo()
        user_id = user_repo.get_user_id_by_phone_or_email(args.customer_contact, None)
        if not user_id:
            return None
        return order_repo.get_latest_order_by_user(user_id, args.restaurant_id)

    order = await _run_service_call(_lookup)
    if not order:
        return {"status": "NOT_FOUND", "message": "No order found for this contact at this restaurant."}
    return {"status": "FOUND", "order": order}


def _flatten_menu_items(menus: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return menus


def _match_menu_item(menu_items: List[Dict[str, Any]], request_item: OrderItem) -> Optional[Dict[str, Any]]:
    """Match a requested item against menu items by ID or name."""
    for item in menu_items:
        # Match by item_id if provided
        if request_item.item_id and item.get("id") == request_item.item_id:
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

    Returns clear status for each item:
    - AVAILABLE: Item exists and is available
    - UNAVAILABLE: Item exists but is currently unavailable
    - UNKNOWN_ITEM: Item not found in menu
    """
    args = CheckItemsAvailabilityArgs.model_validate(kwargs)
    logger.info(
        "check_items_availability invoked restaurant_id=%s item_count=%s",
        args.restaurant_id,
        len(args.items),
    )
    menu_repo = _get_menu_repo()
    # Get ALL items (both available and unavailable) to properly check status
    all_menu_items = await _run_service_call(menu_repo.get_menus_by_restaurant, args.restaurant_id)
    all_menu_items = _flatten_menu_items(all_menu_items)
    results = []
    for requested in args.items:
        match = _match_menu_item(all_menu_items, requested)
        if match:
            # Normalize availability to boolean (handles MySQL TINYINT 0/1 and Python booleans)
            is_available_bool = _normalize_boolean(match.get("is_available"))
            item_id = match.get("id")
            price = match.get("price")
            category = match.get("category")
            item_name = match.get("item_name") or match.get("name") or requested.name

            if is_available_bool:
                results.append(
                    {
                        "requested_item": requested.name,
                        "status": "AVAILABLE",
                        "item_id": item_id,
                        "price": str(price) if price is not None else "0",
                        "category": category,
                        "message": f"{item_name} is available for ${price if price else 0}.",
                    },
                )
            else:
                results.append(
                    {
                        "requested_item": requested.name,
                        "status": "UNAVAILABLE",
                        "item_id": item_id,
                        "message": f"{item_name} is currently unavailable.",
                    },
                )
        else:
            results.append(
                {
                    "requested_item": requested.name,
                    "status": "UNKNOWN_ITEM",
                    "message": f"{requested.name} is not on our menu.",
                },
            )

    return {
        "restaurant_id": args.restaurant_id,
        "results": results,
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
    if isinstance(created_at, datetime):
        # Make timezone-aware if naive
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
    elif isinstance(created_at, str):
        try:
            created_at = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
        except ValueError:
            return False
    else:
        return False

    elapsed_seconds = (now - created_at).total_seconds()
    return elapsed_seconds <= update_window_seconds


async def update_order_details(**kwargs) -> Dict[str, Any]:
    args = UpdateOrderDetailsArgs.model_validate(kwargs)
    await _populate_missing_prices(args.restaurant_id, args.items)
    logger.info("update_order_details invoked customer_contact=%s", args.customer_contact)

    def _update():
        user_repo = _get_user_repo()
        order_repo = _get_order_repo()

        user_id = user_repo.get_user_id_by_phone_or_email(args.customer_contact, None)
        if not user_id:
            return None, None, None, None

        order = order_repo.get_latest_order_by_user(user_id, args.restaurant_id)
        if not order:
            return None, None, None, None
        order_id = order.get("id")
        if not order_id:
            return None, None, None, None

        # Check if order is within the allowed update window
        created_at = order.get("created_at")
        if not _is_within_update_window(created_at):
            return "UPDATE_WINDOW_EXPIRED", None, None, order

        # Update user's name if provided (consistent with create_order behavior)
        # Only update after validation to ensure it only executes when order update will succeed
        if args.customer_name:
            user_repo.create_or_update_user(
                {
                    "name": args.customer_name,
                    "phone_number": args.customer_contact,
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
        total_amount = _calculate_total(args.items)
        order_repo.update_order_details(order_id, order_details, args.customization, total_amount)

        # Update status if provided (e.g., cancellation within update window)
        if args.status:
            order_repo.update_order_status(order_id, args.status)

        updated = order_repo.get_order_by_id(order_id)

        return updated, previous_data, order.get("restaurant_id"), order

    result, previous_data, restaurant_id, original_order = await _run_service_call(_update)
    restaurant_id = restaurant_id or args.restaurant_id

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
        return {"status": "NOT_FOUND", "message": "No order found to update for this restaurant."}

    updated_order = result

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
                logger.warning("Cannot log history - restaurant_id is None for order %s", updated_order.get("id"))
        except Exception as history_error:
            logger.exception("[ERROR] Failed to log history for voice agent order update: %s", history_error)

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
