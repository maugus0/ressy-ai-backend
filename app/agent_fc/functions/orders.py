"""Order-related function implementations wired to application services."""

from __future__ import annotations

import asyncio
import inspect
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

    restaurant_id: str = None
    customer_name: Optional[str] = None
    customer_contact: str = None
    pickup_time_iso: Optional[str] = None
    items: List[OrderItem]
    notes: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class LookupOrderArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    customer_contact: str
    restaurant_id: Optional[str] = None


class CheckItemsAvailabilityArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    restaurant_id: str
    items: List[OrderItem]
    location: Optional[str] = None


class UpdateOrderDetailsArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    customer_contact: str
    items: List[OrderItem]
    customization: Dict[str, Any] = Field(default_factory=dict)
    total_amount: Optional[float] = None
    notes: Optional[str] = None


_order_repo = MySQLOrderRepository()
_user_repo = MySQLUserRepository()
_menu_repo = MySQLMenuRepository()
_metadata_repo = MySQLUserRestaurantMetadataRepository()
_history_service = ActivityHistoryService()


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
    """Compute total from item prices * quantities; treats missing prices as 0."""
    total = 0.0
    for item in items:
        price = item.price if item.price is not None else 0.0
        qty = max(item.quantity, 1)
        try:
            total += float(price) * qty
        except (TypeError, ValueError):
            continue
    return round(total, 2)


async def create_order(**kwargs) -> Dict[str, Any]:
    args = CreateOrderArgs.model_validate(kwargs)
    print(f"[INFO] create_order invoked customer_contact={args.customer_contact} items={len(args.items)}")

    def _create():
        # Ensure user exists/updated
        user_id = _user_repo.create_or_update_user(
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
                _metadata_repo.create_mapping(
                    user_id=user_id,
                    restaurant_id=int(args.restaurant_id),
                    source="order",
                    notes="Created via voice agent order",
                )
            except Exception as meta_err:
                # Log but don't fail order creation if metadata mapping fails
                print(f"[WARN] Failed to create user-restaurant metadata: {meta_err}")

        total_amount = _calculate_total(args.items)
        order_payload = {
            "restaurant_id": int(args.restaurant_id) if args.restaurant_id else None,
            "status": "pending",
            "total_amount": total_amount,
            "order_details": [item.model_dump() for item in args.items],
            "customization": args.metadata.get("customization", {}),
        }
        order_id = _order_repo.create_order(user_id, order_payload)
        # Store detail rows for relational table
        for item in args.items:
            item_id = item.item_id
            if item_id:
                for _ in range(max(item.quantity, 1)):
                    _order_repo.create_order_details(order_id, item_id)
        return order_id, user_id

    order_id, user_id = await _run_service_call(_create)

    # Log activity history for voice agent order creation (run in thread since it's a DB operation)
    def _log_history():
        try:
            if args.restaurant_id:
                print(
                    f"[DEBUG] Logging order creation history: order_id={order_id}, restaurant_id={args.restaurant_id}"
                )
                total_amount = _calculate_total(args.items)
                history_id = _history_service.log_order_created(
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
                print(f"[INFO] Activity history logged for order creation: history_id={history_id}")
            else:
                print(f"[WARN] Cannot log history - restaurant_id is None for order {order_id}")
        except Exception as history_error:
            print(f"[ERROR] Failed to log history for voice agent order creation: {history_error}")
            import traceback

            traceback.print_exc()

    await _run_service_call(_log_history)

    return {
        "status": "CREATED",
        "message": "Order created",
        "order_id": order_id,
        "user_id": user_id,
        "restaurant_id": args.restaurant_id,
        "items": _summarize_items(args.items),
    }


async def lookup_order(**kwargs) -> Dict[str, Any]:
    args = LookupOrderArgs.model_validate(kwargs)
    print(f"[INFO] lookup_order invoked customer_contact={args.customer_contact}")

    def _lookup():
        user_id = _user_repo.get_user_id_by_phone_or_email(args.customer_contact, None)
        if not user_id:
            return None
        return _order_repo.get_latest_order_by_user(user_id)

    order = await _run_service_call(_lookup)
    if not order:
        return {"status": "NOT_FOUND"}
    return {"status": "FOUND", "order": order}


def _flatten_menu_items(menus: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return menus


def _match_menu_item(menu_items: List[Dict[str, Any]], request_item: OrderItem) -> Optional[Dict[str, Any]]:
    for item in menu_items:
        if request_item.item_id and item.get("id") == request_item.item_id:
            return item
        if item.get("name") and request_item.name.lower() == str(item.get("name")).lower():
            return item
    return None


async def check_items_availability(**kwargs) -> Dict[str, Any]:
    args = CheckItemsAvailabilityArgs.model_validate(kwargs)
    print(
        f"[INFO] check_items_availability invoked restaurant_id={args.restaurant_id} " f"item_count={len(args.items)}"
    )
    menu_items = await _run_service_call(_menu_repo.get_available_items_by_restaurant, args.restaurant_id)
    menu_items = _flatten_menu_items(menu_items)
    results = []
    for requested in args.items:
        match = _match_menu_item(menu_items, requested)
        if match:
            is_available = match.get("is_available", True)
            results.append(
                {
                    "requested_item": requested.name,
                    "status": "AVAILABLE" if is_available else "UNAVAILABLE",
                    "item_id": match.get("id"),
                    "price": str(match.get("price")),
                    "category": match.get("category"),
                },
            )
        else:
            results.append(
                {
                    "requested_item": requested.name,
                    "status": "UNKNOWN_ITEM",
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
    print(f"[INFO] update_order_details invoked customer_contact={args.customer_contact}")

    def _update():
        user_id = _user_repo.get_user_id_by_phone_or_email(args.customer_contact, None)
        if not user_id:
            return None, None, None, None
        order = _order_repo.get_latest_order_by_user(user_id)
        if not order:
            return None, None, None, None
        order_id = order.get("id")
        if not order_id:
            return None, None, None, None

        # Check if order is within the allowed update window
        created_at = order.get("created_at")
        if not _is_within_update_window(created_at):
            return "UPDATE_WINDOW_EXPIRED", None, None, order

        # Capture previous state for activity history
        previous_data = {
            "order_details": order.get("order_details"),
            "customization": order.get("customization"),
            "total_amount": order.get("total_amount"),
        }

        order_details = [item.model_dump() for item in args.items]
        total_amount = _calculate_total(args.items)
        _order_repo.update_order_details(order_id, order_details, args.customization, total_amount)
        updated = _order_repo.get_order_by_id(order_id)

        return updated, previous_data, order.get("restaurant_id"), order

    result, previous_data, restaurant_id, original_order = await _run_service_call(_update)

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
        return {"status": "NOT_FOUND"}

    updated_order = result

    # Log activity history for voice agent order update (run in thread since it's a DB operation)
    def _log_history():
        try:
            if restaurant_id:
                print(
                    f"[DEBUG] Logging order update history: order_id={updated_order.get('id')}, restaurant_id={restaurant_id}"
                )
                new_data = {
                    "order_details": updated_order.get("order_details"),
                    "customization": updated_order.get("customization"),
                    "total_amount": updated_order.get("total_amount"),
                }
                history_id = _history_service.log_order_updated(
                    order_id=updated_order.get("id"),
                    restaurant_id=int(restaurant_id),
                    previous_data=previous_data or {},
                    new_data=new_data,
                    user_id=updated_order.get("user_id"),
                )
                print(f"[INFO] Activity history logged for order update: history_id={history_id}")
            else:
                print(f"[WARN] Cannot log history - restaurant_id is None for order {updated_order.get('id')}")
        except Exception as history_error:
            print(f"[ERROR] Failed to log history for voice agent order update: {history_error}")
            import traceback

            traceback.print_exc()

    await _run_service_call(_log_history)

    return {"status": "UPDATED", "order": updated_order}
