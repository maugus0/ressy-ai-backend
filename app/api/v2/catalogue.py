"""
Catalogue management API endpoints.
Admin-only CRUD operations for catalogue items including categories, availability, specials, and bulk operations.
"""

from typing import Optional

from fastapi import APIRouter, Body, Depends, Query, status

from app.middleware.auth_middleware import get_current_admin_user
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
    prefix="/api/v2/admin",
    tags=["Catalogue"],
    dependencies=[Depends(get_current_admin_user)],
)

# JSON Schema for OpenAPI documentation
MENU_CREATE_SCHEMA = CatalogueItemCreate.model_json_schema()
MENU_UPDATE_SCHEMA = CatalogueItemUpdate.model_json_schema()
TOGGLE_AVAILABILITY_SCHEMA = ToggleAvailabilityRequest.model_json_schema()
TOGGLE_SPECIAL_SCHEMA = ToggleSpecialRequest.model_json_schema()
BULK_AVAILABILITY_SCHEMA = BulkAvailabilityRequest.model_json_schema()


# ==================== Admin Catalogue Item APIs ====================


@router.post(
    "/businesss/{business_id}/catalogue",
    status_code=status.HTTP_201_CREATED,
    summary="Create Catalogue Item",
    description="Create a new catalogue item for a specific business. Requires admin authentication.",
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
)
async def create_catalogue_item(
    business_id: int,
    payload: dict = Body(..., description="Catalogue item data"),
    catalogue_service: CatalogueService = Depends(get_catalogue_service),
) -> CatalogueItemResponse:
    """
    Create a new catalogue item for a business.

    **Authentication**: Requires valid admin JWT token.

    **Path Parameters**:
    - `business_id`: ID of the business

    **Request Body**:
    - `item_name` (required): Name of the catalogue item
    - `price` (required): Price (must be positive)
    - `category` (optional): Catalogue category
    - `sub_category` (optional): Catalogue sub-category
    - `item_desc` (optional): Item description
    - `avg_prep_time` (optional): Prep time in minutes
    - `suggested_items` (optional): Array of suggested item IDs
    - `is_available` (optional): Availability status (default: true)
    - `is_special` (optional): Special status (default: false)

    **Returns**: Created catalogue item with all details

    **Errors**:
    - 400: Validation error (e.g., invalid price, suggested items don't exist)
    - 401: Unauthorized (invalid or missing JWT token)
    - 404: Restaurant not found
    """
    data = _validate_payload(CatalogueItemCreate, payload)
    result = catalogue_service.create_catalogue_item(business_id, data.model_dump(exclude_none=False))
    return CatalogueItemResponse(**result)


@router.get(
    "/businesss/{business_id}/catalogue",
    summary="List Catalogue Items",
    description="Retrieve paginated catalogue items for a business with optional filters. Requires admin authentication.",
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
)
async def list_catalogue_items(  # pylint: disable=too-many-arguments,too-many-positional-arguments
    business_id: int,
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    limit: int = Query(50, ge=1, le=100, description="Items per page (max 100)"),
    category: Optional[str] = Query(None, description="Filter by category"),
    sub_category: Optional[str] = Query(None, description="Filter by sub-category"),
    is_available: Optional[bool] = Query(None, description="Filter by availability"),
    is_special: Optional[bool] = Query(None, description="Filter by special status"),
    search: Optional[str] = Query(None, description="Search by item name (partial match)"),
    catalogue_service: CatalogueService = Depends(get_catalogue_service),
) -> CatalogueItemsPage:
    """
    Get paginated list of catalogue items for a business with optional filters.

    **Authentication**: Requires valid admin JWT token.

    **Path Parameters**:
    - `business_id`: ID of the business

    **Query Parameters**:
    - `page`: Page number (default: 1)
    - `limit`: Items per page (default: 50, max: 100)
    - `category`: Filter by category
    - `sub_category`: Filter by sub-category
    - `is_available`: Filter by availability (true/false)
    - `is_special`: Filter by special status (true/false)
    - `search`: Search term for item name (partial match)

    **Returns**: Paginated list of catalogue items with metadata

    **Errors**:
    - 401: Unauthorized (invalid or missing JWT token)
    - 404: Restaurant not found
    """
    # pylint: disable=duplicate-code
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
    "/catalogue/{catalogue_id}",
    summary="Get Catalogue Item by ID",
    description="Retrieve detailed information about a specific catalogue item. Requires admin authentication.",
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
                            "item_desc": "Fresh mozzarella, tomato sauce, and basil",
                            "avg_prep_time": 20,
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
)
async def get_catalogue_item(
    catalogue_id: int,
    catalogue_service: CatalogueService = Depends(get_catalogue_service),
) -> CatalogueItemResponse:
    """
    Get a specific catalogue item by ID.

    **Authentication**: Requires valid admin JWT token.

    **Path Parameters**:
    - `catalogue_id`: ID of the catalogue item

    **Returns**: Catalogue item details including business name

    **Errors**:
    - 401: Unauthorized (invalid or missing JWT token)
    - 404: Catalogue item not found
    """
    result = catalogue_service.get_catalogue_item(catalogue_id)
    return CatalogueItemResponse(**result)


@router.put(
    "/catalogue/{catalogue_id}",
    summary="Update Catalogue Item",
    description="Update any fields of a catalogue item. All fields are optional. Requires admin authentication.",
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
        },
        "responses": {
            200: {
                "description": "Catalogue item updated",
                "content": {
                    "application/json": {
                        "example": {
                            "id": 1,
                            "business_id": 10,
                            "business_name": "Ressy Test Kitchen",
                            "item_name": "Margherita Pizza",
                            "price": 17.99,
                            "category": "Pizza",
                            "sub_category": "Classic",
                            "item_desc": "Updated description",
                            "avg_prep_time": 20,
                            "is_available": True,
                            "is_special": True,
                        }
                    }
                },
            }
        },
    },
)
async def update_catalogue_item(
    catalogue_id: int,
    payload: dict = Body(..., description="Catalogue item fields to update"),
    catalogue_service: CatalogueService = Depends(get_catalogue_service),
) -> CatalogueItemResponse:
    """
    Update a catalogue item. Only provided fields will be updated.

    **Authentication**: Requires valid admin JWT token.

    **Path Parameters**:
    - `catalogue_id`: ID of the catalogue item

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

    **Returns**: Updated catalogue item with all details

    **Errors**:
    - 400: Validation error (e.g., invalid price, suggested items don't exist)
    - 401: Unauthorized (invalid or missing JWT token)
    - 404: Catalogue item not found
    """
    data = _validate_payload(CatalogueItemUpdate, payload)
    result = catalogue_service.update_catalogue_item(catalogue_id, data.model_dump(exclude_unset=True))
    return CatalogueItemResponse(**result)


@router.delete(
    "/catalogue/{catalogue_id}",
    status_code=status.HTTP_200_OK,
    summary="Delete Catalogue Item",
    description="Delete a catalogue item and remove it from suggested items of other items. Requires admin authentication.",
)
async def delete_catalogue_item(
    catalogue_id: int,
    catalogue_service: CatalogueService = Depends(get_catalogue_service),
) -> dict:
    """
    Delete a catalogue item from the database.

    This will also remove the item from the suggested_items array of any other catalogue items.

    **Authentication**: Requires valid admin JWT token.

    **Path Parameters**:
    - `catalogue_id`: ID of the catalogue item to delete

    **Returns**: Success message

    **Errors**:
    - 401: Unauthorized (invalid or missing JWT token)
    - 404: Catalogue item not found
    """
    catalogue_service.delete_catalogue_item(catalogue_id)
    return {"message": "Catalogue item deleted successfully", "catalogue_id": catalogue_id}


@router.patch(
    "/catalogue/{catalogue_id}/availability",
    summary="Toggle Catalogue Item Availability",
    description="Update the availability status of a catalogue item. Requires admin authentication.",
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
    catalogue_id: int,
    payload: dict = Body(..., description="Availability status"),
    catalogue_service: CatalogueService = Depends(get_catalogue_service),
) -> CatalogueItemResponse:
    """
    Toggle the availability status of a catalogue item.

    **Authentication**: Requires valid admin JWT token.

    **Path Parameters**:
    - `catalogue_id`: ID of the catalogue item

    **Request Body**:
    - `is_available`: New availability status (true/false)

    **Returns**: Updated catalogue item with new availability status

    **Errors**:
    - 401: Unauthorized (invalid or missing JWT token)
    - 404: Catalogue item not found
    """
    data = _validate_payload(ToggleAvailabilityRequest, payload)
    result = catalogue_service.toggle_availability(catalogue_id, data.is_available)
    return CatalogueItemResponse(**result)


@router.patch(
    "/catalogue/{catalogue_id}/special",
    summary="Toggle Catalogue Item Special Status",
    description="Update the special status of a catalogue item. Requires admin authentication.",
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
    catalogue_id: int,
    payload: dict = Body(..., description="Special status"),
    catalogue_service: CatalogueService = Depends(get_catalogue_service),
) -> CatalogueItemResponse:
    """
    Toggle the special status of a catalogue item.

    **Authentication**: Requires valid admin JWT token.

    **Path Parameters**:
    - `catalogue_id`: ID of the catalogue item

    **Request Body**:
    - `is_special`: New special status (true/false)

    **Returns**: Updated catalogue item with new special status

    **Errors**:
    - 401: Unauthorized (invalid or missing JWT token)
    - 404: Catalogue item not found
    """
    data = _validate_payload(ToggleSpecialRequest, payload)
    result = catalogue_service.toggle_special(catalogue_id, data.is_special)
    return CatalogueItemResponse(**result)


@router.patch(
    "/businesss/{business_id}/catalogue/bulk-availability",
    summary="Bulk Update Catalogue Item Availability",
    description="Update availability for multiple catalogue items at once. Requires admin authentication.",
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {
                "application/json": {
                    "schema": BULK_AVAILABILITY_SCHEMA,
                    "example": {
                        "catalogue_item_ids": [1, 2, 3, 4],
                        "is_available": False,
                    },
                }
            },
        }
    },
)
async def bulk_update_availability(
    business_id: int,
    payload: dict = Body(..., description="Bulk update data"),
    catalogue_service: CatalogueService = Depends(get_catalogue_service),
) -> dict:
    """
    Bulk update availability for multiple catalogue items.

    **Authentication**: Requires valid admin JWT token.

    **Path Parameters**:
    - `business_id`: ID of the business

    **Request Body**:
    - `catalogue_item_ids`: Array of catalogue item IDs to update (at least 1 required)
    - `is_available`: New availability status for all items (true/false)

    **Returns**: Number of items updated

    **Errors**:
    - 400: Validation error (items don't belong to business, empty array)
    - 401: Unauthorized (invalid or missing JWT token)
    - 404: Restaurant not found
    """
    data = _validate_payload(BulkAvailabilityRequest, payload)
    result = catalogue_service.bulk_update_availability(business_id, data.catalogue_item_ids, data.is_available)
    return result


@router.get(
    "/businesss/{business_id}/catalogue/categories",
    summary="Get Catalogue Categories",
    description=(
        "Retrieve all distinct categories and sub-categories for a business's catalogue. " "Requires admin authentication."
    ),
)
async def get_catalogue_categories(
    business_id: int,
    catalogue_service: CatalogueService = Depends(get_catalogue_service),
) -> CatalogueCategoriesResponse:
    """
    Get all distinct categories and sub-categories for a business's catalogue.

    **Authentication**: Requires valid admin JWT token.

    **Path Parameters**:
    - `business_id`: ID of the business

    **Returns**: Dictionary with categories as keys and arrays of sub-categories as values

    **Example Response**:
    ```json
    {
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
    categories = catalogue_service.get_catalogue_categories(business_id)
    return CatalogueCategoriesResponse(categories=categories)
