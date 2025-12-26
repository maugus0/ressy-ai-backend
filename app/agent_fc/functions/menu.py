"""Menu lookup functions the agent can call during a live conversation."""

from __future__ import annotations

import asyncio
from typing import Any, Dict, List, Optional, Tuple

from pydantic import BaseModel, ConfigDict, model_validator

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


class ListMenuArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    restaurant_id: int


class GetMenuItemDetailsArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    restaurant_id: int
    item_id: Optional[int] = None
    search_term: Optional[str] = None

    @model_validator(mode="after")
    def _ensure_lookup_params(self) -> "GetMenuItemDetailsArgs":
        term = (self.search_term or "").strip()
        if self.item_id is None and not term:
            raise ValueError("Either item_id or search_term is required")
        self.search_term = term or None
        return self


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
    Return the full available menu for a restaurant with categories and item names.
    """
    args = ListMenuArgs.model_validate(kwargs)
    logger.info("list_menu_items invoked restaurant_id=%s", args.restaurant_id)

    def _fetch():
        menu_repo = _get_menu_repo()
        return menu_repo.get_available_items_by_restaurant(args.restaurant_id)

    try:
        items = await _run_repo_call(_fetch)
    except Exception as exc:  # noqa: BLE001 - defensive for agent calls
        logger.exception("[ERROR] list_menu_items failed restaurant_id=%s: %s", args.restaurant_id, exc)
        return {
            "status": "ERROR",
            "restaurant_id": args.restaurant_id,
            "message": "Unable to load menu right now.",
        }

    categories, summaries = _summarize_menu_items(items or [])
    status = "FOUND" if summaries else "EMPTY"
    return {
        "status": status,
        "restaurant_id": args.restaurant_id,
        "categories": categories,
        "items": summaries,
    }


async def get_menu_item_details(**kwargs) -> Dict[str, Any]:
    """
    Lookup detailed information about a single menu item using its ID, or search for items.

    Creates a fresh repository instance per call to ensure up-to-date menu data
    during active voice calls (fixes mid-call menu updates not being detected).
    """
    args = GetMenuItemDetailsArgs.model_validate(kwargs)
    item: Optional[Dict[str, Any]] = None
    logger.info(
        "get_menu_item_details invoked restaurant_id=%s item_id=%s search_term=%s",
        args.restaurant_id,
        args.item_id,
        args.search_term,
    )

    def _fetch_by_id():
        menu_repo = _get_menu_repo()
        found = menu_repo.get_menu_by_id(args.restaurant_id, args.item_id)
        if not found:
            found = menu_repo.get_by_id(args.item_id)
        return found

    def _search():
        menu_repo = _get_menu_repo()
        items, _count = menu_repo.get_paginated_by_restaurant(
            restaurant_id=args.restaurant_id,
            page=1,
            limit=25,
            search=args.search_term,
            is_available=True,
        )
        return items

    try:
        if args.item_id is not None:
            item = await _run_repo_call(_fetch_by_id)
        else:
            items = await _run_repo_call(_search)
            if not items:
                return {"status": "NOT_FOUND", "search_term": args.search_term, "restaurant_id": args.restaurant_id}
            return {
                "status": "SEARCH_RESULTS",
                "restaurant_id": args.restaurant_id,
                "search_term": args.search_term,
                "items": [
                    {
                        "item_id": item.get("id"),
                        "name": item.get("item_name"),
                        "description": item.get("item_desc"),
                        "price": item.get("price"),
                        "category": item.get("category"),
                        "sub_category": item.get("sub_category"),
                        "is_special": item.get("is_special"),
                    }
                    for item in items
                ],
            }
    except Exception as exc:
        logger.exception(
            "[ERROR] get_menu_item_details failed restaurant_id=%s item_id=%s search_term=%s: %s",
            args.restaurant_id,
            args.item_id,
            args.search_term,
            exc,
        )
        return {
            "status": "ERROR",
            "item_id": args.item_id,
            "search_term": args.search_term,
            "restaurant_id": args.restaurant_id,
            "message": "Unable to load item details.",
        }

    if not item:
        return {"status": "NOT_FOUND", "item_id": args.item_id, "restaurant_id": args.restaurant_id}

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
        },
    }
