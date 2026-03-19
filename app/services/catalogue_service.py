from typing import Any, Dict, List, Optional, Tuple

from fastapi import HTTPException, status

from app.repositories.mysql_catalogue_repo import MySQLCatalogueRepository
from app.repositories.mysql_business_repo import MySQLBusinessRepository


class CatalogueService:
    def __init__(
        self,
        catalogue_repo: Optional[MySQLCatalogueRepository] = None,
        business_repo: Optional[MySQLBusinessRepository] = None,
    ):
        self.catalogue_repo = catalogue_repo or MySQLCatalogueRepository()
        self.business_repo = business_repo or MySQLBusinessRepository()

    def _validate_business(self, business_id: int) -> Dict[str, Any]:
        """Validate that a business exists."""
        business = self.business_repo.get_by_id(business_id)
        if not business:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Restaurant not found")
        return business

    def _validate_pagination(self, page: int, limit: int) -> Tuple[int, int]:
        """Validate pagination parameters."""
        if page < 1 or limit < 1:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="page and limit must be positive")
        return page, limit

    def _enrich_with_business_name(
        self, item: Dict[str, Any], cache: Optional[Dict[int, Optional[str]]] = None
    ) -> Dict[str, Any]:
        """Populate business_name if missing, caching lookups within a batch."""
        if not item:
            return item
        business_id = item.get("business_id")
        if item.get("business_name") or business_id is None:
            return item
        try:
            business_id_int = int(business_id)
        except (TypeError, ValueError):
            return item

        cache = cache if cache is not None else {}
        if business_id_int not in cache:
            business = self.business_repo.get_by_id(business_id_int)
            cache[business_id_int] = business.get("name") if business else None
        business_name = cache.get(business_id_int)
        if business_name:
            item["business_name"] = business_name
        return item

    # ==================== Legacy methods for backwards compatibility ====================

    def create_catalogue(self, business_id: str, data: dict) -> dict:
        """Create a new catalogue (legacy method)."""
        catalogue_id = self.catalogue_repo.create_catalogue(int(business_id), data)
        return {"message": "Catalogue created successfully", "catalogue_id": catalogue_id}

    def list_catalogues(self, business_id: str) -> list:
        """List all catalogues for a business (legacy method)."""
        return self.catalogue_repo.get_catalogues_by_business(int(business_id))

    def get_catalogue(self, business_id: str, catalogue_id: str) -> dict:
        """Get a specific catalogue by ID (legacy method)."""
        return self.catalogue_repo.get_catalogue_by_id(int(business_id), int(catalogue_id))

    def update_catalogue(self, business_id: str, catalogue_id: str, data: dict) -> dict:
        """Update an existing catalogue (legacy method)."""
        self.catalogue_repo.update_catalogue(int(business_id), int(catalogue_id), data)
        return {"message": "Catalogue updated successfully"}

    def delete_catalogue(self, business_id: str, catalogue_id: str) -> dict:
        """Delete a catalogue (legacy method)."""
        self.catalogue_repo.delete_catalogue(int(business_id), int(catalogue_id))
        return {"message": "Catalogue deleted successfully"}

    def get_available_items_by_business(self, business_id: str) -> list:
        """List available catalogue items (is_available = TRUE)."""
        return self.catalogue_repo.get_available_items_by_business(int(business_id))

    # ==================== New Admin API methods ====================

    def create_catalogue_item(self, business_id: int, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a new catalogue item for a business.

        Args:
            business_id: ID of the business
            data: Catalogue item data from CatalogueItemCreate model

        Returns:
            Created catalogue item with all details

        Raises:
            HTTPException: 404 if business not found, 400 for validation errors
        """
        # Validate business exists
        business = self._validate_business(business_id)

        # Validate item name is not duplicate within the business
        item_name = data.get("item_name")
        if item_name and self.catalogue_repo.catalogue_item_name_exists(business_id, item_name):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"A catalogue item with the name '{item_name}' already exists in this business",
            )

        # Validate suggested_items if provided
        suggested_items = data.get("suggested_items")
        if suggested_items:
            # Remove duplicates (already handled in model, but double-check)
            suggested_items = list(dict.fromkeys(suggested_items))  # Preserve order, remove duplicates

            # Validate all suggested items exist
            if not self.catalogue_repo.validate_suggested_items(suggested_items):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="One or more suggested item IDs do not exist",
                )

            # Validate all suggested items belong to the same business
            if not self.catalogue_repo.validate_suggested_items_belong_to_business(suggested_items, business_id):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="All suggested items must belong to the same business",
                )

            # Update data with deduplicated list
            data["suggested_items"] = suggested_items

        # Normalize None values to defaults for boolean fields
        # This prevents NULL from being stored when client explicitly sends null
        if data.get("is_available") is None:
            data["is_available"] = True
        if data.get("is_special") is None:
            data["is_special"] = False

        # Create the catalogue item
        catalogue_id = self.catalogue_repo.create_catalogue(business_id, data)
        if not catalogue_id:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create catalogue item",
            )

        # Fetch and return the created item
        created_item = self.catalogue_repo.get_by_id(catalogue_id)
        if not created_item:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to retrieve created catalogue item",
            )

        # Enrich with business name
        self._enrich_with_business_name(created_item, {business_id: business.get("name")})
        return created_item

    def list_catalogue_items_paginated(  # pylint: disable=too-many-arguments,too-many-positional-arguments
        self,
        business_id: int,
        page: int = 1,
        limit: int = 50,
        category: Optional[str] = None,
        sub_category: Optional[str] = None,
        is_available: Optional[bool] = None,
        is_special: Optional[bool] = None,
        search: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Get paginated catalogue items with filters.

        Args:
            business_id: ID of the business
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
            HTTPException: 404 if business not found
        """
        # Validate business exists
        self._validate_business(business_id)

        # Validate pagination
        page, limit = self._validate_pagination(page, limit)

        # Clean search term
        search_term = (search or "").strip() or None

        # Get paginated items
        items, total = self.catalogue_repo.get_paginated_by_business(
            business_id=business_id,
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

    def get_catalogue_item(self, catalogue_id: int) -> Dict[str, Any]:
        """
        Get a catalogue item by ID.

        Args:
            catalogue_id: ID of the catalogue item

        Returns:
            Catalogue item data with business name

        Raises:
            HTTPException: 404 if catalogue item not found
        """
        item = self.catalogue_repo.get_catalogue_item_with_options(catalogue_id)
        if not item:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Catalogue item not found")
        self._enrich_with_business_name(item)
        return item

    def _get_scoped_catalogue_item_or_404(self, business_id: int, catalogue_id: int) -> Dict[str, Any]:
        """Fetch a catalogue item ensuring it belongs to the business."""
        item = self.catalogue_repo.get_catalogue_by_id(business_id, catalogue_id)
        if not item:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Catalogue item not found")
        item["option_groups"] = self.catalogue_repo.get_option_groups_for_item(catalogue_id)
        self._enrich_with_business_name(item, {business_id: None})
        return item

    def get_catalogue_item_for_business(self, business_id: int, catalogue_id: int) -> Dict[str, Any]:
        """Get a catalogue item scoped to a business."""
        return self._get_scoped_catalogue_item_or_404(business_id, catalogue_id)

    def update_catalogue_item(self, catalogue_id: int, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update a catalogue item.

        Args:
            catalogue_id: ID of the catalogue item
            data: Fields to update from CatalogueItemUpdate model

        Returns:
            Updated catalogue item with all details

        Raises:
            HTTPException: 404 if catalogue item not found, 400 for validation errors
        """
        # Check if item exists
        existing_item = self.catalogue_repo.get_by_id(catalogue_id)
        if not existing_item:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Catalogue item not found")

        # Filter out None values
        update_fields = {k: v for k, v in data.items() if v is not None}
        if not update_fields:
            # No fields to update, return existing item
            self._enrich_with_business_name(existing_item)
            return existing_item

        # Validate item name is not duplicate if being updated
        if "item_name" in update_fields:
            item_name = update_fields["item_name"]
            business_id = existing_item.get("business_id")
            if item_name and self.catalogue_repo.item_name_exists(business_id, item_name, exclude_catalogue_id=catalogue_id):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"A catalogue item with the name '{item_name}' already exists in this business",
                )

        # Validate suggested_items if provided
        if "suggested_items" in update_fields:
            suggested_items = update_fields["suggested_items"]
            if suggested_items:
                # Remove duplicates (already handled in model, but double-check)
                suggested_items = list(dict.fromkeys(suggested_items))  # Preserve order, remove duplicates

                # Prevent circular reference (item cannot suggest itself)
                if catalogue_id in suggested_items:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="A catalogue item cannot suggest itself",
                    )

                # Validate all suggested items exist
                if not self.catalogue_repo.validate_suggested_items(suggested_items):
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="One or more suggested item IDs do not exist",
                    )

                # Validate all suggested items belong to the same business
                business_id = existing_item.get("business_id")
                if business_id and not self.catalogue_repo.validate_suggested_items_belong_to_business(
                    suggested_items, business_id
                ):
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="All suggested items must belong to the same business",
                    )

                # Update with deduplicated list
                update_fields["suggested_items"] = suggested_items

        # Update the item
        self.catalogue_repo.update_by_id(catalogue_id, update_fields)

        # Fetch and return updated item
        updated_item = self.catalogue_repo.get_by_id(catalogue_id)
        if not updated_item:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to retrieve updated catalogue item",
            )

        self._enrich_with_business_name(updated_item)
        return updated_item

    def update_catalogue_item_for_business(self, business_id: int, catalogue_id: int, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update a catalogue item scoped to a business.

        Ensures the item belongs to the business before delegating to the common update logic.
        """
        self._get_scoped_catalogue_item_or_404(business_id, catalogue_id)
        return self.update_catalogue_item(catalogue_id, data)

    def delete_catalogue_item(self, catalogue_id: int) -> Dict[str, str]:
        """
        Delete a catalogue item.

        Args:
            catalogue_id: ID of the catalogue item

        Returns:
            Success message

        Raises:
            HTTPException: 404 if catalogue item not found
        """
        # Check if item exists
        existing_item = self.catalogue_repo.get_by_id(catalogue_id)
        if not existing_item:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Catalogue item not found")

        # Delete the item (also removes from suggested_items of other items)
        deleted = self.catalogue_repo.delete_by_id(catalogue_id)
        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to delete catalogue item",
            )

        return {"message": "Catalogue item deleted successfully", "catalogue_id": catalogue_id}

    def delete_catalogue_item_for_business(self, business_id: int, catalogue_id: int) -> Dict[str, str]:
        """Delete a catalogue item scoped to a business."""
        self._get_scoped_catalogue_item_or_404(business_id, catalogue_id)
        return self.delete_catalogue_item(catalogue_id)

    def toggle_availability(self, catalogue_id: int, is_available: bool) -> Dict[str, Any]:
        """
        Toggle catalogue item availability.

        Args:
            catalogue_id: ID of the catalogue item
            is_available: New availability status

        Returns:
            Updated catalogue item

        Raises:
            HTTPException: 404 if catalogue item not found
        """
        # Check if item exists
        existing_item = self.catalogue_repo.get_by_id(catalogue_id)
        if not existing_item:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Catalogue item not found")

        # Update availability
        self.catalogue_repo.update_by_id(catalogue_id, {"is_available": is_available})

        # Fetch and return updated item
        updated_item = self.catalogue_repo.get_by_id(catalogue_id)
        if not updated_item:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to retrieve updated catalogue item",
            )

        self._enrich_with_business_name(updated_item)
        return updated_item

    def toggle_availability_for_business(
        self, business_id: int, catalogue_id: int, is_available: bool
    ) -> Dict[str, Any]:
        """Toggle availability scoped to a business."""
        self._get_scoped_catalogue_item_or_404(business_id, catalogue_id)
        return self.toggle_availability(catalogue_id, is_available)

    def toggle_special(self, catalogue_id: int, is_special: bool) -> Dict[str, Any]:
        """
        Toggle catalogue item special status.

        Args:
            catalogue_id: ID of the catalogue item
            is_special: New special status

        Returns:
            Updated catalogue item

        Raises:
            HTTPException: 404 if catalogue item not found
        """
        # Check if item exists
        existing_item = self.catalogue_repo.get_by_id(catalogue_id)
        if not existing_item:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Catalogue item not found")

        # Update special status
        self.catalogue_repo.update_by_id(catalogue_id, {"is_special": is_special})

        # Fetch and return updated item
        updated_item = self.catalogue_repo.get_by_id(catalogue_id)
        if not updated_item:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to retrieve updated catalogue item",
            )

        self._enrich_with_business_name(updated_item)
        return updated_item

    def toggle_special_for_business(self, business_id: int, catalogue_id: int, is_special: bool) -> Dict[str, Any]:
        """Toggle special status scoped to a business."""
        self._get_scoped_catalogue_item_or_404(business_id, catalogue_id)
        return self.toggle_special(catalogue_id, is_special)

    def bulk_update_availability(
        self, business_id: int, catalogue_item_ids: List[int], is_available: bool
    ) -> Dict[str, int]:
        """
        Bulk update availability for multiple catalogue items.

        Args:
            business_id: ID of the business
            catalogue_item_ids: List of catalogue item IDs to update
            is_available: New availability status

        Returns:
            Dictionary with count of updated items

        Raises:
            HTTPException: 404 if business not found, 400 for validation errors
        """
        # Validate business exists
        self._validate_business(business_id)

        if not catalogue_item_ids:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="catalogue_item_ids cannot be empty",
            )

        # Remove duplicates from catalogue_item_ids
        catalogue_item_ids = list(dict.fromkeys(catalogue_item_ids))  # Preserve order, remove duplicates

        # Validate all items exist
        if not self.catalogue_repo.items_exist(catalogue_item_ids):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="One or more catalogue item IDs do not exist",
            )

        # Verify all items belong to the business
        if not self.catalogue_repo.verify_items_belong_to_business(catalogue_item_ids, business_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="One or more catalogue items do not belong to this business",
            )

        # Update availability
        updated_count = self.catalogue_repo.bulk_update_availability(business_id, catalogue_item_ids, is_available)

        return {"updated_count": updated_count}

    def get_catalogue_categories(self, business_id: int) -> Dict[str, List[str]]:
        """
        Get distinct categories and sub-categories for a business.

        Args:
            business_id: ID of the business

        Returns:
            Dictionary with categories as keys and sub-categories as arrays

        Raises:
            HTTPException: 404 if business not found
        """
        # Validate business exists
        self._validate_business(business_id)

        categories = self.catalogue_repo.get_catalogue_categories(business_id)
        return categories
