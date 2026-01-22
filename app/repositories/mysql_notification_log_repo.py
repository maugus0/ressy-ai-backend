from datetime import datetime
from typing import Any, Dict, List, Optional

from app.repositories.mysql_base import MySQLBaseRepository


class MySQLNotificationLogRepository(MySQLBaseRepository):

    def create_log(
        self,
        restaurant_id: int,
        entity_type: str,
        entity_id: int,
        recipient_phone: str,
        message_content: str,
        status: str = "pending",
    ) -> int:
        query = """
            INSERT INTO Notification_Logs (
                restaurant_id, entity_type, entity_id, recipient_phone,
                message_content, status, created_at, updated_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, NOW(), NOW())
        """
        return self._execute_insert(
            query,
            (
                restaurant_id,
                entity_type,
                entity_id,
                recipient_phone,
                message_content,
                status,
            ),
        )

    def update_status(
        self,
        log_id: int,
        status: str,
        twilio_message_sid: Optional[str] = None,
        error_message: Optional[str] = None,
    ) -> bool:
        fields = ["status = %s", "updated_at = NOW()"]
        params: List[Any] = [status]

        if status == "sent":
            fields.append("sent_at = NOW()")

        if status == "delivered":
            fields.append("delivered_at = NOW()")

        if twilio_message_sid:
            fields.append("twilio_message_sid = %s")
            params.append(twilio_message_sid)

        if error_message:
            fields.append("error_message = %s")
            params.append(error_message)

        params.append(log_id)

        query = f"UPDATE Notification_Logs SET {', '.join(fields)} WHERE id = %s"
        affected = self._execute_update(query, tuple(params))
        return affected > 0

    def increment_retry_count(self, log_id: int) -> bool:
        query = """
            UPDATE Notification_Logs
            SET retry_count = retry_count + 1, updated_at = NOW()
            WHERE id = %s
        """
        affected = self._execute_update(query, (log_id,))
        return affected > 0

    def get_by_id(self, log_id: int) -> Optional[Dict[str, Any]]:
        query = """
            SELECT
                id, restaurant_id, entity_type, entity_id, recipient_phone,
                message_content, status, twilio_message_sid,
                error_message, retry_count, sent_at, delivered_at,
                created_at, updated_at
            FROM Notification_Logs
            WHERE id = %s
            LIMIT 1
        """
        results = self._execute_query(query, (log_id,))
        return results[0] if results else None

    def get_by_entity(
        self,
        entity_type: str,
        entity_id: int,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        query = """
            SELECT
                id, restaurant_id, entity_type, entity_id, recipient_phone,
                message_content, status, twilio_message_sid,
                error_message, retry_count, sent_at, delivered_at,
                created_at, updated_at
            FROM Notification_Logs
            WHERE entity_type = %s AND entity_id = %s
            ORDER BY created_at DESC
            LIMIT %s OFFSET %s
        """
        return self._execute_query(query, (entity_type, entity_id, limit, offset))

    def get_pending_for_retry(
        self,
        max_retry_count: int = 3,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        query = """
            SELECT
                id, restaurant_id, entity_type, entity_id, recipient_phone,
                message_content, status, twilio_message_sid,
                error_message, retry_count, sent_at, delivered_at,
                created_at, updated_at
            FROM Notification_Logs
            WHERE status = 'failed' AND retry_count < %s
            ORDER BY created_at ASC
            LIMIT %s
        """
        return self._execute_query(query, (max_retry_count, limit))

    def get_logs_by_restaurant(
        self,
        restaurant_id: int,
        status: Optional[str] = None,
        entity_type: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        query = """
            SELECT
                id, restaurant_id, entity_type, entity_id, recipient_phone,
                message_content, status, twilio_message_sid,
                error_message, retry_count, sent_at, delivered_at,
                created_at, updated_at
            FROM Notification_Logs
            WHERE restaurant_id = %s
        """
        params: List[Any] = [restaurant_id]

        if status:
            query += " AND status = %s"
            params.append(status)

        if entity_type:
            query += " AND entity_type = %s"
            params.append(entity_type)

        if start_date:
            query += " AND created_at >= %s"
            params.append(start_date)

        if end_date:
            query += " AND created_at <= %s"
            params.append(end_date)

        query += " ORDER BY created_at DESC LIMIT %s OFFSET %s"
        params.extend([limit, offset])

        return self._execute_query(query, tuple(params))
