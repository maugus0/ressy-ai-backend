import json
import re
from datetime import datetime, time, timedelta
from typing import Any, Dict, Optional

from fastapi import HTTPException, status

from app.repositories.mysql_restaurant_repo import MySQLRestaurantRepository
from app.services.admin_user_common import build_pagination


class RestaurantService:
    """Service layer for restaurant CRUD and lookups."""

    def __init__(self, restaurant_repo: Optional[MySQLRestaurantRepository] = None):
        self.restaurant_repo = restaurant_repo or MySQLRestaurantRepository()

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

        # Accept native time/timedelta objects defensively
        if isinstance(value, time):
            return value.strftime("%H:%M:%S")
        if isinstance(value, timedelta):
            total_seconds = int(value.total_seconds()) % 86400
            hours, remainder = divmod(total_seconds, 3600)
            minutes, seconds = divmod(remainder, 60)
            return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

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

    def _parse_json_fields(self, restaurant: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Parse JSON columns to dicts and normalize operating hours for consistent responses."""
        if not restaurant:
            return restaurant
        for field in ("twilio_details", "deepgram_details", "open_table_details"):
            if restaurant.get(field):
                restaurant[field] = (
                    json.loads(restaurant[field]) if isinstance(restaurant[field], str) else restaurant[field]
                )
        restaurant["opening_time"] = self._format_time_field(restaurant.get("opening_time"), default="09:00:00")
        restaurant["closing_time"] = self._format_time_field(restaurant.get("closing_time"), default="22:00:00")
        return restaurant

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
        if isinstance(value, time):
            return value.strftime("%H:%M:%S")
        if isinstance(value, timedelta):
            total_seconds = int(value.total_seconds()) % 86400
            hours, remainder = divmod(total_seconds, 3600)
            minutes, seconds = divmod(remainder, 60)
            return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        return str(value)

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
        self._validate_json_field("twilio_details", data.get("twilio_details"))
        self._validate_json_field("deepgram_details", data.get("deepgram_details"))
        self._validate_json_field("open_table_details", data.get("open_table_details"))
        self._validate_minutes(data.get("forward_minutes"), "forward_minutes")
        self._validate_minutes(data.get("backward_minutes"), "backward_minutes")
        opening_time = self._normalize_time_field(data.get("opening_time"), "opening_time", default="09:00:00")
        closing_time = self._normalize_time_field(data.get("closing_time"), "closing_time", default="22:00:00")
        self._ensure_unique_name(name)
        self._ensure_unique_twilio_number(data.get("twilio_phone_number"))

        payload = {
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
            "opening_time": opening_time,
            "closing_time": closing_time,
        }

        try:
            restaurant_id = self.restaurant_repo.create(payload)
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
    ) -> Dict[str, Any]:
        """Return paginated restaurants with optional filters."""
        page = max(1, int(page))
        limit = min(100, max(1, int(limit)))
        search_term = (search or "").strip() or None

        try:
            restaurants, total = self.restaurant_repo.get_all(page, limit, search_term, is_credit_card_required)
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
        if "opening_time" in data:
            data["opening_time"] = self._normalize_time_field(data.get("opening_time"), "opening_time", allow_none=True)
        if "closing_time" in data:
            data["closing_time"] = self._normalize_time_field(data.get("closing_time"), "closing_time", allow_none=True)

        try:
            updated = self.restaurant_repo.update(int(restaurant_id), data)
        except Exception as exc:  # pragma: no cover - defensive logging for DB errors
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to update restaurant: {exc}",
            )

        if not updated:
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
