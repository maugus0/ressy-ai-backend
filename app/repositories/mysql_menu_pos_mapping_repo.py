from datetime import datetime
from typing import Any, Dict, List, Optional

from app.repositories.mysql_base import MySQLBaseRepository
from app.utils.logging_config import get_logger

logger = get_logger(__name__)


class MySQLMenuPOSMappingRepository(MySQLBaseRepository):
    def get_mapping(self, menu_item_id: int, pos_integration_id: int) -> Optional[Dict]:
        query = """
            SELECT
                id,
                restaurant_id,
                menu_item_id,
                pos_integration_id,
                pos_menu_item_id,
                pos_menu_item_name,
                last_synced_at,
                created_at,
                updated_at
            FROM Menu_POS_Mapping
            WHERE menu_item_id = %s AND pos_integration_id = %s
            LIMIT 1
        """
        results = self._execute_query(query, (menu_item_id, pos_integration_id))
        return results[0] if results else None

    def get_mappings_by_restaurant(self, restaurant_id: int, pos_integration_id: int) -> List[Dict]:
        query = """
            SELECT
                id,
                restaurant_id,
                menu_item_id,
                pos_integration_id,
                pos_menu_item_id,
                pos_menu_item_name,
                last_synced_at,
                created_at,
                updated_at
            FROM Menu_POS_Mapping
            WHERE restaurant_id = %s AND pos_integration_id = %s
        """
        return self._execute_query(query, (restaurant_id, pos_integration_id))

    def create_mapping(
        self,
        restaurant_id: int,
        menu_item_id: int,
        pos_integration_id: int,
        pos_menu_item_id: str,
        pos_menu_item_name: Optional[str] = None,
    ) -> int:
        query = """
            INSERT INTO Menu_POS_Mapping
            (restaurant_id, menu_item_id, pos_integration_id, pos_menu_item_id, pos_menu_item_name)
            VALUES (%s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                pos_menu_item_id = VALUES(pos_menu_item_id),
                pos_menu_item_name = VALUES(pos_menu_item_name),
                last_synced_at = NOW(),
                updated_at = NOW()
        """
        return self._execute_insert(
            query, (restaurant_id, menu_item_id, pos_integration_id, pos_menu_item_id, pos_menu_item_name)
        )

    def update_mapping(
        self, mapping_id: int, pos_menu_item_id: Optional[str] = None, pos_menu_item_name: Optional[str] = None
    ) -> bool:
        update_fields = []
        params = []
        if pos_menu_item_id is not None:
            update_fields.append("pos_menu_item_id = %s")
            params.append(pos_menu_item_id)
        if pos_menu_item_name is not None:
            update_fields.append("pos_menu_item_name = %s")
            params.append(pos_menu_item_name)
        if not update_fields:
            return False
        update_fields.append("last_synced_at = NOW()")
        update_fields.append("updated_at = NOW()")
        params.append(mapping_id)
        query = f"UPDATE Menu_POS_Mapping SET {', '.join(update_fields)} WHERE id = %s"
        affected = self._execute_update(query, tuple(params))
        return affected > 0

    def delete_mapping(self, mapping_id: int) -> bool:
        query = "DELETE FROM Menu_POS_Mapping WHERE id = %s"
        affected = self._execute_update(query, (mapping_id,))
        return affected > 0

    def bulk_create_mappings(self, mappings: List[Dict[str, Any]]) -> int:
        if not mappings:
            return 0
        query = """
            INSERT INTO Menu_POS_Mapping
            (restaurant_id, menu_item_id, pos_integration_id, pos_menu_item_id, pos_menu_item_name)
            VALUES (%s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                pos_menu_item_id = VALUES(pos_menu_item_id),
                pos_menu_item_name = VALUES(pos_menu_item_name),
                last_synced_at = NOW(),
                updated_at = NOW()
        """
        values = [
            (
                m["restaurant_id"],
                m["menu_item_id"],
                m["pos_integration_id"],
                m["pos_menu_item_id"],
                m.get("pos_menu_item_name"),
            )
            for m in mappings
        ]
        connection = None
        cursor = None
        try:
            connection = self._get_connection()
            if connection is None:
                raise RuntimeError("Database connection unavailable")
            cursor = connection.cursor()
            cursor.executemany(query, values)
            connection.commit()
            return cursor.rowcount
        except Exception as e:
            if connection:
                try:
                    connection.rollback()
                except Exception:
                    pass
            logger.exception("Error bulk creating menu POS mappings: %s", e)
            raise
        finally:
            if cursor:
                try:
                    cursor.close()
                except Exception:
                    pass
            self._return_connection(connection)
