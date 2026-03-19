from __future__ import annotations

import asyncio
from typing import Any, Dict, Optional

from app.repositories.mysql_business_repo import MySQLBusinessRepository
from app.utils.logging_config import get_logger

logger = get_logger(__name__)


def _get_business_repo() -> MySQLBusinessRepository:
    """Create fresh business repository instance per function call."""
    return MySQLBusinessRepository()


async def load_business(business_id: int) -> Optional[Dict[str, Any]]:
    """Fetch business details for open-hours checks."""
    business_repo = _get_business_repo()
    try:
        if asyncio.iscoroutinefunction(business_repo.get_by_id):
            return await business_repo.get_by_id(int(business_id))
        return await asyncio.to_thread(business_repo.get_by_id, int(business_id))
    except Exception as exc:  # noqa: BLE001 - defensive for agent calls
        logger.warning("Unable to fetch business for open-hours check business_id=%s: %s", business_id, exc)
        return None
