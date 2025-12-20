from datetime import datetime
from typing import Any

from fastapi import APIRouter, Body, Depends, status
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.api.restaurants import get_restaurant_service
from app.middleware.auth_middleware import get_current_restaurant_user
from app.utils.payload_validator import validate_payload


def _strip_or_none(value: str | None) -> str | None:
    """Trim whitespace and normalize blank strings to None."""
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


class ClientRestaurantResponse(BaseModel):
    """Client restaurant response - excludes sensitive integration details."""

    id: int
    name: str
    address: str | None = None
    phone_number: str | None = None
    twilio_phone_number: str | None = None
    forward_minutes: int | None = None
    backward_minutes: int | None = None
    is_credit_card_required_for_reservation: bool | None = None
    opening_time: str | None = None
    closing_time: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    model_config = ConfigDict(extra="ignore")


class ClientUpdateRestaurantRequest(BaseModel):
    """Client payload for updating a restaurant - excludes sensitive fields."""

    name: str | None = Field(None, max_length=255, description="Restaurant name")
    address: str | None = Field(None, description="Street address")
    phone_number: str | None = Field(None, max_length=20, description="Public phone number")
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

    @field_validator("address", "phone_number", mode="before")
    @classmethod
    def trim_optional_strings(cls, value: Any) -> Any:  # noqa: ANN401 - pydantic hook allows Any
        if isinstance(value, str):
            return _strip_or_none(value)
        return value


router = APIRouter(
    prefix="/api/v1/client",
    tags=["Restaurants"],
    dependencies=[Depends(get_current_restaurant_user)],
)


@router.get(
    "/restaurant",
    summary="Get restaurant (Client)",
    response_model=ClientRestaurantResponse,
    description="Return the authenticated restaurant details. Sensitive integration details are excluded.",
    response_description="Restaurant details scoped to the authenticated restaurant.",
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
                            "is_credit_card_required_for_reservation": False,
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
    service=Depends(get_restaurant_service),
    claims: dict = Depends(get_current_restaurant_user),
):
    restaurant_id = int(claims["restaurant_id"])
    result = service.get_restaurant(restaurant_id)
    return ClientRestaurantResponse(**result)


@router.put(
    "/restaurant",
    status_code=status.HTTP_200_OK,
    summary="Update restaurant (Client)",
    description="Update the authenticated restaurant. All fields are optional; server-side validation still applies. Sensitive integration fields cannot be updated via this endpoint.",
    response_model=ClientRestaurantResponse,
    response_description="Updated restaurant details.",
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {
                "application/json": {
                    "schema": ClientUpdateRestaurantRequest.model_json_schema(),
                    "example": {"name": "Updated Restaurant", "forward_minutes": 30},
                }
            },
        },
        "responses": {
            200: {
                "description": "Restaurant updated",
                "content": {
                    "application/json": {
                        "example": {
                            "id": 10,
                            "name": "Updated Restaurant",
                            "address": "123 Main St, Springfield",
                            "phone_number": "+15551234567",
                            "twilio_phone_number": "+15557654321",
                            "forward_minutes": 30,
                            "backward_minutes": 15,
                            "is_credit_card_required_for_reservation": False,
                            "opening_time": "09:00:00",
                            "closing_time": "22:00:00",
                            "created_at": "2024-02-01T10:00:00Z",
                            "updated_at": "2024-02-02T10:00:00Z",
                        }
                    }
                },
            }
        },
    },
)
async def update_restaurant(
    payload: dict = Body(..., description="Restaurant fields to update"),
    service=Depends(get_restaurant_service),
    claims: dict = Depends(get_current_restaurant_user),
):
    restaurant_id = int(claims["restaurant_id"])
    data = validate_payload(ClientUpdateRestaurantRequest, payload)
    result = service.update_restaurant(restaurant_id, data.model_dump(exclude_unset=True))
    return ClientRestaurantResponse(**result)
