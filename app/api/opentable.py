"""
OpenTable API routes for handling reservation operations.
"""

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.middleware.auth_middleware import get_current_active_user
from app.services.opentable_service import OpenTableService

router = APIRouter()
opentable_service = OpenTableService()


# Pydantic models for request validation
class LockSlotRequest(BaseModel):
    party_size: int = Field(..., gt=0, description="Party size")
    date_time: str = Field(..., description="Date and time in format yyyy-mm-ddThh:ss")
    reservation_attribute: str = Field(default="default", description="Reservation attribute")
    experience: Optional[Dict[str, Any]] = Field(None, description="Experience details")
    dining_area_id: Optional[int] = Field(None, description="Dining area ID")
    environment: Optional[str] = Field(None, description="Environment (e.g., Indoor, Outdoor)")


class CreateReservationRequest(BaseModel):
    reservation_token: str = Field(..., description="Token from slot lock")
    first_name: str = Field(..., min_length=1, description="First name")
    last_name: str = Field(..., min_length=1, description="Last name")
    email_address: str = Field(..., description="Email address")
    phone: Dict[str, str] = Field(..., description="Phone number with number, country_code, phone_type")
    reservation_attribute: str = Field(default="default", description="Reservation attribute")
    special_request: Optional[str] = Field(None, description="Special request")
    credit_card: Optional[Dict[str, str]] = Field(None, description="Credit card with token and last4")
    restaurant_email_marketing_opt_in: Optional[str] = Field(None, description="Marketing opt-in")
    dining_area_id: Optional[str] = Field(None, description="Dining area ID")
    environment: Optional[str] = Field(None, description="Environment")
    experience: Optional[Dict[str, Any]] = Field(None, description="Experience details")


class UpdateReservationRequest(BaseModel):
    party_size: Optional[int] = Field(None, gt=0, description="Party size")
    date_time: Optional[str] = Field(None, description="New date and time in format yyyy-mm-ddThh:ss")
    reservation_attribute: Optional[str] = Field(None, description="Reservation attribute")
    reservation_token: Optional[str] = Field(None, description="Reservation token")
    special_request: Optional[str] = Field(None, description="Special request")
    experience: Optional[Dict[str, Any]] = Field(None, description="Experience details")


# ---------- GET AVAILABILITY ----------
@router.get(
    "/availability/{restaurant_id}/{rid}",
    summary="Get OpenTable Availability",
    description="Retrieve available time slots for reservations through the OpenTable API integration. Returns available booking times from OpenTable's system. Requires both internal restaurant ID and OpenTable restaurant ID (rid).",
    response_description="List of available time slots from OpenTable with booking information, table types, and pricing options.",
)
async def get_availability(
    restaurant_id: int,
    rid: int,
    start_date_time: str = Query(..., description="Start date and time in format yyyy-mm-ddThh:ss (e.g., 2024-01-15T18:00:00)"),
    forward_minutes: Optional[int] = Query(None, description="Forward booking window in minutes from start_date_time"),
    backward_minutes: Optional[int] = Query(None, description="Backward booking window in minutes from start_date_time"),
    party_size: Optional[int] = Query(None, gt=0, description="Filter availability by party size"),
    require_attributes: Optional[str] = Query(None, description="Comma-separated list of required table attributes (e.g., 'outdoor,window')"),
    include_credit_card_results: Optional[bool] = Query(None, description="Include availability that requires credit card on file"),
    include_experiences: Optional[bool] = Query(None, description="Include special dining experiences in results"),
    current_user: dict = Depends(get_current_active_user),
):
    """
    Get table availability for a restaurant from OpenTable API.
    
    **Authentication**: Required (authenticated user)
    
    **Path Parameters**:
    - restaurant_id: Internal restaurant ID in our system
    - rid: OpenTable restaurant ID (OpenTable's identifier for the restaurant)
    
    **Query Parameters**:
    - start_date_time: Starting date and time for availability check (required, format: yyyy-mm-ddThh:ss)
    - forward_minutes: How many minutes forward to check availability
    - backward_minutes: How many minutes backward to check availability
    - party_size: Filter by specific party size
    - require_attributes: Filter by table attributes (comma-separated, e.g., "outdoor,window")
    - include_credit_card_results: Include slots requiring credit card on file
    - include_experiences: Include special dining experiences
    
    **Response**: List of available time slots from OpenTable including:
    - Available dates and times
    - Table capacity and attributes
    - Pricing information
    - Experience options (if requested)
    - Credit card requirements (if applicable)
    """
    try:
        result = opentable_service.get_availability(
            restaurant_id=restaurant_id,
            rid=rid,
            start_date_time=start_date_time,
            forward_minutes=forward_minutes,
            backward_minutes=backward_minutes,
            party_size=party_size,
            require_attributes=require_attributes,
            include_credit_card_results=include_credit_card_results,
            include_experiences=include_experiences,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching availability: {str(e)}")


# ---------- LOCK SLOT ----------
@router.post(
    "/booking/{restaurant_id}/{rid}/slot_locks",
    summary="Lock OpenTable Booking Slot",
    description="Temporarily lock a booking slot through OpenTable to prevent double-booking while the customer completes their reservation. Returns a reservation token that must be used within OpenTable's time window to create the reservation.",
    response_description="Reservation token from OpenTable and locked slot information. The token must be used to create the reservation.",
)
async def lock_slot(
    restaurant_id: int, rid: int, request: LockSlotRequest, current_user: dict = Depends(get_current_active_user)
):
    """
    Lock a booking slot for a reservation through OpenTable.
    
    **Authentication**: Required (authenticated user)
    
    **Path Parameters**:
    - restaurant_id: Internal restaurant ID in our system
    - rid: OpenTable restaurant ID
    
    **Request Body**:
    - party_size: Number of guests (required, must be > 0)
    - date_time: Desired reservation date and time in format yyyy-mm-ddThh:ss (required)
    - reservation_attribute: Table type or special requirement (default: "default")
    - experience: Optional experience details dictionary
    - dining_area_id: Optional specific dining area ID
    - environment: Optional environment preference (e.g., "Indoor", "Outdoor")
    
    **Response**: 
    - reservation_token: OpenTable reservation token (expires after OpenTable's time limit)
    - Locked slot information including date, time, party size, and table details
    
    **Note**: The slot lock expires after OpenTable's configured time period. You must create the reservation using the token before it expires.
    """
    try:
        result = opentable_service.lock_slot(
            restaurant_id=restaurant_id,
            rid=rid,
            party_size=request.party_size,
            date_time=request.date_time,
            reservation_attribute=request.reservation_attribute,
            experience=request.experience,
            dining_area_id=request.dining_area_id,
            environment=request.environment,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error locking slot: {str(e)}")


# ---------- CREATE RESERVATION ----------
@router.post(
    "/booking/{restaurant_id}/{rid}/reservations",
    summary="Create OpenTable Reservation",
    description="Create a new reservation through the OpenTable API integration using a valid reservation token from slot lock. The reservation is created directly in OpenTable's system and synced to our database.",
    response_description="Created reservation object with OpenTable confirmation number, reservation ID, and all booking details.",
)
async def create_reservation(
    restaurant_id: int,
    rid: int,
    request: CreateReservationRequest,
    current_user: dict = Depends(get_current_active_user),
):
    """
    Create a new reservation through OpenTable.
    
    **Authentication**: Required (authenticated user)
    
    **Path Parameters**:
    - restaurant_id: Internal restaurant ID in our system
    - rid: OpenTable restaurant ID
    
    **Request Body**:
    - reservation_token: Token obtained from OpenTable slot lock endpoint (required)
    - first_name: Customer's first name (required)
    - last_name: Customer's last name (required)
    - email_address: Customer's email address (required)
    - phone: Phone number object with number, country_code, and phone_type (required)
    - reservation_attribute: Table type or special requirement (default: "default")
    - special_request: Special requests or notes (optional)
    - credit_card: Credit card information with token and last4 (optional, for restaurants requiring it)
    - restaurant_email_marketing_opt_in: Marketing opt-in preference (optional)
    - dining_area_id: Specific dining area ID (optional)
    - environment: Environment preference (optional)
    - experience: Experience details (optional)
    
    **Response**: 
    - confirmation_number: OpenTable confirmation number
    - reservation_id: Internal reservation ID
    - All reservation details including date, time, party size, customer information
    - Status and booking confirmation
    
    **Note**: The reservation is created directly in OpenTable's system and automatically synced to our database.
    """
    try:
        result = opentable_service.create_reservation(
            restaurant_id=restaurant_id,
            rid=rid,
            reservation_token=request.reservation_token,
            first_name=request.first_name,
            last_name=request.last_name,
            email_address=request.email_address,
            phone=request.phone,
            reservation_attribute=request.reservation_attribute,
            special_request=request.special_request,
            credit_card=request.credit_card,
            restaurant_email_marketing_opt_in=request.restaurant_email_marketing_opt_in,
            dining_area_id=request.dining_area_id,
            environment=request.environment,
            experience=request.experience,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creating reservation: {str(e)}")


# ---------- UPDATE RESERVATION ----------
@router.put(
    "/booking/{restaurant_id}/{rid}/reservations/{confirmation_id}",
    summary="Update OpenTable Reservation",
    description="Update an existing reservation in OpenTable's system. Can modify party size, date/time, special requests, or experience details. Changes are synced to both OpenTable and our database.",
    response_description="Updated reservation object with modified fields and updated timestamps.",
)
async def update_reservation(
    restaurant_id: int,
    rid: int,
    confirmation_id: int,
    request: UpdateReservationRequest,
    current_user: dict = Depends(get_current_active_user),
):
    """
    Update an existing reservation in OpenTable.
    
    **Authentication**: Required (authenticated user)
    
    **Path Parameters**:
    - restaurant_id: Internal restaurant ID in our system
    - rid: OpenTable restaurant ID
    - confirmation_id: OpenTable confirmation number of the reservation to update
    
    **Request Body** (all fields optional, only include fields to update):
    - party_size: New party size
    - date_time: New date and time in format yyyy-mm-ddThh:ss
    - reservation_attribute: Updated table type or requirement
    - reservation_token: New reservation token if changing time slot
    - special_request: Updated special requests
    - experience: Updated experience details
    
    **Response**: Updated reservation object with:
    - All modified fields
    - Updated timestamps
    - Confirmation number (unchanged)
    - Current status
    
    **Note**: Updates are made in OpenTable's system first, then synced to our database. Some changes may require a new slot lock if the time slot is changing.
    """
    try:
        result = opentable_service.update_reservation(
            restaurant_id=restaurant_id,
            rid=rid,
            confirmation_id=confirmation_id,
            party_size=request.party_size,
            date_time=request.date_time,
            reservation_attribute=request.reservation_attribute,
            reservation_token=request.reservation_token,
            special_request=request.special_request,
            experience=request.experience,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error updating reservation: {str(e)}")


# ---------- CANCEL RESERVATION ----------
@router.put(
    "/booking/{restaurant_id}/{rid}/reservations/{confirmation_id}/cancel",
    summary="Cancel OpenTable Reservation",
    description="Cancel an existing reservation in OpenTable's system. The cancellation is processed through OpenTable and synced to our database. Once cancelled, the reservation cannot be reactivated.",
    response_description="Cancelled reservation object with status updated to 'cancelled' and cancellation timestamp.",
)
async def cancel_reservation(
    restaurant_id: int, rid: int, confirmation_id: int, current_user: dict = Depends(get_current_active_user)
):
    """
    Cancel a reservation in OpenTable.
    
    **Authentication**: Required (authenticated user)
    
    **Path Parameters**:
    - restaurant_id: Internal restaurant ID in our system
    - rid: OpenTable restaurant ID
    - confirmation_id: OpenTable confirmation number of the reservation to cancel
    
    **Response**: Updated reservation object with:
    - Status changed to "cancelled"
    - Cancellation timestamp
    - All other reservation details preserved
    - Cancellation confirmation from OpenTable
    
    **Note**: Once cancelled, a reservation cannot be reactivated. The cancellation is processed in OpenTable's system and automatically synced to our database. A new reservation must be created if needed.
    """
    try:
        result = opentable_service.cancel_reservation(
            restaurant_id=restaurant_id, rid=rid, confirmation_id=confirmation_id
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error cancelling reservation: {str(e)}")
