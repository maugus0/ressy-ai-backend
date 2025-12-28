from __future__ import annotations

import asyncio
from typing import Any, Dict, Optional

from app.repositories.mysql_restaurant_repo import MySQLRestaurantRepository
from app.utils.logging_config import get_logger

logger = get_logger(__name__)


def _get_restaurant_repo() -> MySQLRestaurantRepository:
    """Create fresh restaurant repository instance per function call."""
    return MySQLRestaurantRepository()


async def load_restaurant(restaurant_id: int) -> Optional[Dict[str, Any]]:
    """Fetch restaurant details for open-hours checks."""
    restaurant_repo = _get_restaurant_repo()
    try:
        if asyncio.iscoroutinefunction(restaurant_repo.get_by_id):
            return await restaurant_repo.get_by_id(int(restaurant_id))
        return await asyncio.to_thread(restaurant_repo.get_by_id, int(restaurant_id))
    except Exception as exc:  # noqa: BLE001 - defensive for agent calls
        logger.warning("Unable to fetch restaurant for open-hours check restaurant_id=%s: %s", restaurant_id, exc)
        return None
