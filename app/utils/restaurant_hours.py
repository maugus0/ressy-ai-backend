import logging
from datetime import datetime
from datetime import time as dt_time
from datetime import timedelta, timezone
from typing import Any, Optional, Tuple, Union
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.config import settings

logger = logging.getLogger(__name__)


def _parse_operating_time(value: Any) -> Optional[dt_time]:
    """Convert stored operating time values to datetime.time."""
    if value is None:
        return None
    if isinstance(value, dt_time):
        return value
    if isinstance(value, timedelta):
        total_seconds = int(value.total_seconds()) % 86400
        hours, remainder = divmod(total_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        return dt_time(hour=hours, minute=minutes, second=seconds)
    try:
        return datetime.strptime(str(value), "%H:%M:%S").time()
    except (TypeError, ValueError):
        logger.warning("Invalid operating time value encountered: %s", value)
        return None


def resolve_restaurant_timezone(restaurant: dict) -> Tuple[Union[ZoneInfo, timezone], str]:
    """Resolve the restaurant's timezone object and label with sensible fallbacks."""
    default_timezone = getattr(settings, "RESTAURANT_TIMEZONE", "America/Vancouver")
    timezone_name = str(restaurant.get("timezone") or restaurant.get("time_zone") or default_timezone).strip()
    if not timezone_name:
        timezone_name = default_timezone

    try:
        tz = ZoneInfo(timezone_name)
        label = timezone_name
    except ZoneInfoNotFoundError:
        logger.warning("Invalid timezone label in configuration %s. Using system timezone.", timezone_name)
        tz = datetime.now().astimezone().tzinfo or timezone.utc
        label = tz.tzname(None) or default_timezone
    return tz, label


def _is_time_within(open_time: dt_time, close_time: dt_time, current_time: dt_time) -> bool:
    """Check whether current_time falls between open_time and close_time (supports overnight hours)."""
    if open_time == close_time:
        # Treat identical times as always open to avoid hard blocking on bad data.
        return True
    if open_time < close_time:
        return open_time <= current_time < close_time
    # Overnight hours (e.g., 18:00 - 02:00)
    return current_time >= open_time or current_time < close_time


def is_restaurant_open_now(restaurant: dict, now_utc: Optional[datetime] = None) -> bool:
    """
    Determine if the restaurant is open at the given UTC time (default: current).

    Assumes the UTC instant provided represents the current moment; converts to restaurant tz for evaluation.
    """
    opening_time = _parse_operating_time(restaurant.get("opening_time"))
    closing_time = _parse_operating_time(restaurant.get("closing_time"))

    if not opening_time or not closing_time:
        # If operating hours are missing or invalid, default to open to avoid unnecessary blocks.
        return True

    tz, _ = resolve_restaurant_timezone(restaurant)
    now_utc = now_utc or datetime.now(timezone.utc)
    local_time = now_utc.astimezone(tz).timetz()
    if local_time.tzinfo:
        local_time = local_time.replace(tzinfo=None)
    return _is_time_within(opening_time, closing_time, local_time)


def is_datetime_within_operating_hours(restaurant: dict, target_dt: datetime) -> bool:
    """
    Check if a proposed datetime falls within the restaurant's operating hours.

    Assumes a naive datetime is already in the restaurant's local time. If tz-aware,
    it will be converted to the restaurant's timezone before evaluation.
    """
    opening_time = _parse_operating_time(restaurant.get("opening_time"))
    closing_time = _parse_operating_time(restaurant.get("closing_time"))

    if not opening_time or not closing_time:
        return True

    tz, _ = resolve_restaurant_timezone(restaurant)
    if target_dt.tzinfo is None:
        # Caller is responsible for providing naive times in local restaurant time.
        target_local = target_dt.replace(tzinfo=tz)
    else:
        target_local = target_dt.astimezone(tz)

    local_time = target_local.timetz()
    if local_time.tzinfo:
        local_time = local_time.replace(tzinfo=None)

    return _is_time_within(opening_time, closing_time, local_time)


def format_operating_window(restaurant: dict) -> str:
    """Return a human-friendly operating window string, defaulting to raw values if parsing fails."""
    try:
        open_time = _parse_operating_time(restaurant.get("opening_time"))
        close_time = _parse_operating_time(restaurant.get("closing_time"))
        if open_time and close_time:
            # Use locale-independent formatting; %-I not on Windows, so use %I and strip leading zero.
            return f"{open_time.strftime('%I:%M %p').lstrip('0')} - {close_time.strftime('%I:%M %p').lstrip('0')}"
    except Exception:
        # Fallback to raw values if parsing/formatting fails.
        pass
    return f"{restaurant.get('opening_time')} - {restaurant.get('closing_time')}"
