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


DAYS_OF_WEEK = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]


def _get_previous_day(day_name: str) -> str:
    """Get the previous day of the week."""
    idx = DAYS_OF_WEEK.index(day_name.lower())
    prev_idx = (idx - 1) % 7
    return DAYS_OF_WEEK[prev_idx]


def _is_overnight_hours(open_time: dt_time, close_time: dt_time) -> bool:
    """Check if operating hours span overnight (close time is before open time)."""
    return close_time < open_time


def _is_time_within(open_time: dt_time, close_time: dt_time, current_time: dt_time) -> bool:
    """Check whether current_time falls between open_time and close_time (supports overnight hours)."""
    if open_time == close_time:
        # Treat identical times as always open to avoid hard blocking on bad data.
        return True
    if open_time < close_time:
        return open_time <= current_time < close_time
    # Overnight hours (e.g., 18:00 - 02:00)
    return current_time >= open_time or current_time < close_time


def _get_day_hours(restaurant: dict, day_name: str) -> Tuple[Optional[dt_time], Optional[dt_time], bool]:
    """Get operating hours for a specific day from restaurant data.

    Supports both flat column format (monday_open, etc.) and nested operating_hours object.
    Returns (open_time, close_time, is_closed).
    """
    # Check for nested operating_hours object first (API response format)
    operating_hours = restaurant.get("operating_hours")
    if isinstance(operating_hours, dict) and day_name in operating_hours:
        day_hours = operating_hours[day_name]
        if isinstance(day_hours, dict):
            is_closed = bool(day_hours.get("is_closed", False))
            open_time = _parse_operating_time(day_hours.get("open"))
            close_time = _parse_operating_time(day_hours.get("close"))
            return open_time, close_time, is_closed

    # Fallback to flat column format (database format)
    is_closed = bool(restaurant.get(f"{day_name}_closed", False))
    open_time = _parse_operating_time(restaurant.get(f"{day_name}_open"))
    close_time = _parse_operating_time(restaurant.get(f"{day_name}_close"))
    return open_time, close_time, is_closed


def is_restaurant_open_now(restaurant: dict, now_utc: Optional[datetime] = None) -> bool:
    """
    Determine if the restaurant is open at the given UTC time (default: current).

    Uses per-day operating hours. Converts UTC to restaurant timezone for evaluation.
    Handles overnight hours that span across midnight by checking both the current day
    and the previous day's hours.
    """
    tz, _ = resolve_restaurant_timezone(restaurant)
    now_utc = now_utc or datetime.now(timezone.utc)
    local_dt = now_utc.astimezone(tz)
    day_name = local_dt.strftime("%A").lower()

    local_time = local_dt.timetz()
    if local_time.tzinfo:
        local_time = local_time.replace(tzinfo=None)

    # Check current day's hours first
    open_time, close_time, is_closed = _get_day_hours(restaurant, day_name)

    if not is_closed and open_time and close_time:
        if _is_time_within(open_time, close_time, local_time):
            return True

    # Check if previous day had overnight hours that extend into today
    # This handles cases like: Monday 18:00-02:00, and it's now Tuesday 1:30am
    previous_day = _get_previous_day(day_name)
    prev_open, prev_close, prev_closed = _get_day_hours(restaurant, previous_day)

    if not prev_closed and prev_open and prev_close:
        if _is_overnight_hours(prev_open, prev_close):
            # Previous day has overnight hours - check if we're still within the closing time
            if local_time < prev_close:
                return True

    # If current day is explicitly closed and not covered by previous day's overnight
    if is_closed:
        return False

    # If no hours defined for current day, default to open
    if not open_time or not close_time:
        return True

    return False


def is_datetime_within_operating_hours(restaurant: dict, target_dt: datetime) -> bool:
    """
    Check if a proposed datetime falls within the restaurant's operating hours for that day.

    Assumes a naive datetime is already in the restaurant's local time. If tz-aware,
    it will be converted to the restaurant's timezone before evaluation.
    Handles overnight hours that span across midnight by checking both the target day
    and the previous day's hours.
    """
    tz, _ = resolve_restaurant_timezone(restaurant)
    if target_dt.tzinfo is None:
        # Caller is responsible for providing naive times in local restaurant time.
        target_local = target_dt.replace(tzinfo=tz)
    else:
        target_local = target_dt.astimezone(tz)

    day_name = target_local.strftime("%A").lower()
    local_time = target_local.timetz()
    if local_time.tzinfo:
        local_time = local_time.replace(tzinfo=None)

    # Check current day's hours first
    open_time, close_time, is_closed = _get_day_hours(restaurant, day_name)

    if not is_closed and open_time and close_time:
        if _is_time_within(open_time, close_time, local_time):
            return True

    # Check if previous day had overnight hours that extend into today
    # This handles cases like: Monday 18:00-02:00, and target is Tuesday 1:30am
    previous_day = _get_previous_day(day_name)
    prev_open, prev_close, prev_closed = _get_day_hours(restaurant, previous_day)

    if not prev_closed and prev_open and prev_close:
        if _is_overnight_hours(prev_open, prev_close):
            # Previous day has overnight hours - check if target time is within the closing period
            if local_time < prev_close:
                return True

    # If current day is explicitly closed and not covered by previous day's overnight
    if is_closed:
        return False

    # If no hours defined for current day, default to within hours
    if not open_time or not close_time:
        return True

    return False


def get_day_operating_hours(restaurant: dict, day_name: str) -> Tuple[Optional[dt_time], Optional[dt_time], bool]:
    """Get operating hours for a specific day. Public interface for _get_day_hours."""
    return _get_day_hours(restaurant, day_name)


def format_operating_window(restaurant: dict, day_name: Optional[str] = None) -> str:
    """Return a human-friendly operating window string for a specific day or today.

    If day_name is not provided, uses the current day based on restaurant timezone.
    """
    try:
        if day_name is None:
            tz, _ = resolve_restaurant_timezone(restaurant)
            day_name = datetime.now(tz).strftime("%A").lower()

        open_time, close_time, is_closed = _get_day_hours(restaurant, day_name)

        if is_closed:
            return "Closed"

        if open_time and close_time:
            # Use locale-independent formatting; %-I not on Windows, so use %I and strip leading zero.
            return f"{open_time.strftime('%I:%M %p').lstrip('0')} - {close_time.strftime('%I:%M %p').lstrip('0')}"
    except Exception:
        # Fallback if parsing/formatting fails.
        pass
    return "Hours not available"
