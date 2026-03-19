"""
MySQL Catalogue Repository for fetching available catalogue items.
"""

import json
from typing import Any, Dict, List, Optional, Tuple

from app.repositories.mysql_base import MySQLBaseRepository
from app.utils.logging_config import get_logger


class MySQLCatalogueRepository(MySQLBaseRepository):
    """Repository for catalogue data access in MySQL."""

    logger = get_logger(__name__)

    def _parse_suggested_items(self, item: Dict) -> Dict:
        """Parse suggested_items and metadata JSON fields."""
        if item:
            # Parse suggested_items
            if item.get("suggested_items"):
                try:
                    if isinstance(item["suggested_items"], str):
                        item["suggested_items"] = json.loads(item["suggested_items"])
                except (json.JSONDecodeError, TypeError):
                    item["suggested_items"] = []
            else:
                item["suggested_items"] = []
            
            # Parse metadata
            if item.get("metadata"):
                try:
                    if isinstance(item["metadata"], str):
                        item["metadata"] = json.loads(item["metadata"])
                except (json.JSONDecodeError, TypeError):
                    item["metadata"] = None
        return item

    def get_available_items_by_business(self, business_id: int) -> List[Dict]:
        """
        Get all available catalogue items for a restaurant.
        Only returns items where is_available = TRUE.
        """
        query = """
            SELECT
                id,
                business_id,
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
            FROM Catalogue
            WHERE business_id = %s
              AND is_available = TRUE
            ORDER BY category, sub_category, item_name
        """
        items = self._execute_query(query, (business_id,))
        return [self._parse_suggested_items(item) for item in items]

    def get_catalogue_item_by_name(self, business_id: int, item_name: str) -> Dict:
        """
        Get catalogue item by name (for order details).
        """
        query = """
            SELECT id, business_id, item_name, price
            FROM Catalogue
            WHERE business_id = %s
              AND LOWER(item_name) LIKE LOWER(%s)
              AND is_available = TRUE
            LIMIT 1
        """
        results = self._execute_query(query, (business_id, f"%{item_name}%"))
        return results[0] if results else None

    def catalogue_item_name_exists(self, business_id: int, item_name: str, exclude_catalogue_id: Optional[int] = None) -> bool:
        """
        Check if a catalogue item with the same name already exists in the restaurant.
        Case-insensitive comparison.

        Args:
            business_id: ID of the restaurant
            item_name: Name of the catalogue item to check
            exclude_catalogue_id: Optional catalogue item ID to exclude from the check (for updates)

        Returns:
            True if item name exists, False otherwise
        """
        query = """
            SELECT COUNT(*) as count
            FROM Catalogue
            WHERE business_id = %s
              AND LOWER(TRIM(item_name)) = LOWER(TRIM(%s))
        """
        params = [business_id, item_name]

        if exclude_catalogue_id:
            query += " AND id != %s"
            params.append(exclude_catalogue_id)

        results = self._execute_query(query, tuple(params))
        return results[0]["count"] > 0 if results else False

    def create_catalogue(self, business_id: int, data: Dict[str, Any]) -> int:
        """Create a new catalogue item."""
        query = """
            INSERT INTO Catalogue (business_id, category, sub_category, item_name, item_desc, metadata, price, avg_prep_time, suggested_items, is_available, is_special, created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
        """
        suggested_items = data.get("suggested_items")
        suggested_items_json = json.dumps(suggested_items) if suggested_items else json.dumps([])
        
        metadata = data.get("metadata")
        metadata_json = json.dumps(metadata) if metadata else None

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
                business_id,
                data.get("category"),
                data.get("sub_category"),
                data.get("item_name"),
                data.get("item_desc"),
                metadata_json,
                data.get("price", 0.0),
                data.get("avg_prep_time"),
                suggested_items_json,
                is_available,
                is_special,
            ),
        )

    def get_catalogues_by_restaurant(self, business_id: int) -> List[Dict]:
        query = """
            SELECT * FROM Catalogue
            WHERE business_id = %s
            ORDER BY category, sub_category, item_name
        """
        items = self._execute_query(query, (business_id,))
        return [self._parse_suggested_items(item) for item in items]

    def get_catalogue_by_id(self, business_id: int, catalogue_id: int) -> Dict:
        query = "SELECT * FROM Catalogue WHERE business_id = %s AND id = %s LIMIT 1"
        results = self._execute_query(query, (business_id, catalogue_id))
        return self._parse_suggested_items(results[0]) if results else {}

    def get_by_id(self, catalogue_id: int) -> Optional[Dict]:
        """Get a catalogue item by ID (without business_id restriction)."""
        query = """
            SELECT
                c.*,
                b.name as business_name
            FROM Catalogue c
            LEFT JOIN Businesses b ON c.business_id = b.id
            WHERE c.id = %s
            LIMIT 1
        """
        results = self._execute_query(query, (catalogue_id,))
        return self._parse_suggested_items(results[0]) if results else None

    def get_by_ids(self, catalogue_ids: List[int]) -> Dict[int, Dict]:
        """
        Get multiple catalogue items by their IDs in a single query.

        Args:
            catalogue_ids: List of catalogue item IDs to fetch

        Returns:
            Dictionary mapping item_id to catalogue item data.
            Missing items will not be present in the dictionary.
        """
        if not catalogue_ids:
            return {}

        placeholders = ", ".join(["%s"] * len(catalogue_ids))
        query = f"""
            SELECT
                m.*,
                b.name as business_name
            FROM Catalogue c
            LEFT JOIN Businesses r ON m.business_id = r.id
            WHERE c.id IN ({placeholders})
        """
        # Ensure catalogue_ids are integers for consistent query with error handling
        catalogue_ids_int: List[int] = []
        for mid in catalogue_ids:
            try:
                catalogue_ids_int.append(int(mid))
            except (TypeError, ValueError) as exc:
                raise ValueError(f"Invalid catalogue ID '{mid}' in catalogue_ids; expected an integer.") from exc

        results = self._execute_query(query, tuple(catalogue_ids_int))

        # Build a dictionary keyed by item ID for O(1) lookup
        items_by_id: Dict[int, Dict] = {}
        for item in results:
            parsed_item = self._parse_suggested_items(item)
            # Ensure the ID key is an integer for consistent lookup with error handling
            try:
                item_id_from_db = int(parsed_item["id"])
            except (TypeError, ValueError, KeyError) as exc:
                # Log the error but don't fail the entire query - skip this item
                self.logger.warning(
                    "Skipping catalogue item with invalid ID: %s (type: %s). Error: %s",
                    parsed_item.get("id", "missing"),
                    type(parsed_item.get("id")).__name__,
                    exc,
                )
                continue
            items_by_id[item_id_from_db] = parsed_item

        return items_by_id

    def get_paginated_by_business(  # pylint: disable=too-many-arguments,too-many-positional-arguments,too-many-locals
        self,
        business_id: int,
        page: int = 1,
        limit: int = 50,
        category: Optional[str] = None,
        sub_category: Optional[str] = None,
        is_available: Optional[bool] = None,
        is_special: Optional[bool] = None,
        search: Optional[str] = None,
    ) -> Tuple[List[Dict], int]:
        """
        Get paginated catalogue items with filters.

        Args:
            business_id: ID of the restaurant
            page: Page number (1-indexed)
            limit: Number of items per page
            category: Filter by category
            sub_category: Filter by sub-category
            is_available: Filter by availability
            is_special: Filter by special status
            search: Search term for item name

        Returns:
            Tuple of (list of catalogue items, total count)
        """
        # Build WHERE clause
        where_clauses = ["m.business_id = %s"]
        params: List[Any] = [business_id]

        if category:
            where_clauses.append("c.category = %s")
            params.append(category)

        if sub_category:
            where_clauses.append("c.sub_category = %s")
            params.append(sub_category)

        if is_available is not None:
            where_clauses.append("c.is_available = %s")
            params.append(is_available)

        if is_special is not None:
            where_clauses.append("c.is_special = %s")
            params.append(is_special)

        if search:
            where_clauses.append("c.item_name LIKE %s")
            params.append(f"%{search}%")

        where_clause = " AND ".join(where_clauses)

        # Get total count
        count_query = f"SELECT COUNT(*) as total FROM Catalogue c WHERE {where_clause}"
        count_result = self._execute_query(count_query, tuple(params))
        total = count_result[0]["total"] if count_result else 0

        # Get paginated results
        offset = (page - 1) * limit
        query = f"""
            SELECT
                m.*,
                b.name as business_name
            FROM Catalogue c
            LEFT JOIN Businesses r ON m.business_id = r.id
            WHERE {where_clause}
            ORDER BY c.category, c.sub_category, c.item_name
            LIMIT %s OFFSET %s
        """
        params.extend([limit, offset])

        items = self._execute_query(query, tuple(params))

        # Parse suggested_items JSON
        for item in items:
            self._parse_suggested_items(item)

        return items, total

    def update_catalogue(self, business_id: int, catalogue_id: int, data: Dict[str, Any]) -> int:
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
        params.extend([business_id, catalogue_id])
        query = f"UPDATE Catalogue SET {', '.join(fields)} WHERE business_id = %s AND id = %s"
        return self._execute_update(query, tuple(params))

    def update_by_id(self, catalogue_id: int, data: Dict[str, Any]) -> int:
        """Update a catalogue item by ID (without business_id restriction)."""
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
        params.append(catalogue_id)
        query = f"UPDATE Catalogue SET {', '.join(fields)} WHERE id = %s"
        return self._execute_update(query, tuple(params))

    def delete_catalogue(self, business_id: int, catalogue_id: int) -> int:
        return self._execute_update("DELETE FROM Catalogue WHERE business_id = %s AND id = %s", (business_id, catalogue_id))

    def delete_by_id(self, catalogue_id: int) -> int:
        """Delete a catalogue item by ID (without business_id restriction)."""
        # First, remove this item from suggested_items of other catalogue items
        self._remove_from_suggested_items(catalogue_id)
        return self._execute_update("DELETE FROM Catalogue WHERE id = %s", (catalogue_id,))

    def _remove_from_suggested_items(self, catalogue_id: int) -> None:
        """Remove a catalogue item ID from suggested_items of all other catalogue items."""
        # Get items that reference this catalogue_id in suggested_items
        query = """
            SELECT id, suggested_items
            FROM Catalogue
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
                if suggested and catalogue_id in suggested:
                    suggested.remove(catalogue_id)
                    update_query = "UPDATE Catalogue SET suggested_items = %s, updated_at = NOW() WHERE id = %s"
                    self._execute_update(update_query, (json.dumps(suggested), item["id"]))
            except (json.JSONDecodeError, TypeError, ValueError):
                continue

    def validate_suggested_items(self, catalogue_item_ids: List[int]) -> bool:
        """
        Validate that all suggested item IDs exist in the Catalogues table.

        Args:
            catalogue_item_ids: List of catalogue item IDs to validate

        Returns:
            True if all IDs exist, False otherwise
        """
        if not catalogue_item_ids:
            return True

        placeholders = ", ".join(["%s"] * len(catalogue_item_ids))
        query = f"SELECT COUNT(*) as count FROM Catalogue WHERE id IN ({placeholders})"
        result = self._execute_query(query, tuple(catalogue_item_ids))

        return result[0]["count"] == len(catalogue_item_ids) if result else False

    def validate_suggested_items_belong_to_business(self, catalogue_item_ids: List[int], business_id: int) -> bool:
        """
        Validate that all suggested item IDs belong to the same restaurant.

        Args:
            catalogue_item_ids: List of catalogue item IDs to validate
            business_id: ID of the restaurant

        Returns:
            True if all items belong to the restaurant, False otherwise
        """
        if not catalogue_item_ids:
            return True

        placeholders = ", ".join(["%s"] * len(catalogue_item_ids))
        query = f"""
            SELECT COUNT(*) as count
            FROM Catalogue
            WHERE id IN ({placeholders}) AND business_id = %s
        """
        params = list(catalogue_item_ids) + [business_id]
        result = self._execute_query(query, tuple(params))

        return result[0]["count"] == len(catalogue_item_ids) if result else False

    def items_exist(self, catalogue_item_ids: List[int]) -> bool:
        """
        Validate that all catalogue item IDs exist in the Catalogues table.

        Args:
            catalogue_item_ids: List of catalogue item IDs to validate

        Returns:
            True if all IDs exist, False otherwise
        """
        if not catalogue_item_ids:
            return True

        placeholders = ", ".join(["%s"] * len(catalogue_item_ids))
        query = f"SELECT COUNT(*) as count FROM Catalogue WHERE id IN ({placeholders})"
        result = self._execute_query(query, tuple(catalogue_item_ids))

        return result[0]["count"] == len(catalogue_item_ids) if result else False

    def bulk_update_catalogue_availability(self, business_id: int, catalogue_item_ids: List[int], is_available: bool) -> int:
        """
        Bulk update availability for multiple catalogue items.

        Args:
            business_id: ID of the restaurant (for security validation)
            catalogue_item_ids: List of catalogue item IDs to update
            is_available: New availability status

        Returns:
            Number of items updated
        """
        if not catalogue_item_ids:
            return 0

        placeholders = ", ".join(["%s"] * len(catalogue_item_ids))
        query = f"""
            UPDATE Catalogue
            SET is_available = %s, updated_at = NOW()
            WHERE id IN ({placeholders}) AND business_id = %s
        """

        params = [is_available] + catalogue_item_ids + [business_id]
        affected = self._execute_update(query, tuple(params))
        return affected

    def verify_items_belong_to_business(self, catalogue_item_ids: List[int], business_id: int) -> bool:
        """
        Verify that all catalogue items belong to the specified restaurant.

        Args:
            catalogue_item_ids: List of catalogue item IDs
            business_id: ID of the restaurant

        Returns:
            True if all items belong to the restaurant, False otherwise
        """
        if not catalogue_item_ids:
            return True

        placeholders = ", ".join(["%s"] * len(catalogue_item_ids))
        query = f"""
            SELECT COUNT(*) as count
            FROM Catalogue
            WHERE id IN ({placeholders}) AND business_id = %s
        """

        params = list(catalogue_item_ids) + [business_id]
        result = self._execute_query(query, tuple(params))

        return result[0]["count"] == len(catalogue_item_ids) if result else False

    def get_catalogue_categories(self, business_id: int) -> Dict[str, List[str]]:
        """
        Get distinct categories and sub-categories for a restaurant.

        Args:
            business_id: ID of the restaurant

        Returns:
            Dictionary with categories as keys and sub-categories as arrays
        """
        query = """
            SELECT DISTINCT category, sub_category
            FROM Catalogue
            WHERE business_id = %s AND category IS NOT NULL
            ORDER BY category, sub_category
        """

        results = self._execute_query(query, (business_id,))

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

    def create_special_catalogue_item(self, business_id: int, data: Dict[str, Any]) -> int:
        payload = dict(data)
        payload["is_special"] = True
        return self.create_catalogue(business_id, payload)

    def get_specials_by_business(self, business_id: int) -> List[Dict]:
        query = """
            SELECT * FROM Catalogue
            WHERE business_id = %s AND is_special = TRUE
            ORDER BY created_at DESC
        """
        items = self._execute_query(query, (business_id,))
        return [self._parse_suggested_items(item) for item in items]

    def get_special_catalogue_item_by_id(self, business_id: int, special_id: int) -> Dict:
        return self.get_catalogue_by_id(business_id, special_id)

    def update_special_catalogue_item(self, business_id: int, special_id: int, data: Dict[str, Any]) -> int:
        payload = dict(data)
        payload["is_special"] = True
        return self.update_catalogue(business_id, special_id, payload)

    def delete_special_catalogue_item(self, business_id: int, special_id: int) -> int:
        return self.delete_catalogue(business_id, special_id)

    def get_option_groups_for_catalogue_item(self, catalogue_item_id: int) -> List[Dict[str, Any]]:
        """
        Fetch option groups (with overrides) and values for a catalogue item.
        """
        group_query = """
            SELECT
                mog.*,
                mig.catalogue_item_id,
                cig.min_select_override,
                cig.max_select_override,
                cig.free_allowance_override,
                cig.allows_quantity_override,
                cig.max_quantity_per_option_override,
                cig.is_required_override,
                cig.sort_order AS item_sort_order
            FROM Catalogue_Item_Option_Groups mig
            JOIN Catalogue_Option_Groups mog ON cig.group_id = cog.id
            WHERE mig.catalogue_item_id = %s
            ORDER BY cig.sort_order, cog.sort_order, cog.name
        """
        groups = self._execute_query(group_query, (catalogue_item_id,))
        if not groups:
            return []
        group_ids = [group["id"] for group in groups if group.get("id") is not None]
        if not group_ids:
            return groups
        placeholders = ", ".join(["%s"] * len(group_ids))
        values_query = f"""
            SELECT * FROM Catalogue_Option_Values
            WHERE group_id IN ({placeholders})
            ORDER BY sort_order, name
        """
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
            self._apply_option_group_overrides(group)
        return groups

    def get_catalogue_item_with_options(self, catalogue_item_id: int) -> Optional[Dict[str, Any]]:
        """
        Fetch a catalogue item and attach option groups/values when present.
        """
        item = self.get_by_id(catalogue_item_id)
        if not item:
            return None
        item["option_groups"] = self.get_option_groups_for_catalogue_item(catalogue_item_id)
        return item

    def get_option_group_summaries_for_catalogue_items(self, catalogue_item_ids: List[int]) -> Dict[int, List[Dict[str, Any]]]:
        """
        Fetch summarized option group data for multiple catalogue items in one query.
        """
        if not catalogue_item_ids:
            return {}
        placeholders = ", ".join(["%s"] * len(catalogue_item_ids))
        query = f"""
            SELECT
                mig.catalogue_item_id,
                mog.id AS group_id,
                cog.name,
                mog.prompt_style,
                mog.selection_type,
                COALESCE(cig.min_select_override, mog.min_select) AS min_select,
                COALESCE(cig.max_select_override, mog.max_select) AS max_select,
                COALESCE(cig.free_allowance_override, mog.free_allowance) AS free_allowance,
                COALESCE(cig.allows_quantity_override, mog.allows_quantity) AS allows_quantity,
                COALESCE(cig.max_quantity_per_option_override, mog.max_quantity_per_option) AS max_quantity_per_option,
                COALESCE(cig.is_required_override, mog.is_required) AS is_required,
                mog.is_available
            FROM Catalogue_Item_Option_Groups mig
            JOIN Catalogue_Option_Groups mog ON cig.group_id = cog.id
            WHERE mig.catalogue_item_id IN ({placeholders})
            ORDER BY mig.catalogue_item_id, mig.sort_order, cog.sort_order, cog.name
        """
        results = self._execute_query(query, tuple(catalogue_item_ids))
        summaries: Dict[int, List[Dict[str, Any]]] = {}
        for row in results:
            catalogue_item_id = row.get("catalogue_item_id")
            if catalogue_item_id is None:
                continue
            summaries.setdefault(int(catalogue_item_id), []).append(
                {
                    "group_id": row.get("group_id"),
                    "name": row.get("name"),
                    "prompt_style": row.get("prompt_style"),
                    "selection_type": row.get("selection_type"),
                    "min_select": row.get("min_select"),
                    "max_select": row.get("max_select"),
                    "free_allowance": row.get("free_allowance"),
                    "allows_quantity": row.get("allows_quantity"),
                    "max_quantity_per_option": row.get("max_quantity_per_option"),
                    "is_required": row.get("is_required"),
                    "is_available": row.get("is_available"),
                }
            )
        return summaries

    def get_catalogue_items_with_option_groups(self, catalogue_item_ids: List[int]) -> Dict[int, bool]:
        """
        Return which catalogue items have option groups attached.
        """
        if not catalogue_item_ids:
            return {}
        placeholders = ", ".join(["%s"] * len(catalogue_item_ids))
        query = f"""
            SELECT DISTINCT catalogue_item_id
            FROM Catalogue_Item_Option_Groups
            WHERE catalogue_item_id IN ({placeholders})
        """
        results = self._execute_query(query, tuple(catalogue_item_ids))
        return {int(row["catalogue_item_id"]): True for row in results if row.get("catalogue_item_id") is not None}

    @staticmethod
    def _apply_option_group_overrides(group: Dict[str, Any]) -> None:
        override_map = {
            "min_select": "min_select_override",
            "max_select": "max_select_override",
            "free_allowance": "free_allowance_override",
            "allows_quantity": "allows_quantity_override",
            "max_quantity_per_option": "max_quantity_per_option_override",
            "is_required": "is_required_override",
        }
        for field, override_field in override_map.items():
            if override_field in group and group[override_field] is not None:
                group[field] = group[override_field]
