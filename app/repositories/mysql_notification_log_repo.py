"""
MySQL repository for Notification_Logs (SMS notification audit and retry).
"""

from typing import List, Optional

from app.repositories.mysql_base import MySQLBaseRepository


class MySQLNotificationLogRepository(MySQLBaseRepository):
    """Repository for notification log data access."""

    def create_log(
        self,
        restaurant_id: int,
        entity_type: str,
        entity_id: int,
        recipient_phone: str,
        message_content: str,
    ) -> int:
        """Insert a notification log row and return its id."""
        query = """
            INSERT INTO Notification_Logs (
                restaurant_id, entity_type, entity_id, recipient_phone, message_content, status
            )
            VALUES (%s, %s, %s, %s, %s, 'pending')
        """
        return self._execute_insert(
            query,
            (restaurant_id, entity_type, entity_id, recipient_phone, message_content),
        )

    def update_status(
        self,
        log_id: int,
        status: str,
        twilio_message_sid: Optional[str] = None,
        error_message: Optional[str] = None,
    ) -> int:
        """Update status (and optionally twilio_message_sid, error_message) for a log row."""
        if twilio_message_sid is not None and error_message is not None:
            query = """
                UPDATE Notification_Logs
                SET status = %s, twilio_message_sid = %s, error_message = %s,
                    sent_at = CASE WHEN %s = 'sent' THEN NOW() ELSE sent_at END,
                    updated_at = NOW()
                WHERE id = %s
            """
            params = (status, twilio_message_sid, error_message, status, log_id)
        elif twilio_message_sid is not None:
            query = """
                UPDATE Notification_Logs
                SET status = %s, twilio_message_sid = %s,
                    sent_at = CASE WHEN %s = 'sent' THEN NOW() ELSE sent_at END,
                    updated_at = NOW()
                WHERE id = %s
            """
            params = (status, twilio_message_sid, status, log_id)
        elif error_message is not None:
            query = """
                UPDATE Notification_Logs
                SET status = %s, error_message = %s, updated_at = NOW()
                WHERE id = %s
            """
            params = (status, error_message, log_id)
        else:
            query = """
                UPDATE Notification_Logs
                SET status = %s,
                    sent_at = CASE WHEN %s = 'sent' THEN NOW() ELSE sent_at END,
                    updated_at = NOW()
                WHERE id = %s
            """
            params = (status, status, log_id)
        return self._execute_update(query, params)

    def increment_retry_count(self, log_id: int) -> int:
        """Increment retry_count for a log row."""
        query = """
            UPDATE Notification_Logs
            SET retry_count = retry_count + 1, updated_at = NOW()
            WHERE id = %s
        """
        return self._execute_update(query, (log_id,))

    def get_pending_for_retry(
        self,
        max_retries: int,
        limit: int = 100,
    ) -> List[dict]:
        """Return pending/failed logs with retry_count < max_retries for retry processing."""
        query = """
            SELECT id, restaurant_id, entity_type, entity_id, recipient_phone, message_content, retry_count
            FROM Notification_Logs
            WHERE status IN ('pending', 'failed') AND retry_count < %s
            ORDER BY created_at ASC
            LIMIT %s
        """
        return self._execute_query(query, (max_retries, limit))
