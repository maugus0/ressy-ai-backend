import json
import re
from datetime import datetime, time, timedelta
from typing import Any, Dict, Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import HTTPException, status

from app.config import settings
from app.repositories.mysql_restaurant_features_repo import MySQLRestaurantFeaturesRepository
from app.repositories.mysql_restaurant_repo import MySQLRestaurantRepository
from app.services.admin_user_common import build_pagination
from app.utils.restaurant_hours import DAYS_OF_WEEK


class RestaurantService:
    """Service layer for restaurant CRUD and lookups."""

    def __init__(
        self,
        restaurant_repo: Optional[MySQLRestaurantRepository] = None,
        features_repo: Optional[MySQLRestaurantFeaturesRepository] = None,
    ):
        self.restaurant_repo = restaurant_repo or MySQLRestaurantRepository()
        self.features_repo = features_repo or MySQLRestaurantFeaturesRepository()

    # ---------- Validation helpers ----------
    def _normalize_name(self, name: Optional[str]) -> str:
        """Validate and normalize restaurant name."""
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
        if not re.match(r"^[\d\s\-\+\(\)]+$", phone_number):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid {field_name} format")

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
                    detail="Orders capability must be disabled when Orders SMS Redirect is enabled.",
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
                    detail="Reservations capability must be disabled when Reservations SMS Redirect is enabled.",
                )
            if not reservations_sms.get("redirect_url"):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Reservations redirect URL is required when Reservations SMS Redirect is enabled.",
                )

    def _flatten_features_for_db(self, features: Dict[str, Any]) -> Dict[str, Any]:
        """Flatten nested features structure for database update."""
        flat = {
            "orders_enabled": features.get("orders_enabled"),
            "reservations_enabled": features.get("reservations_enabled"),
            "faqs_enabled": features.get("faqs_enabled"),
        }
        orders_sms = features.get("orders_sms_redirect") or {}
        reservations_sms = features.get("reservations_sms_redirect") or {}

        if orders_sms:
            flat["orders_sms_redirect_enabled"] = orders_sms.get("enabled", False)
            if "redirect_url" in orders_sms:
                flat["orders_redirect_url"] = orders_sms.get("redirect_url")
            if "redirect_message" in orders_sms:
                flat["orders_redirect_message"] = orders_sms.get("redirect_message")

        if reservations_sms:
            flat["reservations_sms_redirect_enabled"] = reservations_sms.get("enabled", False)
            if "redirect_url" in reservations_sms:
                flat["reservations_redirect_url"] = reservations_sms.get("redirect_url")
            if "redirect_message" in reservations_sms:
                flat["reservations_redirect_message"] = reservations_sms.get("redirect_message")

        return {k: v for k, v in flat.items() if v is not None}

    # Not used currently. If needed, we can add this validation to restaurant create and update flows later.
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

    def _parse_json_fields(self, restaurant: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Parse JSON columns to dicts and normalize operating hours for consistent responses."""
        if not restaurant:
            return restaurant
        for field in ("twilio_details", "deepgram_details", "open_table_details"):
            if restaurant.get(field):
                restaurant[field] = (
                    json.loads(restaurant[field]) if isinstance(restaurant[field], str) else restaurant[field]
                )
        # Build operating_hours object from day columns
        restaurant["operating_hours"] = self._build_operating_hours(restaurant)
        # Remove flat day columns from response (keep only operating_hours object)
        for day in DAYS_OF_WEEK:
            restaurant.pop(f"{day}_open", None)
            restaurant.pop(f"{day}_close", None)
            restaurant.pop(f"{day}_closed", None)
            restaurant.pop(f"{day}_24_hours", None)
        restaurant["timezone"] = self._format_timezone_field(restaurant.get("timezone"))
        if "forward_escalations" in restaurant:
            try:
                restaurant["forward_escalations"] = bool(int(restaurant["forward_escalations"]))
            except (TypeError, ValueError):
                restaurant["forward_escalations"] = False
        features_source = restaurant.get("features")
        if features_source is None and restaurant.get("id") is not None:
            try:
                features_source = self.features_repo.get_by_restaurant_id(int(restaurant["id"]))
            except Exception:
                features_source = None
        features = self._merge_feature_flags(restaurant, features_source)
        restaurant["features"] = features
        restaurant.pop("orders_enabled", None)
        restaurant.pop("reservations_enabled", None)
        restaurant.pop("faqs_enabled", None)
        # Remove flat SMS redirect fields if present
        restaurant.pop("orders_sms_redirect_enabled", None)
        restaurant.pop("orders_redirect_url", None)
        restaurant.pop("orders_redirect_message", None)
        restaurant.pop("reservations_sms_redirect_enabled", None)
        restaurant.pop("reservations_redirect_url", None)
        restaurant.pop("reservations_redirect_message", None)
        return restaurant

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

        converted = RestaurantService._time_like_to_string(value)
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
        converted = RestaurantService._time_like_to_string(value)
        return converted

    def _build_operating_hours(self, restaurant: Dict[str, Any]) -> Dict[str, Any]:
        """Transform day columns into operating_hours object for API response."""
        operating_hours = {}
        for day in DAYS_OF_WEEK:
            operating_hours[day] = {
                "open": self._format_time_field_optional(restaurant.get(f"{day}_open")),
                "close": self._format_time_field_optional(restaurant.get(f"{day}_close")),
                "is_closed": bool(restaurant.get(f"{day}_closed", False)),
                "is_24_hours": bool(restaurant.get(f"{day}_24_hours", False)),
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

    def _get_or_404(self, restaurant_id: int) -> Dict[str, Any]:
        """Fetch a restaurant or raise 404."""
        restaurant = self.restaurant_repo.get_by_id(int(restaurant_id))
        if not restaurant:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Restaurant not found")
        return self._parse_json_fields(restaurant) or {}

    def _ensure_unique_name(self, name: str, restaurant_id: Optional[int] = None) -> None:
        """Ensure restaurant name is unique."""
        existing = self.restaurant_repo.get_by_name(name)
        if existing and existing.get("id") != restaurant_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="restaurant name already exists")

    def _ensure_unique_twilio_number(
        self, twilio_phone_number: Optional[str], restaurant_id: Optional[int] = None
    ) -> None:
        """Ensure Twilio phone number is unique when provided."""
        if not twilio_phone_number:
            return
        existing = self.restaurant_repo.get_by_twilio_number(twilio_phone_number)
        if existing and existing.get("id") != restaurant_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="twilio_phone_number already in use by another restaurant",
            )

    # ---------- CRUD operations ----------
    def create_restaurant(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new restaurant with validation."""
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
            restaurant_id = self.restaurant_repo.create(payload)
            self.features_repo.create_defaults(restaurant_id)
            self.features_repo.update(restaurant_id, flat_feature_flags)
        except Exception as exc:  # pragma: no cover - defensive logging for DB errors
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to create restaurant: {exc}",
            )
        return self._get_or_404(restaurant_id)

    def list_restaurants(
        self,
        page: int = 1,
        limit: int = 20,
        search: Optional[str] = None,
        is_credit_card_required: Optional[bool] = None,
        orders_enabled: Optional[bool] = None,
        reservations_enabled: Optional[bool] = None,
        faqs_enabled: Optional[bool] = None,
    ) -> Dict[str, Any]:
        """Return paginated restaurants with optional filters."""
        page = max(1, int(page))
        limit = min(100, max(1, int(limit)))
        search_term = (search or "").strip() or None

        try:
            restaurants, total = self.restaurant_repo.get_all(
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
                detail=f"Failed to retrieve restaurants: {exc}",
            )

        parsed_items = [self._parse_json_fields(item) or {} for item in restaurants]
        return {"items": parsed_items, "pagination": build_pagination(page, limit, total)}

    def get_restaurant(self, restaurant_id: int) -> Dict[str, Any]:
        """Get a specific restaurant by ID."""
        return self._get_or_404(int(restaurant_id))

    def update_restaurant(self, restaurant_id: int, data: Dict[str, Any]) -> Dict[str, Any]:
        """Update an existing restaurant with validation."""
        current = self._get_or_404(int(restaurant_id))
        if not data:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No fields provided for update")

        feature_updates = data.pop("features", None)

        # Validate provided fields
        if "name" in data:
            data["name"] = self._normalize_name(data.get("name"))
            if data["name"] != current.get("name"):
                self._ensure_unique_name(data["name"], restaurant_id=int(restaurant_id))
        if "phone_number" in data:
            self._validate_phone_number(data.get("phone_number"), "phone_number")
        if "twilio_phone_number" in data:
            self._validate_phone_number(data.get("twilio_phone_number"), "twilio_phone_number")
            if data.get("twilio_phone_number") != current.get("twilio_phone_number"):
                self._ensure_unique_twilio_number(data.get("twilio_phone_number"), restaurant_id=int(restaurant_id))
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

        merged_features = self._merge_feature_flags(current.get("features", {}), feature_updates)

        # Validate SMS redirect business rules
        self.validate_sms_redirect_rules(merged_features)

        # Flatten features for database update
        flat_features = self._flatten_features_for_db(merged_features)

        try:
            updated = self.restaurant_repo.update(int(restaurant_id), data)
            if feature_updates is not None:
                self.features_repo.create_defaults(int(restaurant_id))
                self.features_repo.update(int(restaurant_id), flat_features)
        except Exception as exc:  # pragma: no cover - defensive logging for DB errors
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to update restaurant: {exc}",
            )

        if not updated and feature_updates is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No fields to update")

        # Return refreshed record with parsed JSON fields
        return self._get_or_404(int(restaurant_id))

    def delete_restaurant(self, restaurant_id: int) -> Dict[str, str]:
        """Delete a restaurant."""
        self._get_or_404(int(restaurant_id))
        try:
            deleted = self.restaurant_repo.delete(int(restaurant_id))
        except Exception as exc:  # pragma: no cover - defensive logging for DB errors
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to delete restaurant: {exc}",
            )

        if not deleted:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to delete restaurant")
        return {"message": "Restaurant deleted successfully"}

    # ---------- Lookups and analytics ----------
    def get_restaurant_by_phone(self, phone_number: str) -> Dict[str, Any]:
        """Get restaurant details by its published phone number."""
        if not phone_number:
            return {}
        return self._parse_json_fields(self.restaurant_repo.get_by_phone(phone_number)) or {}

    def get_restaurant_by_twilio(self, twilio_phone_number: str) -> Dict[str, Any]:
        """Lookup restaurant by Twilio phone number."""
        return self._parse_json_fields(self.restaurant_repo.get_by_twilio_number(twilio_phone_number)) or {}

    def get_restaurant_statistics(self, restaurant_id: int) -> Dict[str, Any]:
        """Get aggregated statistics for a restaurant."""
        self._get_or_404(int(restaurant_id))
        try:
            return self.restaurant_repo.get_statistics(int(restaurant_id))
        except Exception as exc:  # pragma: no cover - defensive logging for DB errors
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to retrieve restaurant statistics: {exc}",
            )
