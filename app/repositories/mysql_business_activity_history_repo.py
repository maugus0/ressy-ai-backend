"""
MySQL Activity History Repository.
Handles CRUD operations for order and reservation activity history/audit logs.
"""

import json
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional

from app.repositories.mysql_base import MySQLBaseRepository
from app.utils.timezone import isoformat_z


class DecimalEncoder(json.JSONEncoder):
    """Custom JSON encoder that handles Decimal types."""

    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        if isinstance(obj, datetime):
            return isoformat_z(obj)
        return super().default(obj)


class MySQLActivityHistoryRepository(MySQLBaseRepository):
    """Repository for user activity history operations."""

    def create_history_entry(
        self,
        activity_type: str,
        action: str,
        business_id: int,
        user_id: Optional[int] = None,
        order_id: Optional[int] = None,
        booking_id: Optional[int] = None,
        previous_value: Optional[Dict[str, Any]] = None,
        new_value: Optional[Dict[str, Any]] = None,
        change_summary: Optional[str] = None,
    ) -> int:
        """
        Create a new activity history entry.

        Args:
            activity_type: Type of activity ('order' or 'reservation')
            action: Action performed (created, updated, cancelled, status_changed, etc.)
            business_id: Restaurant ID for RBAC
            user_id: User ID (from Users table)
            order_id: Associated order ID (if applicable)
            booking_id: Associated reservation ID (if applicable)
            previous_value: Previous state before change (as dict)
            new_value: New state after change (as dict)
            change_summary: Human-readable summary of the change

        Returns:
            Created history entry ID
        """
        query = """
            INSERT INTO Business_User_Activity_History
            (user_id, activity_type, order_id, booking_id, action,
             previous_value, new_value, change_summary, business_id, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
        """
        return self._execute_insert(
            query,
            (
                user_id,
                activity_type,
                order_id,
                booking_id,
                action,
                json.dumps(previous_value, cls=DecimalEncoder) if previous_value else None,
                json.dumps(new_value, cls=DecimalEncoder) if new_value else None,
                (change_summary or "")[:500],
                business_id,
            ),
        )

    def get_history_by_order(
        self,
        order_id: int,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """
        Get activity history for a specific order.

        Args:
            order_id: Order ID
            limit: Maximum results
            offset: Pagination offset

        Returns:
            List of history entries
        """
        query = """
            SELECT
                h.id,
                h.user_id,
                h.activity_type,
                h.order_id,
                h.booking_id,
                h.action,
                h.previous_value,
                h.new_value,
                h.change_summary,
                h.business_id,
                h.created_at,
                u.name as performed_by_name,
                u.email as performed_by_email
            FROM Business_User_Activity_History h
            LEFT JOIN Users u ON h.user_id = u.id
            WHERE h.order_id = %s
            ORDER BY h.created_at DESC
            LIMIT %s OFFSET %s
        """
        results = self._execute_query(query, (order_id, limit, offset))
        return self._parse_json_fields(results)

    def get_history_by_reservation(
        self,
        booking_id: int,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """
        Get activity history for a specific reservation.

        Args:
            booking_id: Reservation ID
            limit: Maximum results
            offset: Pagination offset

        Returns:
            List of history entries
        """
        query = """
            SELECT
                h.id,
                h.user_id,
                h.activity_type,
                h.order_id,
                h.booking_id,
                h.action,
                h.previous_value,
                h.new_value,
                h.change_summary,
                h.business_id,
                h.created_at,
                u.name as performed_by_name,
                u.email as performed_by_email
            FROM Business_User_Activity_History h
            LEFT JOIN Users u ON h.user_id = u.id
            WHERE h.booking_id = %s
            ORDER BY h.created_at DESC
            LIMIT %s OFFSET %s
        """
        results = self._execute_query(query, (booking_id, limit, offset))
        return self._parse_json_fields(results)

    def count_history_by_order(self, order_id: int) -> int:
        """Count history entries for an order."""
        query = """
            SELECT COUNT(*) as total
            FROM Business_User_Activity_History
            WHERE order_id = %s
        """
        results = self._execute_query(query, (order_id,))
        return results[0]["total"] if results else 0

    def count_history_by_reservation(self, booking_id: int) -> int:
        """Count history entries for a reservation."""
        query = """
            SELECT COUNT(*) as total
            FROM Business_User_Activity_History
            WHERE booking_id = %s
        """
        results = self._execute_query(query, (booking_id,))
        return results[0]["total"] if results else 0

    def get_order_business_id(self, order_id: int) -> Optional[int]:
        """Get business_id for an order (for RBAC)."""
        query = """
            SELECT business_id
            FROM Business_Orders
            WHERE id = %s
            LIMIT 1
        """
        results = self._execute_query(query, (order_id,))
        if results and results[0].get("business_id"):
            return int(results[0]["business_id"])
        return None

    def get_reservation_business_id(self, booking_id: int) -> Optional[int]:
        """Get business_id for a reservation (for RBAC)."""
        query = """
            SELECT sb.business_id
            FROM Bookings r
            INNER JOIN Slot_Bookings sb ON r.slot_booking_id = sb.id
            WHERE r.id = %s
            LIMIT 1
        """
        results = self._execute_query(query, (booking_id,))
        if results and results[0].get("business_id"):
            return int(results[0]["business_id"])
        return None

    def _parse_json_fields(self, results: List[Dict]) -> List[Dict]:
        """Parse JSON string fields back to dicts."""
        parsed = []
        for row in results:
            row_copy = dict(row)
            for field in ["previous_value", "new_value"]:
                if row_copy.get(field) and isinstance(row_copy[field], str):
                    try:
                        row_copy[field] = json.loads(row_copy[field])
                    except (json.JSONDecodeError, TypeError):
                        pass
            # Convert datetime to ISO format string
            if isinstance(row_copy.get("created_at"), datetime):
                row_copy["created_at"] = isoformat_z(row_copy["created_at"])
            parsed.append(row_copy)
        return parsed
