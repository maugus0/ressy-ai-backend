from typing import Any, Dict, List, Optional, Tuple

from fastapi import HTTPException, status

from app.repositories.mysql_menu_repo import MySQLMenuRepository
from app.repositories.mysql_restaurant_repo import MySQLRestaurantRepository


class MenuService:
    def __init__(
        self,
        menu_repo: Optional[MySQLMenuRepository] = None,
        restaurant_repo: Optional[MySQLRestaurantRepository] = None,
    ):
        self.menu_repo = menu_repo or MySQLMenuRepository()
        self.restaurant_repo = restaurant_repo or MySQLRestaurantRepository()

    def _validate_restaurant(self, restaurant_id: int) -> Dict[str, Any]:
        """Validate that a restaurant exists."""
        restaurant = self.restaurant_repo.get_by_id(restaurant_id)
        if not restaurant:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Restaurant not found")
        return restaurant

    def _validate_pagination(self, page: int, limit: int) -> Tuple[int, int]:
        """Validate pagination parameters."""
        if page < 1 or limit < 1:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="page and limit must be positive")
        return page, limit

    def _enrich_with_restaurant_name(
        self, item: Dict[str, Any], cache: Optional[Dict[int, Optional[str]]] = None
    ) -> Dict[str, Any]:
        """Populate restaurant_name if missing, caching lookups within a batch."""
        if not item:
            return item
        restaurant_id = item.get("restaurant_id")
        if item.get("restaurant_name") or restaurant_id is None:
            return item
        try:
            restaurant_id_int = int(restaurant_id)
        except (TypeError, ValueError):
            return item

        cache = cache if cache is not None else {}
        if restaurant_id_int not in cache:
            restaurant = self.restaurant_repo.get_by_id(restaurant_id_int)
            cache[restaurant_id_int] = restaurant.get("name") if restaurant else None
        restaurant_name = cache.get(restaurant_id_int)
        if restaurant_name:
            item["restaurant_name"] = restaurant_name
        return item

    # ==================== Legacy methods for backwards compatibility ====================

    def create_menu(self, restaurant_id: str, data: dict) -> dict:
        """Create a new menu (legacy method)."""
        menu_id = self.menu_repo.create_menu(int(restaurant_id), data)
        return {"message": "Menu created successfully", "menu_id": menu_id}

    def list_menus(self, restaurant_id: str) -> list:
        """List all menus for a restaurant (legacy method)."""
        return self.menu_repo.get_menus_by_restaurant(int(restaurant_id))

    def get_menu(self, restaurant_id: str, menu_id: str) -> dict:
        """Get a specific menu by ID (legacy method)."""
        return self.menu_repo.get_menu_by_id(int(restaurant_id), int(menu_id))

    def update_menu(self, restaurant_id: str, menu_id: str, data: dict) -> dict:
        """Update an existing menu (legacy method)."""
        self.menu_repo.update_menu(int(restaurant_id), int(menu_id), data)
        return {"message": "Menu updated successfully"}

    def delete_menu(self, restaurant_id: str, menu_id: str) -> dict:
        """Delete a menu (legacy method)."""
        self.menu_repo.delete_menu(int(restaurant_id), int(menu_id))
        return {"message": "Menu deleted successfully"}

    def get_available_items_by_restaurant(self, restaurant_id: str) -> list:
        """List available menu items (is_available = TRUE)."""
        return self.menu_repo.get_available_items_by_restaurant(int(restaurant_id))

    # ==================== New Admin API methods ====================

    def create_menu_item(self, restaurant_id: int, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a new menu item for a restaurant.

        Args:
            restaurant_id: ID of the restaurant
            data: Menu item data from MenuItemCreate model

        Returns:
            Created menu item with all details

        Raises:
            HTTPException: 404 if restaurant not found, 400 for validation errors
        """
        # Validate restaurant exists
        restaurant = self._validate_restaurant(restaurant_id)

        # Validate suggested_items if provided
        suggested_items = data.get("suggested_items")
        if suggested_items:
            if not self.menu_repo.validate_suggested_items(suggested_items):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="One or more suggested item IDs do not exist",
                )

        # Create the menu item
        menu_id = self.menu_repo.create_menu(restaurant_id, data)
        if not menu_id:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create menu item",
            )

        # Fetch and return the created item
        created_item = self.menu_repo.get_by_id(menu_id)
        if not created_item:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to retrieve created menu item",
            )

        # Enrich with restaurant name
        self._enrich_with_restaurant_name(created_item, {restaurant_id: restaurant.get("name")})
        return created_item

    def list_menu_items_paginated(  # pylint: disable=too-many-arguments,too-many-positional-arguments
        self,
        restaurant_id: int,
        page: int = 1,
        limit: int = 50,
        category: Optional[str] = None,
        sub_category: Optional[str] = None,
        is_available: Optional[bool] = None,
        is_special: Optional[bool] = None,
        search: Optional[str] = None,
    ) -> Dict[str, Any]:
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
            Dictionary with items and pagination info

        Raises:
            HTTPException: 404 if restaurant not found
        """
        # Validate restaurant exists
        self._validate_restaurant(restaurant_id)

        # Validate pagination
        page, limit = self._validate_pagination(page, limit)

        # Clean search term
        search_term = (search or "").strip() or None

        # Get paginated items
        items, total = self.menu_repo.get_paginated_by_restaurant(
            restaurant_id=restaurant_id,
            page=page,
            limit=limit,
            category=category,
            sub_category=sub_category,
            is_available=is_available,
            is_special=is_special,
            search=search_term,
        )

        return {
            "items": items,
            "pagination": {
                "page": page,
                "limit": limit,
                "total": total,
                "pages": (total + limit - 1) // limit if limit else 0,
            },
        }

    def get_menu_item(self, menu_id: int) -> Dict[str, Any]:
        """
        Get a menu item by ID.

        Args:
            menu_id: ID of the menu item

        Returns:
            Menu item data with restaurant name

        Raises:
            HTTPException: 404 if menu item not found
        """
        item = self.menu_repo.get_by_id(menu_id)
        if not item:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Menu item not found")
        self._enrich_with_restaurant_name(item)
        return item

    def update_menu_item(self, menu_id: int, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update a menu item.

        Args:
            menu_id: ID of the menu item
            data: Fields to update from MenuItemUpdate model

        Returns:
            Updated menu item with all details

        Raises:
            HTTPException: 404 if menu item not found, 400 for validation errors
        """
        # Check if item exists
        existing_item = self.menu_repo.get_by_id(menu_id)
        if not existing_item:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Menu item not found")

        # Filter out None values
        update_fields = {k: v for k, v in data.items() if v is not None}
        if not update_fields:
            # No fields to update, return existing item
            self._enrich_with_restaurant_name(existing_item)
            return existing_item

        # Validate suggested_items if provided
        if "suggested_items" in update_fields:
            suggested_items = update_fields["suggested_items"]
            if suggested_items and not self.menu_repo.validate_suggested_items(suggested_items):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="One or more suggested item IDs do not exist",
                )

        # Update the item
        self.menu_repo.update_by_id(menu_id, update_fields)

        # Fetch and return updated item
        updated_item = self.menu_repo.get_by_id(menu_id)
        if not updated_item:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to retrieve updated menu item",
            )

        self._enrich_with_restaurant_name(updated_item)
        return updated_item

    def delete_menu_item(self, menu_id: int) -> Dict[str, str]:
        """
        Delete a menu item.

        Args:
            menu_id: ID of the menu item

        Returns:
            Success message

        Raises:
            HTTPException: 404 if menu item not found
        """
        # Check if item exists
        existing_item = self.menu_repo.get_by_id(menu_id)
        if not existing_item:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Menu item not found")

        # Delete the item (also removes from suggested_items of other items)
        deleted = self.menu_repo.delete_by_id(menu_id)
        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to delete menu item",
            )

        return {"message": "Menu item deleted successfully", "menu_id": menu_id}

    def toggle_availability(self, menu_id: int, is_available: bool) -> Dict[str, Any]:
        """
        Toggle menu item availability.

        Args:
            menu_id: ID of the menu item
            is_available: New availability status

        Returns:
            Updated menu item

        Raises:
            HTTPException: 404 if menu item not found
        """
        # Check if item exists
        existing_item = self.menu_repo.get_by_id(menu_id)
        if not existing_item:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Menu item not found")

        # Update availability
        self.menu_repo.update_by_id(menu_id, {"is_available": is_available})

        # Fetch and return updated item
        updated_item = self.menu_repo.get_by_id(menu_id)
        self._enrich_with_restaurant_name(updated_item)
        return updated_item

    def toggle_special(self, menu_id: int, is_special: bool) -> Dict[str, Any]:
        """
        Toggle menu item special status.

        Args:
            menu_id: ID of the menu item
            is_special: New special status

        Returns:
            Updated menu item

        Raises:
            HTTPException: 404 if menu item not found
        """
        # Check if item exists
        existing_item = self.menu_repo.get_by_id(menu_id)
        if not existing_item:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Menu item not found")

        # Update special status
        self.menu_repo.update_by_id(menu_id, {"is_special": is_special})

        # Fetch and return updated item
        updated_item = self.menu_repo.get_by_id(menu_id)
        self._enrich_with_restaurant_name(updated_item)
        return updated_item

    def bulk_update_availability(
        self, restaurant_id: int, menu_item_ids: List[int], is_available: bool
    ) -> Dict[str, int]:
        """
        Bulk update availability for multiple menu items.

        Args:
            restaurant_id: ID of the restaurant
            menu_item_ids: List of menu item IDs to update
            is_available: New availability status

        Returns:
            Dictionary with count of updated items

        Raises:
            HTTPException: 404 if restaurant not found, 400 for validation errors
        """
        # Validate restaurant exists
        self._validate_restaurant(restaurant_id)

        if not menu_item_ids:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="menu_item_ids cannot be empty",
            )

        # Verify all items belong to the restaurant
        if not self.menu_repo.verify_items_belong_to_restaurant(menu_item_ids, restaurant_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="One or more menu items do not belong to this restaurant",
            )

        # Update availability
        updated_count = self.menu_repo.bulk_update_availability(restaurant_id, menu_item_ids, is_available)

        return {"updated_count": updated_count}

    def get_menu_categories(self, restaurant_id: int) -> Dict[str, List[str]]:
        """
        Get distinct categories and sub-categories for a restaurant.

        Args:
            restaurant_id: ID of the restaurant

        Returns:
            Dictionary with categories as keys and sub-categories as arrays

        Raises:
            HTTPException: 404 if restaurant not found
        """
        # Validate restaurant exists
        self._validate_restaurant(restaurant_id)

        categories = self.menu_repo.get_menu_categories(restaurant_id)
        return categories
