"""
OpenTable API routes for handling reservation operations.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional, Dict, Any
from app.middleware.auth_middleware import get_current_active_user, require_role
from app.services.opentable_service import OpenTableService
from pydantic import BaseModel, Field

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
    summary="Get table availability for a restaurant"
)
async def get_availability(
    restaurant_id: int,
    rid: int,
    start_date_time: str = Query(..., description="Start date and time in format yyyy-mm-ddThh:ss"),
    forward_minutes: Optional[int] = Query(None, description="Forward booking window in minutes"),
    backward_minutes: Optional[int] = Query(None, description="Backward booking window in minutes"),
    party_size: Optional[int] = Query(None, gt=0, description="Party size"),
    require_attributes: Optional[str] = Query(None, description="Table types (comma-separated)"),
    include_credit_card_results: Optional[bool] = Query(None, description="Include credit card results"),
    include_experiences: Optional[bool] = Query(None, description="Include experiences"),
    current_user: dict = Depends(get_current_active_user)
):
    """
    Get table availability for a restaurant from OpenTable API.
    
    - **restaurant_id**: Internal restaurant ID
    - **rid**: OpenTable restaurant ID
    - **start_date_time**: Start date and time
    - **forward_minutes**: Forward booking window
    - **backward_minutes**: Backward booking window
    - **party_size**: Party size
    - **require_attributes**: Table types
    - **include_credit_card_results**: Include credit card results
    - **include_experiences**: Include experiences
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
            include_experiences=include_experiences
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching availability: {str(e)}")


# ---------- LOCK SLOT ----------
@router.post(
    "/booking/{restaurant_id}/{rid}/slot_locks",
    summary="Lock a booking slot"
)
async def lock_slot(
    restaurant_id: int,
    rid: int,
    request: LockSlotRequest,
    current_user: dict = Depends(get_current_active_user)
):
    """
    Lock a booking slot for a reservation.
    
    - **restaurant_id**: Internal restaurant ID
    - **rid**: OpenTable restaurant ID
    - **request**: Slot lock request body
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
            environment=request.environment
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error locking slot: {str(e)}")


# ---------- CREATE RESERVATION ----------
@router.post(
    "/booking/{restaurant_id}/{rid}/reservations",
    summary="Create a reservation"
)
async def create_reservation(
    restaurant_id: int,
    rid: int,
    request: CreateReservationRequest,
    current_user: dict = Depends(get_current_active_user)
):
    """
    Create a reservation.
    
    - **restaurant_id**: Internal restaurant ID
    - **rid**: OpenTable restaurant ID
    - **request**: Reservation creation request body
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
            experience=request.experience
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creating reservation: {str(e)}")


# ---------- UPDATE RESERVATION ----------
@router.put(
    "/booking/{restaurant_id}/{rid}/reservations/{confirmation_id}",
    summary="Update a reservation"
)
async def update_reservation(
    restaurant_id: int,
    rid: int,
    confirmation_id: int,
    request: UpdateReservationRequest,
    current_user: dict = Depends(get_current_active_user)
):
    """
    Update an existing reservation.
    
    - **restaurant_id**: Internal restaurant ID
    - **rid**: OpenTable restaurant ID
    - **confirmation_id**: Confirmation number
    - **request**: Reservation update request body
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
            experience=request.experience
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error updating reservation: {str(e)}")


# ---------- CANCEL RESERVATION ----------
@router.put(
    "/booking/{restaurant_id}/{rid}/reservations/{confirmation_id}/cancel",
    summary="Cancel a reservation"
)
async def cancel_reservation(
    restaurant_id: int,
    rid: int,
    confirmation_id: int,
    current_user: dict = Depends(get_current_active_user)
):
    """
    Cancel a reservation.
    
    - **restaurant_id**: Internal restaurant ID
    - **rid**: OpenTable restaurant ID
    - **confirmation_id**: Confirmation number
    """
    try:
        result = opentable_service.cancel_reservation(
            restaurant_id=restaurant_id,
            rid=rid,
            confirmation_id=confirmation_id
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error cancelling reservation: {str(e)}")

