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
    description="Create a new menu item for the authenticated restaurant.",
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
        },
        "responses": {
            201: {
                "description": "Menu item created",
                "content": {
                    "application/json": {
                        "example": {
                            "id": 1,
                            "restaurant_id": 10,
                            "restaurant_name": "Ressy Test Kitchen",
                            "item_name": "Margherita Pizza",
                            "price": 15.99,
                            "category": "Pizza",
                            "sub_category": "Classic",
                            "is_available": True,
                            "is_special": False,
                        }
                    }
                },
            }
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
                "description": "Menu items retrieved",
                "content": {
                    "application/json": {
                        "example": {
                            "items": [
                                {
                                    "id": 1,
                                    "restaurant_id": 10,
                                    "restaurant_name": "Ressy Test Kitchen",
                                    "item_name": "Margherita Pizza",
                                    "price": 15.99,
                                    "category": "Pizza",
                                    "sub_category": "Classic",
                                    "is_available": True,
                                    "is_special": False,
                                    "option_groups": None,
                                }
                            ],
                            "pagination": {"page": 1, "limit": 50, "total": 1, "pages": 1},
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
                "description": "Categories retrieved",
                "content": {
                    "application/json": {
                        "example": {
                            "categories": {
                                "Pizza": ["Classic", "Specialty"],
                                "Drinks": ["Hot", "Cold"],
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
                "description": "Menu item retrieved",
                "content": {
                    "application/json": {
                        "example": {
                            "id": 1,
                            "restaurant_id": 10,
                            "restaurant_name": "Ressy Test Kitchen",
                            "item_name": "Margherita Pizza",
                            "price": 15.99,
                            "category": "Pizza",
                            "sub_category": "Classic",
                            "is_available": True,
                            "is_special": False,
                            "option_groups": [
                                {
                                    "id": 12,
                                    "restaurant_id": 10,
                                    "name": "Toppings",
                                    "description": "Choose your toppings",
                                    "selection_type": "multiple",
                                    "min_select": 0,
                                    "max_select": 5,
                                    "free_allowance": 2,
                                    "allows_quantity": True,
                                    "max_quantity_per_option": 2,
                                    "prompt_style": "ASK_ALWAYS",
                                    "is_required": False,
                                    "is_available": True,
                                    "sort_order": 1,
                                    "values": [
                                        {
                                            "id": 101,
                                            "group_id": 12,
                                            "name": "Pepperoni",
                                            "price_delta": 1.5,
                                            "is_default": False,
                                            "is_available": True,
                                            "sort_order": 1,
                                        }
                                    ],
                                }
                            ],
                        }
                    }
                },
            }
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
                    "example": {"price": 17.99, "item_desc": "Updated description", "is_special": True},
                }
            },
        },
        "responses": {
            200: {
                "description": "Menu item updated",
                "content": {
                    "application/json": {
                        "example": {
                            "id": 1,
                            "restaurant_id": 10,
                            "item_name": "Margherita Pizza",
                            "price": 17.99,
                            "is_special": True,
                        }
                    }
                },
            }
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
    description="Delete a menu item for the authenticated restaurant.",
    openapi_extra={
        "responses": {
            200: {
                "description": "Menu item deleted",
                "content": {
                    "application/json": {"example": {"message": "Menu item deleted successfully", "menu_id": 1}}
                },
            }
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
                "description": "Availability updated",
                "content": {
                    "application/json": {
                        "example": {
                            "id": 1,
                            "item_name": "Margherita Pizza",
                            "is_available": False,
                            "restaurant_id": 10,
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
                "description": "Special status updated",
                "content": {
                    "application/json": {
                        "example": {
                            "id": 1,
                            "item_name": "Margherita Pizza",
                            "is_special": True,
                            "restaurant_id": 10,
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
                    "example": {"menu_item_ids": [1, 2, 3], "is_available": False},
                }
            },
        },
        "responses": {
            200: {
                "description": "Availability updated",
                "content": {"application/json": {"example": {"updated_count": 3}}},
            }
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
