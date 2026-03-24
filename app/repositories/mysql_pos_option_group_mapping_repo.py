"""
MySQL repository for generic POS option group mappings.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.repositories.mysql_base import MySQLBaseRepository


class MySQLPOSOptionGroupMappingRepository(MySQLBaseRepository):
    """Repository for external POS option group mappings."""

    def get_by_internal_group(self, option_group_id: int, pos_integration_id: int) -> Optional[Dict[str, Any]]:
        query = """
            SELECT * FROM POS_Option_Group_Mappings
            WHERE option_group_id = %s AND pos_integration_id = %s
            LIMIT 1
        """
        results = self._execute_query(query, (option_group_id, pos_integration_id))
        return results[0] if results else None

    def get_by_external_group(self, pos_integration_id: int, external_group_id: str) -> Optional[Dict[str, Any]]:
        query = """
            SELECT * FROM POS_Option_Group_Mappings
            WHERE pos_integration_id = %s AND external_group_id = %s
            LIMIT 1
        """
        results = self._execute_query(query, (pos_integration_id, external_group_id))
        return results[0] if results else None

    def list_by_restaurant(self, restaurant_id: int, pos_integration_id: int) -> List[Dict[str, Any]]:
        query = """
            SELECT * FROM POS_Option_Group_Mappings
            WHERE restaurant_id = %s AND pos_integration_id = %s
            ORDER BY option_group_id
        """
        return self._execute_query(query, (restaurant_id, pos_integration_id))

    def upsert_mapping(
        self,
        *,
        restaurant_id: int,
        pos_integration_id: int,
        option_group_id: int,
        external_group_id: str,
        external_parent_id: Optional[str] = None,
        external_object_type: str = "OPTION_GROUP",
        external_name: Optional[str] = None,
        external_version: Optional[str] = None,
        is_active: bool = True,
    ) -> int:
        query = """
            INSERT INTO POS_Option_Group_Mappings (
                restaurant_id,
                pos_integration_id,
                option_group_id,
                external_group_id,
                external_parent_id,
                external_object_type,
                external_name,
                external_version,
                is_active,
                last_seen_at,
                created_at,
                updated_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW(), NOW())
            ON DUPLICATE KEY UPDATE
                external_group_id = VALUES(external_group_id),
                external_parent_id = VALUES(external_parent_id),
                external_object_type = VALUES(external_object_type),
                external_name = VALUES(external_name),
                external_version = VALUES(external_version),
                is_active = VALUES(is_active),
                last_seen_at = NOW(),
                updated_at = NOW()
        """
        return self._execute_insert(
            query,
            (
                restaurant_id,
                pos_integration_id,
                option_group_id,
                external_group_id,
                external_parent_id,
                external_object_type,
                external_name,
                external_version,
                is_active,
            ),
        )

    def set_active_state_for_missing(
        self,
        *,
        restaurant_id: int,
        pos_integration_id: int,
        active_external_group_ids: List[str],
        is_active: bool,
    ) -> int:
        params: List[Any] = [is_active, restaurant_id, pos_integration_id]
        query = """
            UPDATE POS_Option_Group_Mappings
            SET is_active = %s, updated_at = NOW()
            WHERE restaurant_id = %s AND pos_integration_id = %s
        """
        if active_external_group_ids:
            placeholders = ", ".join(["%s"] * len(active_external_group_ids))
            query += f" AND external_group_id NOT IN ({placeholders})"
            params.extend(active_external_group_ids)
        return self._execute_update(query, tuple(params))
