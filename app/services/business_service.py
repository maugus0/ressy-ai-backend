import json
import re
from datetime import datetime, time, timedelta
from typing import Any, Dict, Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import HTTPException, status

from app.config import settings
from app.repositories.mysql_business_features_repo import MySQLBusinessFeaturesRepository
from app.repositories.mysql_business_repo import MySQLBusinessRepository
from app.services.admin_user_common import build_pagination
from app.utils.restaurant_hours import DAYS_OF_WEEK


class BusinessService:
    """Service layer for business CRUD and lookups."""

    E164_PHONE_PATTERN = re.compile(r"^\+[1-9]\d{1,14}$")

    def __init__(
        self,
        business_repo: Optional[MySQLBusinessRepository] = None,
        features_repo: Optional[MySQLBusinessFeaturesRepository] = None,
    ):
        self.business_repo = business_repo or MySQLBusinessRepository()
        self.features_repo = features_repo or MySQLBusinessFeaturesRepository()

    # ---------- Validation helpers ----------
    def _normalize_name(self, name: Optional[str]) -> str:
        """Validate and normalize business name."""
        normalized = str(name or "").strip()
        if not normalized:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="name is required")
        if len(normalized) > 255:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="name must be 255 characters or less")
        return normalized

    def _validate_phone_number(self, phone_number: Optional[str], field_name: str) -> None:
        """Validate phone number format and length."""
        if phone_number is None:
            return
        if len(phone_number) > 20:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail=f"{field_name} must be 20 characters or less"
            )
        if not self.E164_PHONE_PATTERN.match(phone_number):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"{field_name} must be a valid E.164 phone number (e.g. +14155551234)",
            )

    def _validate_json_field(self, field_name: str, value: Optional[Dict[str, Any]]) -> None:
        """Ensure JSON-typed fields are objects when provided."""
        if value is None:
            return
        if not isinstance(value, dict):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail=f"{field_name} must be a valid JSON object"
            )

    def _normalize_time_field(
        self, value: Any, field_name: str, default: Optional[str] = None, allow_none: bool = False
    ) -> Optional[str]:
        """
        Normalize input time values to HH:MM:SS strings.

        Accepts strings, datetime.time, or datetime.timedelta (some drivers) and ensures valid formatting.
        """
        if value is None:
            if allow_none:
                return None
            return default

        converted = self._time_like_to_string(value)
        if converted is not None:
            return converted

        if not isinstance(value, str):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"{field_name} must be a string in HH:MM:SS format",
            )

        try:
            parsed = datetime.strptime(value, "%H:%M:%S")
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"{field_name} must be in HH:MM:SS format",
            )
        return parsed.strftime("%H:%M:%S")

    def _validate_minutes(self, minutes: Optional[int], field_name: str) -> None:
        """Validate minute values are non-negative integers."""
        if minutes is None:
            return
        if minutes < 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail=f"{field_name} must be a non-negative integer"
            )

    def _validate_seating_capacity(self, capacity: Optional[int]) -> None:
        """Validate seating capacity is within valid range."""
        if capacity is None:
            return
        if capacity < 1 or capacity > 1000:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="reservation_seating_capacity must be between 1 and 1000",
            )

    def _validate_advance_days(self, days: Optional[int]) -> None:
        """Validate advance booking days is within valid range."""
        if days is None:
            return
        if days < 1 or days > 365:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="reservation_advance_days must be between 1 and 365",
            )

    def _normalize_timezone(self, value: Optional[str], allow_none: bool = False) -> Optional[str]:
        """Validate timezone strings and default when missing."""
        if value is None:
            return None if allow_none else settings.RESTAURANT_TIMEZONE
        cleaned = str(value).strip()
        if not cleaned:
            return None if allow_none else settings.RESTAURANT_TIMEZONE
        try:
            ZoneInfo(cleaned)
        except ZoneInfoNotFoundError:
            valid_timezones = [
                "America/Vancouver",
                "America/Los_Angeles",
                "America/Denver",
                "America/Chicago",
                "America/New_York",
                "America/Toronto",
                "Europe/London",
                "Europe/Paris",
                "Asia/Tokyo",
                "Asia/Singapore",
                "Australia/Sydney",
                "Pacific/Auckland",
                "UTC",
            ]
            if cleaned not in valid_timezones:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid timezone")
        return cleaned

    @staticmethod
    def _validate_escalation_forwarding(forward_escalations: bool, escalation_phone_number: Optional[str]) -> None:
        if forward_escalations and not escalation_phone_number:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="escalation_phone_number is required when forward_escalations is enabled",
            )

    @staticmethod
    def _normalize_feature_value(value: Any, default: bool = True) -> bool:
        """Normalize feature flag values from DB or request payloads."""
        if value is None:
            return default
        if isinstance(value, bool):
            return value
        try:
            return bool(int(value))
        except (TypeError, ValueError):
            return default

    def _compute_kill_switch_blockers(
        self, forward_escalations: Any, escalation_phone_number: Optional[str]
    ) -> list[str]:
        """Return blocking reasons that prevent safe kill-switch redirection."""
        blockers: list[str] = []
        forwarding_enabled = self._normalize_feature_value(forward_escalations, default=False)
        escalation_phone = str(escalation_phone_number).strip() if escalation_phone_number is not None else ""

        if not forwarding_enabled:
            blockers.append("forward_escalations_disabled")
        if not escalation_phone:
            blockers.append("escalation_phone_number_missing")
        return blockers

    def _annotate_kill_switch_fields(self, business: Dict[str, Any]) -> None:
        """Attach computed kill-switch readiness fields to a business payload."""
        kill_switch_enabled = self._normalize_feature_value(business.get("kill_switch_enabled"), default=False)
        blockers = self._compute_kill_switch_blockers(
            business.get("forward_escalations"),
            business.get("escalation_phone_number"),
        )
        business["kill_switch_enabled"] = kill_switch_enabled
        business["kill_switch_can_redirect"] = len(blockers) == 0
        business["kill_switch_blockers"] = blockers

    def _merge_sms_redirect_config(
        self, current: Optional[Dict[str, Any]], incoming: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Merge SMS redirect config with current values and defaults."""
        current = current or {}
        incoming = incoming or {}
        return {
            "enabled": self._normalize_feature_value(
                incoming.get("enabled"),
                default=self._normalize_feature_value(current.get("enabled"), False),
            ),
            "redirect_url": incoming.get("redirect_url") if "redirect_url" in incoming else current.get("redirect_url"),
            "redirect_message": (
                incoming.get("redirect_message") if "redirect_message" in incoming else current.get("redirect_message")
            ),
        }

    def _merge_feature_flags(self, current: Dict[str, Any], incoming: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Merge incoming feature flags with current values and defaults (including SMS redirect)."""
        incoming = incoming or {}
        current_orders_sms = current.get("orders_sms_redirect") or {}
        current_reservations_sms = current.get("reservations_sms_redirect") or {}
        incoming_orders_sms = incoming.get("orders_sms_redirect")
        incoming_reservations_sms = incoming.get("reservations_sms_redirect")

        return {
            "orders_enabled": self._normalize_feature_value(
                incoming.get("orders_enabled"),
                default=self._normalize_feature_value(current.get("orders_enabled"), True),
            ),
            "reservations_enabled": self._normalize_feature_value(
                incoming.get("reservations_enabled"),
                default=self._normalize_feature_value(current.get("reservations_enabled"), True),
            ),
            "faqs_enabled": self._normalize_feature_value(
                incoming.get("faqs_enabled"),
                default=self._normalize_feature_value(current.get("faqs_enabled"), True),
            ),
            "orders_sms_redirect": self._merge_sms_redirect_config(current_orders_sms, incoming_orders_sms),
            "reservations_sms_redirect": self._merge_sms_redirect_config(
                current_reservations_sms, incoming_reservations_sms
            ),
        }

    @staticmethod
    def validate_sms_redirect_rules(features: Dict[str, Any]) -> None:
        """Validate SMS redirect business rules.

        Rules:
        - orders_sms_redirect.enabled requires orders_enabled = False
        - reservations_sms_redirect.enabled requires reservations_enabled = False
        - URL is required when SMS redirect is enabled
        """
        orders_enabled = features.get("orders_enabled", True)
        reservations_enabled = features.get("reservations_enabled", True)
        orders_sms = features.get("orders_sms_redirect") or {}
        reservations_sms = features.get("reservations_sms_redirect") or {}

        # Orders SMS redirect validation
        if orders_sms.get("enabled"):
            if orders_enabled:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Cannot enable Orders SMS Redirect while Orders capability is enabled. "
                    "Please set orders_enabled=false first.",
                )
            if not orders_sms.get("redirect_url"):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Orders redirect URL is required when Orders SMS Redirect is enabled.",
                )

        # Reservations SMS redirect validation
        if reservations_sms.get("enabled"):
            if reservations_enabled:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Cannot enable Reservations SMS Redirect while Reservations capability is enabled. "
                    "Please set reservations_enabled=false first.",
                )
            if not reservations_sms.get("redirect_url"):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Reservations redirect URL is required when Reservations SMS Redirect is enabled.",
                )

    def _flatten_features_for_db(self, features: Dict[str, Any]) -> Dict[str, Any]:
        """Flatten nested features structure for database update.

        This method preserves explicit None values so callers can clear fields
        (set them to NULL in the database). Fields not present in the input
        are omitted and will not be updated.
        """
        flat: Dict[str, Any] = {}

        # Top-level feature flags: only include keys that are actually present
        if "orders_enabled" in features:
            flat["orders_enabled"] = features["orders_enabled"]
        if "reservations_enabled" in features:
            flat["reservations_enabled"] = features["reservations_enabled"]
        if "faqs_enabled" in features:
            flat["faqs_enabled"] = features["faqs_enabled"]

        # Orders SMS redirect: only process if the caller provided this section
        if "orders_sms_redirect" in features:
            orders_sms = features.get("orders_sms_redirect") or {}
            if "enabled" in orders_sms:
                flat["orders_sms_redirect_enabled"] = orders_sms["enabled"]
            if "redirect_url" in orders_sms:
                flat["orders_redirect_url"] = orders_sms["redirect_url"]
            if "redirect_message" in orders_sms:
                flat["orders_redirect_message"] = orders_sms["redirect_message"]

        # Reservations SMS redirect: only process if the caller provided this section
        if "reservations_sms_redirect" in features:
            reservations_sms = features.get("reservations_sms_redirect") or {}
            if "enabled" in reservations_sms:
                flat["reservations_sms_redirect_enabled"] = reservations_sms["enabled"]
            if "redirect_url" in reservations_sms:
                flat["reservations_redirect_url"] = reservations_sms["redirect_url"]
            if "redirect_message" in reservations_sms:
                flat["reservations_redirect_message"] = reservations_sms["redirect_message"]

        return flat

    # Not used currently. If needed, we can add this validation to business create and update flows later.
    def _validate_feature_forwarding(
        self,
        feature_flags: Dict[str, bool],
        forward_escalations: bool,
        escalation_phone_number: Optional[str],
    ) -> None:
        """Require forwarding when any feature is disabled."""
        any_disabled = not all(feature_flags.values())
        if any_disabled and (not forward_escalations or not escalation_phone_number):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=("forward_escalations and escalation_phone_number are required when any feature is disabled"),
            )

    def _parse_json_fields(self, business: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Parse JSON columns to dicts and normalize operating hours for consistent responses."""
        if not business:
            return business
        for field in ("twilio_details", "deepgram_details", "open_table_details"):
            if business.get(field):
                business[field] = (
                    json.loads(business[field]) if isinstance(business[field], str) else business[field]
                )
        # Build operating_hours object from day columns
        business["operating_hours"] = self._build_operating_hours(business)
        # Remove flat day columns from response (keep only operating_hours object)
        for day in DAYS_OF_WEEK:
            business.pop(f"{day}_open", None)
            business.pop(f"{day}_close", None)
            business.pop(f"{day}_closed", None)
            business.pop(f"{day}_24_hours", None)
        business["timezone"] = self._format_timezone_field(business.get("timezone"))
        if "forward_escalations" in business:
            try:
                business["forward_escalations"] = bool(int(business["forward_escalations"]))
            except (TypeError, ValueError):
                business["forward_escalations"] = False
        if "kill_switch_enabled" in business:
            try:
                business["kill_switch_enabled"] = bool(int(business["kill_switch_enabled"]))
            except (TypeError, ValueError):
                business["kill_switch_enabled"] = False
        else:
            business["kill_switch_enabled"] = False
        features_source = business.get("features")
        if features_source is None and business.get("id") is not None:
            try:
                features_source = self.features_repo.get_by_business_id(int(business["id"]))
            except Exception:
                features_source = None
        features = self._merge_feature_flags(business, features_source)
        business["features"] = features
        business.pop("orders_enabled", None)
        business.pop("reservations_enabled", None)
        business.pop("faqs_enabled", None)
        # Remove flat SMS redirect fields if present
        business.pop("orders_sms_redirect_enabled", None)
        business.pop("orders_redirect_url", None)
        business.pop("orders_redirect_message", None)
        business.pop("reservations_sms_redirect_enabled", None)
        business.pop("reservations_redirect_url", None)
        business.pop("reservations_redirect_message", None)
        self._annotate_kill_switch_fields(business)
        return business

    def _format_timezone_field(self, value: Optional[str]) -> Optional[str]:
        """Format timezone field for API response without validation."""
        if value is None:
            return settings.RESTAURANT_TIMEZONE
        cleaned = str(value).strip()
        return cleaned if cleaned else settings.RESTAURANT_TIMEZONE

    @staticmethod
    def _time_like_to_string(value: Any) -> Optional[str]:
        """Convert datetime.time or timedelta to HH:MM:SS string."""
        if isinstance(value, time):
            return value.strftime("%H:%M:%S")
        if isinstance(value, timedelta):
            total_seconds = int(value.total_seconds()) % 86400
            hours, remainder = divmod(total_seconds, 3600)
            minutes, seconds = divmod(remainder, 60)
            return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        return None

    @staticmethod
    def _format_time_field(value: Any, default: str) -> str:
        """
        Normalize database time values to HH:MM:SS strings for API responses.

        MySQL TIME columns can come back as timedelta objects via some drivers; this ensures
        the response model always receives strings.
        """
        if value is None:
            return default
        if isinstance(value, str):
            return value

        converted = BusinessService._time_like_to_string(value)
        if converted is not None:
            return converted
        return str(value)

    @staticmethod
    def _format_time_field_optional(value: Any) -> Optional[str]:
        """Format time field, returning None if not set."""
        if value is None:
            return None
        if isinstance(value, str):
            return value
        converted = BusinessService._time_like_to_string(value)
        return converted

    def _build_operating_hours(self, business: Dict[str, Any]) -> Dict[str, Any]:
        """Transform day columns into operating_hours object for API response."""
        operating_hours = {}
        for day in DAYS_OF_WEEK:
            operating_hours[day] = {
                "open": self._format_time_field_optional(business.get(f"{day}_open")),
                "close": self._format_time_field_optional(business.get(f"{day}_close")),
                "is_closed": bool(business.get(f"{day}_closed", False)),
                "is_24_hours": bool(business.get(f"{day}_24_hours", False)),
            }
        return operating_hours

    def _flatten_operating_hours(self, operating_hours: Dict[str, Any]) -> Dict[str, Any]:
        """Transform operating_hours object into flat columns for database.

        Priority: is_closed > is_24_hours > open/close times.
        When is_closed=True, times are NULL and is_24_hours=False.
        When is_24_hours=True, times are NULL (ignored anyway).
        """
        flat: Dict[str, Any] = {}
        for day in DAYS_OF_WEEK:
            day_hours = operating_hours.get(day, {})
            if not isinstance(day_hours, dict):
                continue

            is_closed = day_hours.get("is_closed", False)
            is_24_hours = day_hours.get("is_24_hours", False)

            if is_closed:
                # Closed takes priority - clear everything
                flat[f"{day}_open"] = None
                flat[f"{day}_close"] = None
                flat[f"{day}_closed"] = True
                flat[f"{day}_24_hours"] = False
            elif is_24_hours:
                # 24 hours - times are ignored, store NULL for consistency
                flat[f"{day}_open"] = None
                flat[f"{day}_close"] = None
                flat[f"{day}_closed"] = False
                flat[f"{day}_24_hours"] = True
            else:
                # Normal hours
                if "open" in day_hours:
                    flat[f"{day}_open"] = day_hours.get("open")
                if "close" in day_hours:
                    flat[f"{day}_close"] = day_hours.get("close")
                flat[f"{day}_closed"] = False
                flat[f"{day}_24_hours"] = False
        return flat

    def _validate_operating_hours(self, operating_hours: Dict[str, Any]) -> None:
        """Validate operating_hours structure and values."""
        if not isinstance(operating_hours, dict):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="operating_hours must be an object")

        for day in DAYS_OF_WEEK:
            if day not in operating_hours:
                continue
            day_hours = operating_hours[day]
            if not isinstance(day_hours, dict):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST, detail=f"operating_hours.{day} must be an object"
                )

            is_closed = day_hours.get("is_closed", False)
            is_24_hours = day_hours.get("is_24_hours", False)
            if is_closed and is_24_hours:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"operating_hours.{day}: a day cannot be both closed and open 24 hours",
                )
            if not is_closed:
                open_time = day_hours.get("open")
                close_time = day_hours.get("close")
                if open_time:
                    self._normalize_time_field(open_time, f"{day}_open")
                if close_time:
                    self._normalize_time_field(close_time, f"{day}_close")

    def _get_or_404(self, business_id: int) -> Dict[str, Any]:
        """Fetch a business or raise 404."""
        business = self.business_repo.get_by_id(int(business_id))
        if not business:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Business not found")
        return self._parse_json_fields(business) or {}

    def _ensure_unique_name(self, name: str, business_id: Optional[int] = None) -> None:
        """Ensure business name is unique."""
        existing = self.business_repo.get_by_name(name)
        if existing and existing.get("id") != business_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="business name already exists")

    def _ensure_unique_twilio_number(
        self, twilio_phone_number: Optional[str], business_id: Optional[int] = None
    ) -> None:
        """Ensure Twilio phone number is unique when provided."""
        if not twilio_phone_number:
            return
        existing = self.business_repo.get_by_twilio_number(twilio_phone_number)
        if existing and existing.get("id") != business_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="twilio_phone_number already in use by another business",
            )

    # ---------- CRUD operations ----------
    def create_business(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new business with validation."""
        name = self._normalize_name(data.get("name"))
        self._validate_phone_number(data.get("phone_number"), "phone_number")
        self._validate_phone_number(data.get("twilio_phone_number"), "twilio_phone_number")
        self._validate_phone_number(data.get("escalation_phone_number"), "escalation_phone_number")
        self._validate_escalation_forwarding(bool(data.get("forward_escalations")), data.get("escalation_phone_number"))
        self._validate_json_field("twilio_details", data.get("twilio_details"))
        self._validate_json_field("deepgram_details", data.get("deepgram_details"))
        self._validate_json_field("open_table_details", data.get("open_table_details"))
        self._validate_minutes(data.get("forward_minutes"), "forward_minutes")
        self._validate_minutes(data.get("backward_minutes"), "backward_minutes")
        self._validate_seating_capacity(data.get("reservation_seating_capacity"))
        self._validate_advance_days(data.get("reservation_advance_days"))
        timezone_value = self._normalize_timezone(data.get("timezone"))
        self._ensure_unique_name(name)
        self._ensure_unique_twilio_number(data.get("twilio_phone_number"))
        feature_flags = self._merge_feature_flags({}, data.get("features"))

        # Validate SMS redirect business rules
        self.validate_sms_redirect_rules(feature_flags)

        # Flatten features for database update
        flat_feature_flags = self._flatten_features_for_db(feature_flags)

        # Validate and flatten operating_hours if provided
        if "operating_hours" in data:
            self._validate_operating_hours(data["operating_hours"])

        payload: Dict[str, Any] = {
            "name": name,
            "address": data.get("address"),
            "phone_number": data.get("phone_number"),
            "twilio_phone_number": data.get("twilio_phone_number"),
            "twilio_details": data.get("twilio_details"),
            "deepgram_details": data.get("deepgram_details"),
            "open_table_details": data.get("open_table_details"),
            "forward_minutes": data.get("forward_minutes", 0),
            "backward_minutes": data.get("backward_minutes", 0),
            "is_credit_card_required_for_reservation": data.get("is_credit_card_required_for_reservation", False),
            "forward_escalations": data.get("forward_escalations", False),
            "escalation_phone_number": data.get("escalation_phone_number"),
            "kill_switch_enabled": data.get("kill_switch_enabled", False),
            "timezone": timezone_value,
            "reservation_seating_capacity": data.get("reservation_seating_capacity", 50),
            "reservation_advance_days": data.get("reservation_advance_days", 30),
        }

        # Handle operating_hours - flatten to day columns with defaults for missing days
        DEFAULT_OPEN = "09:00:00"
        DEFAULT_CLOSE = "22:00:00"

        if "operating_hours" in data:
            provided_hours = data["operating_hours"]
            # Apply defaults for any missing days to prevent NULL values
            for day in DAYS_OF_WEEK:
                if day in provided_hours and isinstance(provided_hours[day], dict):
                    day_hours = provided_hours[day]
                    is_closed = day_hours.get("is_closed", False)
                    is_24_hours = day_hours.get("is_24_hours", False)

                    if is_closed:
                        # Closed takes priority
                        payload[f"{day}_open"] = None
                        payload[f"{day}_close"] = None
                        payload[f"{day}_closed"] = True
                        payload[f"{day}_24_hours"] = False
                    elif is_24_hours:
                        # 24 hours - no need for open/close times
                        payload[f"{day}_open"] = None
                        payload[f"{day}_close"] = None
                        payload[f"{day}_closed"] = False
                        payload[f"{day}_24_hours"] = True
                    else:
                        # Normal hours with defaults
                        payload[f"{day}_open"] = day_hours.get("open") or DEFAULT_OPEN
                        payload[f"{day}_close"] = day_hours.get("close") or DEFAULT_CLOSE
                        payload[f"{day}_closed"] = False
                        payload[f"{day}_24_hours"] = False
                else:
                    # Day not provided - use defaults
                    payload[f"{day}_open"] = DEFAULT_OPEN
                    payload[f"{day}_close"] = DEFAULT_CLOSE
                    payload[f"{day}_closed"] = False
                    payload[f"{day}_24_hours"] = False
        else:
            # No operating_hours provided - use defaults for all days
            for day in DAYS_OF_WEEK:
                payload[f"{day}_open"] = DEFAULT_OPEN
                payload[f"{day}_close"] = DEFAULT_CLOSE
                payload[f"{day}_closed"] = False
                payload[f"{day}_24_hours"] = False

        try:
            business_id = self.business_repo.create(payload)
            self.features_repo.create_defaults(business_id)
            self.features_repo.update(business_id, flat_feature_flags)
        except Exception as exc:  # pragma: no cover - defensive logging for DB errors
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to create business: {exc}",
            )
        return self._get_or_404(business_id)

    def list_businesss(
        self,
        page: int = 1,
        limit: int = 20,
        search: Optional[str] = None,
        is_credit_card_required: Optional[bool] = None,
        orders_enabled: Optional[bool] = None,
        reservations_enabled: Optional[bool] = None,
        faqs_enabled: Optional[bool] = None,
    ) -> Dict[str, Any]:
        """Return paginated businesss with optional filters."""
        page = max(1, int(page))
        limit = min(100, max(1, int(limit)))
        search_term = (search or "").strip() or None

        try:
            businesss, total = self.business_repo.get_all(
                page,
                limit,
                search_term,
                is_credit_card_required,
                orders_enabled,
                reservations_enabled,
                faqs_enabled,
            )
        except Exception as exc:  # pragma: no cover - defensive logging for DB errors
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to retrieve businesss: {exc}",
            )

        parsed_items = [self._parse_json_fields(item) or {} for item in businesss]
        return {"items": parsed_items, "pagination": build_pagination(page, limit, total)}

    def get_business(self, business_id: int) -> Dict[str, Any]:
        """Get a specific business by ID."""
        return self._get_or_404(int(business_id))

    def update_business(self, business_id: int, data: Dict[str, Any]) -> Dict[str, Any]:
        """Update an existing business with validation."""
        current = self._get_or_404(int(business_id))
        if not data:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No fields provided for update")

        feature_updates = data.pop("features", None)

        # Validate provided fields
        if "name" in data:
            data["name"] = self._normalize_name(data.get("name"))
            if data["name"] != current.get("name"):
                self._ensure_unique_name(data["name"], business_id=int(business_id))
        if "phone_number" in data:
            self._validate_phone_number(data.get("phone_number"), "phone_number")
        if "twilio_phone_number" in data:
            self._validate_phone_number(data.get("twilio_phone_number"), "twilio_phone_number")
            if data.get("twilio_phone_number") != current.get("twilio_phone_number"):
                self._ensure_unique_twilio_number(data.get("twilio_phone_number"), business_id=int(business_id))
        if "escalation_phone_number" in data:
            self._validate_phone_number(data.get("escalation_phone_number"), "escalation_phone_number")
        if "twilio_details" in data:
            self._validate_json_field("twilio_details", data.get("twilio_details"))
        if "deepgram_details" in data:
            self._validate_json_field("deepgram_details", data.get("deepgram_details"))
        if "open_table_details" in data:
            self._validate_json_field("open_table_details", data.get("open_table_details"))
        if "forward_minutes" in data:
            self._validate_minutes(data.get("forward_minutes"), "forward_minutes")
        if "backward_minutes" in data:
            self._validate_minutes(data.get("backward_minutes"), "backward_minutes")
        if "reservation_seating_capacity" in data:
            self._validate_seating_capacity(data.get("reservation_seating_capacity"))
        if "reservation_advance_days" in data:
            self._validate_advance_days(data.get("reservation_advance_days"))
        # Handle operating_hours - validate and flatten to day columns
        if "operating_hours" in data:
            self._validate_operating_hours(data["operating_hours"])
            flat_hours = self._flatten_operating_hours(data["operating_hours"])
            data.update(flat_hours)
            del data["operating_hours"]
        if "timezone" in data:
            data["timezone"] = self._normalize_timezone(data.get("timezone"))

        forward_escalations = bool(data.get("forward_escalations", current.get("forward_escalations", False)))
        escalation_phone_number = data.get("escalation_phone_number", current.get("escalation_phone_number"))
        self._validate_escalation_forwarding(forward_escalations, escalation_phone_number)

        # Guard against kill-switch state drift: if kill switch is currently enabled,
        # forwarding must remain valid unless this update explicitly disables kill switch.
        current_kill_switch_enabled = self._normalize_feature_value(current.get("kill_switch_enabled"), default=False)
        requested_kill_switch = data.get("kill_switch_enabled")
        requested_kill_switch_disabled = requested_kill_switch is not None and not bool(requested_kill_switch)
        if current_kill_switch_enabled and not requested_kill_switch_disabled:
            blockers = self._compute_kill_switch_blockers(forward_escalations, escalation_phone_number)
            if blockers:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={
                        "message": (
                            "Cannot apply update while kill switch is enabled and escalation forwarding would be invalid. "
                            "Disable kill switch first or keep forwarding fully configured."
                        ),
                        "kill_switch_blockers": blockers,
                    },
                )

        merged_features = self._merge_feature_flags(current.get("features", {}), feature_updates)

        # Validate SMS redirect business rules
        self.validate_sms_redirect_rules(merged_features)

        # Flatten features for database update
        flat_features = self._flatten_features_for_db(merged_features)

        try:
            updated = self.business_repo.update(int(business_id), data)
            if feature_updates is not None:
                self.features_repo.create_defaults(int(business_id))
                self.features_repo.update(int(business_id), flat_features)
        except Exception as exc:  # pragma: no cover - defensive logging for DB errors
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to update business: {exc}",
            )

        if not updated and feature_updates is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No fields to update")

        # Return refreshed record with parsed JSON fields
        return self._get_or_404(int(business_id))

    def set_business_kill_switch(self, business_id: int, enabled: bool) -> Dict[str, Any]:
        """Enable or disable kill switch for a single business."""
        current = self._get_or_404(int(business_id))
        current_enabled = self._normalize_feature_value(current.get("kill_switch_enabled"), default=False)
        desired = bool(enabled)

        if desired:
            blockers = current.get("kill_switch_blockers") or self._compute_kill_switch_blockers(
                current.get("forward_escalations"),
                current.get("escalation_phone_number"),
            )
            if blockers:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={
                        "message": "Cannot enable kill switch until escalation forwarding is fully configured",
                        "kill_switch_blockers": blockers,
                    },
                )

        if current_enabled == desired:
            return current

        try:
            updated = self.business_repo.update(int(business_id), {"kill_switch_enabled": desired})
        except Exception as exc:  # pragma: no cover - defensive logging for DB errors
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to update kill switch: {exc}",
            )

        if not updated:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update kill switch",
            )
        return self._get_or_404(int(business_id))

    def set_all_businesss_kill_switch(self, enabled: bool) -> Dict[str, Any]:
        """Bulk update kill switch for all businesss."""
        try:
            targeted_count = self.business_repo.count_businesss()
        except Exception as exc:  # pragma: no cover - defensive logging for DB errors
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to fetch business counts for kill switch update: {exc}",
            )

        desired = bool(enabled)

        if targeted_count == 0:
            return {
                "enabled": desired,
                "targeted_count": 0,
                "eligible_count": 0,
                "updated_count": 0,
                "skipped_count": 0,
                "skipped": [],
                "_changed_businesss": [],
            }

        if not desired:
            try:
                changed_rows = self.business_repo.list_kill_switch_changed_businesss(False)
                updated_count = self.business_repo.set_kill_switch_all(False)
            except Exception as exc:  # pragma: no cover - defensive logging for DB errors
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to bulk disable kill switch: {exc}",
                )
            changed_businesss = [
                {
                    "business_id": int(row["id"]),
                    "business_name": row.get("name"),
                    "previous_enabled": self._normalize_feature_value(row.get("kill_switch_enabled"), default=False),
                }
                for row in changed_rows
            ]
            return {
                "enabled": False,
                "targeted_count": targeted_count,
                "eligible_count": targeted_count,
                "updated_count": updated_count,
                "skipped_count": 0,
                "skipped": [],
                "_changed_businesss": changed_businesss,
            }

        skipped: list[Dict[str, Any]] = []
        try:
            invalid_rows = self.business_repo.list_kill_switch_invalid_businesss()
        except Exception as exc:  # pragma: no cover - defensive logging for DB errors
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to fetch businesss with invalid kill switch forwarding: {exc}",
            )

        for business in invalid_rows:
            blockers = self._compute_kill_switch_blockers(
                business.get("forward_escalations"),
                business.get("escalation_phone_number"),
            )
            if blockers:
                skipped.append(
                    {
                        "business_id": int(business["id"]),
                        "business_name": business.get("name"),
                        "kill_switch_blockers": blockers,
                    }
                )

        eligible_count = max(targeted_count - len(skipped), 0)

        updated_count = 0
        changed_businesss: list[Dict[str, Any]] = []
        if eligible_count > 0:
            try:
                changed_rows = self.business_repo.list_kill_switch_changed_businesss(True, only_redirect_ready=True)
                updated_count = self.business_repo.set_kill_switch_all_redirect_ready(True)
            except Exception as exc:  # pragma: no cover - defensive logging for DB errors
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to bulk enable kill switch: {exc}",
                )
            changed_businesss = [
                {
                    "business_id": int(row["id"]),
                    "business_name": row.get("name"),
                    "previous_enabled": self._normalize_feature_value(row.get("kill_switch_enabled"), default=False),
                }
                for row in changed_rows
            ]

        return {
            "enabled": True,
            "targeted_count": targeted_count,
            "eligible_count": eligible_count,
            "updated_count": updated_count,
            "skipped_count": len(skipped),
            "skipped": skipped,
            "_changed_businesss": changed_businesss,
        }

    def list_kill_switch_candidates(self) -> list[Dict[str, Any]]:
        """Return businesss with kill-switch readiness fields for operational workflows."""
        try:
            return self.business_repo.list_kill_switch_candidates()
        except Exception as exc:  # pragma: no cover - defensive logging for DB errors
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to fetch businesss for kill switch workflows: {exc}",
            )

    def delete_business(self, business_id: int) -> Dict[str, str]:
        """Delete a business."""
        self._get_or_404(int(business_id))
        try:
            deleted = self.business_repo.delete(int(business_id))
        except Exception as exc:  # pragma: no cover - defensive logging for DB errors
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to delete business: {exc}",
            )

        if not deleted:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to delete business")
        return {"message": "Business deleted successfully"}

    # ---------- Lookups and analytics ----------
    def get_business_by_phone(self, phone_number: str) -> Dict[str, Any]:
        """Get business details by its published phone number."""
        if not phone_number:
            return {}
        return self._parse_json_fields(self.business_repo.get_by_phone(phone_number)) or {}

    def get_business_by_twilio(self, twilio_phone_number: str) -> Dict[str, Any]:
        """Lookup business by Twilio phone number."""
        return self._parse_json_fields(self.business_repo.get_by_twilio_number(twilio_phone_number)) or {}

    def get_business_statistics(self, business_id: int) -> Dict[str, Any]:
        """Get aggregated statistics for a business."""
        self._get_or_404(int(business_id))
        try:
            return self.business_repo.get_statistics(int(business_id))
        except Exception as exc:  # pragma: no cover - defensive logging for DB errors
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to retrieve business statistics: {exc}",
            )
