"""
Admin menu option group/value management endpoints.
"""

from fastapi import APIRouter, Body, Depends, status

from app.middleware.auth_middleware import get_current_admin_user
from app.models.menu_option_models import (
    MenuItemOptionGroupAttach,
    MenuOptionGroupCreate,
    MenuOptionGroupResponse,
    MenuOptionGroupUpdate,
    MenuOptionValueCreate,
    MenuOptionValueResponse,
    MenuOptionValueUpdate,
)
from app.services.menu_option_service import MenuOptionService
from app.utils.payload_validator import validate_payload


def _validate_payload(model, payload: dict):
    return validate_payload(model, payload)


def get_menu_option_service() -> MenuOptionService:
    return MenuOptionService()


router = APIRouter(
    prefix="/api/v1/admin",
    tags=["Menus"],
    dependencies=[Depends(get_current_admin_user)],
)

OPTION_GROUP_UPDATE_SCHEMA = MenuOptionGroupUpdate.model_json_schema()
OPTION_VALUE_CREATE_SCHEMA = MenuOptionValueCreate.model_json_schema()
OPTION_VALUE_UPDATE_SCHEMA = MenuOptionValueUpdate.model_json_schema()
ITEM_OPTION_GROUP_ATTACH_SCHEMA = MenuItemOptionGroupAttach.model_json_schema()


@router.post(
    "/restaurants/{restaurant_id}/menu/option-groups",
    status_code=status.HTTP_201_CREATED,
    summary="Create Option Group",
    description="Create a reusable customization option group for a restaurant. Groups can later be attached to menu items.",
    openapi_extra={
        "requestBody": {
            "content": {
                "application/json": {
                    "example": {
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
                                "name": "No Heat",
                                "price_delta": 0,
                                "is_default": True,
                                "is_available": True,
                                "sort_order": 0,
                            },
                            {
                                "name": "Mild Hot",
                                "price_delta": 0,
                                "is_default": False,
                                "is_available": True,
                                "sort_order": 1,
                            },
                            {
                                "name": "Medium Hot",
                                "price_delta": 0,
                                "is_default": False,
                                "is_available": True,
                                "sort_order": 2,
                            },
                            {
                                "name": "Extra Hot",
                                "price_delta": 0,
                                "is_default": False,
                                "is_available": True,
                                "sort_order": 3,
                            },
                            {
                                "name": "911",
                                "price_delta": 0.50,
                                "is_default": False,
                                "is_available": True,
                                "sort_order": 4,
                            },
                        ],
                    },
                }
            },
        }
    },
    responses={
        201: {
            "description": "Created option group with inline values",
            "content": {
                "application/json": {
                    "example": {
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
                    }
                }
            },
        }
    },
)
async def create_option_group(
    restaurant_id: int,
    payload: MenuOptionGroupCreate = Body(..., description="Option group with optional inline values"),
    service: MenuOptionService = Depends(get_menu_option_service),
) -> MenuOptionGroupResponse:
    result = service.create_option_group(restaurant_id, payload.model_dump(exclude_none=True))
    return MenuOptionGroupResponse(**result)


@router.get(
    "/restaurants/{restaurant_id}/menu/option-groups",
    summary="List Option Groups",
    description="List all customization option groups for a restaurant, each with their values.",
    responses={
        200: {
            "description": "All option groups with nested values",
            "content": {
                "application/json": {
                    "example": [
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
                    ]
                }
            },
        }
    },
)
async def list_option_groups(
    restaurant_id: int,
    service: MenuOptionService = Depends(get_menu_option_service),
) -> list[MenuOptionGroupResponse]:
    groups = service.list_option_groups(restaurant_id)
    return [MenuOptionGroupResponse(**group) for group in groups]


@router.get(
    "/menu/option-groups/{group_id}",
    summary="Get Option Group",
    description="Retrieve a single option group by ID with all its values.",
    responses={
        200: {
            "description": "Option group with all values",
            "content": {
                "application/json": {
                    "example": {
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
                                "name": "Corn Slaw",
                                "price_delta": 3.50,
                                "is_default": False,
                                "is_available": True,
                                "sort_order": 4,
                            },
                            {
                                "id": 11,
                                "group_id": 2,
                                "name": "Grilled Mozza",
                                "price_delta": 3.00,
                                "is_default": False,
                                "is_available": True,
                                "sort_order": 5,
                            },
                            {
                                "id": 12,
                                "group_id": 2,
                                "name": "Bacon (2 slices)",
                                "price_delta": 3.00,
                                "is_default": False,
                                "is_available": True,
                                "sort_order": 6,
                            },
                            {
                                "id": 13,
                                "group_id": 2,
                                "name": "Hash Brown",
                                "price_delta": 2.00,
                                "is_default": False,
                                "is_available": True,
                                "sort_order": 7,
                            },
                        ],
                    }
                }
            },
        },
        404: {
            "description": "Option group not found",
            "content": {"application/json": {"example": {"detail": "Option group not found"}}},
        },
    },
)
async def get_option_group(
    group_id: int,
    service: MenuOptionService = Depends(get_menu_option_service),
) -> MenuOptionGroupResponse:
    group = service.get_option_group(group_id)
    return MenuOptionGroupResponse(**group)


@router.put(
    "/menu/option-groups/{group_id}",
    summary="Update Option Group",
    description="Update any fields of an option group. Only provided fields are changed.",
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {
                "application/json": {
                    "schema": OPTION_GROUP_UPDATE_SCHEMA,
                    "example": {
                        "max_select": 3,
                        "free_allowance": 1,
                        "free_allowance_strategy": "LOWEST_PRICE_FIRST",
                        "prompt_style": "ASK_IF_MENTIONED",
                    },
                }
            },
        }
    },
    responses={
        200: {
            "description": "Updated option group with all values",
            "content": {
                "application/json": {
                    "example": {
                        "id": 2,
                        "restaurant_id": 5,
                        "name": "Sandwich Add-ons",
                        "description": "Add extra items to your sandwich",
                        "selection_type": "multiple",
                        "min_select": 0,
                        "max_select": 3,
                        "free_allowance": 1,
                        "free_allowance_strategy": "LOWEST_PRICE_FIRST",
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
                    }
                }
            },
        },
        404: {
            "description": "Option group not found",
            "content": {"application/json": {"example": {"detail": "Option group not found"}}},
        },
    },
)
async def update_option_group(
    group_id: int,
    payload: dict = Body(...),
    service: MenuOptionService = Depends(get_menu_option_service),
) -> MenuOptionGroupResponse:
    data = _validate_payload(MenuOptionGroupUpdate, payload)
    group = service.update_option_group(group_id, data.model_dump(exclude_unset=True))
    return MenuOptionGroupResponse(**group)


@router.delete(
    "/menu/option-groups/{group_id}",
    summary="Delete Option Group",
    description="Delete an option group. Fails if the group is still attached to menu items or referenced by orders.",
    responses={
        200: {
            "description": "Option group deleted",
            "content": {"application/json": {"example": {"message": "Option group deleted"}}},
        },
        400: {
            "description": "Cannot delete (still attached to items or used in orders)",
            "content": {
                "application/json": {
                    "example": {"detail": "Option group cannot be deleted while attached to menu items"}
                }
            },
        },
        404: {
            "description": "Option group not found",
            "content": {"application/json": {"example": {"detail": "Option group not found"}}},
        },
    },
)
async def delete_option_group(
    group_id: int,
    service: MenuOptionService = Depends(get_menu_option_service),
) -> dict:
    return service.delete_option_group(group_id)


@router.post(
    "/menu/option-groups/{group_id}/values",
    status_code=status.HTTP_201_CREATED,
    summary="Create Option Value",
    description="Add a new selectable value to an existing option group.",
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {
                "application/json": {
                    "schema": OPTION_VALUE_CREATE_SCHEMA,
                    "example": {
                        "name": "Hash Brown",
                        "price_delta": 2.00,
                        "is_default": False,
                        "is_available": True,
                        "sort_order": 7,
                    },
                }
            },
        }
    },
    responses={
        201: {
            "description": "Created option value",
            "content": {
                "application/json": {
                    "example": {
                        "id": 13,
                        "group_id": 2,
                        "name": "Hash Brown",
                        "price_delta": 2.00,
                        "is_default": False,
                        "is_available": True,
                        "sort_order": 7,
                    }
                }
            },
        },
        404: {
            "description": "Option group not found",
            "content": {"application/json": {"example": {"detail": "Option group not found"}}},
        },
    },
)
async def create_option_value(
    group_id: int,
    payload: dict = Body(...),
    service: MenuOptionService = Depends(get_menu_option_service),
) -> MenuOptionValueResponse:
    data = _validate_payload(MenuOptionValueCreate, payload)
    value = service.create_option_value(group_id, data.model_dump(exclude_none=True))
    return MenuOptionValueResponse(**value)


@router.put(
    "/menu/option-values/{value_id}",
    summary="Update Option Value",
    description="Update any fields of an option value. Only provided fields are changed.",
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {
                "application/json": {
                    "schema": OPTION_VALUE_UPDATE_SCHEMA,
                    "example": {"price_delta": 3.00, "is_available": False},
                }
            },
        }
    },
    responses={
        200: {
            "description": "Updated option value",
            "content": {
                "application/json": {
                    "example": {
                        "id": 6,
                        "group_id": 2,
                        "name": "Egg",
                        "price_delta": 3.00,
                        "is_default": False,
                        "is_available": False,
                        "sort_order": 0,
                    }
                }
            },
        },
        400: {
            "description": "Validation error (e.g. default options must be available)",
            "content": {"application/json": {"example": {"detail": "Default options must be available"}}},
        },
        404: {
            "description": "Option value not found",
            "content": {"application/json": {"example": {"detail": "Option value not found"}}},
        },
    },
)
async def update_option_value(
    value_id: int,
    payload: dict = Body(...),
    service: MenuOptionService = Depends(get_menu_option_service),
) -> MenuOptionValueResponse:
    data = _validate_payload(MenuOptionValueUpdate, payload)
    value = service.update_option_value(value_id, data.model_dump(exclude_unset=True))
    return MenuOptionValueResponse(**value)


@router.delete(
    "/menu/option-values/{value_id}",
    summary="Delete Option Value",
    description="Delete an option value. Default values and values used in orders cannot be deleted.",
    responses={
        200: {
            "description": "Option value deleted",
            "content": {"application/json": {"example": {"message": "Option value deleted"}}},
        },
        400: {
            "description": "Cannot delete (default value or used in orders)",
            "content": {"application/json": {"example": {"detail": "Default options cannot be deleted"}}},
        },
        404: {
            "description": "Option value not found",
            "content": {"application/json": {"example": {"detail": "Option value not found"}}},
        },
    },
)
async def delete_option_value(
    value_id: int,
    service: MenuOptionService = Depends(get_menu_option_service),
) -> dict:
    return service.delete_option_value(value_id)


@router.post(
    "/menu/{menu_id}/option-groups",
    summary="Attach Option Group to Menu Item",
    description=(
        "Attach a reusable option group to a menu item. Overrides let you customize "
        "min/max selection, free allowance, and quantity rules per item without changing the group itself."
    ),
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {
                "application/json": {
                    "schema": ITEM_OPTION_GROUP_ATTACH_SCHEMA,
                    "example": {
                        "group_id": 1,
                        "min_select_override": None,
                        "max_select_override": None,
                        "free_allowance_override": None,
                        "allows_quantity_override": None,
                        "max_quantity_per_option_override": None,
                        "is_required_override": None,
                        "sort_order": 1,
                    },
                }
            },
        }
    },
    responses={
        200: {
            "description": "Option group attached to menu item",
            "content": {
                "application/json": {"example": {"message": "Option group attached", "menu_item_id": 1, "group_id": 1}}
            },
        },
        400: {
            "description": "Validation error (group has no available values, cross-restaurant, override conflicts)",
            "content": {
                "application/json": {
                    "example": {"detail": "Option group must belong to the same restaurant as the menu item"}
                }
            },
        },
        404: {
            "description": "Menu item or option group not found",
            "content": {"application/json": {"example": {"detail": "Menu item not found"}}},
        },
    },
)
async def attach_option_group(
    menu_id: int,
    payload: dict = Body(...),
    service: MenuOptionService = Depends(get_menu_option_service),
) -> dict:
    data = _validate_payload(MenuItemOptionGroupAttach, payload)
    return service.attach_group_to_item(menu_id, data.group_id, data.model_dump(exclude_unset=True))


@router.delete(
    "/menu/{menu_id}/option-groups/{group_id}",
    summary="Detach Option Group from Menu Item",
    description="Remove an option group attachment from a menu item. The group itself is not deleted.",
    responses={
        200: {
            "description": "Option group detached from menu item",
            "content": {
                "application/json": {"example": {"message": "Option group detached", "menu_item_id": 1, "group_id": 1}}
            },
        },
        404: {
            "description": "Item-group mapping not found",
            "content": {"application/json": {"example": {"detail": "Item-group mapping not found"}}},
        },
    },
)
async def detach_option_group(
    menu_id: int,
    group_id: int,
    service: MenuOptionService = Depends(get_menu_option_service),
) -> dict:
    return service.detach_group_from_item(menu_id, group_id)
