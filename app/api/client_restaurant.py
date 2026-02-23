from datetime import datetime
from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.api.restaurants import (
    OperatingHours,
    RestaurantFeaturesResponse,
    RestaurantFeaturesUpdate,
    get_restaurant_service,
)
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
    forward_escalations: bool | None = None
    escalation_phone_number: str | None = None
    kill_switch_enabled: bool = False
    kill_switch_can_redirect: bool = False
    kill_switch_blockers: list[str] = Field(default_factory=list)
    forward_minutes: int | None = None
    backward_minutes: int | None = None
    is_credit_card_required_for_reservation: bool | None = None
    operating_hours: OperatingHours | None = None
    reservation_seating_capacity: int | None = None
    reservation_advance_days: int | None = None
    timezone: str | None = None
    features: RestaurantFeaturesResponse | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    model_config = ConfigDict(extra="ignore")


class ClientUpdateRestaurantRequest(BaseModel):
    """Client payload for updating a restaurant - excludes sensitive fields."""

    name: str | None = Field(None, max_length=255, description="Restaurant name")
    address: str | None = Field(None, description="Street address")
    phone_number: str | None = Field(None, max_length=20, description="Public phone number")
    forward_escalations: bool | None = Field(None, description="Forward escalations to a live phone number")
    escalation_phone_number: str | None = Field(
        None, max_length=20, description="Phone number to forward escalation calls"
    )
    forward_minutes: int | None = Field(None, ge=0, description="Forward booking window in minutes")
    backward_minutes: int | None = Field(None, ge=0, description="Backward booking window in minutes")
    is_credit_card_required_for_reservation: bool | None = Field(
        None, description="Require credit card for reservations"
    )
    operating_hours: OperatingHours | None = Field(None, description="Weekly operating hours")
    reservation_seating_capacity: int | None = Field(
        None, ge=1, le=1000, description="Total seating capacity for reservations"
    )
    reservation_advance_days: int | None = Field(
        None, ge=1, le=365, description="Maximum days in advance for reservations"
    )
    features: RestaurantFeaturesUpdate | None = Field(None, description="Feature flags for the voice agent")
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

    @field_validator("address", "phone_number", "escalation_phone_number", mode="before")
    @classmethod
    def trim_optional_strings(cls, value: Any) -> Any:  # noqa: ANN401 - pydantic hook allows Any
        if isinstance(value, str):
            return _strip_or_none(value)
        return value


class ClientKillSwitchUpdateRequest(BaseModel):
    """Client payload for kill-switch toggle."""

    enabled: bool = Field(..., description="Enable or disable kill switch")
    model_config = ConfigDict(extra="ignore")


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
                            "forward_escalations": True,
                            "escalation_phone_number": "+15550001111",
                            "forward_minutes": 45,
                            "backward_minutes": 15,
                            "is_credit_card_required_for_reservation": False,
                            "operating_hours": {
                                "monday": {"open": "09:00:00", "close": "22:00:00", "is_closed": False},
                                "tuesday": {"open": "09:00:00", "close": "22:00:00", "is_closed": False},
                                "wednesday": {"open": "09:00:00", "close": "22:00:00", "is_closed": False},
                                "thursday": {"open": "09:00:00", "close": "22:00:00", "is_closed": False},
                                "friday": {"open": "09:00:00", "close": "22:00:00", "is_closed": False},
                                "saturday": {"open": "09:00:00", "close": "22:00:00", "is_closed": False},
                                "sunday": {"open": "09:00:00", "close": "22:00:00", "is_closed": False},
                            },
                            "reservation_seating_capacity": 50,
                            "reservation_advance_days": 30,
                            "timezone": "America/Vancouver",
                            "features": {
                                "orders_enabled": True,
                                "reservations_enabled": True,
                                "faqs_enabled": True,
                                "orders_sms_redirect": {
                                    "enabled": False,
                                    "redirect_url": None,
                                    "redirect_message": None,
                                },
                                "reservations_sms_redirect": {
                                    "enabled": False,
                                    "redirect_url": None,
                                    "redirect_message": None,
                                },
                            },
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
    description="Update the authenticated restaurant. All fields are optional; server-side validation still applies. Sensitive integration fields cannot be updated via this endpoint. `forward_escalations` requires `escalation_phone_number`. Agent capabilities (features) include SMS Redirect: when enabled, the agent sends an SMS with a link instead of processing orders/reservations directly. SMS redirect requires the corresponding direct capability to be disabled and a valid URL.",
    response_model=ClientRestaurantResponse,
    response_description="Updated restaurant details.",
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {
                "application/json": {
                    "schema": ClientUpdateRestaurantRequest.model_json_schema(),
                    "example": {
                        "name": "Updated Restaurant",
                        "forward_minutes": 30,
                        "forward_escalations": True,
                        "escalation_phone_number": "+15550001111",
                        "reservation_seating_capacity": 60,
                        "reservation_advance_days": 14,
                        "features": {
                            "orders_enabled": True,
                            "reservations_enabled": False,
                            "faqs_enabled": True,
                            "orders_sms_redirect": {"enabled": False, "redirect_url": None, "redirect_message": None},
                            "reservations_sms_redirect": {
                                "enabled": False,
                                "redirect_url": None,
                                "redirect_message": None,
                            },
                        },
                    },
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
                            "forward_escalations": True,
                            "escalation_phone_number": "+15550001111",
                            "forward_minutes": 30,
                            "backward_minutes": 15,
                            "is_credit_card_required_for_reservation": False,
                            "operating_hours": {
                                "monday": {"open": "09:00:00", "close": "22:00:00", "is_closed": False},
                                "tuesday": {"open": "09:00:00", "close": "22:00:00", "is_closed": False},
                                "wednesday": {"open": "09:00:00", "close": "22:00:00", "is_closed": False},
                                "thursday": {"open": "09:00:00", "close": "22:00:00", "is_closed": False},
                                "friday": {"open": "09:00:00", "close": "22:00:00", "is_closed": False},
                                "saturday": {"open": "09:00:00", "close": "22:00:00", "is_closed": False},
                                "sunday": {"open": "09:00:00", "close": "22:00:00", "is_closed": False},
                            },
                            "reservation_seating_capacity": 60,
                            "reservation_advance_days": 14,
                            "timezone": "America/Vancouver",
                            "features": {
                                "orders_enabled": True,
                                "reservations_enabled": False,
                                "faqs_enabled": True,
                                "orders_sms_redirect": {
                                    "enabled": False,
                                    "redirect_url": None,
                                    "redirect_message": None,
                                },
                                "reservations_sms_redirect": {
                                    "enabled": False,
                                    "redirect_url": None,
                                    "redirect_message": None,
                                },
                            },
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
    # BUSINESS RULE: FAQs must always be enabled.
    # Menu questions require FAQ functionality to work properly with orders.
    # See: [FE/BE] Agent Answers FAQ Questions When FAQ Flag is Disabled
    # See: [FE/BE] Agent Cannot Provide Menu Information When Orders Enabled but FAQ Disabled
    if data.features is not None and data.features.faqs_enabled is False:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="FAQ Agent Capability cannot be disabled.",
        )
    result = service.update_restaurant(restaurant_id, data.model_dump(exclude_unset=True))
    return ClientRestaurantResponse(**result)


@router.patch(
    "/restaurant/kill-switch",
    status_code=status.HTTP_200_OK,
    summary="Set Kill Switch (Client)",
    description="Enable or disable kill switch for the authenticated restaurant.",
    response_model=ClientRestaurantResponse,
    response_description="Updated restaurant details.",
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {
                "application/json": {
                    "schema": ClientKillSwitchUpdateRequest.model_json_schema(),
                    "example": {"enabled": True},
                }
            },
        },
        "responses": {
            200: {
                "description": "Kill switch updated for authenticated restaurant",
                "content": {
                    "application/json": {
                        "example": {
                            "id": 10,
                            "name": "Ressy Test Kitchen",
                            "forward_escalations": True,
                            "escalation_phone_number": "+15550001111",
                            "kill_switch_enabled": True,
                            "kill_switch_can_redirect": True,
                            "kill_switch_blockers": [],
                        }
                    }
                },
            },
            400: {
                "description": "Kill switch cannot be enabled because forwarding is misconfigured",
                "content": {
                    "application/json": {
                        "example": {
                            "detail": {
                                "message": "Cannot enable kill switch until escalation forwarding is fully configured",
                                "kill_switch_blockers": [
                                    "forward_escalations_disabled",
                                    "escalation_phone_number_missing",
                                ],
                            }
                        }
                    }
                },
            },
        },
    },
)
async def set_kill_switch(
    payload: dict = Body(..., description="Kill-switch toggle payload"),
    service=Depends(get_restaurant_service),
    claims: dict = Depends(get_current_restaurant_user),
):
    restaurant_id = int(claims["restaurant_id"])
    data = validate_payload(ClientKillSwitchUpdateRequest, payload)
    result = service.set_restaurant_kill_switch(restaurant_id, data.enabled)
    return ClientRestaurantResponse(**result)
