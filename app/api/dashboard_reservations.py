"""
Dashboard API routes for in-house reservation management.
"""
from fastapi import APIRouter, HTTPException, Query
from typing import Optional
from app.services.reservation_service import ReservationService
from pydantic import BaseModel, Field

router = APIRouter()
reservation_service = ReservationService()


# Pydantic models for request validation
class FinalizeReservationRequest(BaseModel):
    confirmation_number: Optional[str] = Field(None, description="Optional confirmation number override")


# ---------- FINALIZE RESERVATION (Dashboard Only) ----------
@router.put(
    "/reservations/{reservation_id}/finalize",
    summary="Finalize a reservation (Dashboard only)"
)
async def finalize_reservation(
    reservation_id: int,
    request: FinalizeReservationRequest
):
    """
    Finalize a reservation by changing status from 'pending' to 'confirmed'.
    
    - **reservation_id**: Reservation ID
    - **request**: Finalization request body (optional confirmation_number)
    """
    try:
        result = reservation_service.finalize_reservation(
            reservation_id=reservation_id,
            confirmation_number=request.confirmation_number
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error finalizing reservation: {str(e)}")


# ---------- GET RESERVATIONS BY RESTAURANT (Dashboard) ----------
@router.get(
    "/restaurants/{restaurant_id}/reservations",
    summary="Get reservations for a restaurant (Dashboard)"
)
async def get_restaurant_reservations(
    restaurant_id: int,
    status: Optional[str] = Query(None, description="Filter by status (pending, confirmed, cancelled, completed)"),
    start_date: Optional[str] = Query(None, description="Filter by start date (ISO format)"),
    end_date: Optional[str] = Query(None, description="Filter by end date (ISO format)"),
    limit: int = Query(100, ge=1, le=1000, description="Limit results"),
    offset: int = Query(0, ge=0, description="Offset for pagination")
):
    """
    Get reservations for a restaurant.
    
    - **restaurant_id**: Restaurant ID
    - **status**: Filter by status
    - **start_date**: Filter by start date
    - **end_date**: Filter by end date
    - **limit**: Limit results
    - **offset**: Offset for pagination
    """
    try:
        result = reservation_service.get_reservations_by_restaurant(
            restaurant_id=restaurant_id,
            status=status,
            start_date=start_date,
            end_date=end_date,
            limit=limit,
            offset=offset
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching reservations: {str(e)}")


# ---------- GET RESERVATION BY ID (Dashboard) ----------
@router.get(
    "/reservations/{reservation_id}",
    summary="Get a reservation by ID (Dashboard)"
)
async def get_reservation_dashboard(
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


# ---------- CANCEL RESERVATION (Dashboard) ----------
@router.put(
    "/reservations/{reservation_id}/cancel",
    summary="Cancel a reservation (Dashboard)"
)
async def cancel_reservation_dashboard(
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

