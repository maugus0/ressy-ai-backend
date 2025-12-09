"""
In-House Reservation API routes for handling reservation operations.
"""

from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.services.reservation_service import ReservationService

router = APIRouter()
reservation_service = ReservationService()


# Pydantic models for request validation
class LockSlotRequest(BaseModel):
    party_size: int = Field(..., gt=0, description="Party size")
    date_time: str = Field(..., description="Date and time in ISO format")
    reservation_attribute: str = Field(default="default", description="Reservation attribute")


class CreateReservationRequest(BaseModel):
    reservation_token: str = Field(..., description="Token from slot lock")
    name: str = Field(..., min_length=1, description="Full name")
    phone_number: str = Field(..., min_length=1, description="Phone number")
    email_address: Optional[str] = Field(None, description="Email address (optional)")
    special_request: Optional[str] = Field(None, description="Special request (optional)")


class FinalizeReservationRequest(BaseModel):
    confirmation_number: Optional[str] = Field(None, description="Optional confirmation number override")


# ---------- GET AVAILABILITY ----------
@router.get(
    "/availability/{restaurant_id}",
    summary="Get Table Availability",
    description="Retrieve available time slots for reservations at a restaurant. Returns available booking times within the specified time window. Used by the voice agent to check availability before creating reservations.",
    response_description="List of available time slots with booking information.",
)
async def get_availability(
    restaurant_id: int,
    start_date_time: str = Query(..., description="Start date and time in ISO format (e.g., 2024-01-15T18:00:00)"),
    forward_minutes: Optional[int] = Query(None, description="Forward booking window in minutes from start_date_time (default: restaurant's forward booking limit)"),
    backward_minutes: Optional[int] = Query(None, description="Backward booking window in minutes from start_date_time (default: restaurant's backward booking limit)"),
    party_size: Optional[int] = Query(None, gt=0, description="Filter availability by party size (optional)"),
):
    """
    Get table availability for a restaurant.
    
    **Authentication**: Public (no authentication required)
    
    **Path Parameters**:
    - restaurant_id: Unique identifier of the restaurant
    
    **Query Parameters**:
    - start_date_time: Starting date and time for availability check (required, ISO format)
    - forward_minutes: How many minutes forward to check availability (optional)
    - backward_minutes: How many minutes backward to check availability (optional)
    - party_size: Filter by specific party size (optional)
    
    **Response**: List of available time slots with:
    - Available dates and times
    - Table capacity information
    - Booking constraints
    """
    try:
        result = reservation_service.get_availability(
            restaurant_id=restaurant_id,
            start_date_time=start_date_time,
            forward_minutes=forward_minutes,
            backward_minutes=backward_minutes,
            party_size=party_size,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching availability: {str(e)}")


# ---------- LOCK SLOT ----------
@router.post(
    "/booking/{restaurant_id}/slot_locks",
    summary="Lock Booking Slot",
    description="Temporarily lock a booking slot to prevent double-booking while the customer completes their reservation. Returns a reservation token that must be used within a short time window to create the reservation.",
    response_description="Reservation token and locked slot information. The token must be used to create the reservation.",
)
async def lock_slot(restaurant_id: int, request: LockSlotRequest):
    """
    Lock a booking slot for a reservation.
    
    **Authentication**: Public (no authentication required)
    
    **Path Parameters**:
    - restaurant_id: Unique identifier of the restaurant
    
    **Request Body**:
    - party_size: Number of guests (required, must be > 0)
    - date_time: Desired reservation date and time in ISO format (required)
    - reservation_attribute: Table type or special requirement (default: "default")
    
    **Response**: 
    - reservation_token: Token to use when creating the reservation (expires after a short time)
    - Locked slot information including date, time, and party size
    
    **Note**: The slot lock expires after a short period. You must create the reservation using the token before it expires.
    """
    try:
        result = reservation_service.lock_slot(
            restaurant_id=restaurant_id,
            party_size=request.party_size,
            date_time=request.date_time,
            reservation_attribute=request.reservation_attribute,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error locking slot: {str(e)}")


# ---------- CREATE RESERVATION ----------
@router.post(
    "/booking/{restaurant_id}/reservations",
    summary="Create Reservation",
    description="Create a new reservation using a valid reservation token from slot lock. The reservation is created in 'pending' status and must be finalized by the restaurant. Used by the voice agent when customers make reservations.",
    response_description="Created reservation object with reservation ID, confirmation number (if assigned), and status.",
)
async def create_reservation(restaurant_id: int, request: CreateReservationRequest):
    """
    Create a new reservation.
    
    **Authentication**: Public (no authentication required)
    
    **Path Parameters**:
    - restaurant_id: Unique identifier of the restaurant
    
    **Request Body**:
    - reservation_token: Token obtained from slot lock endpoint (required)
    - name: Customer's full name (required)
    - phone_number: Customer's phone number (required)
    - email_address: Customer's email address (optional)
    - special_request: Special requests or notes (optional)
    
    **Response**: 
    - reservation_id: Unique identifier of the created reservation
    - confirmation_number: Confirmation number (may be null if not yet finalized)
    - status: Reservation status (initially "pending")
    - All reservation details including date, time, party size, and customer information
    
    **Note**: The reservation starts in "pending" status and must be finalized by the restaurant through the dashboard.
    """
    try:
        result = reservation_service.create_reservation(
            restaurant_id=restaurant_id,
            reservation_token=request.reservation_token,
            name=request.name,
            phone_number=request.phone_number,
            email_address=request.email_address,
            special_request=request.special_request,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creating reservation: {str(e)}")


# ---------- GET RESERVATION ----------
@router.get(
    "/{reservation_id}",
    summary="Get Reservation Details",
    description="Retrieve detailed information for a specific reservation by ID. Includes customer information, booking details, status, and confirmation number.",
    response_description="Complete reservation object with all details including customer info, booking time, status, and confirmation number.",
)
async def get_reservation(reservation_id: int):
    """
    Get detailed information for a specific reservation.
    
    **Authentication**: Public (no authentication required)
    
    **Path Parameters**:
    - reservation_id: Unique identifier of the reservation
    
    **Response**: Complete reservation object including:
    - Reservation ID and confirmation number
    - Customer information (name, phone, email)
    - Booking details (date, time, party size)
    - Status (pending, confirmed, cancelled, completed)
    - Special requests
    - Created and updated timestamps
    """
    try:
        result = reservation_service.get_reservation(reservation_id=reservation_id)
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching reservation: {str(e)}")


# ---------- CANCEL RESERVATION ----------
@router.put(
    "/{reservation_id}/cancel",
    summary="Cancel Reservation",
    description="Cancel an existing reservation. Changes the reservation status to 'cancelled'. Can be called by customers or restaurant staff.",
    response_description="Updated reservation object with status changed to 'cancelled'.",
)
async def cancel_reservation(reservation_id: int):
    """
    Cancel a reservation.
    
    **Authentication**: Public (no authentication required)
    
    **Path Parameters**:
    - reservation_id: Unique identifier of the reservation to cancel
    
    **Response**: Updated reservation object with:
    - Status changed to "cancelled"
    - Cancellation timestamp
    - All other reservation details preserved
    
    **Note**: Once cancelled, a reservation cannot be reactivated. A new reservation must be created if needed.
    """
    try:
        result = reservation_service.cancel_reservation(reservation_id=reservation_id)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error cancelling reservation: {str(e)}")
