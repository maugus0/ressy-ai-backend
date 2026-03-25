"""Menu lookup functions the agent can call during a live conversation."""

from __future__ import annotations

import asyncio
from typing import Any, Dict, List, Optional, Tuple

from pydantic import BaseModel, ConfigDict, Field

from app.agent_fc.functions.function_context import NoArgs, context_restaurant_id, split_call_context
from app.repositories.mysql_menu_repo import MySQLMenuRepository
from app.utils.logging_config import get_logger

logger = get_logger(__name__)


def _get_menu_repo() -> MySQLMenuRepository:
    """
    Create a fresh menu repository instance for each function call.

    This ensures fresh database connections from the pool, preventing stale
    data issues during active voice calls. Each function call gets its own
    repository instance with a fresh connection.
    """
    return MySQLMenuRepository()


class GetMenuItemDetailsArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    item_id: int


class GetMenuItemCustomizationsArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    item_id: int
    completed_group_ids: List[int] = Field(default_factory=list)
    include_ask_if_mentioned: bool = False
    reset_progress: bool = False


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


def _is_available(record: Dict[str, Any]) -> bool:
    return _normalize_boolean(record.get("is_available", True))


def _format_option_value(value: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": value.get("id"),
        "name": value.get("name"),
        "price_delta": value.get("price_delta"),
        "is_default": _normalize_boolean(value.get("is_default")),
    }


def _format_option_group(group: Dict[str, Any]) -> Dict[str, Any]:
    input_type = str(group.get("input_type") or "SELECT").strip().upper()
    values = [
        _format_option_value(value)
        for value in sorted(group.get("values", []), key=lambda entry: entry.get("sort_order", 0))
        if _is_available(value)
    ]
    return {
        "id": group.get("id"),
        "name": group.get("name"),
        "description": group.get("description"),
        "selection_type": group.get("selection_type"),
        "input_type": input_type,
        "min_select": group.get("min_select"),
        "max_select": group.get("max_select"),
        "free_allowance": group.get("free_allowance"),
        "allows_quantity": _normalize_boolean(group.get("allows_quantity")),
        "max_quantity_per_option": group.get("max_quantity_per_option"),
        "prompt_style": group.get("prompt_style"),
        "is_required": _normalize_boolean(group.get("is_required")),
        "text_required": _normalize_boolean(group.get("text_required")),
        "max_text_length": group.get("max_text_length"),
        "values": values,
    }


def _group_id(group: Dict[str, Any]) -> int | None:
    raw_group_id = group.get("id")
    if raw_group_id is None:
        return None
    try:
        return int(raw_group_id)
    except (TypeError, ValueError):
        return None


async def _run_repo_call(func, *args, **kwargs):
    return await asyncio.to_thread(func, *args, **kwargs)


def _summarize_menu_items(items: List[Dict[str, Any]]) -> Tuple[List[str], List[Dict[str, Any]]]:
    categories: List[str] = []
    summaries: List[Dict[str, Any]] = []
    for item in items:
        category = item.get("category")
        if category is not None:
            categories.append(str(category))
        name = item.get("item_name")
        if not name:
            continue
        summaries.append(
            {
                "item_id": item.get("id"),
                "name": name,
                "category": category,
                "sub_category": item.get("sub_category"),
            }
        )
    deduped_categories = list(dict.fromkeys(categories))
    return deduped_categories, summaries


async def list_menu_items(**kwargs) -> Dict[str, Any]:
    """
    Return the full active menu for a restaurant, split into available and unavailable items.

    Inactive catalog records are hidden from the voice agent. Among active items, unavailable
    entries are still returned so the agent can explain that they exist but cannot be ordered
    right now.
    """
    context, model_kwargs = split_call_context(kwargs, NoArgs)
    NoArgs.model_validate(model_kwargs)
    call_sid = context.get("call_sid")
    restaurant_id = context_restaurant_id(context)
    if restaurant_id is None:
        return {"status": "ERROR", "message": "Missing restaurant context for menu lookup."}
    logger.info("list_menu_items invoked restaurant_id=%s call_sid=%s", restaurant_id, call_sid)

    def _fetch():
        menu_repo = _get_menu_repo()
        # Get all active items and then split them by current availability.
        return menu_repo.get_menus_by_restaurant(restaurant_id, only_active=True)

    try:
        all_items = await _run_repo_call(_fetch)
    except Exception as exc:  # noqa: BLE001 - defensive for agent calls
        logger.exception(
            "[ERROR] list_menu_items failed restaurant_id=%s call_sid=%s: %s",
            restaurant_id,
            call_sid,
            exc,
        )
        return {
            "status": "ERROR",
            "restaurant_id": restaurant_id,
            "message": "Unable to load menu right now.",
        }

    # Separate items by availability (using consistent boolean normalization)
    available_items = [item for item in (all_items or []) if _normalize_boolean(item.get("is_available"))]
    unavailable_items = [item for item in (all_items or []) if not _normalize_boolean(item.get("is_available"))]

    # Summarize both lists
    categories_available, summaries_available = _summarize_menu_items(available_items)
    categories_unavailable, summaries_unavailable = _summarize_menu_items(unavailable_items)

    # Combine unique categories from both lists
    all_categories = list(dict.fromkeys(categories_available + categories_unavailable))

    status = "FOUND" if (summaries_available or summaries_unavailable) else "EMPTY"

    return {
        "status": status,
        "restaurant_id": restaurant_id,
        "categories": all_categories,
        "items_available": summaries_available,
        "items_unavailable": summaries_unavailable,
        "total_items": len(summaries_available) + len(summaries_unavailable),
        "available_count": len(summaries_available),
        "unavailable_count": len(summaries_unavailable),
    }


async def get_menu_item_details(**kwargs) -> Dict[str, Any]:
    """
    Lookup detailed information about a single menu item using its ID.

    Creates a fresh repository instance per call to ensure up-to-date menu data
    during active voice calls (fixes mid-call menu updates not being detected).
    """
    context, model_kwargs = split_call_context(kwargs, GetMenuItemDetailsArgs)
    args = GetMenuItemDetailsArgs.model_validate(model_kwargs)
    call_sid = context.get("call_sid")
    restaurant_id = context_restaurant_id(context)
    if restaurant_id is None:
        return {
            "status": "ERROR",
            "item_id": args.item_id,
            "message": "Missing restaurant context for item details lookup.",
        }
    logger.info(
        "get_menu_item_details invoked restaurant_id=%s item_id=%s call_sid=%s",
        restaurant_id,
        args.item_id,
        call_sid,
    )

    def _fetch_by_id():
        menu_repo = _get_menu_repo()
        found = menu_repo.get_menu_by_id(restaurant_id, args.item_id)
        if found and not _normalize_boolean(found.get("is_active", True)):
            return None
        if found:
            found["option_groups"] = menu_repo.get_option_groups_for_item(found.get("id"), only_active=True)
        return found

    try:
        item = await _run_repo_call(_fetch_by_id)
    except Exception as exc:
        logger.exception(
            "[ERROR] get_menu_item_details failed restaurant_id=%s item_id=%s call_sid=%s: %s",
            restaurant_id,
            args.item_id,
            call_sid,
            exc,
        )
        return {
            "status": "ERROR",
            "item_id": args.item_id,
            "restaurant_id": restaurant_id,
            "message": "Unable to load item details.",
        }

    if not item:
        return {"status": "NOT_FOUND", "item_id": args.item_id, "restaurant_id": restaurant_id}

    option_groups = [
        _format_option_group(group)
        for group in sorted(item.get("option_groups", []), key=lambda entry: entry.get("sort_order", 0))
        if _is_available(group)
    ]
    option_groups = [group for group in option_groups if group.get("input_type") == "TEXT" or group.get("values")]

    return {
        "status": "FOUND",
        "item": {
            "item_id": item.get("id"),
            "name": item.get("item_name"),
            "description": item.get("item_desc"),
            "price": item.get("price"),
            "category": item.get("category"),
            "sub_category": item.get("sub_category"),
            "is_special": item.get("is_special"),
            "option_groups": option_groups,
        },
    }


async def get_menu_item_customizations(**kwargs) -> Dict[str, Any]:
    """
    Return customization option group progression for a single menu item.
    """
    context, model_kwargs = split_call_context(kwargs, GetMenuItemCustomizationsArgs)
    args = GetMenuItemCustomizationsArgs.model_validate(model_kwargs)
    restaurant_id = context_restaurant_id(context)
    call_sid = context.get("call_sid")
    progress_store = context.get("customization_progress_by_item")
    if not isinstance(progress_store, dict):
        progress_store = {}
    logger.info(
        "get_menu_item_customizations invoked restaurant_id=%s item_id=%s completed_group_ids=%s include_ask_if_mentioned=%s reset_progress=%s progress_store=%s call_sid=%s",
        restaurant_id,
        args.item_id,
        args.completed_group_ids,
        args.include_ask_if_mentioned,
        args.reset_progress,
        progress_store,
        call_sid,
    )
    if restaurant_id is None:
        return {
            "status": "ERROR",
            "message": "Missing restaurant context for customizations lookup.",
        }
    if args.reset_progress:
        progress_store.pop(args.item_id, None)

    def _fetch_for_item(item_id: int) -> Tuple[List[Dict[str, Any]], bool]:
        menu_repo = _get_menu_repo()
        found = menu_repo.get_menu_by_id(int(restaurant_id), item_id)
        if not found or not _normalize_boolean(found.get("is_active", True)):
            return [], False
        groups = menu_repo.get_option_groups_for_item(item_id, only_active=True)
        return groups or [], True

    try:
        groups, found = await _run_repo_call(_fetch_for_item, args.item_id)
    except Exception as exc:  # noqa: BLE001 - defensive for agent calls
        logger.exception(
            "[ERROR] get_menu_item_customizations failed restaurant_id=%s item_id=%s call_sid=%s: %s",
            restaurant_id,
            args.item_id,
            call_sid,
            exc,
        )
        return {
            "status": "ERROR",
            "restaurant_id": restaurant_id,
            "message": "Unable to load customizations right now.",
        }

    if not found:
        progress_store.pop(args.item_id, None)
        return {
            "status": "NOT_FOUND",
            "restaurant_id": restaurant_id,
            "item_id": args.item_id,
            "message": "Menu item was not found for this restaurant.",
        }

    progress = progress_store.get(args.item_id)
    if not isinstance(progress, dict):
        progress = {}
        progress_store[args.item_id] = progress

    existing_completed = progress.get("completed_group_ids")
    completed_group_ids: set[int] = set()
    if isinstance(existing_completed, set):
        completed_group_ids = {int(group_id) for group_id in existing_completed}
    elif isinstance(existing_completed, list):
        for group_id in existing_completed:
            try:
                completed_group_ids.add(int(group_id))
            except (TypeError, ValueError):
                continue

    for group_id in args.completed_group_ids:
        try:
            completed_group_ids.add(int(group_id))
        except (TypeError, ValueError):
            continue

    if args.include_ask_if_mentioned:
        progress["include_ask_if_mentioned"] = True
    include_ask_if_mentioned = bool(progress.get("include_ask_if_mentioned"))

    pending_group_id: Optional[int]
    raw_pending_group_id = progress.get("pending_group_id")
    try:
        pending_group_id = int(raw_pending_group_id) if raw_pending_group_id is not None else None
    except (TypeError, ValueError):
        pending_group_id = None

    option_groups = [
        _format_option_group(group)
        for group in sorted(groups, key=lambda entry: entry.get("sort_order", 0))
        if _is_available(group)
    ]
    option_groups = [group for group in option_groups if group.get("input_type") == "TEXT" or group.get("values")]

    all_group_ids = {_group_id(group) for group in option_groups}
    all_group_ids.discard(None)
    completed_group_ids.intersection_update({int(group_id) for group_id in all_group_ids})

    if pending_group_id is not None and (
        pending_group_id in completed_group_ids or pending_group_id not in all_group_ids
    ):
        pending_group_id = None

    active_groups: List[Dict[str, Any]] = []
    deferred_group_ids: List[int] = []
    for group in option_groups:
        group_id = _group_id(group)
        if group_id is None or group_id in completed_group_ids:
            continue
        if group.get("prompt_style") == "ASK_IF_MENTIONED" and not include_ask_if_mentioned:
            deferred_group_ids.append(group_id)
            continue
        active_groups.append(group)

    next_group = None
    if pending_group_id is not None:
        for group in active_groups:
            if _group_id(group) == pending_group_id:
                next_group = group
                break
    if next_group is None and active_groups:
        next_group = active_groups[0]
        pending_group_id = _group_id(next_group)
    if next_group is None:
        pending_group_id = None

    next_group_id = _group_id(next_group) if next_group else None
    remaining_group_ids = [
        group_id
        for group_id in (_group_id(group) for group in active_groups)
        if group_id is not None and group_id != next_group_id
    ]

    progress["completed_group_ids"] = completed_group_ids
    progress["pending_group_id"] = pending_group_id
    progress["include_ask_if_mentioned"] = include_ask_if_mentioned

    return {
        "status": "FOUND",
        "restaurant_id": restaurant_id,
        "item_id": args.item_id,
        "next_group": next_group,
        "remaining_group_ids": remaining_group_ids,
        "remaining_count": len(remaining_group_ids),
        "deferred_group_ids": deferred_group_ids,
        "deferred_count": len(deferred_group_ids),
        "completed_group_ids": sorted(completed_group_ids),
        "pending_group_id": pending_group_id,
        "include_ask_if_mentioned": include_ask_if_mentioned,
        "progress_note": (
            "Only next_group contains options for caller dialogue. "
            "After the caller answers, call get_menu_item_customizations again with completed_group_ids "
            "including the previous pending_group_id."
        ),
    }
