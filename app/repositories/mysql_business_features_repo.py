"""
MySQL repository for business feature flags.
"""

from typing import Any, Dict, Optional

from app.repositories.mysql_base import MySQLBaseRepository


class MySQLBusinessFeaturesRepository(MySQLBaseRepository):
    """Repository for Business_Features CRUD and lookups."""

    def get_by_business_id(self, business_id: int) -> Optional[Dict[str, Any]]:
        query = """
            SELECT
                business_id,
                orders_enabled,
                reservations_enabled,
                faqs_enabled,
                orders_sms_redirect_enabled,
                orders_redirect_url,
                orders_redirect_message,
                reservations_sms_redirect_enabled,
                reservations_redirect_url,
                reservations_redirect_message,
                created_at,
                updated_at
            FROM Business_Features
            WHERE business_id = %s
            LIMIT 1
        """
        results = self._execute_query(query, (business_id,))
        if not results:
            return None
        row = results[0]
        # Structure the response with nested SMS redirect configs
        return {
            "business_id": row.get("business_id"),
            "orders_enabled": bool(row.get("orders_enabled", True)),
            "reservations_enabled": bool(row.get("reservations_enabled", True)),
            "faqs_enabled": bool(row.get("faqs_enabled", True)),
            "orders_sms_redirect": {
                "enabled": bool(row.get("orders_sms_redirect_enabled", False)),
                "redirect_url": row.get("orders_redirect_url"),
                "redirect_message": row.get("orders_redirect_message"),
            },
            "reservations_sms_redirect": {
                "enabled": bool(row.get("reservations_sms_redirect_enabled", False)),
                "redirect_url": row.get("reservations_redirect_url"),
                "redirect_message": row.get("reservations_redirect_message"),
            },
            "created_at": row.get("created_at"),
            "updated_at": row.get("updated_at"),
        }

    def create_defaults(self, business_id: int) -> None:
        query = """
            INSERT IGNORE INTO Business_Features (business_id)
            VALUES (%s)
        """
        self._execute_insert(query, (business_id,))

    def update(self, business_id: int, data: Dict[str, Any]) -> bool:
        update_fields = []
        params = []

        # Standard capability flags
        if "orders_enabled" in data:
            update_fields.append("orders_enabled = %s")
            params.append(data["orders_enabled"])
        if "reservations_enabled" in data:
            update_fields.append("reservations_enabled = %s")
            params.append(data["reservations_enabled"])
        if "faqs_enabled" in data:
            update_fields.append("faqs_enabled = %s")
            params.append(data["faqs_enabled"])

        # SMS redirect fields (flattened)
        if "orders_sms_redirect_enabled" in data:
            update_fields.append("orders_sms_redirect_enabled = %s")
            params.append(data["orders_sms_redirect_enabled"])
        if "orders_redirect_url" in data:
            update_fields.append("orders_redirect_url = %s")
            params.append(data["orders_redirect_url"])
        if "orders_redirect_message" in data:
            update_fields.append("orders_redirect_message = %s")
            params.append(data["orders_redirect_message"])
        if "reservations_sms_redirect_enabled" in data:
            update_fields.append("reservations_sms_redirect_enabled = %s")
            params.append(data["reservations_sms_redirect_enabled"])
        if "reservations_redirect_url" in data:
            update_fields.append("reservations_redirect_url = %s")
            params.append(data["reservations_redirect_url"])
        if "reservations_redirect_message" in data:
            update_fields.append("reservations_redirect_message = %s")
            params.append(data["reservations_redirect_message"])

        if not update_fields:
            return False

        update_fields.append("updated_at = NOW()")
        params.append(business_id)

        query = f"""
            UPDATE Business_Features
            SET {', '.join(update_fields)}
            WHERE business_id = %s
        """
        affected = self._execute_update(query, tuple(params))
        return affected > 0
