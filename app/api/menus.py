"""
Menu management API endpoints.
Admin-only CRUD operations for menu items including categories, availability, specials, and bulk operations.
"""

from typing import Optional

from fastapi import APIRouter, Body, Depends, Query, status

from app.middleware.auth_middleware import get_current_admin_user
from app.models.menu_models import (
    BulkAvailabilityRequest,
    MenuCategoriesResponse,
    MenuItemCreate,
    MenuItemResponse,
    MenuItemsPage,
    MenuItemUpdate,
    ToggleAvailabilityRequest,
    ToggleSpecialRequest,
)
from app.services.menu_service import MenuService
from app.utils.payload_validator import validate_payload


def _validate_payload(model, payload: dict):
    """Validate payload against a Pydantic model."""
    return validate_payload(model, payload)


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
                        "item_name": "OG Hot Chicken",
                        "price": 15.50,
                        "category": "Chicken Sandwiches",
                        "sub_category": "White Meat (Chicken Breast)",
                        "item_desc": "Nashville st hot chicken breast with frying pan hot dust, spicy mayo, cabbage slaw, pickles",
                        "avg_prep_time": 12,
                        "suggested_items": [2, 3],
                        "is_available": True,
                        "is_special": False,
                    },
                }
            },
        },
        "responses": {
            201: {
                "description": "Menu item created successfully",
                "content": {
                    "application/json": {
                        "example": {
                            "id": 1,
                            "restaurant_id": 5,
                            "restaurant_name": "Frying Pan",
                            "category": "Chicken Sandwiches",
                            "sub_category": "White Meat (Chicken Breast)",
                            "item_name": "OG Hot Chicken",
                            "item_desc": "Nashville st hot chicken breast with frying pan hot dust, spicy mayo, cabbage slaw, pickles",
                            "price": 15.50,
                            "avg_prep_time": 12,
                            "suggested_items": [2, 3],
                            "is_available": True,
                            "is_special": False,
                            "created_at": "2026-03-15T12:00:00",
                            "updated_at": "2026-03-15T12:00:00",
                            "option_groups": None,
                        }
                    }
                },
            },
            400: {
                "description": "Validation error (invalid price, duplicate name, invalid suggested items)",
                "content": {
                    "application/json": {
                        "example": {
                            "detail": "A menu item with the name 'OG Hot Chicken' already exists in this restaurant"
                        }
                    }
                },
            },
            404: {
                "description": "Restaurant not found",
                "content": {"application/json": {"example": {"detail": "Restaurant not found"}}},
            },
        },
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
    return MenuItemResponse(**result)


@router.get(
    "/restaurants/{restaurant_id}/menu",
    summary="List Menu Items",
    description="Retrieve paginated menu items for a restaurant with optional filters. Requires admin authentication.",
    openapi_extra={
        "responses": {
            200: {
                "description": "Paginated menu items with metadata",
                "content": {
                    "application/json": {
                        "example": {
                            "items": [
                                {
                                    "id": 1,
                                    "restaurant_id": 5,
                                    "restaurant_name": "Frying Pan",
                                    "category": "Chicken Sandwiches",
                                    "sub_category": "White Meat (Chicken Breast)",
                                    "item_name": "OG Hot Chicken",
                                    "item_desc": "Nashville st hot chicken breast with frying pan hot dust, spicy mayo, cabbage slaw, pickles",
                                    "price": 15.50,
                                    "avg_prep_time": 12,
                                    "suggested_items": [2, 3],
                                    "is_available": True,
                                    "is_special": False,
                                    "created_at": "2026-03-15T12:00:00",
                                    "updated_at": "2026-03-15T12:00:00",
                                    "option_groups": None,
                                },
                                {
                                    "id": 8,
                                    "restaurant_id": 5,
                                    "restaurant_name": "Frying Pan",
                                    "category": "Fries",
                                    "sub_category": None,
                                    "item_name": "Dirty Chicken",
                                    "item_desc": "Waffle fries, tenders with hot dust, marble cheese, green onion, slaw, pickles, sweet soy sauce, spicy mayo",
                                    "price": 18.50,
                                    "avg_prep_time": None,
                                    "suggested_items": None,
                                    "is_available": True,
                                    "is_special": False,
                                    "created_at": "2026-03-15T12:00:00",
                                    "updated_at": "2026-03-15T12:00:00",
                                    "option_groups": None,
                                },
                            ],
                            "pagination": {"page": 1, "limit": 50, "total": 14, "pages": 1},
                        }
                    }
                },
            }
        }
    },
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
    return MenuItemsPage(
        items=[MenuItemResponse(**item) for item in result["items"]],
        pagination=result["pagination"],
    )


@router.get(
    "/menu/{menu_id}",
    summary="Get Menu Item by ID",
    description="Retrieve detailed information about a specific menu item. Requires admin authentication.",
    openapi_extra={
        "responses": {
            200: {
                "description": "Menu item with full customization option groups",
                "content": {
                    "application/json": {
                        "example": {
                            "id": 1,
                            "restaurant_id": 5,
                            "restaurant_name": "Frying Pan",
                            "category": "Chicken Sandwiches",
                            "sub_category": "White Meat (Chicken Breast)",
                            "item_name": "OG Hot Chicken",
                            "item_desc": "Nashville st hot chicken breast with frying pan hot dust, spicy mayo, cabbage slaw, pickles",
                            "price": 15.50,
                            "avg_prep_time": 12,
                            "suggested_items": [2, 3],
                            "is_available": True,
                            "is_special": False,
                            "created_at": "2026-03-15T12:00:00",
                            "updated_at": "2026-03-15T12:00:00",
                            "option_groups": [
                                {
                                    "id": 1,
                                    "restaurant_id": 5,
                                    "name": "Spice Level",
                                    "description": "Choose your heat level",
                                    "selection_type": "single",
                                    "min_select": 0,
                                    "max_select": 1,
                                    "free_allowance": 0,
                                    "free_allowance_strategy": "HIGHEST_PRICE_FIRST",
                                    "allows_quantity": False,
                                    "max_quantity_per_option": None,
                                    "prompt_style": "ASK_ALWAYS",
                                    "is_required": False,
                                    "is_available": True,
                                    "sort_order": 1,
                                    "values": [
                                        {
                                            "id": 1,
                                            "group_id": 1,
                                            "name": "No Heat",
                                            "price_delta": 0.0,
                                            "is_default": True,
                                            "is_available": True,
                                            "sort_order": 0,
                                        },
                                        {
                                            "id": 2,
                                            "group_id": 1,
                                            "name": "Mild Hot",
                                            "price_delta": 0.0,
                                            "is_default": False,
                                            "is_available": True,
                                            "sort_order": 1,
                                        },
                                        {
                                            "id": 3,
                                            "group_id": 1,
                                            "name": "Medium Hot",
                                            "price_delta": 0.0,
                                            "is_default": False,
                                            "is_available": True,
                                            "sort_order": 2,
                                        },
                                        {
                                            "id": 4,
                                            "group_id": 1,
                                            "name": "Extra Hot",
                                            "price_delta": 0.0,
                                            "is_default": False,
                                            "is_available": True,
                                            "sort_order": 3,
                                        },
                                        {
                                            "id": 5,
                                            "group_id": 1,
                                            "name": "911",
                                            "price_delta": 0.50,
                                            "is_default": False,
                                            "is_available": True,
                                            "sort_order": 4,
                                        },
                                    ],
                                },
                                {
                                    "id": 2,
                                    "restaurant_id": 5,
                                    "name": "Sandwich Add-ons",
                                    "description": "Add extra items to your sandwich",
                                    "selection_type": "multiple",
                                    "min_select": 0,
                                    "max_select": None,
                                    "free_allowance": 0,
                                    "free_allowance_strategy": "HIGHEST_PRICE_FIRST",
                                    "allows_quantity": False,
                                    "max_quantity_per_option": None,
                                    "prompt_style": "ASK_IF_MENTIONED",
                                    "is_required": False,
                                    "is_available": True,
                                    "sort_order": 2,
                                    "values": [
                                        {
                                            "id": 6,
                                            "group_id": 2,
                                            "name": "Egg",
                                            "price_delta": 2.50,
                                            "is_default": False,
                                            "is_available": True,
                                            "sort_order": 0,
                                        },
                                        {
                                            "id": 7,
                                            "group_id": 2,
                                            "name": "Cheese",
                                            "price_delta": 1.50,
                                            "is_default": False,
                                            "is_available": True,
                                            "sort_order": 1,
                                        },
                                        {
                                            "id": 8,
                                            "group_id": 2,
                                            "name": "Egg + Cheese",
                                            "price_delta": 3.50,
                                            "is_default": False,
                                            "is_available": True,
                                            "sort_order": 2,
                                        },
                                        {
                                            "id": 9,
                                            "group_id": 2,
                                            "name": "Pickled Jalapeno",
                                            "price_delta": 1.00,
                                            "is_default": False,
                                            "is_available": True,
                                            "sort_order": 3,
                                        },
                                        {
                                            "id": 10,
                                            "group_id": 2,
                                            "name": "Bacon (2 slices)",
                                            "price_delta": 3.00,
                                            "is_default": False,
                                            "is_available": True,
                                            "sort_order": 6,
                                        },
                                    ],
                                },
                                {
                                    "id": 3,
                                    "restaurant_id": 5,
                                    "name": "Make It Combo",
                                    "description": "Served with house mayo and ketchup",
                                    "selection_type": "single",
                                    "min_select": 0,
                                    "max_select": 1,
                                    "free_allowance": 0,
                                    "free_allowance_strategy": "HIGHEST_PRICE_FIRST",
                                    "allows_quantity": False,
                                    "max_quantity_per_option": None,
                                    "prompt_style": "ASK_ALWAYS",
                                    "is_required": False,
                                    "is_available": True,
                                    "sort_order": 3,
                                    "values": [
                                        {
                                            "id": 14,
                                            "group_id": 3,
                                            "name": "Waffle Fries",
                                            "price_delta": 4.50,
                                            "is_default": False,
                                            "is_available": True,
                                            "sort_order": 0,
                                        },
                                        {
                                            "id": 15,
                                            "group_id": 3,
                                            "name": "Yam Fries",
                                            "price_delta": 5.50,
                                            "is_default": False,
                                            "is_available": True,
                                            "sort_order": 1,
                                        },
                                        {
                                            "id": 16,
                                            "group_id": 3,
                                            "name": "Fries + Pop (Waffle Fries)",
                                            "price_delta": 6.00,
                                            "is_default": False,
                                            "is_available": True,
                                            "sort_order": 2,
                                        },
                                    ],
                                },
                            ],
                        }
                    }
                },
            },
            404: {
                "description": "Menu item not found",
                "content": {"application/json": {"example": {"detail": "Menu item not found"}}},
            },
        }
    },
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
    return MenuItemResponse(**result)


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
                        "price": 16.50,
                        "item_desc": "Nashville st hot chicken breast with frying pan hot dust, spicy mayo, cabbage slaw, pickles — now with extra crunch",
                        "is_special": True,
                    },
                }
            },
        },
        "responses": {
            200: {
                "description": "Updated menu item with all fields",
                "content": {
                    "application/json": {
                        "example": {
                            "id": 1,
                            "restaurant_id": 5,
                            "restaurant_name": "Frying Pan",
                            "category": "Chicken Sandwiches",
                            "sub_category": "White Meat (Chicken Breast)",
                            "item_name": "OG Hot Chicken",
                            "item_desc": "Nashville st hot chicken breast with frying pan hot dust, spicy mayo, cabbage slaw, pickles — now with extra crunch",
                            "price": 16.50,
                            "avg_prep_time": 12,
                            "suggested_items": [2, 3],
                            "is_available": True,
                            "is_special": True,
                            "created_at": "2026-03-15T12:00:00",
                            "updated_at": "2026-03-15T13:30:00",
                            "option_groups": None,
                        }
                    }
                },
            },
            400: {
                "description": "Validation error",
                "content": {"application/json": {"example": {"detail": "One or more suggested item IDs do not exist"}}},
            },
            404: {
                "description": "Menu item not found",
                "content": {"application/json": {"example": {"detail": "Menu item not found"}}},
            },
        },
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
    return MenuItemResponse(**result)


@router.delete(
    "/menu/{menu_id}",
    status_code=status.HTTP_200_OK,
    summary="Delete Menu Item",
    description=(
        "Delete a menu item and remove it from suggested items of other items. "
        "Returns 409 if the item is referenced by existing orders. Requires admin authentication."
    ),
    openapi_extra={
        "responses": {
            200: {
                "description": "Menu item deleted",
                "content": {
                    "application/json": {"example": {"message": "Menu item deleted successfully", "menu_id": 1}}
                },
            },
            404: {
                "description": "Menu item not found",
                "content": {"application/json": {"example": {"detail": "Menu item not found"}}},
            },
            409: {
                "description": "Menu item is referenced by existing orders and cannot be deleted",
                "content": {
                    "application/json": {
                        "example": {
                            "detail": "Cannot delete this menu item because it is referenced by existing orders. Consider marking it as unavailable instead."
                        }
                    }
                },
            },
        }
    },
)
async def delete_menu_item(
    menu_id: int,
    menu_service: MenuService = Depends(get_menu_service),
) -> dict:
    """
    Delete a menu item from the database.

    This will also remove the item from the suggested_items array of any other menu items
    and detach any option group mappings.

    **Authentication**: Requires valid admin JWT token.

    **Path Parameters**:
    - `menu_id`: ID of the menu item to delete

    **Returns**: Success message

    **Errors**:
    - 401: Unauthorized (invalid or missing JWT token)
    - 404: Menu item not found
    - 409: Item is referenced by existing orders (foreign key constraint)
    """
    menu_service.delete_menu_item(menu_id)
    return {"message": "Menu item deleted successfully", "menu_id": menu_id}


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
        },
        "responses": {
            200: {
                "description": "Menu item with updated availability",
                "content": {
                    "application/json": {
                        "example": {
                            "id": 1,
                            "restaurant_id": 5,
                            "restaurant_name": "Frying Pan",
                            "category": "Chicken Sandwiches",
                            "sub_category": "White Meat (Chicken Breast)",
                            "item_name": "OG Hot Chicken",
                            "item_desc": "Nashville st hot chicken breast with frying pan hot dust, spicy mayo, cabbage slaw, pickles",
                            "price": 15.50,
                            "avg_prep_time": 12,
                            "suggested_items": [2, 3],
                            "is_available": False,
                            "is_special": False,
                            "created_at": "2026-03-15T12:00:00",
                            "updated_at": "2026-03-15T14:00:00",
                            "option_groups": None,
                        }
                    }
                },
            },
        },
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
    return MenuItemResponse(**result)


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
        },
        "responses": {
            200: {
                "description": "Menu item with updated special status",
                "content": {
                    "application/json": {
                        "example": {
                            "id": 4,
                            "restaurant_id": 5,
                            "restaurant_name": "Frying Pan",
                            "category": "Chicken Sandwiches",
                            "sub_category": "White Meat (Chicken Breast)",
                            "item_name": "Waffle Sando",
                            "item_desc": "Nashville st hot chicken breast with frying pan hot dust, marble cheese, powdered sugar, house-made maple butter syrup",
                            "price": 17.00,
                            "avg_prep_time": None,
                            "suggested_items": None,
                            "is_available": True,
                            "is_special": True,
                            "created_at": "2026-03-15T12:00:00",
                            "updated_at": "2026-03-15T14:00:00",
                            "option_groups": None,
                        }
                    }
                },
            },
        },
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
    return MenuItemResponse(**result)


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
                        "menu_item_ids": [1, 2, 3, 4, 5, 6, 7],
                        "is_available": False,
                    },
                }
            },
        },
        "responses": {
            200: {
                "description": "Number of items updated",
                "content": {"application/json": {"example": {"updated_count": 7}}},
            },
            400: {
                "description": "Validation error (items don't belong to restaurant, empty array, or IDs don't exist)",
                "content": {
                    "application/json": {
                        "example": {"detail": "One or more menu items do not belong to this restaurant"}
                    }
                },
            },
        },
    },
)
async def bulk_update_availability(
    restaurant_id: int,
    payload: dict = Body(..., description="Bulk update data"),
    menu_service: MenuService = Depends(get_menu_service),
) -> dict:
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
    return result


@router.get(
    "/restaurants/{restaurant_id}/menu/categories",
    summary="Get Menu Categories",
    description="Retrieve all distinct categories and sub-categories for a restaurant's menu. Requires admin authentication.",
    openapi_extra={
        "responses": {
            200: {
                "description": "Categories with their sub-categories",
                "content": {
                    "application/json": {
                        "example": {
                            "categories": {
                                "Chicken Sandwiches": [
                                    "White Meat (Chicken Breast)",
                                    "Dark Meat (Chicken Thigh)",
                                ],
                                "Fries": [],
                            }
                        }
                    }
                },
            },
        }
    },
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

    **Errors**:
    - 401: Unauthorized (invalid or missing JWT token)
    - 404: Restaurant not found
    """
    categories = menu_service.get_menu_categories(restaurant_id)
    return MenuCategoriesResponse(categories=categories)
