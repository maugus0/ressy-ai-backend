"""
MySQL repository for catalogue item to option group mappings.
"""

from __future__ import annotations

from typing import Any, Dict, List

from app.repositories.mysql_base import MySQLBaseRepository


class MySQLCatalogueItemOptionRepository(MySQLBaseRepository):
    """Repository for catalogue item option group mappings."""

    def upsert_item_group(self, catalogue_item_id: int, group_id: int, overrides: Dict[str, Any]) -> int:
        query = """
            INSERT INTO Catalogue_Item_Option_Groups (
                catalogue_item_id,
                group_id,
                min_select_override,
                max_select_override,
                free_allowance_override,
                allows_quantity_override,
                max_quantity_per_option_override,
                is_required_override,
                sort_order,
                created_at,
                updated_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
            ON DUPLICATE KEY UPDATE
                min_select_override = VALUES(min_select_override),
                max_select_override = VALUES(max_select_override),
                free_allowance_override = VALUES(free_allowance_override),
                allows_quantity_override = VALUES(allows_quantity_override),
                max_quantity_per_option_override = VALUES(max_quantity_per_option_override),
                is_required_override = VALUES(is_required_override),
                sort_order = VALUES(sort_order),
                updated_at = NOW()
        """
        return self._execute_insert(
            query,
            (
                catalogue_item_id,
                group_id,
                overrides.get("min_select_override"),
                overrides.get("max_select_override"),
                overrides.get("free_allowance_override"),
                overrides.get("allows_quantity_override"),
                overrides.get("max_quantity_per_option_override"),
                overrides.get("is_required_override"),
                overrides.get("sort_order", 0),
            ),
        )

    def detach_item_group(self, catalogue_item_id: int, group_id: int) -> int:
        query = "DELETE FROM Catalogue_Item_Option_Groups WHERE catalogue_item_id = %s AND group_id = %s"
        return self._execute_update(query, (catalogue_item_id, group_id))

    def list_item_groups(self, catalogue_item_id: int) -> List[Dict[str, Any]]:
        query = """
            SELECT * FROM Catalogue_Item_Option_Groups
            WHERE catalogue_item_id = %s
            ORDER BY sort_order, group_id
        """
        return self._execute_query(query, (catalogue_item_id,))

    def has_group_attachment(self, group_id: int) -> bool:
        query = """
            SELECT 1
            FROM Catalogue_Item_Option_Groups
            WHERE group_id = %s
            LIMIT 1
        """
        return bool(self._execute_query(query, (group_id,)))
