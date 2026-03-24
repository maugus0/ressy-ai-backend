"""
MySQL repository for menu item to option group mappings.
"""

from __future__ import annotations

from typing import Any, Dict, List

from app.repositories.mysql_base import MySQLBaseRepository


class MySQLMenuItemOptionRepository(MySQLBaseRepository):
    """Repository for menu item option group mappings."""

    def upsert_item_group(self, menu_item_id: int, group_id: int, overrides: Dict[str, Any]) -> int:
        query = """
            INSERT INTO Menu_Item_Option_Groups (
                menu_item_id,
                group_id,
                selection_type_override,
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
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
            ON DUPLICATE KEY UPDATE
                selection_type_override = VALUES(selection_type_override),
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
                menu_item_id,
                group_id,
                overrides.get("selection_type_override"),
                overrides.get("min_select_override"),
                overrides.get("max_select_override"),
                overrides.get("free_allowance_override"),
                overrides.get("allows_quantity_override"),
                overrides.get("max_quantity_per_option_override"),
                overrides.get("is_required_override"),
                overrides.get("sort_order", 0),
            ),
        )

    def detach_item_group(self, menu_item_id: int, group_id: int) -> int:
        query = "DELETE FROM Menu_Item_Option_Groups WHERE menu_item_id = %s AND group_id = %s"
        return self._execute_update(query, (menu_item_id, group_id))

    def list_item_groups(self, menu_item_id: int) -> List[Dict[str, Any]]:
        query = """
            SELECT * FROM Menu_Item_Option_Groups
            WHERE menu_item_id = %s
            ORDER BY sort_order, group_id
        """
        return self._execute_query(query, (menu_item_id,))

    def list_by_restaurant(self, restaurant_id: int) -> List[Dict[str, Any]]:
        query = """
            SELECT mig.*
            FROM Menu_Item_Option_Groups mig
            JOIN Menus m ON m.id = mig.menu_item_id
            WHERE m.restaurant_id = %s
            ORDER BY mig.menu_item_id, mig.sort_order, mig.group_id
        """
        return self._execute_query(query, (restaurant_id,))

    def has_group_attachment(self, group_id: int) -> bool:
        query = """
            SELECT 1
            FROM Menu_Item_Option_Groups
            WHERE group_id = %s
            LIMIT 1
        """
        return bool(self._execute_query(query, (group_id,)))
