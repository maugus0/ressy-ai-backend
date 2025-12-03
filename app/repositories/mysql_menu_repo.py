"""
MySQL Menu Repository for fetching available menu items.
"""

import json
from typing import Any, Dict, List

from app.repositories.mysql_base import MySQLBaseRepository


class MySQLMenuRepository(MySQLBaseRepository):
    """Repository for menu data access in MySQL."""

    def get_available_items_by_restaurant(self, restaurant_id: int) -> List[Dict]:
        """
        Get all available menu items for a restaurant.
        Only returns items where is_available = TRUE.
        """
        query = """
            SELECT
                id,
                restaurant_id,
                category,
                sub_category,
                item_name,
                item_desc,
                price,
                avg_prep_time,
                suggested_items,
                is_available,
                is_special,
                created_at,
                updated_at
            FROM Menus
            WHERE restaurant_id = %s
              AND is_available = TRUE
            ORDER BY category, sub_category, item_name
        """
        return self._execute_query(query, (restaurant_id,))

    def get_item_by_name(self, restaurant_id: int, item_name: str) -> Dict:
        """
        Get menu item by name (for order details).
        """
        query = """
            SELECT id, restaurant_id, item_name, price
            FROM Menus
            WHERE restaurant_id = %s
              AND LOWER(item_name) LIKE LOWER(%s)
              AND is_available = TRUE
            LIMIT 1
        """
        results = self._execute_query(query, (restaurant_id, f"%{item_name}%"))
        return results[0] if results else None

    def create_menu(self, restaurant_id: int, data: Dict[str, Any]) -> int:
        """Create a new menu item."""
        query = """
            INSERT INTO Menus (restaurant_id, category, sub_category, item_name, item_desc, price, avg_prep_time, suggested_items, is_available, is_special, created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
        """
        return self._execute_insert(
            query,
            (
                restaurant_id,
                data.get("category"),
                data.get("sub_category"),
                data.get("item_name"),
                data.get("item_desc"),
                data.get("price", 0.0),
                data.get("avg_prep_time"),
                json.dumps(data.get("suggested_items")),
                data.get("is_available", True),
                data.get("is_special", False),
            ),
        )

    def get_menus_by_restaurant(self, restaurant_id: int) -> List[Dict]:
        query = """
            SELECT * FROM Menus
            WHERE restaurant_id = %s
            ORDER BY category, sub_category, item_name
        """
        return self._execute_query(query, (restaurant_id,))

    def get_menu_by_id(self, restaurant_id: int, menu_id: int) -> Dict:
        query = "SELECT * FROM Menus WHERE restaurant_id = %s AND id = %s LIMIT 1"
        results = self._execute_query(query, (restaurant_id, menu_id))
        return results[0] if results else {}

    def update_menu(self, restaurant_id: int, menu_id: int, data: Dict[str, Any]) -> int:
        fields = []
        params = []
        for key in [
            "category",
            "sub_category",
            "item_name",
            "item_desc",
            "price",
            "avg_prep_time",
            "suggested_items",
            "is_available",
            "is_special",
        ]:
            if key in data:
                value = data[key]
                if key == "suggested_items":
                    value = json.dumps(value)
                fields.append(f"{key} = %s")
                params.append(value)
        if not fields:
            return 0
        fields.append("updated_at = NOW()")
        params.extend([restaurant_id, menu_id])
        query = f"UPDATE Menus SET {', '.join(fields)} WHERE restaurant_id = %s AND id = %s"
        return self._execute_update(query, tuple(params))

    def delete_menu(self, restaurant_id: int, menu_id: int) -> int:
        return self._execute_update("DELETE FROM Menus WHERE restaurant_id = %s AND id = %s", (restaurant_id, menu_id))

    def create_special(self, restaurant_id: int, data: Dict[str, Any]) -> int:
        payload = dict(data)
        payload["is_special"] = True
        return self.create_menu(restaurant_id, payload)

    def get_specials_by_restaurant(self, restaurant_id: int) -> List[Dict]:
        query = """
            SELECT * FROM Menus
            WHERE restaurant_id = %s AND is_special = TRUE
            ORDER BY created_at DESC
        """
        return self._execute_query(query, (restaurant_id,))

    def get_special_by_id(self, restaurant_id: int, special_id: int) -> Dict:
        return self.get_menu_by_id(restaurant_id, special_id)

    def update_special(self, restaurant_id: int, special_id: int, data: Dict[str, Any]) -> int:
        payload = dict(data)
        payload["is_special"] = True
        return self.update_menu(restaurant_id, special_id, payload)

    def delete_special(self, restaurant_id: int, special_id: int) -> int:
        return self.delete_menu(restaurant_id, special_id)
