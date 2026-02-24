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

OPTION_GROUP_CREATE_SCHEMA = MenuOptionGroupCreate.model_json_schema()
OPTION_GROUP_UPDATE_SCHEMA = MenuOptionGroupUpdate.model_json_schema()
OPTION_VALUE_CREATE_SCHEMA = MenuOptionValueCreate.model_json_schema()
OPTION_VALUE_UPDATE_SCHEMA = MenuOptionValueUpdate.model_json_schema()
ITEM_OPTION_GROUP_ATTACH_SCHEMA = MenuItemOptionGroupAttach.model_json_schema()


@router.post(
    "/restaurants/{restaurant_id}/menu/option-groups",
    status_code=status.HTTP_201_CREATED,
    summary="Create Option Group",
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {
                "application/json": {
                    "schema": OPTION_GROUP_CREATE_SCHEMA,
                    "example": {
                        "name": "Pizza Toppings",
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
                            {"name": "Pepperoni", "price_delta": 1.5, "is_default": False, "is_available": True},
                            {"name": "Mushrooms", "price_delta": 1.0, "is_default": False, "is_available": True},
                        ],
                    },
                }
            },
        }
    },
    responses={
        201: {
            "description": "Created option group",
            "content": {
                "application/json": {
                    "example": {
                        "id": 12,
                        "restaurant_id": 3,
                        "name": "Pizza Toppings",
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
                }
            },
        }
    },
)
async def create_option_group(
    restaurant_id: int,
    payload: dict = Body(...),
    service: MenuOptionService = Depends(get_menu_option_service),
) -> MenuOptionGroupResponse:
    data = _validate_payload(MenuOptionGroupCreate, payload)
    result = service.create_option_group(restaurant_id, data.model_dump(exclude_none=True))
    return MenuOptionGroupResponse(**result)


@router.get(
    "/restaurants/{restaurant_id}/menu/option-groups",
    summary="List Option Groups",
    responses={
        200: {
            "description": "List of option groups",
            "content": {
                "application/json": {
                    "example": [
                        {
                            "id": 12,
                            "restaurant_id": 3,
                            "name": "Pizza Toppings",
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
    responses={
        200: {
            "description": "Option group",
            "content": {
                "application/json": {
                    "example": {
                        "id": 12,
                        "restaurant_id": 3,
                        "name": "Pizza Toppings",
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
                }
            },
        }
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
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {
                "application/json": {
                    "schema": OPTION_GROUP_UPDATE_SCHEMA,
                    "example": {"max_select": 4, "free_allowance": 1, "prompt_style": "ASK_IF_MENTIONED"},
                }
            },
        }
    },
    responses={
        200: {
            "description": "Updated option group",
            "content": {
                "application/json": {
                    "example": {
                        "id": 12,
                        "restaurant_id": 3,
                        "name": "Pizza Toppings",
                        "description": "Choose your toppings",
                        "selection_type": "multiple",
                        "min_select": 0,
                        "max_select": 4,
                        "free_allowance": 1,
                        "allows_quantity": True,
                        "max_quantity_per_option": 2,
                        "prompt_style": "ASK_IF_MENTIONED",
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
                }
            },
        }
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
    responses={
        200: {
            "description": "Deleted option group",
            "content": {"application/json": {"example": {"message": "Option group deleted"}}},
        }
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
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {
                "application/json": {
                    "schema": OPTION_VALUE_CREATE_SCHEMA,
                    "example": {"name": "Extra Cheese", "price_delta": 1.25, "is_default": False, "is_available": True},
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
                        "id": 101,
                        "group_id": 12,
                        "name": "Extra Cheese",
                        "price_delta": 1.25,
                        "is_default": False,
                        "is_available": True,
                        "sort_order": 0,
                    }
                }
            },
        }
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
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {
                "application/json": {
                    "schema": OPTION_VALUE_UPDATE_SCHEMA,
                    "example": {"price_delta": 1.5, "is_available": False},
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
                        "id": 101,
                        "group_id": 12,
                        "name": "Extra Cheese",
                        "price_delta": 1.5,
                        "is_default": False,
                        "is_available": False,
                        "sort_order": 0,
                    }
                }
            },
        }
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
    responses={
        200: {
            "description": "Deleted option value",
            "content": {"application/json": {"example": {"message": "Option value deleted"}}},
        }
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
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {
                "application/json": {
                    "schema": ITEM_OPTION_GROUP_ATTACH_SCHEMA,
                    "example": {
                        "group_id": 12,
                        "min_select_override": 0,
                        "max_select_override": 3,
                        "free_allowance_override": 1,
                        "allows_quantity_override": True,
                        "max_quantity_per_option_override": 2,
                        "is_required_override": False,
                        "sort_order": 1,
                    },
                }
            },
        }
    },
    responses={
        200: {
            "description": "Attached option group",
            "content": {
                "application/json": {
                    "example": {"message": "Option group attached", "menu_item_id": 444, "group_id": 12}
                }
            },
        }
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
    responses={
        200: {
            "description": "Detached option group",
            "content": {
                "application/json": {
                    "example": {"message": "Option group detached", "menu_item_id": 444, "group_id": 12}
                }
            },
        }
    },
)
async def detach_option_group(
    menu_id: int,
    group_id: int,
    service: MenuOptionService = Depends(get_menu_option_service),
) -> dict:
    return service.detach_group_from_item(menu_id, group_id)
