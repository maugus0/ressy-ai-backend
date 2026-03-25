import json
from datetime import datetime
from typing import Dict, List, Optional

from app.repositories.mysql_base import MySQLBaseRepository
from app.utils.logging_config import get_logger

logger = get_logger(__name__)


class MySQLOrderPOSSyncRepository(MySQLBaseRepository):
    def create_sync_record(
        self, order_id: int, restaurant_id: int, pos_integration_id: int, idempotency_key: str
    ) -> int:
        query = """
            INSERT INTO Order_POS_Sync
            (order_id, restaurant_id, pos_integration_id, idempotency_key, status, attempts)
            VALUES (%s, %s, %s, %s, 'PENDING', 0)
        """
        return self._execute_insert(query, (order_id, restaurant_id, pos_integration_id, idempotency_key))

    def get_by_order_and_pos(self, order_id: int, pos_integration_id: int) -> Optional[Dict]:
        query = """
            SELECT
                id,
                order_id,
                restaurant_id,
                pos_integration_id,
                external_order_id,
                external_payment_id,
                idempotency_key,
                status,
                last_error,
                attempts,
                next_retry_at,
                request_payload,
                response_payload,
                created_at,
                updated_at
            FROM Order_POS_Sync
            WHERE order_id = %s AND pos_integration_id = %s
            ORDER BY created_at DESC
            LIMIT 1
        """
        results = self._execute_query(query, (order_id, pos_integration_id))
        if results:
            result = results[0]
            if result.get("request_payload") and isinstance(result["request_payload"], str):
                try:
                    result["request_payload"] = json.loads(result["request_payload"])
                except (json.JSONDecodeError, TypeError):
                    result["request_payload"] = {}
            if result.get("response_payload") and isinstance(result["response_payload"], str):
                try:
                    result["response_payload"] = json.loads(result["response_payload"])
                except (json.JSONDecodeError, TypeError):
                    result["response_payload"] = {}
            return result
        return None

    def update_sync_status(
        self,
        sync_id: int,
        status: Optional[str] = None,
        external_order_id: Optional[str] = None,
        external_payment_id: Optional[str] = None,
        error: Optional[str] = None,
        attempts: Optional[int] = None,
        next_retry_at: Optional[datetime] = None,
        request_payload: Optional[Dict] = None,
        response_payload: Optional[Dict] = None,
    ) -> bool:
        update_fields = []
        params = []
        if status is not None:
            update_fields.append("status = %s")
            params.append(status)
        if external_order_id is not None:
            update_fields.append("external_order_id = %s")
            params.append(external_order_id)
        if external_payment_id is not None:
            update_fields.append("external_payment_id = %s")
            params.append(external_payment_id)
        if error is not None:
            update_fields.append("last_error = %s")
            params.append(error)
        if attempts is not None:
            update_fields.append("attempts = %s")
            params.append(attempts)
        if next_retry_at is not None:
            update_fields.append("next_retry_at = %s")
            params.append(next_retry_at)
        if request_payload is not None:
            update_fields.append("request_payload = %s")
            params.append(json.dumps(request_payload))
        if response_payload is not None:
            update_fields.append("response_payload = %s")
            params.append(json.dumps(response_payload))
        if not update_fields:
            return False
        update_fields.append("updated_at = NOW()")
        params.append(sync_id)
        query = f"UPDATE Order_POS_Sync SET {', '.join(update_fields)} WHERE id = %s"
        affected = self._execute_update(query, tuple(params))
        return affected > 0

    def get_pending_retries(self) -> List[Dict]:
        query = """
            SELECT
                id,
                order_id,
                restaurant_id,
                pos_integration_id,
                external_order_id,
                external_payment_id,
                idempotency_key,
                status,
                last_error,
                attempts,
                next_retry_at,
                request_payload,
                response_payload,
                created_at,
                updated_at
            FROM Order_POS_Sync
            WHERE status IN ('PENDING', 'SENT')
                AND (next_retry_at IS NULL OR next_retry_at <= NOW())
            ORDER BY created_at ASC
        """
        results = self._execute_query(query)
        for result in results:
            if result.get("request_payload") and isinstance(result["request_payload"], str):
                try:
                    result["request_payload"] = json.loads(result["request_payload"])
                except (json.JSONDecodeError, TypeError):
                    result["request_payload"] = {}
            if result.get("response_payload") and isinstance(result["response_payload"], str):
                try:
                    result["response_payload"] = json.loads(result["response_payload"])
                except (json.JSONDecodeError, TypeError):
                    result["response_payload"] = {}
        return results

    def get_by_order_id(self, order_id: int) -> List[Dict]:
        query = """
            SELECT
                id,
                order_id,
                restaurant_id,
                pos_integration_id,
                external_order_id,
                external_payment_id,
                idempotency_key,
                status,
                last_error,
                attempts,
                next_retry_at,
                request_payload,
                response_payload,
                created_at,
                updated_at
            FROM Order_POS_Sync
            WHERE order_id = %s
            ORDER BY created_at ASC
        """
        results = self._execute_query(query, (order_id,))
        for result in results:
            if result.get("request_payload") and isinstance(result["request_payload"], str):
                try:
                    result["request_payload"] = json.loads(result["request_payload"])
                except (json.JSONDecodeError, TypeError):
                    result["request_payload"] = {}
            if result.get("response_payload") and isinstance(result["response_payload"], str):
                try:
                    result["response_payload"] = json.loads(result["response_payload"])
                except (json.JSONDecodeError, TypeError):
                    result["response_payload"] = {}
        return results

    def get_latest_confirmed_syncs(self, order_id: int) -> List[Dict]:
        query = """
            SELECT
                id,
                order_id,
                restaurant_id,
                pos_integration_id,
                external_order_id,
                external_payment_id,
                idempotency_key,
                status,
                last_error,
                attempts,
                next_retry_at,
                request_payload,
                response_payload,
                created_at,
                updated_at
            FROM Order_POS_Sync
            WHERE order_id = %s AND status = 'CONFIRMED'
            ORDER BY created_at DESC
        """
        results = self._execute_query(query, (order_id,))
        for result in results:
            if result.get("request_payload") and isinstance(result["request_payload"], str):
                try:
                    result["request_payload"] = json.loads(result["request_payload"])
                except (json.JSONDecodeError, TypeError):
                    result["request_payload"] = {}
            if result.get("response_payload") and isinstance(result["response_payload"], str):
                try:
                    result["response_payload"] = json.loads(result["response_payload"])
                except (json.JSONDecodeError, TypeError):
                    result["response_payload"] = {}
        return results
