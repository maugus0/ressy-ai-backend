from datetime import datetime
from typing import Any

from fastapi import APIRouter, Body, Depends, Query, status
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.middleware.auth_middleware import get_current_admin_user
from app.models.common_models import PaginationResponse
from app.services.restaurant_service import RestaurantService
from app.utils.payload_validator import validate_payload


def _strip_or_none(value: str | None) -> str | None:
    """Trim whitespace and normalize blank strings to None."""
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


class CreateRestaurantRequest(BaseModel):
    """Payload for creating a restaurant."""

    name: str = Field(..., max_length=255, description="Restaurant name (required)")
    address: str | None = Field(None, description="Street address")
    phone_number: str | None = Field(None, max_length=20, description="Public phone number")
    twilio_phone_number: str | None = Field(None, max_length=20, description="Twilio phone number for routing calls")
    twilio_details: dict | None = Field(None, description="Twilio configuration JSON")
    deepgram_details: dict | None = Field(None, description="Deepgram configuration JSON")
    open_table_details: dict | None = Field(None, description="OpenTable integration details JSON")
    forward_minutes: int | None = Field(0, ge=0, description="Forward booking window in minutes")
    backward_minutes: int | None = Field(0, ge=0, description="Backward booking window in minutes")
    is_credit_card_required_for_reservation: bool | None = Field(
        False, description="Require credit card for reservations"
    )
    opening_time: str | None = Field(
        None, pattern=r"^\d{2}:\d{2}:\d{2}$", description="Opening time in HH:MM:SS (24h) format"
    )
    closing_time: str | None = Field(
        None, pattern=r"^\d{2}:\d{2}:\d{2}$", description="Closing time in HH:MM:SS (24h) format"
    )
    model_config = ConfigDict(extra="ignore")

    @field_validator("name")
    @classmethod
    def name_not_empty(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("name is required")
        return cleaned

    @field_validator("address", "phone_number", "twilio_phone_number", mode="before")
    @classmethod
    def trim_strings(cls, value: Any) -> Any:  # noqa: ANN401 - pydantic hook allows Any
        if isinstance(value, str):
            return _strip_or_none(value)
        return value


class UpdateRestaurantRequest(BaseModel):
    """Payload for updating a restaurant (all fields optional)."""

    name: str | None = Field(None, max_length=255, description="Restaurant name")
    address: str | None = Field(None, description="Street address")
    phone_number: str | None = Field(None, max_length=20, description="Public phone number")
    twilio_phone_number: str | None = Field(None, max_length=20, description="Twilio phone number for routing calls")
    twilio_details: dict | None = Field(None, description="Twilio configuration JSON")
    deepgram_details: dict | None = Field(None, description="Deepgram configuration JSON")
    open_table_details: dict | None = Field(None, description="OpenTable integration details JSON")
    forward_minutes: int | None = Field(None, ge=0, description="Forward booking window in minutes")
    backward_minutes: int | None = Field(None, ge=0, description="Backward booking window in minutes")
    is_credit_card_required_for_reservation: bool | None = Field(
        None, description="Require credit card for reservations"
    )
    opening_time: str | None = Field(
        None, pattern=r"^\d{2}:\d{2}:\d{2}$", description="Opening time in HH:MM:SS (24h) format"
    )
    closing_time: str | None = Field(
        None, pattern=r"^\d{2}:\d{2}:\d{2}$", description="Closing time in HH:MM:SS (24h) format"
    )
    model_config = ConfigDict(extra="ignore")

    @field_validator("name")
    @classmethod
    def name_not_empty(cls, value: str | None) -> str | None:
        if value is None:
            return value
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("name cannot be empty")
        return cleaned

    @field_validator("address", "phone_number", "twilio_phone_number", mode="before")
    @classmethod
    def trim_optional_strings(cls, value: Any) -> Any:  # noqa: ANN401 - pydantic hook allows Any
        if isinstance(value, str):
            return _strip_or_none(value)
        return value


class RestaurantResponse(BaseModel):
    """Restaurant response shape."""

    id: int
    name: str
    address: str | None = None
    phone_number: str | None = None
    twilio_phone_number: str | None = None
    twilio_details: dict | None = None
    deepgram_details: dict | None = None
    open_table_details: dict | None = None
    forward_minutes: int | None = None
    backward_minutes: int | None = None
    is_credit_card_required_for_reservation: bool | None = None
    opening_time: str | None = None
    closing_time: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    model_config = ConfigDict(extra="ignore")


class RestaurantListResponse(BaseModel):
    """Paginated restaurant listing."""

    items: list[RestaurantResponse]
    pagination: PaginationResponse
    model_config = ConfigDict(extra="ignore")


class RestaurantStatsResponse(BaseModel):
    """Aggregated statistics for a restaurant."""

    total_menu_items: int = Field(..., description="Total menu items")
    available_menu_items: int = Field(..., description="Menu items currently available")
    special_items_count: int = Field(..., description="Menu items marked as special")
    total_faqs: int = Field(..., description="FAQ entries for this restaurant")
    total_administrators: int = Field(..., description="CRM administrators assigned")
    total_calls: int = Field(..., description="Total calls logged")
    total_minute_usage: float = Field(..., description="Total call duration (minutes)")
    model_config = ConfigDict(extra="ignore")


class MessageResponse(BaseModel):
    """Generic message wrapper."""

    message: str
    model_config = ConfigDict(extra="ignore")


def get_restaurant_service() -> RestaurantService:
    """Dependency injector for RestaurantService."""
    return RestaurantService()


router = APIRouter(
    prefix="/api/v1/restaurants",
    tags=["Restaurants"],
    dependencies=[Depends(get_current_admin_user)],
)


@router.post(
    "/",
    status_code=status.HTTP_201_CREATED,
    summary="Create Restaurant",
    description="Create a new restaurant for the Admin CRM. Admin access only.",
    response_model=RestaurantResponse,
    response_description="Created restaurant with IDs and integration metadata.",
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {
                "application/json": {
                    "schema": CreateRestaurantRequest.model_json_schema(),
                    "example": {
                        "name": "Ressy Test Kitchen",
                        "address": "123 Main St, Springfield",
                        "phone_number": "+15551234567",
                        "twilio_phone_number": "+15557654321",
                        "forward_minutes": 45,
                        "backward_minutes": 15,
                        "is_credit_card_required_for_reservation": True,
                        "twilio_details": {"workspace_sid": "WSxxxx", "phone_sid": "PNxxxx"},
                        "deepgram_details": {"project_id": "dg-project-1"},
                        "open_table_details": {"rid": "99999"},
                        "opening_time": "09:00:00",
                        "closing_time": "22:00:00",
                    },
                }
            },
        }
    },
)
async def create_restaurant(
    payload: dict | None = Body(None, description="Restaurant payload"),
    restaurant_service: RestaurantService = Depends(get_restaurant_service),
):
    """
    Create a new restaurant and return the full record.

    **Authentication**: Admin access required (Admin CRM token)

    **Notes**:
    - Phone numbers are validated for length and format
    - JSON fields must be valid objects (not strings)
    - Missing minute fields default to 0; credit card requirement defaults to `false`
    """
    data = validate_payload(CreateRestaurantRequest, payload)
    # Use exclude_unset to allow explicit nulls to flow through for clearing values
    return restaurant_service.create_restaurant(data.model_dump(exclude_unset=True))


@router.get(
    "/",
    summary="List Restaurants",
    description="Paginated restaurant listing for the Admin CRM with search and credit-card filter.",
    response_model=RestaurantListResponse,
    response_description="Paginated restaurants with metadata.",
    openapi_extra={
        "responses": {
            200: {
                "description": "Restaurants retrieved",
                "content": {
                    "application/json": {
                        "example": {
                            "items": [
                                {
                                    "id": 10,
                                    "name": "Ressy Test Kitchen",
                                    "address": "123 Main St, Springfield",
                                    "phone_number": "+15551234567",
                                    "twilio_phone_number": "+15557654321",
                                    "forward_minutes": 45,
                                    "backward_minutes": 15,
                                    "is_credit_card_required_for_reservation": True,
                                    "twilio_details": {"workspace_sid": "WSxxxx"},
                                    "deepgram_details": {"project_id": "dg-project-1"},
                                    "open_table_details": {"rid": "99999"},
                                    "opening_time": "09:00:00",
                                    "closing_time": "22:00:00",
                                    "created_at": "2024-02-01T10:00:00Z",
                                    "updated_at": "2024-02-02T10:00:00Z",
                                }
                            ],
                            "pagination": {"page": 1, "limit": 20, "total": 1, "pages": 1},
                        }
                    }
                },
            }
        }
    },
)
async def list_restaurants(
    page: int = Query(1, ge=1, description="Page number (1-based)"),
    limit: int = Query(20, ge=1, le=100, description="Items per page (max 100)"),
    search: str | None = Query(None, description="Search by restaurant name"),
    is_credit_card_required: bool | None = Query(
        None, description="Filter by restaurants that require a credit card for reservations"
    ),
    restaurant_service: RestaurantService = Depends(get_restaurant_service),
):
    """
    List restaurants with pagination, search, and filtering.

    **Authentication**: Admin access required

    **Query Parameters**:
    - `page`: Page number (1-based)
    - `limit`: Items per page (max 100)
    - `search`: Optional fuzzy search on restaurant name
    - `is_credit_card_required`: Optional filter for credit-card requirement
    """
    return restaurant_service.list_restaurants(
        page=page, limit=limit, search=search, is_credit_card_required=is_credit_card_required
    )


@router.get(
    "/{restaurant_id}",
    summary="Get Restaurant Details",
    description="Fetch a single restaurant by ID including integration metadata. Admin access only.",
    response_model=RestaurantResponse,
    response_description="Full restaurant record for the given ID.",
    openapi_extra={
        "responses": {
            200: {
                "description": "Restaurant retrieved",
                "content": {
                    "application/json": {
                        "example": {
                            "id": 10,
                            "name": "Ressy Test Kitchen",
                            "address": "123 Main St, Springfield",
                            "phone_number": "+15551234567",
                            "twilio_phone_number": "+15557654321",
                            "forward_minutes": 45,
                            "backward_minutes": 15,
                            "is_credit_card_required_for_reservation": True,
                            "twilio_details": {"workspace_sid": "WSxxxx"},
                            "deepgram_details": {"project_id": "dg-project-1"},
                            "open_table_details": {"rid": "99999"},
                            "opening_time": "09:00:00",
                            "closing_time": "22:00:00",
                            "created_at": "2024-02-01T10:00:00Z",
                            "updated_at": "2024-02-02T10:00:00Z",
                        }
                    }
                },
            }
        }
    },
)
async def get_restaurant(
    restaurant_id: int,
    restaurant_service: RestaurantService = Depends(get_restaurant_service),
):
    """
    Get restaurant details by ID.

    **Authentication**: Admin access required
    """
    return restaurant_service.get_restaurant(restaurant_id)


@router.put(
    "/{restaurant_id}",
    summary="Update Restaurant",
    description="Update restaurant metadata, contact info, and integration settings. Admin access only.",
    response_model=RestaurantResponse,
    response_description="Updated restaurant record.",
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {
                "application/json": {
                    "schema": UpdateRestaurantRequest.model_json_schema(),
                    "example": {
                        "name": "Ressy Test Kitchen - Updated",
                        "address": "456 Elm St, Springfield",
                        "forward_minutes": 60,
                        "is_credit_card_required_for_reservation": False,
                        "open_table_details": {"rid": "12345", "api_key": "secret"},
                        "opening_time": "10:00:00",
                        "closing_time": "23:00:00",
                    },
                }
            },
        }
    },
)
async def update_restaurant(
    restaurant_id: int,
    payload: dict | None = Body(None, description="Restaurant fields to update"),
    restaurant_service: RestaurantService = Depends(get_restaurant_service),
):
    """
    Update a restaurant.

    **Authentication**: Admin access required

    **Notes**:
    - Only provided fields are updated
    - Validation mirrors creation (phone formats, JSON objects, non-negative minutes)
    """
    data = validate_payload(UpdateRestaurantRequest, payload)
    return restaurant_service.update_restaurant(restaurant_id, data.model_dump(exclude_unset=True))


@router.delete(
    "/{restaurant_id}",
    summary="Delete Restaurant",
    description="Permanently delete a restaurant. Admin access only.",
    response_model=MessageResponse,
    response_description="Confirmation message on successful deletion.",
)
async def delete_restaurant(
    restaurant_id: int,
    restaurant_service: RestaurantService = Depends(get_restaurant_service),
):
    """
    Delete a restaurant by ID.

    **Authentication**: Admin access required
    """
    return restaurant_service.delete_restaurant(restaurant_id)


@router.get(
    "/{restaurant_id}/stats",
    summary="Restaurant Statistics",
    description="Retrieve aggregated counts for menus, FAQs, admins, calls, and minute usage. Admin access only.",
    response_model=RestaurantStatsResponse,
    response_description="Aggregate statistics for the restaurant.",
    openapi_extra={
        "responses": {
            200: {
                "description": "Statistics retrieved",
                "content": {
                    "application/json": {
                        "example": {
                            "total_menu_items": 120,
                            "available_menu_items": 100,
                            "special_items_count": 15,
                            "total_faqs": 8,
                            "total_administrators": 5,
                            "total_calls": 230,
                            "total_minute_usage": 540.5,
                        }
                    }
                },
            }
        }
    },
)
async def get_restaurant_statistics(
    restaurant_id: int,
    restaurant_service: RestaurantService = Depends(get_restaurant_service),
):
    """
    Get restaurant analytics rollups.

    **Authentication**: Admin access required
    """
    return restaurant_service.get_restaurant_statistics(restaurant_id)
