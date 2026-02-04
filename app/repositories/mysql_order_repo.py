"""
MySQL Order Repository for order operations.
"""

import json
from datetime import datetime
from typing import Any, Dict, List, Optional

from app.repositories.mysql_base import MySQLBaseRepository


class MySQLOrderRepository(MySQLBaseRepository):
    """Repository for order data access in MySQL."""

    def create_order(self, user_id: int, order_data: Dict) -> int:
        """
        Create a new order and return order ID.
        """
        query = """
            INSERT INTO Orders (
                user_id, restaurant_id, status, total_amount,
                order_details, customization, created_at, updated_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, NOW(), NOW())
        """
        order_id = self._execute_insert(
            query,
            (
                user_id,
                order_data.get("restaurant_id"),
                order_data.get("status", "pending"),
                order_data.get("total_amount", 0.0),
                json.dumps(order_data.get("order_details", [])),
                json.dumps(order_data.get("customization", {})),
            ),
        )
        return order_id

    def get_latest_order_by_user(self, user_id: int, restaurant_id: Optional[int] = None) -> Dict:
        """Fetch the most recent order for a user, optionally scoped to a restaurant."""
        query = """
            SELECT
                id,
                user_id,
                restaurant_id,
                status,
                total_amount,
                order_details,
                customization,
                created_at,
                updated_at
            FROM Orders
            WHERE user_id = %s AND deleted_at IS NULL
        """
        params: List[Any] = [user_id]
        if restaurant_id is not None:
            query += " AND restaurant_id = %s"
            params.append(restaurant_id)

        query += " ORDER BY created_at DESC LIMIT 1"
        results = self._execute_query(query, tuple(params))
        return results[0] if results else {}

    def get_order_by_id(self, order_id: int) -> Dict:
        query = """
            SELECT
                id,
                user_id,
                restaurant_id,
                status,
                total_amount,
                order_details,
                customization,
                created_at,
                updated_at,
                deleted_at
            FROM Orders
            WHERE id = %s
            LIMIT 1
        """
        results = self._execute_query(query, (order_id,))
        return results[0] if results else {}

    def get_order_by_id_with_verification(self, order_id: int, restaurant_id: int, user_id: int) -> Dict:
        """
        Get order by ID with verification that it belongs to the specified restaurant and user.
        This ensures security by requiring all three parameters to match.

        Args:
            order_id: Order ID
            restaurant_id: Restaurant ID (must match)
            user_id: User ID (must match)

        Returns:
            Order dict if found and matches all criteria, empty dict otherwise
        """
        query = """
            SELECT
                id,
                user_id,
                restaurant_id,
                status,
                total_amount,
                order_details,
                customization,
                created_at,
                updated_at
            FROM Orders
            WHERE id = %s
                AND restaurant_id = %s
                AND user_id = %s
                AND deleted_at IS NULL
            LIMIT 1
        """
        results = self._execute_query(query, (order_id, restaurant_id, user_id))
        return results[0] if results else {}

    def get_order_with_user(self, order_id: int) -> Dict:
        """
        Get order with user details joined.
        Returns restaurant_id for RBAC checks.
        """
        query = """
            SELECT
                o.id,
                o.user_id,
                o.restaurant_id,
                o.status,
                o.total_amount,
                o.order_details,
                o.customization,
                o.created_at,
                o.updated_at,
                o.deleted_at,
                u.name as customer_name,
                u.phone_number as customer_phone,
                u.email as customer_email
            FROM Orders o
            LEFT JOIN Users u ON o.user_id = u.id
            WHERE o.id = %s AND o.deleted_at IS NULL
            LIMIT 1
        """
        results = self._execute_query(query, (order_id,))
        return results[0] if results else {}

    def update_order_details(
        self,
        order_id: int,
        order_details: list,
        customization: Optional[Dict] = None,
        total_amount: Optional[float] = None,
    ) -> int:
        """Update order details/customization/total_amount."""
        fields = ["order_details = %s"]
        params: List[Any] = [json.dumps(order_details)]
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

    # ---------- Dashboard-specific methods ----------

    def get_orders_by_restaurant(
        self,
        restaurant_id: int,
        status: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 100,
        offset: int = 0,
        include_deleted: bool = False,
    ) -> List[Dict[str, Any]]:
        """
        Get orders for a restaurant with optional filters.

        Args:
            restaurant_id: Restaurant ID
            status: Filter by status
            start_date: Filter by start date
            end_date: Filter by end date
            limit: Limit results
            offset: Offset for pagination
            include_deleted: Include soft-deleted orders

        Returns:
            List of orders with customer details
        """
        query = """
            SELECT
                o.id,
                o.user_id,
                o.restaurant_id,
                o.status,
                o.total_amount,
                o.order_details,
                o.customization,
                o.created_at,
                o.updated_at,
                o.deleted_at,
                u.name as customer_name,
                u.phone_number as customer_phone,
                u.email as customer_email
            FROM Orders o
            LEFT JOIN Users u ON o.user_id = u.id
            WHERE o.restaurant_id = %s
        """
        params: List[Any] = [restaurant_id]

        if not include_deleted:
            query += " AND o.deleted_at IS NULL"

        if status:
            query += " AND o.status = %s"
            params.append(status)

        if start_date:
            query += " AND o.created_at >= %s"
            params.append(start_date)

        if end_date:
            query += " AND o.created_at <= %s"
            params.append(end_date)

        query += " ORDER BY o.created_at DESC LIMIT %s OFFSET %s"
        params.extend([limit, offset])

        return self._execute_query(query, tuple(params))

    def count_orders_by_restaurant(
        self,
        restaurant_id: int,
        status: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        include_deleted: bool = False,
    ) -> int:
        """Count orders for a restaurant with optional filters."""
        query = """
            SELECT COUNT(*) as total
            FROM Orders
            WHERE restaurant_id = %s
        """
        params: List[Any] = [restaurant_id]

        if not include_deleted:
            query += " AND deleted_at IS NULL"

        if status:
            query += " AND status = %s"
            params.append(status)

        if start_date:
            query += " AND created_at >= %s"
            params.append(start_date)

        if end_date:
            query += " AND created_at <= %s"
            params.append(end_date)

        results = self._execute_query(query, tuple(params))
        return results[0]["total"] if results else 0

    def update_order(
        self,
        order_id: int,
        status: Optional[str] = None,
        total_amount: Optional[float] = None,
        order_details: Optional[list] = None,
        customization: Optional[Dict] = None,
    ) -> bool:
        """
        Update order fields.

        Args:
            order_id: Order ID
            status: New status
            total_amount: New total amount
            order_details: New order details
            customization: New customization

        Returns:
            True if update succeeded
        """
        fields = []
        params: List[Any] = []

        if status is not None:
            fields.append("status = %s")
            params.append(status)

        if total_amount is not None:
            fields.append("total_amount = %s")
            params.append(total_amount)

        if order_details is not None:
            fields.append("order_details = %s")
            params.append(json.dumps(order_details))

        if customization is not None:
            fields.append("customization = %s")
            params.append(json.dumps(customization))

        if not fields:
            return True  # Nothing to update

        fields.append("updated_at = NOW()")
        params.append(order_id)

        query = f"UPDATE Orders SET {', '.join(fields)} WHERE id = %s AND deleted_at IS NULL"
        affected = self._execute_update(query, tuple(params))
        return affected > 0

    def update_order_status(self, order_id: int, status: str) -> bool:
        """Update order status."""
        query = """
            UPDATE Orders
            SET status = %s, updated_at = NOW()
            WHERE id = %s AND deleted_at IS NULL
        """
        affected = self._execute_update(query, (status, order_id))
        return affected > 0

    def soft_delete_order(self, order_id: int) -> bool:
        """Soft delete an order by setting deleted_at timestamp."""
        query = """
            UPDATE Orders
            SET deleted_at = NOW(), updated_at = NOW()
            WHERE id = %s AND deleted_at IS NULL
        """
        affected = self._execute_update(query, (order_id,))
        return affected > 0

    def restore_order(self, order_id: int) -> bool:
        """Restore a soft-deleted order."""
        query = """
            UPDATE Orders
            SET deleted_at = NULL, updated_at = NOW()
            WHERE id = %s AND deleted_at IS NOT NULL
        """
        affected = self._execute_update(query, (order_id,))
        return affected > 0

    def get_order_restaurant_id(self, order_id: int) -> Optional[int]:
        """Get just the restaurant_id for an order (for RBAC checks)."""
        query = """
            SELECT restaurant_id
            FROM Orders
            WHERE id = %s
            LIMIT 1
        """
        results = self._execute_query(query, (order_id,))
        if results and results[0].get("restaurant_id"):
            return int(results[0]["restaurant_id"])
        return None

    def calculate_revenue_by_restaurant(
        self,
        restaurant_id: int,
        status: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> float:
        """
        Calculate total revenue for a restaurant using SQL SUM aggregation.

        Args:
            restaurant_id: Restaurant ID
            status: Filter by order status (e.g., 'completed')
            start_date: Start date filter
            end_date: End date filter

        Returns:
            Total revenue as float
        """
        query = """
            SELECT COALESCE(SUM(total_amount), 0) as total_revenue
            FROM Orders
            WHERE restaurant_id = %s AND deleted_at IS NULL
        """
        params: List[Any] = [restaurant_id]

        if status:
            query += " AND status = %s"
            params.append(status)

        if start_date:
            query += " AND created_at >= %s"
            params.append(start_date)

        if end_date:
            query += " AND created_at <= %s"
            params.append(end_date)

        results = self._execute_query(query, tuple(params))
        return float(results[0]["total_revenue"]) if results else 0.0

    def get_order_counts_by_status(
        self,
        restaurant_id: int,
        include_deleted: bool = False,
    ) -> Dict[str, int]:
        """
        Get order counts grouped by status in a single query.

        Args:
            restaurant_id: Restaurant ID
            include_deleted: Whether to include soft-deleted orders

        Returns:
            Dictionary mapping status to count
        """
        query = """
            SELECT status, COUNT(*) as count
            FROM Orders
            WHERE restaurant_id = %s
        """
        params: List[Any] = [restaurant_id]

        if not include_deleted:
            query += " AND deleted_at IS NULL"

        query += " GROUP BY status"

        results = self._execute_query(query, tuple(params))
        return {row["status"]: row["count"] for row in results}
