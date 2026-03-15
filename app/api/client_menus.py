"""
Client-scoped menu CRUD for restaurant staff.
Restaurant is derived from the authenticated token; no restaurant_id is accepted from the request.
"""

from typing import Optional

from fastapi import APIRouter, Body, Depends, Query, status

from app.middleware.auth_middleware import get_current_restaurant_user
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
    prefix="/api/v1/client",
    tags=["Menus"],
    dependencies=[Depends(get_current_restaurant_user)],
)

MENU_CREATE_SCHEMA = MenuItemCreate.model_json_schema()
MENU_UPDATE_SCHEMA = MenuItemUpdate.model_json_schema()
TOGGLE_AVAILABILITY_SCHEMA = ToggleAvailabilityRequest.model_json_schema()
TOGGLE_SPECIAL_SCHEMA = ToggleSpecialRequest.model_json_schema()
BULK_AVAILABILITY_SCHEMA = BulkAvailabilityRequest.model_json_schema()


@router.post(
    "/menu",
    status_code=status.HTTP_201_CREATED,
    summary="Create Menu Item (Client)",
    description="Create a new menu item for the authenticated restaurant. Restaurant ID is derived from the JWT token.",
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {
                "application/json": {
                    "schema": MENU_CREATE_SCHEMA,
                    "example": {
                        "item_name": "Hot Crunch",
                        "price": 14.50,
                        "category": "Chicken Sandwiches",
                        "sub_category": "Dark Meat (Chicken Thigh)",
                        "item_desc": "Chicken thigh, house mayo, cabbage slaw, pickles",
                        "avg_prep_time": 10,
                        "suggested_items": [1, 8],
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
                            "id": 5,
                            "restaurant_id": 5,
                            "restaurant_name": "Frying Pan",
                            "category": "Chicken Sandwiches",
                            "sub_category": "Dark Meat (Chicken Thigh)",
                            "item_name": "Hot Crunch",
                            "item_desc": "Chicken thigh, house mayo, cabbage slaw, pickles",
                            "price": 14.50,
                            "avg_prep_time": 10,
                            "suggested_items": [1, 8],
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
                "description": "Validation error",
                "content": {
                    "application/json": {
                        "example": {
                            "detail": "A menu item with the name 'Hot Crunch' already exists in this restaurant"
                        }
                    }
                },
            },
        },
    },
    response_model=MenuItemResponse,
    response_description="Created menu item scoped to the restaurant.",
)
async def create_menu_item(
    payload: dict = Body(..., description="Menu item data"),
    menu_service: MenuService = Depends(get_menu_service),
    claims: dict = Depends(get_current_restaurant_user),
) -> MenuItemResponse:
    restaurant_id = int(claims["restaurant_id"])
    data = _validate_payload(MenuItemCreate, payload)
    result = menu_service.create_menu_item(restaurant_id, data.model_dump(exclude_none=False))
    return MenuItemResponse(**result)


@router.get(
    "/menu",
    summary="List Menu Items (Client)",
    description="Retrieve paginated menu items for the authenticated restaurant with optional filters.",
    openapi_extra={
        "responses": {
            200: {
                "description": "Paginated menu items with metadata",
                "content": {
                    "application/json": {
                        "example": {
                            "items": [
                                {
                                    "id": 5,
                                    "restaurant_id": 5,
                                    "restaurant_name": "Frying Pan",
                                    "category": "Chicken Sandwiches",
                                    "sub_category": "Dark Meat (Chicken Thigh)",
                                    "item_name": "Hot Crunch",
                                    "item_desc": "Chicken thigh, house mayo, cabbage slaw, pickles",
                                    "price": 14.50,
                                    "avg_prep_time": 10,
                                    "suggested_items": None,
                                    "is_available": True,
                                    "is_special": False,
                                    "created_at": "2026-03-15T12:00:00",
                                    "updated_at": "2026-03-15T12:00:00",
                                    "option_groups": None,
                                },
                                {
                                    "id": 13,
                                    "restaurant_id": 5,
                                    "restaurant_name": "Frying Pan",
                                    "category": "Fries",
                                    "sub_category": None,
                                    "item_name": "Waffle Fries",
                                    "item_desc": "Served with house mayo and ketchup",
                                    "price": 6.50,
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
    response_model=MenuItemsPage,
    response_description="Paginated menu items for the restaurant.",
)
async def list_menu_items(  # pylint: disable=too-many-arguments,too-many-positional-arguments
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    limit: int = Query(50, ge=1, le=100, description="Items per page (max 100)"),
    category: Optional[str] = Query(None, description="Filter by category"),
    sub_category: Optional[str] = Query(None, description="Filter by sub-category"),
    is_available: Optional[bool] = Query(None, description="Filter by availability"),
    is_special: Optional[bool] = Query(None, description="Filter by special status"),
    search: Optional[str] = Query(None, description="Search by item name (partial match)"),
    menu_service: MenuService = Depends(get_menu_service),
    claims: dict = Depends(get_current_restaurant_user),
) -> MenuItemsPage:
    restaurant_id = int(claims["restaurant_id"])
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
    "/menu/categories",
    summary="Get Menu Categories (Client)",
    description="Retrieve all distinct categories and sub-categories for the authenticated restaurant's menu.",
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
            }
        }
    },
)
async def get_menu_categories(
    menu_service: MenuService = Depends(get_menu_service),
    claims: dict = Depends(get_current_restaurant_user),
) -> MenuCategoriesResponse:
    restaurant_id = int(claims["restaurant_id"])
    categories = menu_service.get_menu_categories(restaurant_id)
    return MenuCategoriesResponse(categories=categories)


@router.get(
    "/menu/{menu_id}",
    summary="Get Menu Item by ID (Client)",
    description="Retrieve a specific menu item for the authenticated restaurant.",
    openapi_extra={
        "responses": {
            200: {
                "description": "Menu item with full customization option groups",
                "content": {
                    "application/json": {
                        "example": {
                            "id": 5,
                            "restaurant_id": 5,
                            "restaurant_name": "Frying Pan",
                            "category": "Chicken Sandwiches",
                            "sub_category": "Dark Meat (Chicken Thigh)",
                            "item_name": "Hot Crunch",
                            "item_desc": "Chicken thigh, house mayo, cabbage slaw, pickles",
                            "price": 14.50,
                            "avg_prep_time": 10,
                            "suggested_items": None,
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
    response_model=MenuItemResponse,
)
async def get_menu_item(
    menu_id: int,
    menu_service: MenuService = Depends(get_menu_service),
    claims: dict = Depends(get_current_restaurant_user),
) -> MenuItemResponse:
    restaurant_id = int(claims["restaurant_id"])
    result = menu_service.get_menu_item_for_restaurant(restaurant_id, menu_id)
    return MenuItemResponse(**result)


@router.put(
    "/menu/{menu_id}",
    summary="Update Menu Item (Client)",
    description="Update any fields of a menu item for the authenticated restaurant.",
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {
                "application/json": {
                    "schema": MENU_UPDATE_SCHEMA,
                    "example": {
                        "price": 15.50,
                        "item_desc": "Chicken thigh, house mayo, cabbage slaw, pickles — extra crispy",
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
                            "id": 5,
                            "restaurant_id": 5,
                            "restaurant_name": "Frying Pan",
                            "category": "Chicken Sandwiches",
                            "sub_category": "Dark Meat (Chicken Thigh)",
                            "item_name": "Hot Crunch",
                            "item_desc": "Chicken thigh, house mayo, cabbage slaw, pickles — extra crispy",
                            "price": 15.50,
                            "avg_prep_time": 10,
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
    response_model=MenuItemResponse,
)
async def update_menu_item(
    menu_id: int,
    payload: dict = Body(..., description="Menu item fields to update"),
    menu_service: MenuService = Depends(get_menu_service),
    claims: dict = Depends(get_current_restaurant_user),
) -> MenuItemResponse:
    restaurant_id = int(claims["restaurant_id"])
    data = _validate_payload(MenuItemUpdate, payload)
    result = menu_service.update_menu_item_for_restaurant(
        menu_id=menu_id, restaurant_id=restaurant_id, data=data.model_dump(exclude_unset=True)
    )
    return MenuItemResponse(**result)


@router.delete(
    "/menu/{menu_id}",
    status_code=status.HTTP_200_OK,
    summary="Delete Menu Item (Client)",
    description=(
        "Delete a menu item for the authenticated restaurant. "
        "Returns 409 if the item is referenced by existing orders."
    ),
    openapi_extra={
        "responses": {
            200: {
                "description": "Menu item deleted",
                "content": {
                    "application/json": {"example": {"message": "Menu item deleted successfully", "menu_id": 5}}
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
    response_description="Deletion confirmation.",
)
async def delete_menu_item(
    menu_id: int,
    menu_service: MenuService = Depends(get_menu_service),
    claims: dict = Depends(get_current_restaurant_user),
) -> dict:
    restaurant_id = int(claims["restaurant_id"])
    menu_service.delete_menu_item_for_restaurant(restaurant_id, menu_id)
    return {"message": "Menu item deleted successfully", "menu_id": menu_id}


@router.patch(
    "/menu/{menu_id}/availability",
    summary="Toggle Menu Item Availability (Client)",
    description="Update the availability status of a menu item for the authenticated restaurant.",
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
                            "id": 5,
                            "restaurant_id": 5,
                            "restaurant_name": "Frying Pan",
                            "category": "Chicken Sandwiches",
                            "sub_category": "Dark Meat (Chicken Thigh)",
                            "item_name": "Hot Crunch",
                            "item_desc": "Chicken thigh, house mayo, cabbage slaw, pickles",
                            "price": 14.50,
                            "avg_prep_time": 10,
                            "suggested_items": None,
                            "is_available": False,
                            "is_special": False,
                            "created_at": "2026-03-15T12:00:00",
                            "updated_at": "2026-03-15T14:00:00",
                            "option_groups": None,
                        }
                    }
                },
            }
        },
    },
    response_model=MenuItemResponse,
)
async def toggle_availability(
    menu_id: int,
    payload: dict = Body(..., description="Availability status"),
    menu_service: MenuService = Depends(get_menu_service),
    claims: dict = Depends(get_current_restaurant_user),
) -> MenuItemResponse:
    restaurant_id = int(claims["restaurant_id"])
    data = _validate_payload(ToggleAvailabilityRequest, payload)
    result = menu_service.toggle_availability_for_restaurant(restaurant_id, menu_id, data.is_available)
    return MenuItemResponse(**result)


@router.patch(
    "/menu/{menu_id}/special",
    summary="Toggle Menu Item Special Status (Client)",
    description="Update the special status of a menu item for the authenticated restaurant.",
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
                            "id": 5,
                            "restaurant_id": 5,
                            "restaurant_name": "Frying Pan",
                            "category": "Chicken Sandwiches",
                            "sub_category": "Dark Meat (Chicken Thigh)",
                            "item_name": "Hot Crunch",
                            "item_desc": "Chicken thigh, house mayo, cabbage slaw, pickles",
                            "price": 14.50,
                            "avg_prep_time": 10,
                            "suggested_items": None,
                            "is_available": True,
                            "is_special": True,
                            "created_at": "2026-03-15T12:00:00",
                            "updated_at": "2026-03-15T14:00:00",
                            "option_groups": None,
                        }
                    }
                },
            }
        },
    },
    response_model=MenuItemResponse,
)
async def toggle_special(
    menu_id: int,
    payload: dict = Body(..., description="Special status"),
    menu_service: MenuService = Depends(get_menu_service),
    claims: dict = Depends(get_current_restaurant_user),
) -> MenuItemResponse:
    restaurant_id = int(claims["restaurant_id"])
    data = _validate_payload(ToggleSpecialRequest, payload)
    result = menu_service.toggle_special_for_restaurant(restaurant_id, menu_id, data.is_special)
    return MenuItemResponse(**result)


@router.patch(
    "/menu/bulk-availability",
    summary="Bulk Update Menu Item Availability (Client)",
    description="Update availability for multiple menu items for the authenticated restaurant.",
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {
                "application/json": {
                    "schema": BULK_AVAILABILITY_SCHEMA,
                    "example": {"menu_item_ids": [1, 2, 3, 4, 5, 6, 7], "is_available": False},
                }
            },
        },
        "responses": {
            200: {
                "description": "Number of items updated",
                "content": {"application/json": {"example": {"updated_count": 7}}},
            },
            400: {
                "description": "Validation error",
                "content": {
                    "application/json": {
                        "example": {"detail": "One or more menu items do not belong to this restaurant"}
                    }
                },
            },
        },
    },
    response_model=dict,
)
async def bulk_update_availability(
    payload: dict = Body(..., description="Bulk update data"),
    menu_service: MenuService = Depends(get_menu_service),
    claims: dict = Depends(get_current_restaurant_user),
) -> dict:
    restaurant_id = int(claims["restaurant_id"])
    data = _validate_payload(BulkAvailabilityRequest, payload)
    result = menu_service.bulk_update_availability(restaurant_id, data.menu_item_ids, data.is_available)
    return result
