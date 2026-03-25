"""
MySQL repository for persisted POS webhook deliveries.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Dict, List, Optional

from app.repositories.mysql_base import MySQLBaseRepository


class MySQLPOSWebhookEventRepository(MySQLBaseRepository):
    """Repository for idempotent POS webhook event storage and processing state."""

    @staticmethod
    def _parse_payload(row: Dict[str, Any]) -> Dict[str, Any]:
        if row.get("payload") and isinstance(row["payload"], str):
            try:
                row["payload"] = json.loads(row["payload"])
            except (TypeError, json.JSONDecodeError):
                row["payload"] = {}
        elif row.get("payload") is None:
            row["payload"] = {}
        return row

    def get_by_provider_event(self, *, pos_type: str, provider_event_id: str) -> Optional[Dict[str, Any]]:
        query = """
            SELECT *
            FROM POS_Webhook_Events
            WHERE pos_type = %s AND provider_event_id = %s
            LIMIT 1
        """
        results = self._execute_query(query, (pos_type, provider_event_id))
        return self._parse_payload(results[0]) if results else None

    def get_by_id(self, webhook_event_id: int) -> Optional[Dict[str, Any]]:
        query = "SELECT * FROM POS_Webhook_Events WHERE id = %s LIMIT 1"
        results = self._execute_query(query, (webhook_event_id,))
        return self._parse_payload(results[0]) if results else None

    def create_event(
        self,
        *,
        pos_type: str,
        provider_event_id: str,
        event_type: str,
        external_account_id: Optional[str],
        location_id: Optional[str],
        payload: Dict[str, Any],
        last_retry_number: Optional[int],
        last_retry_reason: Optional[str],
    ) -> int:
        query = """
            INSERT INTO POS_Webhook_Events (
                pos_type,
                provider_event_id,
                event_type,
                external_account_id,
                location_id,
                status,
                delivery_count,
                processing_attempts,
                last_retry_number,
                last_retry_reason,
                payload,
                created_at,
                updated_at
            )
            VALUES (%s, %s, %s, %s, %s, 'PENDING', 1, 0, %s, %s, %s, NOW(), NOW())
        """
        return self._execute_insert(
            query,
            (
                pos_type,
                provider_event_id,
                event_type,
                external_account_id,
                location_id,
                last_retry_number,
                last_retry_reason,
                json.dumps(payload),
            ),
        )

    def record_delivery(
        self,
        webhook_event_id: int,
        *,
        status: Optional[str] = None,
        last_retry_number: Optional[int] = None,
        last_retry_reason: Optional[str] = None,
        payload: Optional[Dict[str, Any]] = None,
        external_account_id: Optional[str] = None,
        location_id: Optional[str] = None,
    ) -> int:
        fields = ["delivery_count = delivery_count + 1", "updated_at = NOW()"]
        params: List[Any] = []
        if status is not None:
            fields.append("status = %s")
            params.append(status)
        if last_retry_number is not None:
            fields.append("last_retry_number = %s")
            params.append(last_retry_number)
        if last_retry_reason is not None:
            fields.append("last_retry_reason = %s")
            params.append(last_retry_reason)
        if payload is not None:
            fields.append("payload = %s")
            params.append(json.dumps(payload))
        if external_account_id is not None:
            fields.append("external_account_id = %s")
            params.append(external_account_id)
        if location_id is not None:
            fields.append("location_id = %s")
            params.append(location_id)
        params.append(webhook_event_id)
        query = f"UPDATE POS_Webhook_Events SET {', '.join(fields)} WHERE id = %s"
        return self._execute_update(query, tuple(params))

    def mark_processing(self, webhook_event_id: int) -> int:
        query = """
            UPDATE POS_Webhook_Events
            SET status = 'PROCESSING',
                processing_attempts = processing_attempts + 1,
                next_retry_at = NULL,
                updated_at = NOW()
            WHERE id = %s
        """
        return self._execute_update(query, (webhook_event_id,))

    def mark_processed(self, webhook_event_id: int) -> int:
        query = """
            UPDATE POS_Webhook_Events
            SET status = 'PROCESSED',
                processed_at = NOW(),
                next_retry_at = NULL,
                last_error = NULL,
                updated_at = NOW()
            WHERE id = %s
        """
        return self._execute_update(query, (webhook_event_id,))

    def mark_ignored(self, webhook_event_id: int, *, error: Optional[str] = None) -> int:
        query = """
            UPDATE POS_Webhook_Events
            SET status = 'IGNORED',
                processed_at = NOW(),
                last_error = %s,
                next_retry_at = NULL,
                updated_at = NOW()
            WHERE id = %s
        """
        return self._execute_update(query, (error, webhook_event_id))

    def mark_failed(self, webhook_event_id: int, *, error: str, next_retry_at: Optional[datetime]) -> int:
        query = """
            UPDATE POS_Webhook_Events
            SET status = 'FAILED',
                last_error = %s,
                next_retry_at = %s,
                updated_at = NOW()
            WHERE id = %s
        """
        return self._execute_update(query, (error, next_retry_at, webhook_event_id))

    def list_pending(
        self,
        *,
        limit: int = 50,
        pos_type: Optional[str] = None,
        stale_processing_minutes: int = 0,
    ) -> List[Dict[str, Any]]:
        params: List[Any] = []
        query = """
            SELECT *
            FROM POS_Webhook_Events
            WHERE (
                (status IN ('PENDING', 'FAILED') AND (next_retry_at IS NULL OR next_retry_at <= NOW()))
        """
        if stale_processing_minutes > 0:
            query += """
                OR (status = 'PROCESSING' AND updated_at <= DATE_SUB(NOW(), INTERVAL %s MINUTE))
            """
            params.append(stale_processing_minutes)
        query += """
            )
        """
        if pos_type is not None:
            query += " AND pos_type = %s"
            params.append(pos_type)
        query += " ORDER BY created_at ASC LIMIT %s"
        params.append(limit)
        return [self._parse_payload(row) for row in self._execute_query(query, tuple(params))]
