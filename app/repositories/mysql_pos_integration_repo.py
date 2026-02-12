import json
from typing import Any, Dict, List, Optional

from app.repositories.mysql_base import MySQLBaseRepository
from app.utils.logging_config import get_logger

logger = get_logger(__name__)


class MySQLPOSIntegrationRepository(MySQLBaseRepository):
    def get_enabled_integrations(self, restaurant_id: int) -> List[Dict]:
        query = """
            SELECT
                id,
                restaurant_id,
                pos_type,
                enabled,
                credentials,
                location_id,
                currency,
                default_order_options,
                created_at,
                updated_at
            FROM POS_Integrations
            WHERE restaurant_id = %s AND enabled = TRUE
        """
        results = self._execute_query(query, (restaurant_id,))
        for result in results:
            if result.get("credentials") and isinstance(result["credentials"], str):
                try:
                    result["credentials"] = json.loads(result["credentials"])
                except (json.JSONDecodeError, TypeError):
                    result["credentials"] = {}
            if result.get("default_order_options") and isinstance(result["default_order_options"], str):
                try:
                    result["default_order_options"] = json.loads(result["default_order_options"])
                except (json.JSONDecodeError, TypeError):
                    result["default_order_options"] = {}
        return results

    def get_by_id(self, pos_integration_id: int) -> Optional[Dict]:
        query = """
            SELECT
                id,
                restaurant_id,
                pos_type,
                enabled,
                credentials,
                location_id,
                currency,
                default_order_options,
                created_at,
                updated_at
            FROM POS_Integrations
            WHERE id = %s
            LIMIT 1
        """
        results = self._execute_query(query, (pos_integration_id,))
        if results:
            result = results[0]
            if result.get("credentials") and isinstance(result["credentials"], str):
                try:
                    result["credentials"] = json.loads(result["credentials"])
                except (json.JSONDecodeError, TypeError):
                    result["credentials"] = {}
            if result.get("default_order_options") and isinstance(result["default_order_options"], str):
                try:
                    result["default_order_options"] = json.loads(result["default_order_options"])
                except (json.JSONDecodeError, TypeError):
                    result["default_order_options"] = {}
            return result
        return None

    def create(self, pos_integration_data: Dict[str, Any]) -> int:
        query = """
            INSERT INTO POS_Integrations
            (restaurant_id, pos_type, enabled, credentials, location_id, currency, default_order_options)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """
        return self._execute_insert(
            query,
            (
                pos_integration_data["restaurant_id"],
                pos_integration_data["pos_type"],
                pos_integration_data.get("enabled", False),
                (
                    json.dumps(pos_integration_data.get("credentials"))
                    if pos_integration_data.get("credentials")
                    else None
                ),
                pos_integration_data.get("location_id"),
                pos_integration_data.get("currency", "USD"),
                (
                    json.dumps(pos_integration_data.get("default_order_options"))
                    if pos_integration_data.get("default_order_options")
                    else None
                ),
            ),
        )

    def update(self, pos_integration_id: int, updates: Dict[str, Any]) -> bool:
        update_fields = []
        params = []
        if "enabled" in updates:
            update_fields.append("enabled = %s")
            params.append(updates["enabled"])
        if "credentials" in updates:
            update_fields.append("credentials = %s")
            params.append(json.dumps(updates["credentials"]) if updates["credentials"] else None)
        if "location_id" in updates:
            update_fields.append("location_id = %s")
            params.append(updates["location_id"])
        if "currency" in updates:
            update_fields.append("currency = %s")
            params.append(updates["currency"])
        if "default_order_options" in updates:
            update_fields.append("default_order_options = %s")
            params.append(json.dumps(updates["default_order_options"]) if updates["default_order_options"] else None)
        if not update_fields:
            return False
        update_fields.append("updated_at = NOW()")
        params.append(pos_integration_id)
        query = f"UPDATE POS_Integrations SET {', '.join(update_fields)} WHERE id = %s"
        affected = self._execute_update(query, tuple(params))
        return affected > 0

    def delete(self, pos_integration_id: int) -> bool:
        query = "DELETE FROM POS_Integrations WHERE id = %s"
        affected = self._execute_update(query, (pos_integration_id,))
        return affected > 0
