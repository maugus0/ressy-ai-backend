"""
In-House Reservation API routes for handling reservation operations.
"""
from fastapi import APIRouter, HTTPException, Query
from typing import Optional
from app.services.reservation_service import ReservationService
from pydantic import BaseModel, Field

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
    summary="Get table availability for a restaurant"
)
async def get_availability(
    restaurant_id: int,
    start_date_time: str = Query(..., description="Start date and time in ISO format"),
    forward_minutes: Optional[int] = Query(None, description="Forward booking window in minutes"),
    backward_minutes: Optional[int] = Query(None, description="Backward booking window in minutes"),
    party_size: Optional[int] = Query(None, gt=0, description="Party size")
):
    """
    Get table availability for a restaurant.

    - **restaurant_id**: Restaurant ID
    - **start_date_time**: Start date and time
    - **forward_minutes**: Forward booking window
    - **backward_minutes**: Backward booking window
    - **party_size**: Party size
    """
    try:
        result = reservation_service.get_availability(
            restaurant_id=restaurant_id,
            start_date_time=start_date_time,
            forward_minutes=forward_minutes,
            backward_minutes=backward_minutes,
            party_size=party_size
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching availability: {str(e)}")


# ---------- LOCK SLOT ----------
@router.post(
    "/booking/{restaurant_id}/slot_locks",
    summary="Lock a booking slot"
)
async def lock_slot(
    restaurant_id: int,
    request: LockSlotRequest
):
    """
    Lock a booking slot for a reservation.

    - **restaurant_id**: Restaurant ID
    - **request**: Slot lock request body
    """
    try:
        result = reservation_service.lock_slot(
            restaurant_id=restaurant_id,
            party_size=request.party_size,
            date_time=request.date_time,
            reservation_attribute=request.reservation_attribute
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error locking slot: {str(e)}")


# ---------- CREATE RESERVATION ----------
@router.post(
    "/booking/{restaurant_id}/reservations",
    summary="Create a reservation"
)
async def create_reservation(
    restaurant_id: int,
    request: CreateReservationRequest
):
    """
    Create a reservation (pending status).

    - **restaurant_id**: Restaurant ID
    - **request**: Reservation creation request body
    """
    try:
        result = reservation_service.create_reservation(
            restaurant_id=restaurant_id,
            reservation_token=request.reservation_token,
            name=request.name,
            phone_number=request.phone_number,
            email_address=request.email_address,
            special_request=request.special_request
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creating reservation: {str(e)}")


# ---------- GET RESERVATION ----------
@router.get(
    "/{reservation_id}",
    summary="Get a reservation by ID"
)
async def get_reservation(
    reservation_id: int
):
    """
    Get a reservation by ID.

    - **reservation_id**: Reservation ID
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
    summary="Cancel a reservation"
)
async def cancel_reservation(
    reservation_id: int
):
    """
    Cancel a reservation.

    - **reservation_id**: Reservation ID
    """
    try:
        result = reservation_service.cancel_reservation(reservation_id=reservation_id)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error cancelling reservation: {str(e)}")
vation: {str(e)}")
