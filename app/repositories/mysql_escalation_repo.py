"""
MySQL Escalation Repository for escalation operations.
"""

from typing import Any, Dict, List, Optional, Tuple

from app.repositories.mysql_base import MySQLBaseRepository
from app.utils.logging_config import get_logger


class MySQLEscalationRepository(MySQLBaseRepository):
    """Repository for escalation data access in MySQL."""

    logger = get_logger(__name__)

    def create_escalation(self, payload: Dict[str, Any]) -> int:
        query = """
            INSERT INTO Escalations (
                call_id,
                user_id,
                restaurant_id,
                twilio_call_sid,
                caller_phone,
                escalation_phone_number,
                urgency,
                reason,
                status,
                requested_at,
                created_at,
                updated_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW(), NOW())
        """
        escalation_id = self._execute_insert(
            query,
            (
                payload.get("call_id"),
                payload.get("user_id"),
                payload.get("restaurant_id"),
                payload.get("twilio_call_sid"),
                payload.get("caller_phone"),
                payload.get("escalation_phone_number"),
                payload.get("urgency"),
                payload.get("reason"),
                payload.get("status", "raised"),
            ),
        )
        self.logger.info(
            "[MySQL] Created escalation: escalation_id=%s call_id=%s restaurant_id=%s",
            escalation_id,
            payload.get("call_id"),
            payload.get("restaurant_id"),
        )
        return escalation_id

    def get_latest_by_call_sid_and_restaurant(
        self, twilio_call_sid: str, restaurant_id: str
    ) -> Optional[Dict[str, Any]]:
        query = """
            SELECT *
            FROM Escalations
            WHERE twilio_call_sid = %s
              AND restaurant_id = %s
            ORDER BY requested_at DESC
            LIMIT 1
        """
        rows = self._execute_query(query, (twilio_call_sid, restaurant_id))
        return rows[0] if rows else None

    def update_status(self, escalation_id: int, status: str, forwarded: bool = False) -> bool:
        if forwarded:
            query = """
                UPDATE Escalations
                SET status = %s,
                    forwarded_at = NOW(),
                    updated_at = NOW()
                WHERE id = %s
            """
        else:
            query = """
                UPDATE Escalations
                SET status = %s,
                    updated_at = NOW()
                WHERE id = %s
            """
        affected = self._execute_update(query, (status, escalation_id))
        return affected > 0

    def list_escalations(
        self,
        restaurant_id: Optional[str] = None,
        status: Optional[str] = None,
        urgency: Optional[str] = None,
        reason: Optional[str] = None,
        caller_phone: Optional[str] = None,
        call_id: Optional[str] = None,
        call_sid: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        page: int = 1,
        limit: int = 20,
        sort_by: str = "requested_at",
        sort_order: str = "desc",
    ) -> Tuple[List[Dict[str, Any]], int]:
        allowed_sort_columns = {
            "requested_at": "e.requested_at",
            "created_at": "e.created_at",
            "updated_at": "e.updated_at",
            "status": "e.status",
        }
        sort_column = allowed_sort_columns.get(sort_by, "e.requested_at")
        order = "DESC" if str(sort_order).lower() == "desc" else "ASC"
        offset = max(page - 1, 0) * limit

        where_clauses = ["1=1"]
        params: List[Any] = []

        if restaurant_id:
            where_clauses.append("e.restaurant_id = %s")
            params.append(str(restaurant_id))
        if status:
            where_clauses.append("e.status = %s")
            params.append(status)
        if urgency:
            where_clauses.append("e.urgency = %s")
            params.append(urgency)
        if reason:
            where_clauses.append("e.reason LIKE %s")
            params.append(f"%{reason}%")
        if caller_phone:
            where_clauses.append("e.caller_phone LIKE %s")
            params.append(f"%{caller_phone}%")
        if call_id:
            where_clauses.append("e.call_id = %s")
            params.append(call_id)
        if call_sid:
            where_clauses.append("e.twilio_call_sid = %s")
            params.append(call_sid)
        if date_from:
            where_clauses.append("e.requested_at >= %s")
            params.append(date_from)
        if date_to:
            where_clauses.append("e.requested_at <= %s")
            params.append(date_to)

        where_sql = " AND ".join(where_clauses)
        base_query = f"""
            FROM Escalations e
            LEFT JOIN Restaurants r ON r.id = CAST(e.restaurant_id AS UNSIGNED)
            WHERE {where_sql}
        """

        data_query = f"""
            SELECT
                e.*,
                r.name AS restaurant_name
            {base_query}
            ORDER BY {sort_column} {order}
            LIMIT %s OFFSET %s
        """
        data_params = params + [limit, offset]
        rows = self._execute_query(data_query, tuple(data_params))

        count_query = f"SELECT COUNT(*) AS total {base_query}"
        count_rows = self._execute_query(count_query, tuple(params))
        total = count_rows[0]["total"] if count_rows else 0
        return rows, total

    def get_by_id(self, escalation_id: int) -> Optional[Dict[str, Any]]:
        query = """
            SELECT
                e.*,
                r.name AS restaurant_name
            FROM Escalations e
            LEFT JOIN Restaurants r ON r.id = CAST(e.restaurant_id AS UNSIGNED)
            WHERE e.id = %s
            LIMIT 1
        """
        rows = self._execute_query(query, (escalation_id,))
        return rows[0] if rows else None
