"""
MySQL Menu Repository for fetching available menu items.
"""

import json
from typing import Any, Dict, List, Optional, Tuple

from app.repositories.mysql_base import MySQLBaseRepository


class MySQLMenuRepository(MySQLBaseRepository):
    """Repository for menu data access in MySQL."""

    def _parse_suggested_items(self, item: Dict) -> Dict:
        """Parse suggested_items JSON field."""
        if item and item.get("suggested_items"):
            try:
                if isinstance(item["suggested_items"], str):
                    item["suggested_items"] = json.loads(item["suggested_items"])
            except (json.JSONDecodeError, TypeError):
                item["suggested_items"] = []
        elif item:
            item["suggested_items"] = []
        return item

    def get_available_items_by_restaurant(self, restaurant_id: int) -> List[Dict]:
        """
        Get all available menu items for a restaurant.
        Only returns items where is_available = TRUE.
        """
        query = """
            SELECT
                id,
                restaurant_id,
                category,
                sub_category,
                item_name,
                item_desc,
                price,
                avg_prep_time,
                suggested_items,
                is_available,
                is_special,
                created_at,
                updated_at
            FROM Menus
            WHERE restaurant_id = %s
              AND is_available = TRUE
            ORDER BY category, sub_category, item_name
        """
        items = self._execute_query(query, (restaurant_id,))
        return [self._parse_suggested_items(item) for item in items]

    def get_item_by_name(self, restaurant_id: int, item_name: str) -> Dict:
        """
        Get menu item by name (for order details).
        """
        query = """
            SELECT id, restaurant_id, item_name, price
            FROM Menus
            WHERE restaurant_id = %s
              AND LOWER(item_name) LIKE LOWER(%s)
              AND is_available = TRUE
            LIMIT 1
        """
        results = self._execute_query(query, (restaurant_id, f"%{item_name}%"))
        return results[0] if results else None

    def item_name_exists(self, restaurant_id: int, item_name: str, exclude_menu_id: Optional[int] = None) -> bool:
        """
        Check if a menu item with the same name already exists in the restaurant.
        Case-insensitive comparison.

        Args:
            restaurant_id: ID of the restaurant
            item_name: Name of the menu item to check
            exclude_menu_id: Optional menu item ID to exclude from the check (for updates)

        Returns:
            True if item name exists, False otherwise
        """
        query = """
            SELECT COUNT(*) as count
            FROM Menus
            WHERE restaurant_id = %s
              AND LOWER(TRIM(item_name)) = LOWER(TRIM(%s))
        """
        params = [restaurant_id, item_name]

        if exclude_menu_id:
            query += " AND id != %s"
            params.append(exclude_menu_id)

        results = self._execute_query(query, tuple(params))
        return results[0]["count"] > 0 if results else False

    def create_menu(self, restaurant_id: int, data: Dict[str, Any]) -> int:
        """Create a new menu item."""
        query = """
            INSERT INTO Menus (restaurant_id, category, sub_category, item_name, item_desc, price, avg_prep_time, suggested_items, is_available, is_special, created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
        """
        suggested_items = data.get("suggested_items")
        suggested_items_json = json.dumps(suggested_items) if suggested_items else json.dumps([])

        # Normalize None values to defaults for boolean fields
        # This is a defensive check in case None values slip through
        is_available = data.get("is_available")
        if is_available is None:
            is_available = True
        is_special = data.get("is_special")
        if is_special is None:
            is_special = False

        return self._execute_insert(
            query,
            (
                restaurant_id,
                data.get("category"),
                data.get("sub_category"),
                data.get("item_name"),
                data.get("item_desc"),
                data.get("price", 0.0),
                data.get("avg_prep_time"),
                suggested_items_json,
                is_available,
                is_special,
            ),
        )

    def get_menus_by_restaurant(self, restaurant_id: int) -> List[Dict]:
        query = """
            SELECT * FROM Menus
            WHERE restaurant_id = %s
            ORDER BY category, sub_category, item_name
        """
        items = self._execute_query(query, (restaurant_id,))
        return [self._parse_suggested_items(item) for item in items]

    def get_menu_by_id(self, restaurant_id: int, menu_id: int) -> Dict:
        query = "SELECT * FROM Menus WHERE restaurant_id = %s AND id = %s LIMIT 1"
        results = self._execute_query(query, (restaurant_id, menu_id))
        return self._parse_suggested_items(results[0]) if results else {}

    def get_by_id(self, menu_id: int) -> Optional[Dict]:
        """Get a menu item by ID (without restaurant_id restriction)."""
        query = """
            SELECT
                m.*,
                r.name as restaurant_name
            FROM Menus m
            LEFT JOIN Restaurants r ON m.restaurant_id = r.id
            WHERE m.id = %s
            LIMIT 1
        """
        results = self._execute_query(query, (menu_id,))
        return self._parse_suggested_items(results[0]) if results else None

    def get_by_ids(self, menu_ids: List[int]) -> Dict[int, Dict]:
        """
        Get multiple menu items by their IDs in a single query.

        Args:
            menu_ids: List of menu item IDs to fetch

        Returns:
            Dictionary mapping item_id to menu item data.
            Missing items will not be present in the dictionary.
        """
        if not menu_ids:
            return {}

        placeholders = ", ".join(["%s"] * len(menu_ids))
        query = f"""
            SELECT
                m.*,
                r.name as restaurant_name
            FROM Menus m
            LEFT JOIN Restaurants r ON m.restaurant_id = r.id
            WHERE m.id IN ({placeholders})
        """
        # Ensure menu_ids are integers for consistent query with error handling
        menu_ids_int: List[int] = []
        for mid in menu_ids:
            try:
                menu_ids_int.append(int(mid))
            except (TypeError, ValueError) as exc:
                raise ValueError(f"Invalid menu ID '{mid}' in menu_ids; expected an integer.") from exc

        results = self._execute_query(query, tuple(menu_ids_int))

        # Build a dictionary keyed by item ID for O(1) lookup
        items_by_id: Dict[int, Dict] = {}
        for item in results:
            parsed_item = self._parse_suggested_items(item)
            # Ensure the ID key is an integer for consistent lookup with error handling
            try:
                item_id_from_db = int(parsed_item["id"])
            except (TypeError, ValueError, KeyError) as exc:
                # Log the error but don't fail the entire query - skip this item
                print(
                    f"[WARN] Skipping menu item with invalid ID: {parsed_item.get('id', 'missing')} "
                    f"(type: {type(parsed_item.get('id')).__name__}). Error: {exc}"
                )
                continue
            items_by_id[item_id_from_db] = parsed_item

        return items_by_id

    def get_paginated_by_restaurant(  # pylint: disable=too-many-arguments,too-many-positional-arguments,too-many-locals
        self,
        restaurant_id: int,
        page: int = 1,
        limit: int = 50,
        category: Optional[str] = None,
        sub_category: Optional[str] = None,
        is_available: Optional[bool] = None,
        is_special: Optional[bool] = None,
        search: Optional[str] = None,
    ) -> Tuple[List[Dict], int]:
        """
        Get paginated menu items with filters.

        Args:
            restaurant_id: ID of the restaurant
            page: Page number (1-indexed)
            limit: Number of items per page
            category: Filter by category
            sub_category: Filter by sub-category
            is_available: Filter by availability
            is_special: Filter by special status
            search: Search term for item name

        Returns:
            Tuple of (list of menu items, total count)
        """
        # Build WHERE clause
        where_clauses = ["m.restaurant_id = %s"]
        params: List[Any] = [restaurant_id]

        if category:
            where_clauses.append("m.category = %s")
            params.append(category)

        if sub_category:
            where_clauses.append("m.sub_category = %s")
            params.append(sub_category)

        if is_available is not None:
            where_clauses.append("m.is_available = %s")
            params.append(is_available)

        if is_special is not None:
            where_clauses.append("m.is_special = %s")
            params.append(is_special)

        if search:
            where_clauses.append("m.item_name LIKE %s")
            params.append(f"%{search}%")

        where_clause = " AND ".join(where_clauses)

        # Get total count
        count_query = f"SELECT COUNT(*) as total FROM Menus m WHERE {where_clause}"
        count_result = self._execute_query(count_query, tuple(params))
        total = count_result[0]["total"] if count_result else 0

        # Get paginated results
        offset = (page - 1) * limit
        query = f"""
            SELECT
                m.*,
                r.name as restaurant_name
            FROM Menus m
            LEFT JOIN Restaurants r ON m.restaurant_id = r.id
            WHERE {where_clause}
            ORDER BY m.category, m.sub_category, m.item_name
            LIMIT %s OFFSET %s
        """
        params.extend([limit, offset])

        items = self._execute_query(query, tuple(params))

        # Parse suggested_items JSON
        for item in items:
            self._parse_suggested_items(item)

        return items, total

    def update_menu(self, restaurant_id: int, menu_id: int, data: Dict[str, Any]) -> int:
        fields = []
        params = []
        for key in [
            "category",
            "sub_category",
            "item_name",
            "item_desc",
            "price",
            "avg_prep_time",
            "suggested_items",
            "is_available",
            "is_special",
        ]:
            if key in data:
                value = data[key]
                if key == "suggested_items":
                    value = json.dumps(value)
                fields.append(f"{key} = %s")
                params.append(value)
        if not fields:
            return 0
        fields.append("updated_at = NOW()")
        params.extend([restaurant_id, menu_id])
        query = f"UPDATE Menus SET {', '.join(fields)} WHERE restaurant_id = %s AND id = %s"
        return self._execute_update(query, tuple(params))

    def update_by_id(self, menu_id: int, data: Dict[str, Any]) -> int:
        """Update a menu item by ID (without restaurant_id restriction)."""
        fields = []
        params = []
        for key in [
            "category",
            "sub_category",
            "item_name",
            "item_desc",
            "price",
            "avg_prep_time",
            "suggested_items",
            "is_available",
            "is_special",
        ]:
            if key in data:
                value = data[key]
                if key == "suggested_items":
                    value = json.dumps(value)
                fields.append(f"{key} = %s")
                params.append(value)
        if not fields:
            return 0
        fields.append("updated_at = NOW()")
        params.append(menu_id)
        query = f"UPDATE Menus SET {', '.join(fields)} WHERE id = %s"
        return self._execute_update(query, tuple(params))

    def delete_menu(self, restaurant_id: int, menu_id: int) -> int:
        return self._execute_update("DELETE FROM Menus WHERE restaurant_id = %s AND id = %s", (restaurant_id, menu_id))

    def delete_by_id(self, menu_id: int) -> int:
        """Delete a menu item by ID (without restaurant_id restriction)."""
        # First, remove this item from suggested_items of other menu items
        self._remove_from_suggested_items(menu_id)
        return self._execute_update("DELETE FROM Menus WHERE id = %s", (menu_id,))

    def _remove_from_suggested_items(self, menu_id: int) -> None:
        """Remove a menu item ID from suggested_items of all other menu items."""
        # Get items that reference this menu_id in suggested_items
        query = """
            SELECT id, suggested_items
            FROM Menus
            WHERE suggested_items IS NOT NULL
              AND suggested_items != '[]'
              AND suggested_items != 'null'
        """
        items = self._execute_query(query)

        for item in items:
            try:
                suggested = item.get("suggested_items")
                if isinstance(suggested, str):
                    suggested = json.loads(suggested)
                if suggested and menu_id in suggested:
                    suggested.remove(menu_id)
                    update_query = "UPDATE Menus SET suggested_items = %s, updated_at = NOW() WHERE id = %s"
                    self._execute_update(update_query, (json.dumps(suggested), item["id"]))
            except (json.JSONDecodeError, TypeError, ValueError):
                continue

    def validate_suggested_items(self, menu_item_ids: List[int]) -> bool:
        """
        Validate that all suggested item IDs exist in the Menus table.

        Args:
            menu_item_ids: List of menu item IDs to validate

        Returns:
            True if all IDs exist, False otherwise
        """
        if not menu_item_ids:
            return True

        placeholders = ", ".join(["%s"] * len(menu_item_ids))
        query = f"SELECT COUNT(*) as count FROM Menus WHERE id IN ({placeholders})"
        result = self._execute_query(query, tuple(menu_item_ids))

        return result[0]["count"] == len(menu_item_ids) if result else False

    def validate_suggested_items_belong_to_restaurant(self, menu_item_ids: List[int], restaurant_id: int) -> bool:
        """
        Validate that all suggested item IDs belong to the same restaurant.

        Args:
            menu_item_ids: List of menu item IDs to validate
            restaurant_id: ID of the restaurant

        Returns:
            True if all items belong to the restaurant, False otherwise
        """
        if not menu_item_ids:
            return True

        placeholders = ", ".join(["%s"] * len(menu_item_ids))
        query = f"""
            SELECT COUNT(*) as count
            FROM Menus
            WHERE id IN ({placeholders}) AND restaurant_id = %s
        """
        params = list(menu_item_ids) + [restaurant_id]
        result = self._execute_query(query, tuple(params))

        return result[0]["count"] == len(menu_item_ids) if result else False

    def items_exist(self, menu_item_ids: List[int]) -> bool:
        """
        Validate that all menu item IDs exist in the Menus table.

        Args:
            menu_item_ids: List of menu item IDs to validate

        Returns:
            True if all IDs exist, False otherwise
        """
        if not menu_item_ids:
            return True

        placeholders = ", ".join(["%s"] * len(menu_item_ids))
        query = f"SELECT COUNT(*) as count FROM Menus WHERE id IN ({placeholders})"
        result = self._execute_query(query, tuple(menu_item_ids))

        return result[0]["count"] == len(menu_item_ids) if result else False

    def bulk_update_availability(self, restaurant_id: int, menu_item_ids: List[int], is_available: bool) -> int:
        """
        Bulk update availability for multiple menu items.

        Args:
            restaurant_id: ID of the restaurant (for security validation)
            menu_item_ids: List of menu item IDs to update
            is_available: New availability status

        Returns:
            Number of items updated
        """
        if not menu_item_ids:
            return 0

        placeholders = ", ".join(["%s"] * len(menu_item_ids))
        query = f"""
            UPDATE Menus
            SET is_available = %s, updated_at = NOW()
            WHERE id IN ({placeholders}) AND restaurant_id = %s
        """

        params = [is_available] + menu_item_ids + [restaurant_id]
        affected = self._execute_update(query, tuple(params))
        return affected

    def verify_items_belong_to_restaurant(self, menu_item_ids: List[int], restaurant_id: int) -> bool:
        """
        Verify that all menu items belong to the specified restaurant.

        Args:
            menu_item_ids: List of menu item IDs
            restaurant_id: ID of the restaurant

        Returns:
            True if all items belong to the restaurant, False otherwise
        """
        if not menu_item_ids:
            return True

        placeholders = ", ".join(["%s"] * len(menu_item_ids))
        query = f"""
            SELECT COUNT(*) as count
            FROM Menus
            WHERE id IN ({placeholders}) AND restaurant_id = %s
        """

        params = list(menu_item_ids) + [restaurant_id]
        result = self._execute_query(query, tuple(params))

        return result[0]["count"] == len(menu_item_ids) if result else False

    def get_menu_categories(self, restaurant_id: int) -> Dict[str, List[str]]:
        """
        Get distinct categories and sub-categories for a restaurant.

        Args:
            restaurant_id: ID of the restaurant

        Returns:
            Dictionary with categories as keys and sub-categories as arrays
        """
        query = """
            SELECT DISTINCT category, sub_category
            FROM Menus
            WHERE restaurant_id = %s AND category IS NOT NULL
            ORDER BY category, sub_category
        """

        results = self._execute_query(query, (restaurant_id,))

        # Organize into nested structure
        categories: Dict[str, List[str]] = {}
        for row in results:
            category = row.get("category")
            sub_category = row.get("sub_category")

            if category and category not in categories:
                categories[category] = []

            if category and sub_category and sub_category not in categories[category]:
                categories[category].append(sub_category)

        return categories

    def create_special(self, restaurant_id: int, data: Dict[str, Any]) -> int:
        payload = dict(data)
        payload["is_special"] = True
        return self.create_menu(restaurant_id, payload)

    def get_specials_by_restaurant(self, restaurant_id: int) -> List[Dict]:
        query = """
            SELECT * FROM Menus
            WHERE restaurant_id = %s AND is_special = TRUE
            ORDER BY created_at DESC
        """
        items = self._execute_query(query, (restaurant_id,))
        return [self._parse_suggested_items(item) for item in items]

    def get_special_by_id(self, restaurant_id: int, special_id: int) -> Dict:
        return self.get_menu_by_id(restaurant_id, special_id)

    def update_special(self, restaurant_id: int, special_id: int, data: Dict[str, Any]) -> int:
        payload = dict(data)
        payload["is_special"] = True
        return self.update_menu(restaurant_id, special_id, payload)

    def delete_special(self, restaurant_id: int, special_id: int) -> int:
        return self.delete_menu(restaurant_id, special_id)
