"""
MySQL Notification Repository for persistent notification system.
"""

import json
import logging
from typing import Any, Dict, List, Optional, Tuple

from app.repositories.mysql_base import MySQLBaseRepository
from app.utils.timezone import json_default

logger = logging.getLogger(__name__)


class MySQLNotificationRepository(MySQLBaseRepository):
    """Repository for Notifications table (persistent notification store)."""

    def create_notification(
        self,
        restaurant_id: int,
        type: str,
        subtype: str,
        title: str,
        message: Optional[str],
        data: Optional[Dict[str, Any]],
        entity_id: Optional[int],
    ) -> Dict[str, Any]:
        """Insert a notification row and return the created row."""
        data_json = json.dumps(data, default=json_default) if data is not None else None
        query = """
            INSERT INTO Notifications (
                restaurant_id, type, subtype, title, message, data, entity_id,
                is_read, created_at, updated_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, FALSE, NOW(), NOW())
        """
        notification_id = self._execute_insert(
            query,
            (restaurant_id, type, subtype, title, message, data_json, entity_id),
        )
        logger.info(
            "[MySQL] Created notification: id=%s restaurant_id=%s type=%s subtype=%s",
            notification_id,
            restaurant_id,
            type,
            subtype,
        )
        row = self.get_notification_by_id(notification_id)
        if not row:
            raise RuntimeError("Failed to fetch created notification")
        return row

    def get_notifications(
        self,
        restaurant_id: Optional[int] = None,
        is_read: Optional[bool] = None,
        type: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Tuple[List[Dict[str, Any]], int]:
        """Select notifications with optional filters, ordered by created_at DESC. Returns (rows, total). When restaurant_id is None, returns across all restaurants (admin)."""
        where_clauses: List[str] = []
        params: List[Any] = []
        if restaurant_id is not None:
            where_clauses.append("restaurant_id = %s")
            params.append(restaurant_id)
        if is_read is not None:
            where_clauses.append("is_read = %s")
            params.append(is_read)
        if type is not None:
            where_clauses.append("type = %s")
            params.append(type)
        where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"

        data_query = f"""
            SELECT *
            FROM Notifications
            WHERE {where_sql}
            ORDER BY created_at DESC
            LIMIT %s OFFSET %s
        """
        data_params = params + [limit, offset]
        rows = self._execute_query(data_query, tuple(data_params))

        count_query = f"SELECT COUNT(*) AS total FROM Notifications WHERE {where_sql}"
        count_rows = self._execute_query(count_query, tuple(params))
        total = count_rows[0]["total"] if count_rows else 0
        return rows, total

    def get_notification_by_id(self, notification_id: int) -> Optional[Dict[str, Any]]:
        """Fetch a single notification by ID."""
        query = "SELECT * FROM Notifications WHERE id = %s LIMIT 1"
        rows = self._execute_query(query, (notification_id,))
        return rows[0] if rows else None

    def mark_as_read(self, notification_id: int) -> Optional[Dict[str, Any]]:
        """Set is_read = TRUE and read_at = NOW() for the given notification. Returns updated row."""
        query = """
            UPDATE Notifications
            SET is_read = TRUE, read_at = NOW(), updated_at = NOW()
            WHERE id = %s
        """
        affected = self._execute_update(query, (notification_id,))
        if affected == 0:
            return None
        return self.get_notification_by_id(notification_id)

    def mark_all_as_read(self, restaurant_id: int, type: Optional[str] = None) -> int:
        """Mark all unread notifications for the restaurant as read. Optional type filter. Returns count affected."""
        if type is not None:
            query = """
                UPDATE Notifications
                SET is_read = TRUE, read_at = NOW(), updated_at = NOW()
                WHERE restaurant_id = %s AND type = %s AND is_read = FALSE
            """
            params: Tuple[Any, ...] = (restaurant_id, type)
        else:
            query = """
                UPDATE Notifications
                SET is_read = TRUE, read_at = NOW(), updated_at = NOW()
                WHERE restaurant_id = %s AND is_read = FALSE
            """
            params = (restaurant_id,)
        return self._execute_update(query, params)

    def get_unread_count(self, restaurant_id: int) -> int:
        """Return count of unread notifications for the restaurant."""
        query = """
            SELECT COUNT(*) AS total
            FROM Notifications
            WHERE restaurant_id = %s AND is_read = FALSE
        """
        rows = self._execute_query(query, (restaurant_id,))
        return rows[0]["total"] if rows else 0

    def get_total_count(
        self,
        restaurant_id: Optional[int] = None,
        is_read: Optional[bool] = None,
        type: Optional[str] = None,
    ) -> int:
        """Return total count matching the same filters as get_notifications."""
        where_clauses = []
        params = []
        if restaurant_id is not None:
            where_clauses.append("restaurant_id = %s")
            params.append(restaurant_id)
        if is_read is not None:
            where_clauses.append("is_read = %s")
            params.append(is_read)
        if type is not None:
            where_clauses.append("type = %s")
            params.append(type)
        where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"
        query = f"SELECT COUNT(*) AS total FROM Notifications WHERE {where_sql}"
        rows = self._execute_query(query, tuple(params))
        return rows[0]["total"] if rows else 0
