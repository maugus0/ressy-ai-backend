"""Helpers for notification API responses."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Dict

from app.utils.timezone import isoformat_z


def normalize_notification_row(row: Dict[str, Any]) -> Dict[str, Any]:
    """Convert DB row to API response dict; serialize datetimes to ISO 8601 with Z (same as orders/calls/reservations)."""
    created_at = row.get("created_at")
    updated_at = row.get("updated_at")
    read_at = row.get("read_at")
    data = row.get("data")
    if isinstance(data, str):
        try:
            data = json.loads(data) if data else None
        except Exception:
            data = None
    return {
        "id": row.get("id"),
        "restaurant_id": row.get("restaurant_id"),
        "type": row.get("type"),
        "subtype": row.get("subtype"),
        "title": row.get("title"),
        "message": row.get("message"),
        "data": data,
        "entity_id": row.get("entity_id"),
        "is_read": bool(row.get("is_read", False)),
        "read_at": _to_iso_z(read_at),
        "created_at": _to_iso_z(created_at) or "",
        "updated_at": _to_iso_z(updated_at) or "",
    }


def _to_iso_z(value: Any) -> str | None:
    """Format datetime for API: use isoformat_z (UTC with Z) to match orders, calls, reservations."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return isoformat_z(value)
    if isinstance(value, str):
        return value
    return str(value)
