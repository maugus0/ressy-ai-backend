"""
MySQL repository for restaurant feature flags.
"""

from typing import Any, Dict, Optional

from app.repositories.mysql_base import MySQLBaseRepository


class MySQLRestaurantFeaturesRepository(MySQLBaseRepository):
    """Repository for Restaurant_Features CRUD and lookups."""

    def get_by_restaurant_id(self, restaurant_id: int) -> Optional[Dict[str, Any]]:
        query = """
            SELECT
                restaurant_id,
                orders_enabled,
                reservations_enabled,
                faqs_enabled,
                created_at,
                updated_at
            FROM Restaurant_Features
            WHERE restaurant_id = %s
            LIMIT 1
        """
        results = self._execute_query(query, (restaurant_id,))
        return results[0] if results else None

    def create_defaults(self, restaurant_id: int) -> None:
        query = """
            INSERT IGNORE INTO Restaurant_Features (restaurant_id)
            VALUES (%s)
        """
        self._execute_insert(query, (restaurant_id,))

    def update(self, restaurant_id: int, data: Dict[str, Any]) -> bool:
        update_fields = []
        params = []

        if "orders_enabled" in data:
            update_fields.append("orders_enabled = %s")
            params.append(data["orders_enabled"])
        if "reservations_enabled" in data:
            update_fields.append("reservations_enabled = %s")
            params.append(data["reservations_enabled"])
        if "faqs_enabled" in data:
            update_fields.append("faqs_enabled = %s")
            params.append(data["faqs_enabled"])

        if not update_fields:
            return False

        update_fields.append("updated_at = NOW()")
        params.append(restaurant_id)

        query = f"""
            UPDATE Restaurant_Features
            SET {', '.join(update_fields)}
            WHERE restaurant_id = %s
        """
        affected = self._execute_update(query, tuple(params))
        return affected > 0
