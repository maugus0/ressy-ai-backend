from __future__ import annotations

import json
from datetime import date, datetime, time, timezone
from decimal import Decimal
from enum import Enum
from typing import Any, Optional

UTC = timezone.utc


def ensure_utc(value: datetime) -> datetime:
    """Coerce datetimes to UTC, assuming naive values are already UTC."""
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def isoformat_z(value: datetime) -> str:
    """Format datetime as ISO 8601 with a trailing Z."""
    return ensure_utc(value).isoformat().replace("+00:00", "Z")


def parse_datetime(value: str | datetime, default_tz: timezone = UTC) -> datetime:
    """
    Parse ISO-ish datetime strings and normalize to UTC.

    Naive values are interpreted in default_tz (UTC by default).
    """
    if isinstance(value, datetime):
        return ensure_utc(value)
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=default_tz)
    return parsed.astimezone(UTC)


def coerce_datetime(value: Any) -> Optional[datetime]:
    """Convert a datetime-like value to UTC-aware datetime if possible."""
    if isinstance(value, datetime):
        return ensure_utc(value)
    if isinstance(value, str):
        try:
            return parse_datetime(value)
        except ValueError:
            return None
    return None


def json_default(value: Any) -> Any:
    """Default JSON serializer that normalizes datetimes to UTC Z."""
    if isinstance(value, datetime):
        return isoformat_z(value)
    if isinstance(value, date) and not isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, time):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, Enum):
        return value.value
    return json.JSONEncoder().default(value)
