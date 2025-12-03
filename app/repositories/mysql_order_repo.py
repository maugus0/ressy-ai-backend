"""
MySQL Order Repository for order operations.
"""

import json
from typing import Dict

from app.repositories.mysql_base import MySQLBaseRepository


class MySQLOrderRepository(MySQLBaseRepository):
    """Repository for order data access in MySQL."""

    def create_order(self, user_id: int, order_data: Dict) -> int:
        """
        Create a new order and return order ID.
        """
        query = """
            INSERT INTO Orders (user_id, status, total_amount, order_details, customization, created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s, NOW(), NOW())
        """
        order_id = self._execute_insert(
            query,
            (
                user_id,
                order_data.get("status", "pending"),
                order_data.get("total_amount", 0.0),
                json.dumps(order_data.get("order_details", [])),
                json.dumps(order_data.get("customization", {})),
            ),
        )
        return order_id

    def get_latest_order_by_user(self, user_id: int) -> Dict:
        """Fetch the most recent order for a user."""
        query = """
            SELECT
                id,
                user_id,
                status,
                total_amount,
                order_details,
                customization,
                created_at,
                updated_at
            FROM Orders
            WHERE user_id = %s
            ORDER BY created_at DESC
            LIMIT 1
        """
        results = self._execute_query(query, (user_id,))
        return results[0] if results else {}

    def get_order_by_id(self, order_id: int) -> Dict:
        query = """
            SELECT
                id,
                user_id,
                status,
                total_amount,
                order_details,
                customization,
                created_at,
                updated_at
            FROM Orders
            WHERE id = %s
            LIMIT 1
        """
        results = self._execute_query(query, (order_id,))
        return results[0] if results else {}

    def update_order_details(
        self, order_id: int, order_details: list, customization: Dict | None = None, total_amount: float | None = None
    ) -> int:
        """Update order details/customization/total_amount."""
        fields = ["order_details = %s"]
        params = [json.dumps(order_details)]
        if customization is not None:
            fields.append("customization = %s")
            params.append(json.dumps(customization))
        if total_amount is not None:
            fields.append("total_amount = %s")
            params.append(total_amount)
        fields.append("updated_at = NOW()")
        params.append(order_id)
        query = f"UPDATE Orders SET {', '.join(fields)} WHERE id = %s"
        return self._execute_update(query, tuple(params))

    def create_order_details(self, order_id: int, menu_item_id: int) -> int:
        """
        Create order detail entry.
        """
        query = """
            INSERT INTO Order_Details (order_id, menu_item_id, created_at, updated_at)
            VALUES (%s, %s, NOW(), NOW())
        """
        return self._execute_insert(query, (order_id, menu_item_id))
