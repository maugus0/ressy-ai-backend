"""
Menu management API endpoints.
Admin-only CRUD operations for menu items including categories, availability, specials, and bulk operations.
"""

from typing import Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query, status
from pydantic import ValidationError

from app.middleware.auth_middleware import get_current_admin_user
from app.models.menu_models import (
    BulkAvailabilityRequest,
    BulkAvailabilityResponse,
    MenuCategoriesResponse,
    MenuItemCreate,
    MenuItemData,
    MenuItemDeleteResponse,
    MenuItemResponse,
    MenuItemsPage,
    MenuItemUpdate,
    ToggleAvailabilityRequest,
    ToggleSpecialRequest,
)
from app.services.menu_service import MenuService


def _validate_payload(model, payload: dict):
    """Validate payload against a Pydantic model."""
    try:
        return model.model_validate(payload or {})
    except ValidationError as exc:
        serialized_errors = []
        for err in exc.errors():
            ctx = err.get("ctx") or {}
            ctx_serialized = {k: str(v) for k, v in ctx.items()} if ctx else None
            err_copy = {k: v for k, v in err.items() if k != "ctx"}
            if ctx_serialized:
                err_copy["ctx"] = ctx_serialized
            serialized_errors.append(err_copy)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=serialized_errors
        ) from exc


def get_menu_service() -> MenuService:
    """Dependency to get MenuService instance."""
    return MenuService()


router = APIRouter(
    prefix="/api/v1/admin",
    tags=["Menus"],
    dependencies=[Depends(get_current_admin_user)],
)

# JSON Schema for OpenAPI documentation
MENU_CREATE_SCHEMA = MenuItemCreate.model_json_schema()
MENU_UPDATE_SCHEMA = MenuItemUpdate.model_json_schema()
TOGGLE_AVAILABILITY_SCHEMA = ToggleAvailabilityRequest.model_json_schema()
TOGGLE_SPECIAL_SCHEMA = ToggleSpecialRequest.model_json_schema()
BULK_AVAILABILITY_SCHEMA = BulkAvailabilityRequest.model_json_schema()


# ==================== Admin Menu Item APIs ====================


@router.post(
    "/restaurants/{restaurant_id}/menu",
    status_code=status.HTTP_201_CREATED,
    summary="Create Menu Item",
    description="Create a new menu item for a specific restaurant. Requires admin authentication.",
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {
                "application/json": {
                    "schema": MENU_CREATE_SCHEMA,
                    "example": {
                        "item_name": "Margherita Pizza",
                        "price": 15.99,
                        "category": "Pizza",
                        "sub_category": "Classic",
                        "item_desc": "Fresh mozzarella, tomato sauce, and basil",
                        "avg_prep_time": 20,
                        "is_available": True,
                        "is_special": False,
                    },
                }
            },
        }
    },
)
async def create_menu_item(
    restaurant_id: int,
    payload: dict = Body(..., description="Menu item data"),
    menu_service: MenuService = Depends(get_menu_service),
) -> MenuItemResponse:
    """
    Create a new menu item for a restaurant.

    **Authentication**: Requires valid admin JWT token.

    **Path Parameters**:
    - `restaurant_id`: ID of the restaurant

    **Request Body**:
    - `item_name` (required): Name of the menu item
    - `price` (required): Price (must be positive)
    - `category` (optional): Menu category
    - `sub_category` (optional): Menu sub-category
    - `item_desc` (optional): Item description
    - `avg_prep_time` (optional): Prep time in minutes
    - `suggested_items` (optional): Array of suggested item IDs
    - `is_available` (optional): Availability status (default: true)
    - `is_special` (optional): Special status (default: false)

    **Returns**: Created menu item with all details

    **Errors**:
    - 400: Validation error (e.g., invalid price, suggested items don't exist)
    - 401: Unauthorized (invalid or missing JWT token)
    - 404: Restaurant not found
    """
    data = _validate_payload(MenuItemCreate, payload)
    result = menu_service.create_menu_item(restaurant_id, data.model_dump(exclude_none=False))
    return MenuItemResponse(
        success=True,
        message="Menu item created successfully",
        data=MenuItemData(**result),
    )


@router.get(
    "/restaurants/{restaurant_id}/menu",
    summary="List Menu Items",
    description="Retrieve paginated menu items for a restaurant with optional filters. Requires admin authentication.",
)
async def list_menu_items(  # pylint: disable=too-many-arguments,too-many-positional-arguments
    restaurant_id: int,
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    limit: int = Query(50, ge=1, le=100, description="Items per page (max 100)"),
    category: Optional[str] = Query(None, description="Filter by category"),
    sub_category: Optional[str] = Query(None, description="Filter by sub-category"),
    is_available: Optional[bool] = Query(None, description="Filter by availability"),
    is_special: Optional[bool] = Query(None, description="Filter by special status"),
    search: Optional[str] = Query(None, description="Search by item name (partial match)"),
    menu_service: MenuService = Depends(get_menu_service),
) -> MenuItemsPage:
    """
    Get paginated list of menu items for a restaurant with optional filters.

    **Authentication**: Requires valid admin JWT token.

    **Path Parameters**:
    - `restaurant_id`: ID of the restaurant

    **Query Parameters**:
    - `page`: Page number (default: 1)
    - `limit`: Items per page (default: 50, max: 100)
    - `category`: Filter by category
    - `sub_category`: Filter by sub-category
    - `is_available`: Filter by availability (true/false)
    - `is_special`: Filter by special status (true/false)
    - `search`: Search term for item name (partial match)

    **Returns**: Paginated list of menu items with metadata

    **Errors**:
    - 401: Unauthorized (invalid or missing JWT token)
    - 404: Restaurant not found
    """
    # pylint: disable=duplicate-code
    result = menu_service.list_menu_items_paginated(
        restaurant_id=restaurant_id,
        page=page,
        limit=limit,
        category=category,
        sub_category=sub_category,
        is_available=is_available,
        is_special=is_special,
        search=search,
    )
    total_items = result["pagination"]["total"]
    return MenuItemsPage(
        success=True,
        message=f"Successfully retrieved {len(result['items'])} menu items (total: {total_items})",
        items=[MenuItemData(**item) for item in result["items"]],
        pagination=result["pagination"],
    )


@router.get(
    "/menu/{menu_id}",
    summary="Get Menu Item by ID",
    description="Retrieve detailed information about a specific menu item. Requires admin authentication.",
)
async def get_menu_item(
    menu_id: int,
    menu_service: MenuService = Depends(get_menu_service),
) -> MenuItemResponse:
    """
    Get a specific menu item by ID.

    **Authentication**: Requires valid admin JWT token.

    **Path Parameters**:
    - `menu_id`: ID of the menu item

    **Returns**: Menu item details including restaurant name

    **Errors**:
    - 401: Unauthorized (invalid or missing JWT token)
    - 404: Menu item not found
    """
    result = menu_service.get_menu_item(menu_id)
    return MenuItemResponse(
        success=True,
        message="Menu item retrieved successfully",
        data=MenuItemData(**result),
    )


@router.put(
    "/menu/{menu_id}",
    summary="Update Menu Item",
    description="Update any fields of a menu item. All fields are optional. Requires admin authentication.",
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {
                "application/json": {
                    "schema": MENU_UPDATE_SCHEMA,
                    "example": {
                        "price": 17.99,
                        "item_desc": "Updated description",
                        "is_special": True,
                    },
                }
            },
        }
    },
)
async def update_menu_item(
    menu_id: int,
    payload: dict = Body(..., description="Menu item fields to update"),
    menu_service: MenuService = Depends(get_menu_service),
) -> MenuItemResponse:
    """
    Update a menu item. Only provided fields will be updated.

    **Authentication**: Requires valid admin JWT token.

    **Path Parameters**:
    - `menu_id`: ID of the menu item

    **Request Body** (all optional):
    - `item_name`: Updated item name
    - `price`: Updated price
    - `category`: Updated category
    - `sub_category`: Updated sub-category
    - `item_desc`: Updated description
    - `avg_prep_time`: Updated prep time
    - `suggested_items`: Updated suggested items
    - `is_available`: Updated availability
    - `is_special`: Updated special status

    **Returns**: Updated menu item with all details

    **Errors**:
    - 400: Validation error (e.g., invalid price, suggested items don't exist)
    - 401: Unauthorized (invalid or missing JWT token)
    - 404: Menu item not found
    """
    data = _validate_payload(MenuItemUpdate, payload)
    result = menu_service.update_menu_item(menu_id, data.model_dump(exclude_unset=True))
    return MenuItemResponse(
        success=True,
        message="Menu item updated successfully",
        data=MenuItemData(**result),
    )


@router.delete(
    "/menu/{menu_id}",
    status_code=status.HTTP_200_OK,
    summary="Delete Menu Item",
    description="Delete a menu item and remove it from suggested items of other items. Requires admin authentication.",
)
async def delete_menu_item(
    menu_id: int,
    menu_service: MenuService = Depends(get_menu_service),
) -> MenuItemDeleteResponse:
    """
    Delete a menu item from the database.

    This will also remove the item from the suggested_items array of any other menu items.

    **Authentication**: Requires valid admin JWT token.

    **Path Parameters**:
    - `menu_id`: ID of the menu item to delete

    **Returns**: Success message

    **Errors**:
    - 401: Unauthorized (invalid or missing JWT token)
    - 404: Menu item not found
    """
    menu_service.delete_menu_item(menu_id)
    return MenuItemDeleteResponse(
        success=True,
        message="Menu item deleted successfully",
        menu_id=menu_id,
    )


@router.patch(
    "/menu/{menu_id}/availability",
    summary="Toggle Menu Item Availability",
    description="Update the availability status of a menu item. Requires admin authentication.",
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {
                "application/json": {
                    "schema": TOGGLE_AVAILABILITY_SCHEMA,
                    "example": {"is_available": False},
                }
            },
        }
    },
)
async def toggle_availability(
    menu_id: int,
    payload: dict = Body(..., description="Availability status"),
    menu_service: MenuService = Depends(get_menu_service),
) -> MenuItemResponse:
    """
    Toggle the availability status of a menu item.

    **Authentication**: Requires valid admin JWT token.

    **Path Parameters**:
    - `menu_id`: ID of the menu item

    **Request Body**:
    - `is_available`: New availability status (true/false)

    **Returns**: Updated menu item with new availability status

    **Errors**:
    - 401: Unauthorized (invalid or missing JWT token)
    - 404: Menu item not found
    """
    data = _validate_payload(ToggleAvailabilityRequest, payload)
    result = menu_service.toggle_availability(menu_id, data.is_available)
    status_text = "available" if data.is_available else "unavailable"
    return MenuItemResponse(
        success=True,
        message=f"Menu item marked as {status_text}",
        data=MenuItemData(**result),
    )


@router.patch(
    "/menu/{menu_id}/special",
    summary="Toggle Menu Item Special Status",
    description="Update the special status of a menu item. Requires admin authentication.",
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {
                "application/json": {
                    "schema": TOGGLE_SPECIAL_SCHEMA,
                    "example": {"is_special": True},
                }
            },
        }
    },
)
async def toggle_special(
    menu_id: int,
    payload: dict = Body(..., description="Special status"),
    menu_service: MenuService = Depends(get_menu_service),
) -> MenuItemResponse:
    """
    Toggle the special status of a menu item.

    **Authentication**: Requires valid admin JWT token.

    **Path Parameters**:
    - `menu_id`: ID of the menu item

    **Request Body**:
    - `is_special`: New special status (true/false)

    **Returns**: Updated menu item with new special status

    **Errors**:
    - 401: Unauthorized (invalid or missing JWT token)
    - 404: Menu item not found
    """
    data = _validate_payload(ToggleSpecialRequest, payload)
    result = menu_service.toggle_special(menu_id, data.is_special)
    status_text = "marked as special" if data.is_special else "removed from specials"
    return MenuItemResponse(
        success=True,
        message=f"Menu item {status_text}",
        data=MenuItemData(**result),
    )


@router.patch(
    "/restaurants/{restaurant_id}/menu/bulk-availability",
    summary="Bulk Update Menu Item Availability",
    description="Update availability for multiple menu items at once. Requires admin authentication.",
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {
                "application/json": {
                    "schema": BULK_AVAILABILITY_SCHEMA,
                    "example": {
                        "menu_item_ids": [1, 2, 3, 4],
                        "is_available": False,
                    },
                }
            },
        }
    },
)
async def bulk_update_availability(
    restaurant_id: int,
    payload: dict = Body(..., description="Bulk update data"),
    menu_service: MenuService = Depends(get_menu_service),
) -> BulkAvailabilityResponse:
    """
    Bulk update availability for multiple menu items.

    **Authentication**: Requires valid admin JWT token.

    **Path Parameters**:
    - `restaurant_id`: ID of the restaurant

    **Request Body**:
    - `menu_item_ids`: Array of menu item IDs to update (at least 1 required)
    - `is_available`: New availability status for all items (true/false)

    **Returns**: Number of items updated

    **Errors**:
    - 400: Validation error (items don't belong to restaurant, empty array)
    - 401: Unauthorized (invalid or missing JWT token)
    - 404: Restaurant not found
    """
    data = _validate_payload(BulkAvailabilityRequest, payload)
    result = menu_service.bulk_update_availability(restaurant_id, data.menu_item_ids, data.is_available)
    updated_count = result.get("updated_count", 0)
    status_text = "available" if data.is_available else "unavailable"
    return BulkAvailabilityResponse(
        success=True,
        message=f"Successfully marked {updated_count} menu items as {status_text}",
        updated_count=updated_count,
    )


@router.get(
    "/restaurants/{restaurant_id}/menu/categories",
    summary="Get Menu Categories",
    description=(
        "Retrieve all distinct categories and sub-categories for a restaurant's menu. "
        "Requires admin authentication."
    ),
)
async def get_menu_categories(
    restaurant_id: int,
    menu_service: MenuService = Depends(get_menu_service),
) -> MenuCategoriesResponse:
    """
    Get all distinct categories and sub-categories for a restaurant's menu.

    **Authentication**: Requires valid admin JWT token.

    **Path Parameters**:
    - `restaurant_id`: ID of the restaurant

    **Returns**: Dictionary with categories as keys and arrays of sub-categories as values

    **Example Response**:
    ```json
    {
      "success": true,
      "message": "Categories retrieved successfully",
      "categories": {
        "Appetizers": ["Vegetarian", "Seafood"],
        "Entrees": ["Chicken", "Beef", "Vegetarian"],
        "Desserts": []
      }
    }
    ```

    **Errors**:
    - 401: Unauthorized (invalid or missing JWT token)
    - 404: Restaurant not found
    """
    categories = menu_service.get_menu_categories(restaurant_id)
    category_count = len(categories)
    return MenuCategoriesResponse(
        success=True,
        message=f"Successfully retrieved {category_count} categories",
        categories=categories,
    )
