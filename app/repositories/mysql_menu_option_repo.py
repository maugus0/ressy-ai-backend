"""
MySQL repositories for menu option groups and values.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.repositories.mysql_base import MySQLBaseRepository


class MySQLMenuOptionRepository(MySQLBaseRepository):
    """Repository for menu option group/value data access."""

    def create_group(self, restaurant_id: int, data: Dict[str, Any]) -> int:
        query = """
            INSERT INTO Menu_Option_Groups (
                restaurant_id, name, description, selection_type, min_select, max_select,
                free_allowance, free_allowance_strategy, allows_quantity, max_quantity_per_option, prompt_style,
                is_required, is_available, is_active, catalog_source, source_name, source_description,
                input_type, text_required, max_text_length, sort_order, created_at, updated_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
        """
        return self._execute_insert(
            query,
            (
                restaurant_id,
                data.get("name"),
                data.get("description"),
                data.get("selection_type", "multiple"),
                data.get("min_select", 0),
                data.get("max_select"),
                data.get("free_allowance", 0),
                data.get("free_allowance_strategy", "HIGHEST_PRICE_FIRST"),
                data.get("allows_quantity", False),
                data.get("max_quantity_per_option"),
                data.get("prompt_style", "ASK_IF_MENTIONED"),
                data.get("is_required", False),
                data.get("is_available", True),
                data.get("is_active", True),
                data.get("catalog_source", "INTERNAL"),
                data.get("source_name"),
                data.get("source_description"),
                data.get("input_type", "SELECT"),
                data.get("text_required", False),
                data.get("max_text_length"),
                data.get("sort_order", 0),
            ),
        )

    def update_group(self, group_id: int, data: Dict[str, Any]) -> int:
        fields: List[str] = []
        params: List[Any] = []
        for field in (
            "name",
            "description",
            "selection_type",
            "min_select",
            "max_select",
            "free_allowance",
            "free_allowance_strategy",
            "allows_quantity",
            "max_quantity_per_option",
            "prompt_style",
            "is_required",
            "is_available",
            "is_active",
            "catalog_source",
            "source_name",
            "source_description",
            "input_type",
            "text_required",
            "max_text_length",
            "sort_order",
        ):
            if field in data:
                fields.append(f"{field} = %s")
                params.append(data[field])
        if not fields:
            return 0
        fields.append("updated_at = NOW()")
        params.append(group_id)
        query = f"UPDATE Menu_Option_Groups SET {', '.join(fields)} WHERE id = %s"
        return self._execute_update(query, tuple(params))

    def get_group_by_id(self, group_id: int) -> Optional[Dict[str, Any]]:
        query = "SELECT * FROM Menu_Option_Groups WHERE id = %s LIMIT 1"
        results = self._execute_query(query, (group_id,))
        return results[0] if results else None

    def list_groups_by_restaurant(
        self, restaurant_id: int, only_active: bool = False, only_available: bool = False
    ) -> List[Dict[str, Any]]:
        query = "SELECT * FROM Menu_Option_Groups WHERE restaurant_id = %s"
        if only_active:
            query += " AND is_active = TRUE"
        if only_available:
            query += " AND is_available = TRUE"
        query += " ORDER BY sort_order, name"
        return self._execute_query(query, (restaurant_id,))

    def delete_group(self, group_id: int) -> int:
        query = "DELETE FROM Menu_Option_Groups WHERE id = %s"
        return self._execute_update(query, (group_id,))

    def set_group_active_state_by_ids(self, group_ids: List[int], is_active: bool) -> int:
        if not group_ids:
            return 0
        placeholders = ", ".join(["%s"] * len(group_ids))
        query = f"UPDATE Menu_Option_Groups SET is_active = %s, updated_at = NOW() WHERE id IN ({placeholders})"
        params = [is_active] + group_ids
        return self._execute_update(query, tuple(params))

    def unset_default_in_group(self, group_id: int) -> int:
        query = "UPDATE Menu_Option_Values SET is_default = FALSE WHERE group_id = %s"
        return self._execute_update(query, (group_id,))

    def create_value(self, group_id: int, data: Dict[str, Any]) -> int:
        query = """
            INSERT INTO Menu_Option_Values (
                group_id, name, price_delta, is_default, is_available, is_active, catalog_source, source_name,
                sort_order, created_at, updated_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
        """
        return self._execute_insert(
            query,
            (
                group_id,
                data.get("name"),
                data.get("price_delta", 0),
                data.get("is_default", False),
                data.get("is_available", True),
                data.get("is_active", True),
                data.get("catalog_source", "INTERNAL"),
                data.get("source_name"),
                data.get("sort_order", 0),
            ),
        )

    def update_value(self, value_id: int, data: Dict[str, Any]) -> int:
        fields: List[str] = []
        params: List[Any] = []
        for field in (
            "name",
            "price_delta",
            "is_default",
            "is_available",
            "is_active",
            "catalog_source",
            "source_name",
            "sort_order",
        ):
            if field in data:
                fields.append(f"{field} = %s")
                params.append(data[field])
        if not fields:
            return 0
        fields.append("updated_at = NOW()")
        params.append(value_id)
        query = f"UPDATE Menu_Option_Values SET {', '.join(fields)} WHERE id = %s"
        return self._execute_update(query, tuple(params))

    def get_value_by_id(self, value_id: int) -> Optional[Dict[str, Any]]:
        query = "SELECT * FROM Menu_Option_Values WHERE id = %s LIMIT 1"
        results = self._execute_query(query, (value_id,))
        return results[0] if results else None

    def list_values_by_group(
        self, group_id: int, only_active: bool = False, only_available: bool = False
    ) -> List[Dict[str, Any]]:
        query = "SELECT * FROM Menu_Option_Values WHERE group_id = %s"
        if only_active:
            query += " AND is_active = TRUE"
        if only_available:
            query += " AND is_available = TRUE"
        query += " ORDER BY sort_order, name"
        return self._execute_query(query, (group_id,))

    def count_available_values(self, group_id: int) -> int:
        query = """
            SELECT COUNT(*) AS count
            FROM Menu_Option_Values
            WHERE group_id = %s AND is_available = TRUE
        """
        results = self._execute_query(query, (group_id,))
        return int(results[0]["count"]) if results else 0

    def count_defaults(self, group_id: int) -> int:
        query = """
            SELECT COUNT(*) AS count
            FROM Menu_Option_Values
            WHERE group_id = %s AND is_default = TRUE
        """
        results = self._execute_query(query, (group_id,))
        return int(results[0]["count"]) if results else 0

    def has_order_usage_for_group(self, group_id: int) -> bool:
        query = """
            SELECT 1
            FROM Order_Item_Options_Snapshots oio
            WHERE oio.option_group_id = %s
               OR EXISTS (
                    SELECT 1
                    FROM Menu_Option_Values mov
                    WHERE mov.id = oio.option_value_id AND mov.group_id = %s
               )
            LIMIT 1
        """
        return bool(self._execute_query(query, (group_id, group_id)))

    def has_order_usage_for_value(self, value_id: int) -> bool:
        query = """
            SELECT 1
            FROM Order_Item_Options_Snapshots
            WHERE option_value_id = %s
            LIMIT 1
        """
        return bool(self._execute_query(query, (value_id,)))

    def delete_value(self, value_id: int) -> int:
        query = "DELETE FROM Menu_Option_Values WHERE id = %s"
        return self._execute_update(query, (value_id,))

    def set_value_active_state_by_ids(self, value_ids: List[int], is_active: bool) -> int:
        if not value_ids:
            return 0
        placeholders = ", ".join(["%s"] * len(value_ids))
        query = f"UPDATE Menu_Option_Values SET is_active = %s, updated_at = NOW() WHERE id IN ({placeholders})"
        params = [is_active] + value_ids
        return self._execute_update(query, tuple(params))

    def bulk_update_value_availability(self, value_ids: List[int], is_available: bool) -> int:
        if not value_ids:
            return 0
        placeholders = ", ".join(["%s"] * len(value_ids))
        query = f"UPDATE Menu_Option_Values SET is_available = %s, updated_at = NOW() WHERE id IN ({placeholders})"
        params = [is_available] + value_ids
        return self._execute_update(query, tuple(params))

    def list_groups_with_values(
        self, restaurant_id: int, only_active: bool = False, only_available: bool = False
    ) -> List[Dict[str, Any]]:
        groups = self.list_groups_by_restaurant(
            restaurant_id,
            only_active=only_active,
            only_available=only_available,
        )
        if not groups:
            return []
        group_ids = [group["id"] for group in groups if group.get("id") is not None]
        if not group_ids:
            return groups
        placeholders = ", ".join(["%s"] * len(group_ids))
        values_query = f"""
            SELECT * FROM Menu_Option_Values
            WHERE group_id IN ({placeholders})
        """
        if only_active:
            values_query += " AND is_active = TRUE"
        if only_available:
            values_query += " AND is_available = TRUE"
        values_query += " ORDER BY sort_order, name"
        values = self._execute_query(values_query, tuple(group_ids))
        values_by_group: Dict[int, List[Dict[str, Any]]] = {}
        for value in values:
            group_id = value.get("group_id")
            if group_id is None:
                continue
            values_by_group.setdefault(int(group_id), []).append(value)
        for group in groups:
            group_id = group.get("id")
            group["values"] = values_by_group.get(int(group_id), []) if group_id is not None else []
        return groups
