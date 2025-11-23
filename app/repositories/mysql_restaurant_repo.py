"""
MySQL Restaurant Repository for multitenant operations.
"""

import json
from typing import Any, Dict, List, Optional

from app.repositories.mysql_base import MySQLBaseRepository


class MySQLRestaurantRepository(MySQLBaseRepository):
    """Repository for restaurant data access in MySQL."""

    def get_by_twilio_number(self, twilio_phone_number: str) -> Optional[Dict]:
        """
        Get restaurant by Twilio phone number.
        Used for multitenant call routing.
        """
        query = """
            SELECT
                id,
                name,
                address,
                phone_number,
                twilio_phone_number,
                twilio_details,
                deepgram_details,
                open_table_details,
                forward_minutes,
                backward_minutes,
                is_credit_card_required_for_reservation,
                created_at,
                updated_at
            FROM Restaurants
            WHERE twilio_phone_number = %s
            LIMIT 1
        """
        results = self._execute_query(query, (twilio_phone_number,))
        return results[0] if results else None

    def create(self, data: Dict[str, Any]) -> int:
        query = """
            INSERT INTO Restaurants (
                name,
                address,
                phone_number,
                twilio_phone_number,
                twilio_details,
                deepgram_details,
                open_table_details,
                forward_minutes,
                backward_minutes,
                is_credit_card_required_for_reservation,
                created_at,
                updated_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
        """
        return self._execute_insert(
            query,
            (
                data.get("name"),
                data.get("address"),
                data.get("phone_number"),
                data.get("twilio_phone_number"),
                json.dumps(data.get("twilio_details")),
                json.dumps(data.get("deepgram_details")),
                json.dumps(data.get("open_table_details")),
                data.get("forward_minutes", 0),
                data.get("backward_minutes", 0),
                data.get("is_credit_card_required_for_reservation", False),
            ),
        )

    def get_by_id(self, restaurant_id: int) -> Dict[str, Any]:
        results = self._execute_query("SELECT * FROM Restaurants WHERE id = %s LIMIT 1", (restaurant_id,))
        return results[0] if results else {}

    def get_all(self) -> List[Dict[str, Any]]:
        return self._execute_query("SELECT * FROM Restaurants ORDER BY created_at DESC")

    def update(self, restaurant_id: int, data: Dict[str, Any]) -> int:
        fields = []
        params = []
        for key in [
            "name",
            "address",
            "phone_number",
            "twilio_phone_number",
            "twilio_details",
            "deepgram_details",
            "open_table_details",
            "forward_minutes",
            "backward_minutes",
            "is_credit_card_required_for_reservation",
        ]:
            if key in data:
                value = data[key]
                if key in {"twilio_details", "deepgram_details", "open_table_details"}:
                    value = json.dumps(value)
                fields.append(f"{key} = %s")
                params.append(value)
        if not fields:
            return 0
        fields.append("updated_at = NOW()")
        params.extend([restaurant_id])
        query = f"UPDATE Restaurants SET {', '.join(fields)} WHERE id = %s"
        return self._execute_update(query, tuple(params))

    def delete(self, restaurant_id: int) -> int:
        return self._execute_update("DELETE FROM Restaurants WHERE id = %s", (restaurant_id,))

    def get_by_phone(self, phone_number: str) -> Dict[str, Any]:
        results = self._execute_query("SELECT * FROM Restaurants WHERE phone_number = %s LIMIT 1", (phone_number,))
        return results[0] if results else {}
