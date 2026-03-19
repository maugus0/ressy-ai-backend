"""
Business hours utilities (reuses restaurant_hours logic since it's generic).
"""

from app.utils.restaurant_hours import (
    DAYS_OF_WEEK,
    _parse_operating_time,
    format_nearest_slot_label,
    format_operating_window,
    get_day_operating_hours,
    is_datetime_on_slot_boundary,
    is_datetime_within_operating_hours,
    is_restaurant_open_now,
    resolve_restaurant_timezone,
    snap_datetime_to_slot,
)

# Re-export with business-specific names for clarity
is_business_open_now = is_restaurant_open_now
resolve_business_timezone = resolve_restaurant_timezone

__all__ = [
    "DAYS_OF_WEEK",
    "_parse_operating_time",
    "format_nearest_slot_label",
    "format_operating_window",
    "get_day_operating_hours",
    "is_datetime_on_slot_boundary",
    "is_datetime_within_operating_hours",
    "is_business_open_now",
    "resolve_business_timezone",
    "snap_datetime_to_slot",
]
