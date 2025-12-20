"""
MySQL Activity History Repository.
Handles CRUD operations for order and reservation activity history/audit logs.
"""

import json
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional

from app.repositories.mysql_base import MySQLBaseRepository


class DecimalEncoder(json.JSONEncoder):
    """Custom JSON encoder that handles Decimal types."""

    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)


class MySQLActivityHistoryRepository(MySQLBaseRepository):
    """Repository for user activity history operations."""

    def create_history_entry(
        self,
        activity_type: str,
        action: str,
        restaurant_id: int,
        user_id: Optional[int] = None,
        actor_uuid: Optional[str] = None,
        actor_type: str = "user",
        order_id: Optional[int] = None,
        reservation_id: Optional[int] = None,
        previous_value: Optional[Dict[str, Any]] = None,
        new_value: Optional[Dict[str, Any]] = None,
        change_summary: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> int:
        """
        Create a new activity history entry.

        Args:
            activity_type: Type of activity ('order' or 'reservation')
            action: Action performed (created, updated, cancelled, status_changed, etc.)
            restaurant_id: Restaurant ID for RBAC
            user_id: User ID (for customer users from Users table), None for admin actions
            actor_uuid: UUID of the actor (admin/staff/system user) who performed the action
            actor_type: Type of actor ('user', 'admin', 'restaurant_admin', 'system')
            order_id: Associated order ID (if applicable)
            reservation_id: Associated reservation ID (if applicable)
            previous_value: Previous state before change (as dict)
            new_value: New state after change (as dict)
            change_summary: Human-readable summary of the change
            ip_address: Request IP address (optional)
            user_agent: Request user agent (optional)

        Returns:
            Created history entry ID
        """
        # Include actor info in change_summary if actor_uuid is provided
        final_change_summary = change_summary or ""
        if actor_uuid or actor_type != "user":
            actor_info = f" [by: {actor_type}"
            if actor_uuid:
                actor_info += f"/{actor_uuid[:8]}..."
            actor_info += "]"
            final_change_summary = (final_change_summary + actor_info)[:500]
        
        query = """
            INSERT INTO User_Activity_History
            (user_id, activity_type, order_id, reservation_id, action,
             previous_value, new_value, change_summary, restaurant_id,
             ip_address, user_agent, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
        """
        return self._execute_insert(
            query,
            (
                user_id,
                activity_type,
                order_id,
                reservation_id,
                action,
                json.dumps(previous_value, cls=DecimalEncoder) if previous_value else None,
                json.dumps(new_value, cls=DecimalEncoder) if new_value else None,
                final_change_summary,
                restaurant_id,
                ip_address,
                user_agent,
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
                h.reservation_id,
                h.action,
                h.previous_value,
                h.new_value,
                h.change_summary,
                h.restaurant_id,
                h.ip_address,
                h.user_agent,
                h.created_at,
                u.name as performed_by_name,
                u.email as performed_by_email
            FROM User_Activity_History h
            LEFT JOIN Users u ON h.user_id = u.id
            WHERE h.order_id = %s
            ORDER BY h.created_at DESC
            LIMIT %s OFFSET %s
        """
        results = self._execute_query(query, (order_id, limit, offset))
        return self._parse_json_fields(results)

    def get_history_by_reservation(
        self,
        reservation_id: int,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """
        Get activity history for a specific reservation.

        Args:
            reservation_id: Reservation ID
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
                h.reservation_id,
                h.action,
                h.previous_value,
                h.new_value,
                h.change_summary,
                h.restaurant_id,
                h.ip_address,
                h.user_agent,
                h.created_at,
                u.name as performed_by_name,
                u.email as performed_by_email
            FROM User_Activity_History h
            LEFT JOIN Users u ON h.user_id = u.id
            WHERE h.reservation_id = %s
            ORDER BY h.created_at DESC
            LIMIT %s OFFSET %s
        """
        results = self._execute_query(query, (reservation_id, limit, offset))
        return self._parse_json_fields(results)

    def get_history_by_restaurant(
        self,
        restaurant_id: int,
        activity_type: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """
        Get activity history for a restaurant.

        Args:
            restaurant_id: Restaurant ID
            activity_type: Filter by type ('order' or 'reservation')
            start_date: Filter by start date
            end_date: Filter by end date
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
                h.reservation_id,
                h.action,
                h.previous_value,
                h.new_value,
                h.change_summary,
                h.restaurant_id,
                h.ip_address,
                h.user_agent,
                h.created_at,
                u.name as performed_by_name,
                u.email as performed_by_email
            FROM User_Activity_History h
            LEFT JOIN Users u ON h.user_id = u.id
            WHERE h.restaurant_id = %s
        """
        params: List[Any] = [restaurant_id]

        if activity_type:
            query += " AND h.activity_type = %s"
            params.append(activity_type)

        if start_date:
            query += " AND h.created_at >= %s"
            params.append(start_date)

        if end_date:
            query += " AND h.created_at <= %s"
            params.append(end_date)

        query += " ORDER BY h.created_at DESC LIMIT %s OFFSET %s"
        params.extend([limit, offset])

        results = self._execute_query(query, tuple(params))
        return self._parse_json_fields(results)

    def count_history_by_order(self, order_id: int) -> int:
        """Count history entries for an order."""
        query = """
            SELECT COUNT(*) as total
            FROM User_Activity_History
            WHERE order_id = %s
        """
        results = self._execute_query(query, (order_id,))
        return results[0]["total"] if results else 0

    def count_history_by_reservation(self, reservation_id: int) -> int:
        """Count history entries for a reservation."""
        query = """
            SELECT COUNT(*) as total
            FROM User_Activity_History
            WHERE reservation_id = %s
        """
        results = self._execute_query(query, (reservation_id,))
        return results[0]["total"] if results else 0

    def count_history_by_restaurant(
        self,
        restaurant_id: int,
        activity_type: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> int:
        """Count history entries for a restaurant."""
        query = """
            SELECT COUNT(*) as total
            FROM User_Activity_History
            WHERE restaurant_id = %s
        """
        params: List[Any] = [restaurant_id]

        if activity_type:
            query += " AND activity_type = %s"
            params.append(activity_type)

        if start_date:
            query += " AND created_at >= %s"
            params.append(start_date)

        if end_date:
            query += " AND created_at <= %s"
            params.append(end_date)

        results = self._execute_query(query, tuple(params))
        return results[0]["total"] if results else 0

    def get_order_restaurant_id(self, order_id: int) -> Optional[int]:
        """Get restaurant_id for an order (for RBAC)."""
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

    def get_reservation_restaurant_id(self, reservation_id: int) -> Optional[int]:
        """Get restaurant_id for a reservation (for RBAC)."""
        query = """
            SELECT sb.restaurant_id
            FROM Reservations r
            INNER JOIN Slot_Bookings sb ON r.slot_booking_id = sb.id
            WHERE r.id = %s
            LIMIT 1
        """
        results = self._execute_query(query, (reservation_id,))
        if results and results[0].get("restaurant_id"):
            return int(results[0]["restaurant_id"])
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
                row_copy["created_at"] = row_copy["created_at"].isoformat()
            parsed.append(row_copy)
        return parsed

