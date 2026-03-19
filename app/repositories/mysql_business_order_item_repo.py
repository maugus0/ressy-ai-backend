"""
MySQL repository for order item snapshots and customization options.
"""

from __future__ import annotations

from typing import Any, Dict, List

from app.repositories.mysql_base import MySQLBaseRepository


class MySQLOrderItemRepository(MySQLBaseRepository):
    """Repository for order item snapshot data."""

    def create_order_item(self, order_id: int, data: Dict[str, Any]) -> int:
        query = """
            INSERT INTO Business_Order_Item_Snapshots (
                order_id,
                catalogue_item_id,
                item_name_snapshot,
                base_price_snapshot,
                quantity,
                instructions,
                final_unit_price_snapshot,
                option_total_snapshot,
                total_price_snapshot,
                created_at,
                updated_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
        """
        return self._execute_insert(
            query,
            (
                order_id,
                data.get("catalogue_item_id"),
                data.get("item_name_snapshot"),
                data.get("base_price_snapshot", 0),
                data.get("quantity", 1),
                data.get("instructions"),
                data.get("final_unit_price_snapshot", 0),
                data.get("option_total_snapshot", 0),
                data.get("total_price_snapshot", 0),
            ),
        )

    def create_order_item_options(self, order_item_id: int, options: List[Dict[str, Any]]) -> int:
        if not options:
            return 0
        query = """
            INSERT INTO Business_Order_Item_Options_Snapshots (
                order_item_id,
                option_value_id,
                option_group_name_snapshot,
                option_value_name_snapshot,
                price_delta_snapshot,
                quantity,
                created_at,
                updated_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, NOW(), NOW())
        """
        params_list = [
            (
                order_item_id,
                opt.get("option_value_id"),
                opt.get("option_group_name_snapshot"),
                opt.get("option_value_name_snapshot"),
                opt.get("price_delta_snapshot", 0),
                opt.get("quantity", 1),
            )
            for opt in options
        ]
        return self._execute_many(query, params_list)

    def list_order_items(self, order_id: int) -> List[Dict[str, Any]]:
        query = """
            SELECT * FROM Business_Order_Item_Snapshots
            WHERE order_id = %s
            ORDER BY id
        """
        return self._execute_query(query, (order_id,))

    def list_order_item_options(self, order_id: int) -> List[Dict[str, Any]]:
        query = """
            SELECT oio.*, oi.order_id
            FROM Business_Order_Item_Options_Snapshots oio
            JOIN Business_Order_Item_Snapshots oi ON oio.order_item_id = oi.id
            WHERE oi.order_id = %s
            ORDER BY oio.id
        """
        return self._execute_query(query, (order_id,))

    def delete_order_items_by_order(self, order_id: int) -> int:
        query = "DELETE FROM Business_Order_Item_Snapshots WHERE order_id = %s"
        return self._execute_update(query, (order_id,))
