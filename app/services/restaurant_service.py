import json
import re
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

    def _validate_minutes(self, minutes: Optional[int], field_name: str) -> None:
        """Validate minute values are non-negative integers."""
        if minutes is None:
            return
        if minutes < 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail=f"{field_name} must be a non-negative integer"
            )

    def _parse_json_fields(self, restaurant: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Parse JSON columns to dicts for consistent responses."""
        if not restaurant:
            return restaurant
        for field in ("twilio_details", "deepgram_details", "open_table_details"):
            if restaurant.get(field):
                restaurant[field] = (
                    json.loads(restaurant[field]) if isinstance(restaurant[field], str) else restaurant[field]
                )
        return restaurant

    def _get_or_404(self, restaurant_id: int) -> Dict[str, Any]:
        """Fetch a restaurant or raise 404."""
        restaurant = self.restaurant_repo.get_by_id(int(restaurant_id))
        if not restaurant:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Restaurant not found")
        return self._parse_json_fields(restaurant) or {}

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
        self._get_or_404(int(restaurant_id))
        if not data:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No fields provided for update")

        # Validate provided fields
        if "name" in data:
            data["name"] = self._normalize_name(data.get("name"))
        if "phone_number" in data:
            self._validate_phone_number(data.get("phone_number"), "phone_number")
        if "twilio_phone_number" in data:
            self._validate_phone_number(data.get("twilio_phone_number"), "twilio_phone_number")
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
