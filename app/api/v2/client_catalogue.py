"""
Client-scoped catalogue CRUD for business staff.
Restaurant is derived from the authenticated token; no business_id is accepted from the request.
"""

from typing import Optional

from fastapi import APIRouter, Body, Depends, Query, status

from app.middleware.auth_middleware import get_current_business_user
from app.models.catalogue_models import (
    BulkAvailabilityRequest,
    CatalogueCategoriesResponse,
    CatalogueItemCreate,
    CatalogueItemResponse,
    CatalogueItemsPage,
    CatalogueItemUpdate,
    ToggleAvailabilityRequest,
    ToggleSpecialRequest,
)
from app.services.catalogue_service import CatalogueService
from app.utils.payload_validator import validate_payload


def _validate_payload(model, payload: dict):
    """Validate payload against a Pydantic model."""
    return validate_payload(model, payload)


def get_catalogue_service() -> CatalogueService:
    """Dependency to get CatalogueService instance."""
    return CatalogueService()


router = APIRouter(
    prefix="/api/v2/client",
    tags=["Catalogue"],
    dependencies=[Depends(get_current_business_user)],
)

MENU_CREATE_SCHEMA = CatalogueItemCreate.model_json_schema()
MENU_UPDATE_SCHEMA = CatalogueItemUpdate.model_json_schema()
TOGGLE_AVAILABILITY_SCHEMA = ToggleAvailabilityRequest.model_json_schema()
TOGGLE_SPECIAL_SCHEMA = ToggleSpecialRequest.model_json_schema()
BULK_AVAILABILITY_SCHEMA = BulkAvailabilityRequest.model_json_schema()


@router.post(
    "/catalogue",
    status_code=status.HTTP_201_CREATED,
    summary="Create Catalogue Item (Client)",
    description="Create a new catalogue item for the authenticated business.",
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
                "description": "Catalogue item created",
                "content": {
                    "application/json": {
                        "example": {
                            "id": 1,
                            "business_id": 10,
                            "business_name": "Ressy Test Kitchen",
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
    response_model=CatalogueItemResponse,
    response_description="Created catalogue item scoped to the business.",
)
async def create_catalogue_item(
    payload: dict = Body(..., description="Catalogue item data"),
    catalogue_service: CatalogueService = Depends(get_catalogue_service),
    claims: dict = Depends(get_current_business_user),
) -> CatalogueItemResponse:
    business_id = int(claims["business_id"])
    data = _validate_payload(CatalogueItemCreate, payload)
    result = catalogue_service.create_catalogue_item(business_id, data.model_dump(exclude_none=False))
    return CatalogueItemResponse(**result)


@router.get(
    "/catalogue",
    summary="List Catalogue Items (Client)",
    description="Retrieve paginated catalogue items for the authenticated business with optional filters.",
    openapi_extra={
        "responses": {
            200: {
                "description": "Catalogue items retrieved",
                "content": {
                    "application/json": {
                        "example": {
                            "items": [
                                {
                                    "id": 1,
                                    "business_id": 10,
                                    "business_name": "Ressy Test Kitchen",
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
    response_model=CatalogueItemsPage,
    response_description="Paginated catalogue items for the business.",
)
async def list_catalogue_items(  # pylint: disable=too-many-arguments,too-many-positional-arguments
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    limit: int = Query(50, ge=1, le=100, description="Items per page (max 100)"),
    category: Optional[str] = Query(None, description="Filter by category"),
    sub_category: Optional[str] = Query(None, description="Filter by sub-category"),
    is_available: Optional[bool] = Query(None, description="Filter by availability"),
    is_special: Optional[bool] = Query(None, description="Filter by special status"),
    search: Optional[str] = Query(None, description="Search by item name (partial match)"),
    catalogue_service: CatalogueService = Depends(get_catalogue_service),
    claims: dict = Depends(get_current_business_user),
) -> CatalogueItemsPage:
    business_id = int(claims["business_id"])
    result = catalogue_service.list_catalogue_items_paginated(
        business_id=business_id,
        page=page,
        limit=limit,
        category=category,
        sub_category=sub_category,
        is_available=is_available,
        is_special=is_special,
        search=search,
    )
    return CatalogueItemsPage(
        items=[CatalogueItemResponse(**item) for item in result["items"]],
        pagination=result["pagination"],
    )


@router.get(
    "/catalogue/categories",
    summary="Get Catalogue Categories (Client)",
    description="Retrieve all distinct categories and sub-categories for the authenticated business's catalogue.",
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
async def get_catalogue_categories(
    catalogue_service: CatalogueService = Depends(get_catalogue_service),
    claims: dict = Depends(get_current_business_user),
) -> CatalogueCategoriesResponse:
    business_id = int(claims["business_id"])
    categories = catalogue_service.get_catalogue_categories(business_id)
    return CatalogueCategoriesResponse(categories=categories)


@router.get(
    "/catalogue/{catalogue_id}",
    summary="Get Catalogue Item by ID (Client)",
    description="Retrieve a specific catalogue item for the authenticated business.",
    openapi_extra={
        "responses": {
            200: {
                "description": "Catalogue item retrieved",
                "content": {
                    "application/json": {
                        "example": {
                            "id": 1,
                            "business_id": 10,
                            "business_name": "Ressy Test Kitchen",
                            "item_name": "Margherita Pizza",
                            "price": 15.99,
                            "category": "Pizza",
                            "sub_category": "Classic",
                            "is_available": True,
                            "is_special": False,
                            "option_groups": [
                                {
                                    "id": 12,
                                    "business_id": 10,
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
    response_model=CatalogueItemResponse,
)
async def get_catalogue_item(
    catalogue_id: int,
    catalogue_service: CatalogueService = Depends(get_catalogue_service),
    claims: dict = Depends(get_current_business_user),
) -> CatalogueItemResponse:
    business_id = int(claims["business_id"])
    result = catalogue_service.get_catalogue_item_for_business(business_id, catalogue_id)
    return CatalogueItemResponse(**result)


@router.put(
    "/catalogue/{catalogue_id}",
    summary="Update Catalogue Item (Client)",
    description="Update any fields of a catalogue item for the authenticated business.",
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
                "description": "Catalogue item updated",
                "content": {
                    "application/json": {
                        "example": {
                            "id": 1,
                            "business_id": 10,
                            "item_name": "Margherita Pizza",
                            "price": 17.99,
                            "is_special": True,
                        }
                    }
                },
            }
        },
    },
    response_model=CatalogueItemResponse,
)
async def update_catalogue_item(
    catalogue_id: int,
    payload: dict = Body(..., description="Catalogue item fields to update"),
    catalogue_service: CatalogueService = Depends(get_catalogue_service),
    claims: dict = Depends(get_current_business_user),
) -> CatalogueItemResponse:
    business_id = int(claims["business_id"])
    data = _validate_payload(CatalogueItemUpdate, payload)
    result = catalogue_service.update_catalogue_item_for_business(
        catalogue_id=catalogue_id, business_id=business_id, data=data.model_dump(exclude_unset=True)
    )
    return CatalogueItemResponse(**result)


@router.delete(
    "/catalogue/{catalogue_id}",
    status_code=status.HTTP_200_OK,
    summary="Delete Catalogue Item (Client)",
    description="Delete a catalogue item for the authenticated business.",
    openapi_extra={
        "responses": {
            200: {
                "description": "Catalogue item deleted",
                "content": {
                    "application/json": {"example": {"message": "Catalogue item deleted successfully", "catalogue_id": 1}}
                },
            }
        }
    },
    response_description="Deletion confirmation.",
)
async def delete_catalogue_item(
    catalogue_id: int,
    catalogue_service: CatalogueService = Depends(get_catalogue_service),
    claims: dict = Depends(get_current_business_user),
) -> dict:
    business_id = int(claims["business_id"])
    catalogue_service.delete_catalogue_item_for_business(business_id, catalogue_id)
    return {"message": "Catalogue item deleted successfully", "catalogue_id": catalogue_id}


@router.patch(
    "/catalogue/{catalogue_id}/availability",
    summary="Toggle Catalogue Item Availability (Client)",
    description="Update the availability status of a catalogue item for the authenticated business.",
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
                            "business_id": 10,
                        }
                    }
                },
            }
        },
    },
    response_model=CatalogueItemResponse,
)
async def toggle_availability(
    catalogue_id: int,
    payload: dict = Body(..., description="Availability status"),
    catalogue_service: CatalogueService = Depends(get_catalogue_service),
    claims: dict = Depends(get_current_business_user),
) -> CatalogueItemResponse:
    business_id = int(claims["business_id"])
    data = _validate_payload(ToggleAvailabilityRequest, payload)
    result = catalogue_service.toggle_availability_for_business(business_id, catalogue_id, data.is_available)
    return CatalogueItemResponse(**result)


@router.patch(
    "/catalogue/{catalogue_id}/special",
    summary="Toggle Catalogue Item Special Status (Client)",
    description="Update the special status of a catalogue item for the authenticated business.",
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
                            "business_id": 10,
                        }
                    }
                },
            }
        },
    },
    response_model=CatalogueItemResponse,
)
async def toggle_special(
    catalogue_id: int,
    payload: dict = Body(..., description="Special status"),
    catalogue_service: CatalogueService = Depends(get_catalogue_service),
    claims: dict = Depends(get_current_business_user),
) -> CatalogueItemResponse:
    business_id = int(claims["business_id"])
    data = _validate_payload(ToggleSpecialRequest, payload)
    result = catalogue_service.toggle_special_for_business(business_id, catalogue_id, data.is_special)
    return CatalogueItemResponse(**result)


@router.patch(
    "/catalogue/bulk-availability",
    summary="Bulk Update Catalogue Item Availability (Client)",
    description="Update availability for multiple catalogue items for the authenticated business.",
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {
                "application/json": {
                    "schema": BULK_AVAILABILITY_SCHEMA,
                    "example": {"catalogue_item_ids": [1, 2, 3], "is_available": False},
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
    catalogue_service: CatalogueService = Depends(get_catalogue_service),
    claims: dict = Depends(get_current_business_user),
) -> dict:
    business_id = int(claims["business_id"])
    data = _validate_payload(BulkAvailabilityRequest, payload)
    result = catalogue_service.bulk_update_availability(business_id, data.catalogue_item_ids, data.is_available)
    return result
