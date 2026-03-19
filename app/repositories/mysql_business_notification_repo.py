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
    """Repository for Business_Notifications table (persistent notification store)."""

    def create_notification(
        self,
        business_id: Optional[int],
        type: str,
        subtype: str,
        title: str,
        message: Optional[str],
        data: Optional[Dict[str, Any]],
        entity_id: Optional[int],
    ) -> Dict[str, Any]:
        """Insert a notification row and return the created row."""
        if business_id is None and (type or "").strip().lower() != "system":
            raise ValueError("business_id can be NULL only for system notifications")

        data_json = json.dumps(data, default=json_default) if data is not None else None
        query = """
            INSERT INTO Business_Notifications (
                business_id, type, subtype, title, message, data, entity_id,
                is_read, created_at, updated_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, FALSE, NOW(), NOW())
        """
        notification_id = self._execute_insert(
            query,
            (business_id, type, subtype, title, message, data_json, entity_id),
        )
        logger.info(
            "[MySQL] Created notification: id=%s business_id=%s type=%s subtype=%s",
            notification_id,
            business_id,
            type,
            subtype,
        )
        row = self.get_notification_by_id(notification_id)
        if not row:
            raise RuntimeError("Failed to fetch created notification")
        return row

    def create_notifications_bulk(self, notifications: List[Dict[str, Any]]) -> int:
        """
        Bulk insert notification rows. Returns number of inserted rows.
        """
        if not notifications:
            return 0

        query = """
            INSERT INTO Business_Notifications (
                business_id, type, subtype, title, message, data, entity_id,
                is_read, created_at, updated_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, FALSE, NOW(), NOW())
        """

        params_list: List[Tuple[Any, ...]] = []
        for row in notifications:
            row_type = (row.get("type") or "").strip().lower()
            business_id = row.get("business_id")
            if business_id is None and row_type != "system":
                raise ValueError("business_id can be NULL only for system notifications")

            data_json = json.dumps(row.get("data"), default=json_default) if row.get("data") is not None else None
            params_list.append(
                (
                    business_id,
                    row_type,
                    row.get("subtype"),
                    row.get("title"),
                    row.get("message"),
                    data_json,
                    row.get("entity_id"),
                )
            )

        self._execute_many(query, params_list)
        logger.info("[MySQL] Bulk created notifications: count=%s", len(params_list))
        return len(params_list)

    def get_notifications(
        self,
        business_id: Optional[int] = None,
        is_read: Optional[bool] = None,
        type: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
        exclude_bulk_system_kill_switch_toggled: bool = False,
    ) -> Tuple[List[Dict[str, Any]], int]:
        """Select notifications with optional filters, ordered by created_at DESC. Returns (rows, total). When business_id is None, returns across all businesss (admin)."""
        where_clauses: List[str] = []
        params: List[Any] = []
        if business_id is not None:
            where_clauses.append("business_id = %s")
            params.append(business_id)
        if is_read is not None:
            where_clauses.append("is_read = %s")
            params.append(is_read)
        if type is not None:
            where_clauses.append("type = %s")
            params.append(type)
        if exclude_bulk_system_kill_switch_toggled:
            where_clauses.append(
                "NOT (type = 'system' AND subtype = 'kill_switch_toggled' AND JSON_EXTRACT(data, '$.bulk') = true)"
            )
        where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"

        data_query = f"""
            SELECT *
            FROM Business_Notifications
            WHERE {where_sql}
            ORDER BY created_at DESC
            LIMIT %s OFFSET %s
        """
        data_params = params + [limit, offset]
        rows = self._execute_query(data_query, tuple(data_params))

        count_query = f"SELECT COUNT(*) AS total FROM Business_Notifications WHERE {where_sql}"
        count_rows = self._execute_query(count_query, tuple(params))
        total = count_rows[0]["total"] if count_rows else 0
        return rows, total

    def get_notification_by_id(self, notification_id: int) -> Optional[Dict[str, Any]]:
        """Fetch a single notification by ID."""
        query = "SELECT * FROM Business_Notifications WHERE id = %s LIMIT 1"
        rows = self._execute_query(query, (notification_id,))
        return rows[0] if rows else None

    def mark_as_read(self, notification_id: int) -> Optional[Dict[str, Any]]:
        """Set is_read = TRUE and read_at = NOW() for the given notification. Idempotent: only updates if currently unread. Returns updated row."""
        query = """
            UPDATE Business_Notifications
            SET is_read = TRUE, read_at = NOW(), updated_at = NOW()
            WHERE id = %s AND is_read = FALSE
        """
        self._execute_update(query, (notification_id,))
        return self.get_notification_by_id(notification_id)

    def mark_all_as_read(self, business_id: int, type: Optional[str] = None) -> int:
        """Mark all unread notifications for the business as read. Optional type filter. Returns count affected."""
        if type is not None:
            query = """
                UPDATE Business_Notifications
                SET is_read = TRUE, read_at = NOW(), updated_at = NOW()
                WHERE business_id = %s AND type = %s AND is_read = FALSE
            """
            params: Tuple[Any, ...] = (business_id, type)
        else:
            query = """
                UPDATE Business_Notifications
                SET is_read = TRUE, read_at = NOW(), updated_at = NOW()
                WHERE business_id = %s AND is_read = FALSE
            """
            params = (business_id,)
        return self._execute_update(query, params)

    def get_unread_count(self, business_id: int) -> int:
        """Return count of unread notifications for the business."""
        query = """
            SELECT COUNT(*) AS total
            FROM Business_Notifications
            WHERE business_id = %s AND is_read = FALSE
        """
        rows = self._execute_query(query, (business_id,))
        return rows[0]["total"] if rows else 0

    def get_total_count(
        self,
        business_id: Optional[int] = None,
        is_read: Optional[bool] = None,
        type: Optional[str] = None,
    ) -> int:
        """Return total count matching the same filters as get_notifications."""
        where_clauses = []
        params = []
        if business_id is not None:
            where_clauses.append("business_id = %s")
            params.append(business_id)
        if is_read is not None:
            where_clauses.append("is_read = %s")
            params.append(is_read)
        if type is not None:
            where_clauses.append("type = %s")
            params.append(type)
        where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"
        query = f"SELECT COUNT(*) AS total FROM Business_Notifications WHERE {where_sql}"
        rows = self._execute_query(query, tuple(params))
        return rows[0]["total"] if rows else 0
