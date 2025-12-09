"""
Dashboard API routes for in-house reservation management.
"""

from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.services.reservation_service import ReservationService

router = APIRouter()
reservation_service = ReservationService()


# Pydantic models for request validation
class FinalizeReservationRequest(BaseModel):
    confirmation_number: Optional[str] = Field(None, description="Optional confirmation number override")


# ---------- FINALIZE RESERVATION (Dashboard Only) ----------
@router.put(
    "/reservations/{reservation_id}/finalize",
    summary="Finalize Reservation",
    description="Finalize a pending reservation by changing its status from 'pending' to 'confirmed'. This is a dashboard-only operation typically performed by restaurant staff. Optionally allows setting a custom confirmation number.",
    response_description="Updated reservation object with status 'confirmed' and confirmation number assigned.",
)
async def finalize_reservation(reservation_id: int, request: FinalizeReservationRequest):
    """
    Finalize a reservation (Dashboard only).

    **Authentication**: Public (no authentication required for dashboard operations)

    **Path Parameters**:
    - reservation_id: Unique identifier of the reservation to finalize

    **Request Body**:
    - confirmation_number: Optional custom confirmation number (if not provided, system generates one)

    **Response**: Updated reservation object with:
    - Status changed from "pending" to "confirmed"
    - Confirmation number assigned (custom or auto-generated)
    - Finalized timestamp
    - All other reservation details

    **Note**: Only reservations in "pending" status can be finalized. This operation is typically performed by restaurant staff through the dashboard.
    """
    try:
        result = reservation_service.finalize_reservation(
            reservation_id=reservation_id, confirmation_number=request.confirmation_number
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error finalizing reservation: {str(e)}")


# ---------- GET RESERVATIONS BY RESTAURANT (Dashboard) ----------
@router.get(
    "/restaurants/{restaurant_id}/reservations",
    summary="Get Restaurant Reservations",
    description="Retrieve all reservations for a specific restaurant with optional filtering and pagination. Dashboard endpoint for restaurant staff to view and manage reservations. Supports filtering by status, date range, and pagination.",
    response_description="Paginated list of reservations matching the filters, including total count for pagination.",
)
async def get_restaurant_reservations(
    restaurant_id: int,
    status: Optional[str] = Query(
        None, description="Filter by status: 'pending', 'confirmed', 'cancelled', or 'completed'"
    ),
    start_date: Optional[str] = Query(
        None, description="Filter reservations from this date onwards (ISO format, e.g., 2024-01-15)"
    ),
    end_date: Optional[str] = Query(
        None, description="Filter reservations up to this date (ISO format, e.g., 2024-01-20)"
    ),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of reservations to return (1-1000)"),
    offset: int = Query(0, ge=0, description="Number of reservations to skip for pagination"),
):
    """
    Get reservations for a restaurant (Dashboard).

    **Authentication**: Public (no authentication required for dashboard operations)

    **Path Parameters**:
    - restaurant_id: Unique identifier of the restaurant

    **Query Parameters**:
    - status: Optional filter by reservation status
    - start_date: Optional filter for reservations on or after this date
    - end_date: Optional filter for reservations on or before this date
    - limit: Maximum number of results (default: 100, max: 1000)
    - offset: Number of results to skip for pagination (default: 0)

    **Response**: Paginated list of reservations including:
    - List of reservation objects matching the filters
    - Total count of matching reservations (for pagination)
    - Each reservation includes all details (customer info, booking time, status, etc.)
    """
    try:
        result = reservation_service.get_reservations_by_restaurant(
            restaurant_id=restaurant_id,
            status=status,
            start_date=start_date,
            end_date=end_date,
            limit=limit,
            offset=offset,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching reservations: {str(e)}")


# ---------- GET RESERVATION BY ID (Dashboard) ----------
@router.get(
    "/reservations/{reservation_id}",
    summary="Get Reservation Details (Dashboard)",
    description="Retrieve detailed information for a specific reservation by ID. Dashboard endpoint for viewing complete reservation information including customer details, booking information, and status history.",
    response_description="Complete reservation object with all details including customer info, booking time, status, confirmation number, and timestamps.",
)
async def get_reservation_dashboard(reservation_id: int):
    """
    Get a reservation by ID (Dashboard).

    **Authentication**: Public (no authentication required for dashboard operations)

    **Path Parameters**:
    - reservation_id: Unique identifier of the reservation

    **Response**: Complete reservation object including:
    - Reservation ID and confirmation number
    - Customer information (name, phone, email)
    - Booking details (date, time, party size, table type)
    - Status and status history
    - Special requests
    - Created, updated, and finalized timestamps
    - All associated metadata
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
    summary="Cancel Reservation (Dashboard)",
    description="Cancel a reservation from the dashboard. Changes the reservation status to 'cancelled'. This is a dashboard endpoint for restaurant staff to manage cancellations.",
    response_description="Updated reservation object with status changed to 'cancelled' and cancellation timestamp.",
)
async def cancel_reservation_dashboard(reservation_id: int):
    """
    Cancel a reservation (Dashboard).

    **Authentication**: Public (no authentication required for dashboard operations)

    **Path Parameters**:
    - reservation_id: Unique identifier of the reservation to cancel

    **Response**: Updated reservation object with:
    - Status changed to "cancelled"
    - Cancellation timestamp
    - All other reservation details preserved

    **Note**: Once cancelled, a reservation cannot be reactivated. Restaurant staff should use this endpoint to handle customer cancellations or manage overbookings.
    """
    try:
        result = reservation_service.cancel_reservation(reservation_id=reservation_id)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error cancelling reservation: {str(e)}")
