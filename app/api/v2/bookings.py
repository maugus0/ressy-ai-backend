"""
In-House Booking API routes for handling booking operations.
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.services.booking_service import BookingService

router = APIRouter()


# ---------- Service dependencies ----------


def get_booking_service() -> BookingService:
    """Dependency to get a fresh booking service instance per request."""
    return BookingService()


# Pydantic models for request validation
class LockSlotRequest(BaseModel):
    party_size: int = Field(..., gt=0, description="Party size")
    date_time: str = Field(..., description="Date and time in ISO format")
    booking_attribute: str = Field(default="default", description="Booking attribute")


class CreateBookingRequest(BaseModel):
    booking_token: str = Field(..., description="Token from slot lock")
    name: str = Field(..., min_length=1, description="Full name")
    phone_number: str = Field(..., min_length=1, description="Phone number")
    email_address: Optional[str] = Field(None, description="Email address (optional)")
    special_request: Optional[str] = Field(None, description="Special request (optional)")


class FinalizeBookingRequest(BaseModel):
    confirmation_number: Optional[str] = Field(None, description="Optional confirmation number override")


# ---------- GET AVAILABILITY ----------
@router.get("/availability/{business_id}", summary="Get table availability for a business")
async def get_availability(
    business_id: int,
    start_date_time: str = Query(..., description="Start date and time in ISO format"),
    forward_minutes: Optional[int] = Query(None, description="Forward booking window in minutes"),
    backward_minutes: Optional[int] = Query(None, description="Backward booking window in minutes"),
    party_size: Optional[int] = Query(None, gt=0, description="Party size"),
    booking_service: BookingService = Depends(get_booking_service),
):
    """
    Get table availability for a business.

    - **business_id**: Restaurant ID
    - **start_date_time**: Start date and time
    - **forward_minutes**: Forward booking window
    - **backward_minutes**: Backward booking window
    - **party_size**: Party size
    """
    try:
        result = booking_service.get_availability(
            business_id=business_id,
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
@router.post("/booking/{business_id}/slot_locks", summary="Lock a booking slot")
async def lock_slot(
    business_id: int,
    request: LockSlotRequest,
    booking_service: BookingService = Depends(get_booking_service),
):
    """
    Lock a booking slot for a booking.

    - **business_id**: Restaurant ID
    - **request**: Slot lock request body
    """
    try:
        result = booking_service.lock_slot(
            business_id=business_id,
            party_size=request.party_size,
            date_time=request.date_time,
            booking_attribute=request.booking_attribute,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error locking slot: {str(e)}")


# ---------- CREATE RESERVATION ----------
@router.post("/booking/{business_id}/bookings", summary="Create a booking")
async def create_booking(
    business_id: int,
    request: CreateBookingRequest,
    booking_service: BookingService = Depends(get_booking_service),
):
    """
    Create a booking (pending status).

    - **business_id**: Restaurant ID
    - **request**: Booking creation request body
    """
    try:
        result = booking_service.create_booking(
            business_id=business_id,
            booking_token=request.booking_token,
            name=request.name,
            phone_number=request.phone_number,
            email_address=request.email_address,
            special_request=request.special_request,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creating booking: {str(e)}")


# ---------- GET RESERVATION ----------
@router.get("/{booking_id}", summary="Get a booking by ID")
async def get_booking(
    booking_id: int,
    booking_service: BookingService = Depends(get_booking_service),
):
    """
    Get a booking by ID.

    - **booking_id**: Booking ID
    """
    try:
        result = booking_service.get_booking(booking_id=booking_id)
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching booking: {str(e)}")


# ---------- CANCEL RESERVATION ----------
@router.put("/{booking_id}/cancel", summary="Cancel a booking")
async def cancel_booking(
    booking_id: int,
    booking_service: BookingService = Depends(get_booking_service),
):
    """
    Cancel a booking.

    - **booking_id**: Booking ID
    """
    try:
        result = booking_service.cancel_booking(booking_id=booking_id)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error cancelling booking: {str(e)}")
