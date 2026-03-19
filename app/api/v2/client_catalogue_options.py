"""
Client-scoped catalogue option group/value management endpoints.
"""

from fastapi import APIRouter, Body, Depends, status

from app.middleware.auth_middleware import get_current_business_user
from app.models.catalogue_option_models import (
    CatalogueItemOptionGroupAttach,
    CatalogueOptionGroupCreate,
    CatalogueOptionGroupResponse,
    CatalogueOptionGroupUpdate,
    CatalogueOptionValueCreate,
    CatalogueOptionValueResponse,
    CatalogueOptionValueUpdate,
)
from app.services.catalogue_option_service import CatalogueOptionService
from app.utils.payload_validator import validate_payload


def _validate_payload(model, payload: dict):
    return validate_payload(model, payload)


def get_catalogue_option_service() -> CatalogueOptionService:
    return CatalogueOptionService()


router = APIRouter(
    prefix="/api/v2/client",
    tags=["Catalogues"],
    dependencies=[Depends(get_current_business_user)],
)

OPTION_GROUP_CREATE_SCHEMA = CatalogueOptionGroupCreate.model_json_schema()
OPTION_GROUP_UPDATE_SCHEMA = CatalogueOptionGroupUpdate.model_json_schema()
OPTION_VALUE_CREATE_SCHEMA = CatalogueOptionValueCreate.model_json_schema()
OPTION_VALUE_UPDATE_SCHEMA = CatalogueOptionValueUpdate.model_json_schema()
ITEM_OPTION_GROUP_ATTACH_SCHEMA = CatalogueItemOptionGroupAttach.model_json_schema()


@router.post(
    "/catalogue/option-groups",
    status_code=status.HTTP_201_CREATED,
    summary="Create Option Group (Client)",
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {
                "application/json": {
                    "schema": OPTION_GROUP_CREATE_SCHEMA,
                    "example": {
                        "name": "Spice Level",
                        "description": "Choose your heat",
                        "selection_type": "single",
                        "min_select": 0,
                        "max_select": 1,
                        "free_allowance": 0,
                        "allows_quantity": False,
                        "prompt_style": "ASK_ALWAYS",
                        "is_required": False,
                        "is_available": True,
                        "sort_order": 1,
                        "values": [
                            {"name": "Mild", "price_delta": 0, "is_default": True, "is_available": True},
                            {"name": "Hot", "price_delta": 0, "is_default": False, "is_available": True},
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
                        "id": 22,
                        "business_id": 5,
                        "name": "Spice Level",
                        "description": "Choose your heat",
                        "selection_type": "single",
                        "min_select": 0,
                        "max_select": 1,
                        "free_allowance": 0,
                        "allows_quantity": False,
                        "max_quantity_per_option": None,
                        "prompt_style": "ASK_ALWAYS",
                        "is_required": False,
                        "is_available": True,
                        "sort_order": 1,
                        "values": [
                            {
                                "id": 301,
                                "group_id": 22,
                                "name": "Mild",
                                "price_delta": 0.0,
                                "is_default": True,
                                "is_available": True,
                                "sort_order": 0,
                            }
                        ],
                    }
                }
            },
        }
    },
)
async def create_option_group(
    payload: dict = Body(...),
    service: CatalogueOptionService = Depends(get_catalogue_option_service),
    claims: dict = Depends(get_current_business_user),
) -> CatalogueOptionGroupResponse:
    business_id = int(claims["business_id"])
    data = _validate_payload(CatalogueOptionGroupCreate, payload)
    result = service.create_option_group(business_id, data.model_dump(exclude_none=True))
    return CatalogueOptionGroupResponse(**result)


@router.get(
    "/catalogue/option-groups",
    summary="List Option Groups (Client)",
    responses={
        200: {
            "description": "List of option groups",
            "content": {
                "application/json": {
                    "example": [
                        {
                            "id": 22,
                            "business_id": 5,
                            "name": "Spice Level",
                            "description": "Choose your heat",
                            "selection_type": "single",
                            "min_select": 0,
                            "max_select": 1,
                            "free_allowance": 0,
                            "allows_quantity": False,
                            "max_quantity_per_option": None,
                            "prompt_style": "ASK_ALWAYS",
                            "is_required": False,
                            "is_available": True,
                            "sort_order": 1,
                            "values": [
                                {
                                    "id": 301,
                                    "group_id": 22,
                                    "name": "Mild",
                                    "price_delta": 0.0,
                                    "is_default": True,
                                    "is_available": True,
                                    "sort_order": 0,
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
    service: CatalogueOptionService = Depends(get_catalogue_option_service),
    claims: dict = Depends(get_current_business_user),
) -> list[CatalogueOptionGroupResponse]:
    business_id = int(claims["business_id"])
    groups = service.list_option_groups(business_id)
    return [CatalogueOptionGroupResponse(**group) for group in groups]


@router.get(
    "/catalogue/option-groups/{group_id}",
    summary="Get Option Group (Client)",
    responses={
        200: {
            "description": "Option group",
            "content": {
                "application/json": {
                    "example": {
                        "id": 22,
                        "business_id": 5,
                        "name": "Spice Level",
                        "description": "Choose your heat",
                        "selection_type": "single",
                        "min_select": 0,
                        "max_select": 1,
                        "free_allowance": 0,
                        "allows_quantity": False,
                        "max_quantity_per_option": None,
                        "prompt_style": "ASK_ALWAYS",
                        "is_required": False,
                        "is_available": True,
                        "sort_order": 1,
                        "values": [
                            {
                                "id": 301,
                                "group_id": 22,
                                "name": "Mild",
                                "price_delta": 0.0,
                                "is_default": True,
                                "is_available": True,
                                "sort_order": 0,
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
    service: CatalogueOptionService = Depends(get_catalogue_option_service),
    claims: dict = Depends(get_current_business_user),
) -> CatalogueOptionGroupResponse:
    business_id = int(claims["business_id"])
    group = service.get_option_group_for_business(business_id, group_id)
    return CatalogueOptionGroupResponse(**group)


@router.put(
    "/catalogue/option-groups/{group_id}",
    summary="Update Option Group (Client)",
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {
                "application/json": {
                    "schema": OPTION_GROUP_UPDATE_SCHEMA,
                    "example": {"is_available": False, "prompt_style": "ASK_IF_MENTIONED"},
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
                        "id": 22,
                        "business_id": 5,
                        "name": "Spice Level",
                        "description": "Choose your heat",
                        "selection_type": "single",
                        "min_select": 0,
                        "max_select": 1,
                        "free_allowance": 0,
                        "allows_quantity": False,
                        "max_quantity_per_option": None,
                        "prompt_style": "ASK_IF_MENTIONED",
                        "is_required": False,
                        "is_available": False,
                        "sort_order": 1,
                        "values": [
                            {
                                "id": 301,
                                "group_id": 22,
                                "name": "Mild",
                                "price_delta": 0.0,
                                "is_default": True,
                                "is_available": True,
                                "sort_order": 0,
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
    service: CatalogueOptionService = Depends(get_catalogue_option_service),
    claims: dict = Depends(get_current_business_user),
) -> CatalogueOptionGroupResponse:
    business_id = int(claims["business_id"])
    data = _validate_payload(CatalogueOptionGroupUpdate, payload)
    group = service.update_option_group_for_business(business_id, group_id, data.model_dump(exclude_unset=True))
    return CatalogueOptionGroupResponse(**group)


@router.delete(
    "/catalogue/option-groups/{group_id}",
    summary="Delete Option Group (Client)",
    responses={
        200: {
            "description": "Deleted option group",
            "content": {"application/json": {"example": {"message": "Option group deleted"}}},
        }
    },
)
async def delete_option_group(
    group_id: int,
    service: CatalogueOptionService = Depends(get_catalogue_option_service),
    claims: dict = Depends(get_current_business_user),
) -> dict:
    business_id = int(claims["business_id"])
    return service.delete_option_group_for_business(business_id, group_id)


@router.post(
    "/catalogue/option-groups/{group_id}/values",
    status_code=status.HTTP_201_CREATED,
    summary="Create Option Value (Client)",
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {
                "application/json": {
                    "schema": OPTION_VALUE_CREATE_SCHEMA,
                    "example": {"name": "Extra Spicy", "price_delta": 0.5, "is_default": False, "is_available": True},
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
                        "id": 302,
                        "group_id": 22,
                        "name": "Extra Spicy",
                        "price_delta": 0.5,
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
    service: CatalogueOptionService = Depends(get_catalogue_option_service),
    claims: dict = Depends(get_current_business_user),
) -> CatalogueOptionValueResponse:
    business_id = int(claims["business_id"])
    data = _validate_payload(CatalogueOptionValueCreate, payload)
    value = service.create_option_value_for_business(business_id, group_id, data.model_dump(exclude_none=True))
    return CatalogueOptionValueResponse(**value)


@router.put(
    "/catalogue/option-values/{value_id}",
    summary="Update Option Value (Client)",
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {
                "application/json": {
                    "schema": OPTION_VALUE_UPDATE_SCHEMA,
                    "example": {"is_default": True},
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
                        "id": 302,
                        "group_id": 22,
                        "name": "Extra Spicy",
                        "price_delta": 0.5,
                        "is_default": True,
                        "is_available": True,
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
    service: CatalogueOptionService = Depends(get_catalogue_option_service),
    claims: dict = Depends(get_current_business_user),
) -> CatalogueOptionValueResponse:
    business_id = int(claims["business_id"])
    data = _validate_payload(CatalogueOptionValueUpdate, payload)
    value = service.update_option_value_for_business(business_id, value_id, data.model_dump(exclude_unset=True))
    return CatalogueOptionValueResponse(**value)


@router.delete(
    "/catalogue/option-values/{value_id}",
    summary="Delete Option Value (Client)",
    responses={
        200: {
            "description": "Deleted option value",
            "content": {"application/json": {"example": {"message": "Option value deleted"}}},
        }
    },
)
async def delete_option_value(
    value_id: int,
    service: CatalogueOptionService = Depends(get_catalogue_option_service),
    claims: dict = Depends(get_current_business_user),
) -> dict:
    business_id = int(claims["business_id"])
    return service.delete_option_value_for_business(business_id, value_id)


@router.post(
    "/catalogue/{catalogue_id}/option-groups",
    summary="Attach Option Group to Catalogue Item (Client)",
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {
                "application/json": {
                    "schema": ITEM_OPTION_GROUP_ATTACH_SCHEMA,
                    "example": {"group_id": 22, "min_select_override": 1, "max_select_override": 2, "sort_order": 2},
                }
            },
        }
    },
    responses={
        200: {
            "description": "Attached option group",
            "content": {
                "application/json": {
                    "example": {"message": "Option group attached", "catalogue_item_id": 444, "group_id": 22}
                }
            },
        }
    },
)
async def attach_option_group(
    catalogue_id: int,
    payload: dict = Body(...),
    service: CatalogueOptionService = Depends(get_catalogue_option_service),
    claims: dict = Depends(get_current_business_user),
) -> dict:
    business_id = int(claims["business_id"])
    data = _validate_payload(CatalogueItemOptionGroupAttach, payload)
    return service.attach_group_to_item_for_business(
        business_id,
        catalogue_id,
        data.group_id,
        data.model_dump(exclude_unset=True),
    )


@router.delete(
    "/catalogue/{catalogue_id}/option-groups/{group_id}",
    summary="Detach Option Group from Catalogue Item (Client)",
    responses={
        200: {
            "description": "Detached option group",
            "content": {
                "application/json": {
                    "example": {"message": "Option group detached", "catalogue_item_id": 444, "group_id": 22}
                }
            },
        }
    },
)
async def detach_option_group(
    catalogue_id: int,
    group_id: int,
    service: CatalogueOptionService = Depends(get_catalogue_option_service),
    claims: dict = Depends(get_current_business_user),
) -> dict:
    business_id = int(claims["business_id"])
    return service.detach_group_from_item_for_business(business_id, catalogue_id, group_id)
