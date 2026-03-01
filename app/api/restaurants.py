from datetime import datetime
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Body, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.middleware.auth_middleware import get_current_admin_user
from app.models.common_models import PaginationResponse
from app.services.kill_switch_event_service import (
    emit_kill_switch_bulk_summary,
    emit_kill_switch_toggled,
    emit_kill_switch_toggled_bulk_for_restaurants,
)
from app.services.restaurant_service import RestaurantService
from app.utils.payload_validator import validate_payload


def _strip_or_none(value: str | None) -> str | None:
    """Trim whitespace and normalize blank strings to None."""
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


class DayHours(BaseModel):
    """Operating hours for a single day."""

    open: str | None = Field(None, pattern=r"^\d{2}:\d{2}:\d{2}$", description="Opening time in HH:MM:SS format")
    close: str | None = Field(None, pattern=r"^\d{2}:\d{2}:\d{2}$", description="Closing time in HH:MM:SS format")
    is_closed: bool = Field(False, description="Whether the restaurant is closed on this day")
    is_24_hours: bool = Field(False, description="Whether open 24 hours (when true, open/close times are ignored)")
    model_config = ConfigDict(extra="ignore")

    @model_validator(mode="after")
    def require_open_close_when_not_closed_or_24h(self) -> "DayHours":
        """When is_closed=False and is_24_hours=False, if either open or close is set, both must be set."""
        if not self.is_closed and not self.is_24_hours:
            if (self.open is None) != (self.close is None):
                raise ValueError(
                    "When is_closed and is_24_hours are both false, open and close must both be provided or both omitted"
                )
        return self


class OperatingHours(BaseModel):
    """Weekly operating hours for a restaurant."""

    monday: DayHours = Field(default_factory=DayHours, description="Monday hours")
    tuesday: DayHours = Field(default_factory=DayHours, description="Tuesday hours")
    wednesday: DayHours = Field(default_factory=DayHours, description="Wednesday hours")
    thursday: DayHours = Field(default_factory=DayHours, description="Thursday hours")
    friday: DayHours = Field(default_factory=DayHours, description="Friday hours")
    saturday: DayHours = Field(default_factory=DayHours, description="Saturday hours")
    sunday: DayHours = Field(default_factory=DayHours, description="Sunday hours")
    model_config = ConfigDict(extra="ignore")


class SMSRedirectConfig(BaseModel):
    """Configuration for SMS redirect capability."""

    enabled: bool = Field(False, description="Enable SMS redirect")
    redirect_url: str | None = Field(None, max_length=512, description="URL to include in SMS")
    redirect_message: str | None = Field(None, description="Custom SMS message template")
    model_config = ConfigDict(extra="ignore")

    @field_validator("redirect_url")
    @classmethod
    def validate_url(cls, v: str | None) -> str | None:
        # Normalize input: trim whitespace and treat blank strings as None
        cleaned = _strip_or_none(v)
        if cleaned is None:
            return None
        # Validate scheme on the normalized, non-empty URL
        if not cleaned.startswith(("http://", "https://")):
            raise ValueError("URL must start with http:// or https://")
        return cleaned


class SMSRedirectConfigResponse(BaseModel):
    """SMS redirect configuration in responses."""

    enabled: bool
    redirect_url: str | None
    redirect_message: str | None
    model_config = ConfigDict(extra="ignore")


class RestaurantFeaturesCreate(BaseModel):
    """Feature flags for restaurant creation (defaults to enabled)."""

    orders_enabled: bool = Field(True, description="Enable pickup order handling")
    reservations_enabled: bool = Field(True, description="Enable reservation handling")
    faqs_enabled: bool = Field(True, description="Enable FAQ handling")
    orders_sms_redirect: SMSRedirectConfig | None = Field(None, description="SMS redirect config for orders")
    reservations_sms_redirect: SMSRedirectConfig | None = Field(
        None, description="SMS redirect config for reservations"
    )
    model_config = ConfigDict(extra="ignore")


class RestaurantFeaturesUpdate(BaseModel):
    """Feature flags for restaurant updates (all optional)."""

    orders_enabled: bool | None = Field(None, description="Enable pickup order handling")
    reservations_enabled: bool | None = Field(None, description="Enable reservation handling")
    faqs_enabled: bool | None = Field(None, description="Enable FAQ handling")
    orders_sms_redirect: SMSRedirectConfig | None = Field(None, description="SMS redirect config for orders")
    reservations_sms_redirect: SMSRedirectConfig | None = Field(
        None, description="SMS redirect config for reservations"
    )
    model_config = ConfigDict(extra="ignore")


class RestaurantFeaturesResponse(BaseModel):
    """Feature flags returned in restaurant responses."""

    orders_enabled: bool
    reservations_enabled: bool
    faqs_enabled: bool
    orders_sms_redirect: SMSRedirectConfigResponse = Field(
        default_factory=lambda: SMSRedirectConfigResponse(enabled=False, redirect_url=None, redirect_message=None)
    )
    reservations_sms_redirect: SMSRedirectConfigResponse = Field(
        default_factory=lambda: SMSRedirectConfigResponse(enabled=False, redirect_url=None, redirect_message=None)
    )
    model_config = ConfigDict(extra="ignore")


class CreateRestaurantRequest(BaseModel):
    """Payload for creating a restaurant."""

    name: str = Field(..., max_length=255, description="Restaurant name (required)")
    address: str | None = Field(None, description="Street address")
    phone_number: str | None = Field(None, max_length=20, description="Public phone number (E.164 format)")
    twilio_phone_number: str | None = Field(
        None, max_length=20, description="Twilio phone number for routing calls (E.164 format)"
    )
    forward_escalations: bool | None = Field(False, description="Forward escalations to a live phone number")
    escalation_phone_number: str | None = Field(
        None, max_length=20, description="Phone number to forward escalation calls (E.164 format)"
    )
    twilio_details: dict | None = Field(None, description="Twilio configuration JSON")
    deepgram_details: dict | None = Field(None, description="Deepgram configuration JSON")
    open_table_details: dict | None = Field(None, description="OpenTable integration details JSON")
    forward_minutes: int | None = Field(0, ge=0, description="Forward booking window in minutes")
    backward_minutes: int | None = Field(0, ge=0, description="Backward booking window in minutes")
    is_credit_card_required_for_reservation: bool | None = Field(
        False, description="Require credit card for reservations"
    )
    operating_hours: OperatingHours | None = Field(
        None,
        description=(
            "Weekly operating hours. Defaults to 09:00-22:00 daily for any days not provided. "
            "When is_closed=true for a day, open/close times are ignored and stored as NULL."
        ),
    )
    timezone: str | None = Field(None, description="Restaurant timezone (IANA name, e.g. America/Vancouver)")
    reservation_seating_capacity: int | None = Field(
        None, ge=1, le=1000, description="Total seating capacity for reservations"
    )
    reservation_advance_days: int | None = Field(
        None, ge=1, le=365, description="Maximum days in advance for reservations"
    )
    features: RestaurantFeaturesCreate | None = Field(
        None, description="Feature flags for the voice agent (defaults to enabled)"
    )
    model_config = ConfigDict(extra="ignore")

    @field_validator("name")
    @classmethod
    def name_not_empty(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("name is required")
        return cleaned

    @field_validator(
        "address", "phone_number", "twilio_phone_number", "escalation_phone_number", "timezone", mode="before"
    )
    @classmethod
    def trim_strings(cls, value: Any) -> Any:  # noqa: ANN401 - pydantic hook allows Any
        if isinstance(value, str):
            return _strip_or_none(value)
        return value


class UpdateRestaurantRequest(BaseModel):
    """Payload for updating a restaurant (all fields optional)."""

    name: str | None = Field(None, max_length=255, description="Restaurant name")
    address: str | None = Field(None, description="Street address")
    phone_number: str | None = Field(None, max_length=20, description="Public phone number (E.164 format)")
    twilio_phone_number: str | None = Field(
        None, max_length=20, description="Twilio phone number for routing calls (E.164 format)"
    )
    forward_escalations: bool | None = Field(None, description="Forward escalations to a live phone number")
    escalation_phone_number: str | None = Field(
        None, max_length=20, description="Phone number to forward escalation calls (E.164 format)"
    )
    twilio_details: dict | None = Field(None, description="Twilio configuration JSON")
    deepgram_details: dict | None = Field(None, description="Deepgram configuration JSON")
    open_table_details: dict | None = Field(None, description="OpenTable integration details JSON")
    forward_minutes: int | None = Field(None, ge=0, description="Forward booking window in minutes")
    backward_minutes: int | None = Field(None, ge=0, description="Backward booking window in minutes")
    is_credit_card_required_for_reservation: bool | None = Field(
        None, description="Require credit card for reservations"
    )
    operating_hours: OperatingHours | None = Field(
        None,
        description=(
            "Weekly operating hours. Partial update supported: only provided days are updated, "
            "other days remain unchanged. When is_closed=true for a day, open/close times are cleared."
        ),
    )
    timezone: str | None = Field(None, description="Restaurant timezone (IANA name, e.g. America/Vancouver)")
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

    @field_validator(
        "address", "phone_number", "twilio_phone_number", "escalation_phone_number", "timezone", mode="before"
    )
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
    forward_escalations: bool | None = None
    escalation_phone_number: str | None = None
    kill_switch_enabled: bool = False
    kill_switch_can_redirect: bool = False
    kill_switch_blockers: list[str] = Field(default_factory=list)
    twilio_details: dict | None = None
    deepgram_details: dict | None = None
    open_table_details: dict | None = None
    forward_minutes: int | None = None
    backward_minutes: int | None = None
    is_credit_card_required_for_reservation: bool | None = None
    operating_hours: OperatingHours | None = None
    timezone: str | None = None
    reservation_seating_capacity: int | None = None
    reservation_advance_days: int | None = None
    features: RestaurantFeaturesResponse | None = None
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


class KillSwitchUpdateRequest(BaseModel):
    """Payload for kill-switch toggle operations."""

    enabled: bool = Field(..., description="Enable or disable kill switch")
    model_config = ConfigDict(extra="ignore")


class KillSwitchSkippedRestaurant(BaseModel):
    """Restaurant skipped during bulk kill-switch enable."""

    restaurant_id: int
    restaurant_name: str | None = None
    kill_switch_blockers: list[str] = Field(default_factory=list)
    model_config = ConfigDict(extra="ignore")


class KillSwitchBulkResponse(BaseModel):
    """Bulk kill-switch update result."""

    enabled: bool
    targeted_count: int
    eligible_count: int
    updated_count: int
    skipped_count: int
    skipped: list[KillSwitchSkippedRestaurant] = Field(default_factory=list)
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
                        "forward_escalations": True,
                        "escalation_phone_number": "+15550001111",
                        "twilio_details": {"workspace_sid": "WSxxxx", "phone_sid": "PNxxxx"},
                        "deepgram_details": {"project_id": "dg-project-1"},
                        "open_table_details": {"rid": "99999"},
                        "operating_hours": {
                            "monday": {"open": "09:00:00", "close": "22:00:00", "is_closed": False},
                            "tuesday": {"open": "09:00:00", "close": "22:00:00", "is_closed": False},
                            "wednesday": {"open": "09:00:00", "close": "22:00:00", "is_closed": False},
                            "thursday": {"open": "09:00:00", "close": "22:00:00", "is_closed": False},
                            "friday": {"open": "09:00:00", "close": "23:00:00", "is_closed": False},
                            "saturday": {"open": "10:00:00", "close": "23:00:00", "is_closed": False},
                            "sunday": {"open": "10:00:00", "close": "21:00:00", "is_closed": False},
                        },
                        "timezone": "America/Vancouver",
                        "reservation_seating_capacity": 50,
                        "reservation_advance_days": 30,
                        "features": {
                            "orders_enabled": True,
                            "reservations_enabled": True,
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
    - `forward_escalations` requires `escalation_phone_number`
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
                                    "forward_escalations": True,
                                    "escalation_phone_number": "+15550001111",
                                    "twilio_details": {"workspace_sid": "WSxxxx"},
                                    "deepgram_details": {"project_id": "dg-project-1"},
                                    "open_table_details": {"rid": "99999"},
                                    "operating_hours": {
                                        "monday": {"open": "09:00:00", "close": "22:00:00", "is_closed": False},
                                        "tuesday": {"open": "09:00:00", "close": "22:00:00", "is_closed": False},
                                        "wednesday": {"open": "09:00:00", "close": "22:00:00", "is_closed": False},
                                        "thursday": {"open": "09:00:00", "close": "22:00:00", "is_closed": False},
                                        "friday": {"open": "09:00:00", "close": "22:00:00", "is_closed": False},
                                        "saturday": {"open": "09:00:00", "close": "22:00:00", "is_closed": False},
                                        "sunday": {"open": "09:00:00", "close": "22:00:00", "is_closed": False},
                                    },
                                    "timezone": "America/Vancouver",
                                    "reservation_seating_capacity": 50,
                                    "reservation_advance_days": 30,
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
    orders_enabled: bool | None = Query(None, description="Filter by pickup orders feature flag"),
    reservations_enabled: bool | None = Query(None, description="Filter by reservations feature flag"),
    faqs_enabled: bool | None = Query(None, description="Filter by FAQs feature flag"),
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
    - `orders_enabled`: Optional filter for pickup orders flag
    - `reservations_enabled`: Optional filter for reservations flag
    - `faqs_enabled`: Optional filter for FAQs flag
    """
    return restaurant_service.list_restaurants(
        page=page,
        limit=limit,
        search=search,
        is_credit_card_required=is_credit_card_required,
        orders_enabled=orders_enabled,
        reservations_enabled=reservations_enabled,
        faqs_enabled=faqs_enabled,
    )


@router.patch(
    "/{restaurant_id}/kill-switch",
    summary="Set Kill Switch",
    description="Enable or disable the kill switch for a specific restaurant. Admin access only.",
    response_model=RestaurantResponse,
    response_description="Updated restaurant with kill-switch state.",
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {
                "application/json": {
                    "schema": KillSwitchUpdateRequest.model_json_schema(),
                    "example": {"enabled": True},
                }
            },
        },
        "responses": {
            200: {
                "description": "Kill switch updated",
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
async def set_restaurant_kill_switch(
    restaurant_id: int,
    background_tasks: BackgroundTasks,
    payload: dict = Body(..., description="Kill-switch toggle payload"),
    restaurant_service: RestaurantService = Depends(get_restaurant_service),
    claims: dict = Depends(get_current_admin_user),
):
    data = validate_payload(KillSwitchUpdateRequest, payload)
    before = restaurant_service.get_restaurant(restaurant_id)
    result = restaurant_service.set_restaurant_kill_switch(restaurant_id, data.enabled)

    previous_enabled = bool(before.get("kill_switch_enabled"))
    current_enabled = bool(result.get("kill_switch_enabled"))
    if previous_enabled != current_enabled:
        background_tasks.add_task(
            emit_kill_switch_toggled,
            restaurant_id=int(result["id"]),
            restaurant_name=result.get("name"),
            enabled=current_enabled,
            previous_enabled=previous_enabled,
            actor_type="admin",
            actor_id=claims.get("sub"),
            actor_email=claims.get("email"),
            source="admin_dashboard",
        )

    return result


@router.patch(
    "/kill-switch/all",
    summary="Set Kill Switch For All Restaurants",
    description=(
        "Bulk enable or disable kill switch for all restaurants. "
        "When enabling, restaurants without forwarding readiness are skipped and reported."
    ),
    response_model=KillSwitchBulkResponse,
    response_description="Bulk operation summary.",
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {
                "application/json": {
                    "schema": KillSwitchUpdateRequest.model_json_schema(),
                    "example": {"enabled": True},
                }
            },
        },
        "responses": {
            200: {
                "description": "Bulk operation completed",
                "content": {
                    "application/json": {
                        "examples": {
                            "enable_with_skips": {
                                "summary": "Enable for all, skip invalid restaurants",
                                "value": {
                                    "enabled": True,
                                    "targeted_count": 3,
                                    "eligible_count": 2,
                                    "updated_count": 2,
                                    "skipped_count": 1,
                                    "skipped": [
                                        {
                                            "restaurant_id": 44,
                                            "restaurant_name": "Downtown Kitchen",
                                            "kill_switch_blockers": ["escalation_phone_number_missing"],
                                        }
                                    ],
                                },
                            },
                            "disable_all": {
                                "summary": "Disable for all restaurants",
                                "value": {
                                    "enabled": False,
                                    "targeted_count": 3,
                                    "eligible_count": 3,
                                    "updated_count": 3,
                                    "skipped_count": 0,
                                    "skipped": [],
                                },
                            },
                        }
                    }
                },
            }
        },
    },
)
async def set_all_restaurants_kill_switch(
    background_tasks: BackgroundTasks,
    payload: dict = Body(..., description="Kill-switch bulk payload"),
    restaurant_service: RestaurantService = Depends(get_restaurant_service),
    claims: dict = Depends(get_current_admin_user),
):
    data = validate_payload(KillSwitchUpdateRequest, payload)
    result = restaurant_service.set_all_restaurants_kill_switch(data.enabled)
    changed_restaurants = result.pop("_changed_restaurants", [])

    if result.get("updated_count", 0) > 0:
        if changed_restaurants:
            background_tasks.add_task(
                emit_kill_switch_toggled_bulk_for_restaurants,
                changed_restaurants=changed_restaurants,
                enabled=bool(data.enabled),
                actor_type="admin",
                actor_id=claims.get("sub"),
                actor_email=claims.get("email"),
                source="admin_dashboard",
                include_admin_sse=False,
            )

    background_tasks.add_task(
        emit_kill_switch_bulk_summary,
        enabled=bool(result.get("enabled")),
        targeted_count=int(result.get("targeted_count", 0)),
        eligible_count=int(result.get("eligible_count", 0)),
        updated_count=int(result.get("updated_count", 0)),
        skipped_count=int(result.get("skipped_count", 0)),
        skipped=result.get("skipped", []),
        actor_type="admin",
        actor_id=claims.get("sub"),
        actor_email=claims.get("email"),
        source="admin_dashboard",
    )

    return result


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
                            "forward_escalations": True,
                            "escalation_phone_number": "+15550001111",
                            "twilio_details": {"workspace_sid": "WSxxxx"},
                            "deepgram_details": {"project_id": "dg-project-1"},
                            "open_table_details": {"rid": "99999"},
                            "operating_hours": {
                                "monday": {"open": "09:00:00", "close": "22:00:00", "is_closed": False},
                                "tuesday": {"open": "09:00:00", "close": "22:00:00", "is_closed": False},
                                "wednesday": {"open": "09:00:00", "close": "22:00:00", "is_closed": False},
                                "thursday": {"open": "09:00:00", "close": "22:00:00", "is_closed": False},
                                "friday": {"open": "09:00:00", "close": "22:00:00", "is_closed": False},
                                "saturday": {"open": "09:00:00", "close": "22:00:00", "is_closed": False},
                                "sunday": {"open": "09:00:00", "close": "22:00:00", "is_closed": False},
                            },
                            "timezone": "America/Vancouver",
                            "reservation_seating_capacity": 50,
                            "reservation_advance_days": 30,
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
                        "forward_escalations": True,
                        "escalation_phone_number": "+15550001111",
                        "open_table_details": {"rid": "12345", "api_key": "secret"},
                        "operating_hours": {
                            "monday": {"open": "10:00:00", "close": "23:00:00", "is_closed": False},
                            "tuesday": {"open": "10:00:00", "close": "23:00:00", "is_closed": False},
                            "wednesday": {"open": "10:00:00", "close": "23:00:00", "is_closed": False},
                            "thursday": {"open": "10:00:00", "close": "23:00:00", "is_closed": False},
                            "friday": {"open": "10:00:00", "close": "00:00:00", "is_closed": False},
                            "saturday": {"open": "10:00:00", "close": "00:00:00", "is_closed": False},
                            "sunday": {"open": None, "close": None, "is_closed": True},
                        },
                        "timezone": "America/Vancouver",
                        "reservation_seating_capacity": 75,
                        "reservation_advance_days": 60,
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
    - `forward_escalations` requires `escalation_phone_number`
    - **Agent Capabilities**: `features` controls voice agent capabilities. FAQs cannot be disabled.
    - **SMS Redirect**: When `orders_sms_redirect.enabled` or `reservations_sms_redirect.enabled` is true,
      the corresponding direct capability (orders_enabled/reservations_enabled) must be false. A valid URL
      is required when SMS redirect is enabled. The agent sends an SMS with the link instead of processing
      the request directly.
    """
    data = validate_payload(UpdateRestaurantRequest, payload)
    # BUSINESS RULE: FAQs must always be enabled.
    # Menu questions require FAQ functionality to work properly with orders.
    # See: [FE/BE] Agent Answers FAQ Questions When FAQ Flag is Disabled
    # See: [FE/BE] Agent Cannot Provide Menu Information When Orders Enabled but FAQ Disabled
    if data.features is not None and data.features.faqs_enabled is False:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="FAQ Agent Capability cannot be disabled.",
        )
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
