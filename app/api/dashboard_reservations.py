"""
Dashboard API routes for in-house reservation management.
Includes RBAC: admins can access all, managers can only access their restaurant's reservations.
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.security import HTTPBearer
from pydantic import BaseModel, Field

from app.middleware.auth_middleware import require_role
from app.services.reservation_service import ReservationService

# Security scheme for Swagger UI - must match the scheme name in main.py custom_openapi()
security = HTTPBearer(
    scheme_name="BearerAuth",  # Match the security scheme name defined in main.py
    description="Enter your JWT access token obtained from login endpoints",
)

router = APIRouter(
    dependencies=[Depends(security)],  # Apply security to all endpoints in this router
)
reservation_service = ReservationService()


# ---------- Pydantic models for request validation ----------


class CreateReservationDirectRequest(BaseModel):
    """Request model for creating a reservation directly from the dashboard."""

    date_time: str = Field(
        ...,
        description="Reservation date and time in ISO format",
        json_schema_extra={"example": "2025-12-20T19:00:00"},
    )
    party_size: int = Field(
        ..., gt=0, le=20, description="Number of guests", json_schema_extra={"example": 4}
    )
    name: str = Field(
        ..., min_length=1, max_length=200, description="Guest name", json_schema_extra={"example": "John Smith"}
    )
    phone_number: str = Field(
        ..., min_length=1, max_length=20, description="Guest phone number", json_schema_extra={"example": "+1234567890"}
    )
    email_address: Optional[str] = Field(
        None, max_length=255, description="Guest email address (optional)", json_schema_extra={"example": "john@example.com"}
    )
    special_request: Optional[str] = Field(
        None, max_length=500, description="Special requests from the guest", json_schema_extra={"example": "Window seat preferred"}
    )
    notes: Optional[str] = Field(
        None, max_length=1000, description="Internal notes for staff", json_schema_extra={"example": "VIP customer, birthday celebration"}
    )


class FinalizeReservationRequest(BaseModel):
    """Request model for finalizing a pending reservation."""

    confirmation_number: Optional[str] = Field(
        None,
        max_length=100,
        description="Optional confirmation number override",
        json_schema_extra={"example": "INH-1-CUSTOM123"},
    )


class UpdateReservationRequest(BaseModel):
    """Request model for updating reservation and slot booking details."""

    # Slot booking fields (from slot_bookings table)
    date_time: Optional[str] = Field(
        None,
        description="Reservation date and time in ISO format (updates slot_bookings.date_time)",
        json_schema_extra={"example": "2025-12-20T19:30:00"},
    )

    # Reservation fields (from reservations table)
    party_size: Optional[int] = Field(
        None, gt=0, le=20, description="Number of guests", json_schema_extra={"example": 6}
    )
    special_request: Optional[str] = Field(
        None, max_length=500, description="Special requests from the guest", json_schema_extra={"example": "Allergic to nuts"}
    )
    notes: Optional[str] = Field(
        None, max_length=1000, description="Internal notes for staff", json_schema_extra={"example": "VIP customer, birthday celebration"}
    )
    confirmation_number: Optional[str] = Field(
        None, max_length=100, description="Confirmation number (override)", json_schema_extra={"example": "INH-1-CUSTOM123"}
    )
    status: Optional[str] = Field(
        None,
        description="Reservation status (pending, confirmed, cancelled, completed, no_show)",
        json_schema_extra={"example": "confirmed"},
    )
    last_cancel_time: Optional[str] = Field(
        None,
        description="Last time reservation can be cancelled (ISO format)",
        json_schema_extra={"example": "2025-12-20T17:00:00"},
    )
    manage_reservation_url: Optional[str] = Field(
        None, max_length=500, description="URL for managing reservation", json_schema_extra={"example": "https://example.com/manage/abc123"}
    )


# ---------- Helper functions for RBAC ----------


def _check_restaurant_access(current_user: dict, restaurant_id: int):
    """
    Check if the current user has access to the specified restaurant.
    Admins have access to all restaurants.
    Restaurant users (managers) can only access their own restaurant.

    Args:
        current_user: JWT claims dict containing user_type, restaurant_id (for restaurant users)
        restaurant_id: The restaurant ID to check access for (from path param or reservation)

    Raises:
        HTTPException 403: If user doesn't have access to this restaurant
    """
    user_type = current_user.get("user_type")

    # Admins (Ressy platform admins) can access all restaurants
    if user_type == "admin":
        return

    # Restaurant users (managers/staff) can only access their own restaurant
    if user_type == "restaurant":
        user_restaurant_id = current_user.get("restaurant_id")

        # Ensure both values are compared as integers to avoid type mismatch
        try:
            user_rest_id_int = int(user_restaurant_id) if user_restaurant_id is not None else None
            target_rest_id_int = int(restaurant_id) if restaurant_id is not None else None
        except (ValueError, TypeError):
            raise HTTPException(
                status_code=403,
                detail="Invalid restaurant ID format",
            )

        if user_rest_id_int is None:
            raise HTTPException(
                status_code=403,
                detail="Your account is not associated with any restaurant",
            )

        if target_rest_id_int is None:
            raise HTTPException(
                status_code=500,
                detail="Target restaurant ID is invalid",
            )

        if user_rest_id_int != target_rest_id_int:
            raise HTTPException(
                status_code=403,
                detail=f"You can only access reservations for your own restaurant (ID: {user_rest_id_int})",
            )
        return

    raise HTTPException(status_code=403, detail="Access denied - unknown user type")


def _check_reservation_access(current_user: dict, reservation_id: int):
    """
    Check if the current user has access to the specified reservation.
    Fetches the reservation with its associated restaurant_id from slot_bookings
    and validates that the user has access to that restaurant.

    The restaurant_id is obtained from the slot_bookings table via JOIN since
    the reservations table doesn't have a direct restaurant_id column.

    Args:
        current_user: JWT claims dict
        reservation_id: The reservation ID to check access for

    Returns:
        The reservation dict if access is granted

    Raises:
        HTTPException 404: If reservation not found
        HTTPException 403: If user doesn't have access
        HTTPException 500: If reservation has no associated restaurant
    """
    try:
        reservation = reservation_service.get_reservation_with_restaurant_check(reservation_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    # restaurant_id comes from slot_bookings table via JOIN
    restaurant_id = reservation.get("restaurant_id")

    if restaurant_id is None:
        raise HTTPException(
            status_code=500,
            detail="Reservation has no associated restaurant - slot_booking may be missing or corrupted",
        )

    _check_restaurant_access(current_user, restaurant_id)
    return reservation


# ---------- CREATE RESERVATION (Dashboard Only) ----------
@router.post(
    "/restaurants/{restaurant_id}/reservations",
    summary="Create a confirmed reservation (Dashboard only)",
    description="""
Create a new reservation directly from the dashboard with confirmed status.

This endpoint performs slot booking and reservation creation in a single transaction,
making it ideal for walk-in customers or phone reservations managed by staff.

**Authentication**: Required (admin or restaurant manager role)

**Authorization**:
- Admins can create reservations for any restaurant
- Restaurant managers can only create reservations for their own restaurant

**Request Body**:
- `date_time`: Reservation date and time in ISO format
- `party_size`: Number of guests (1-20)
- `name`: Guest's full name
- `phone_number`: Guest's phone number
- `email_address`: Guest's email (optional)
- `special_request`: Special requests from the guest (optional)
- `notes`: Internal notes for staff (optional)
""",
    response_description="Created and confirmed reservation with all details",
    responses={
        200: {
            "description": "Reservation created successfully",
            "content": {
                "application/json": {
                    "example": {
                        "reservation_id": 123,
                        "slot_id": 456,
                        "confirmation_number": "INH-1-A1B2C3D4",
                        "status": "confirmed",
                        "date_time": "2025-12-20T19:00:00",
                        "party_size": 4,
                        "name": "John Smith",
                        "phone_number": "+1234567890",
                        "email_address": "john@example.com",
                        "special_request": "Window seat preferred",
                        "notes": "VIP customer, birthday celebration",
                        "message": "Reservation created and confirmed successfully",
                    }
                }
            },
        },
        400: {"description": "Invalid request data or slot already booked"},
        403: {"description": "Access denied - cannot access this restaurant's reservations"},
        404: {"description": "Restaurant not found"},
    },
)
async def create_reservation_direct(
    restaurant_id: int,
    request: CreateReservationDirectRequest,
    current_user: dict = Depends(require_role(["admin", "client"])),
):
    """Create a confirmed reservation directly from the dashboard."""
    _check_restaurant_access(current_user, restaurant_id)

    try:
        result = reservation_service.create_reservation_direct(
            restaurant_id=restaurant_id,
            date_time=request.date_time,
            party_size=request.party_size,
            name=request.name,
            phone_number=request.phone_number,
            email_address=request.email_address,
            special_request=request.special_request,
            notes=request.notes,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creating reservation: {str(e)}")


# ---------- FINALIZE RESERVATION (Dashboard Only) ----------
@router.put(
    "/reservations/{reservation_id}/finalize",
    summary="Finalize a pending reservation (Dashboard only)",
    description="""
Finalize a reservation by changing its status from 'pending' to 'confirmed'.

This is used for reservations created through the voice agent or API that require
manual confirmation by restaurant staff.

**Authentication**: Required (admin or restaurant manager role)

**Authorization**:
- Admins can finalize reservations for any restaurant
- Restaurant managers can only finalize reservations for their own restaurant
""",
    response_description="Finalized reservation with confirmed status",
    responses={
        200: {
            "description": "Reservation finalized successfully",
            "content": {
                "application/json": {
                    "example": {
                        "reservation_id": 123,
                        "confirmation_number": "INH-1-A1B2C3D4",
                        "status": "confirmed",
                        "message": "Reservation confirmed successfully",
                    }
                }
            },
        },
        400: {"description": "Reservation is not in pending status"},
        403: {"description": "Access denied - cannot access this restaurant's reservations"},
        404: {"description": "Reservation not found"},
    },
)
async def finalize_reservation(
    reservation_id: int,
    request: FinalizeReservationRequest,
    current_user: dict = Depends(require_role(["admin", "client"])),
):
    """Finalize a reservation by changing status from 'pending' to 'confirmed'."""
    _check_reservation_access(current_user, reservation_id)

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
    summary="Get reservations for a restaurant (Dashboard)",
    description="""
Retrieve all reservations for a specific restaurant with optional filters.

**Authentication**: Required (admin or restaurant manager role)

**Authorization**:
- Admins can view reservations for any restaurant
- Restaurant managers can only view reservations for their own restaurant

**Query Parameters**:
- `status`: Filter by status (pending, confirmed, cancelled, completed)
- `start_date`: Filter reservations from this date (ISO format)
- `end_date`: Filter reservations until this date (ISO format)
- `limit`: Maximum number of results (default: 100, max: 1000)
- `offset`: Pagination offset (default: 0)
""",
    response_description="List of reservations with customer and booking details",
    responses={
        200: {
            "description": "Reservations retrieved successfully",
            "content": {
                "application/json": {
                    "example": {
                        "restaurant_id": 1,
                        "reservations": [
                            {
                                "id": 123,
                                "reservation_type": "in-house",
                                "confirmation_number": "INH-1-A1B2C3D4",
                                "status": "confirmed",
                                "date_time": "2025-12-20T19:00:00",
                                "party_size": 4,
                                "name": "John Smith",
                                "phone_number": "+1234567890",
                                "email": "john@example.com",
                                "special_request": "Window seat preferred",
                                "notes": "VIP customer",
                                "created_at": "2025-12-13T10:00:00",
                            }
                        ],
                        "total": 1,
                    }
                }
            },
        },
        403: {"description": "Access denied - cannot access this restaurant's reservations"},
    },
)
async def get_restaurant_reservations(
    restaurant_id: int,
    status: Optional[str] = Query(
        None,
        description="Filter by status",
        json_schema_extra={"example": "confirmed"},
    ),
    start_date: Optional[str] = Query(
        None,
        description="Filter by start date (ISO format)",
        json_schema_extra={"example": "2025-12-01T00:00:00"},
    ),
    end_date: Optional[str] = Query(
        None,
        description="Filter by end date (ISO format)",
        json_schema_extra={"example": "2025-12-31T23:59:59"},
    ),
    limit: int = Query(100, ge=1, le=1000, description="Limit results"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    current_user: dict = Depends(require_role(["admin", "client"])),
):
    """Get reservations for a restaurant with optional filters."""
    _check_restaurant_access(current_user, restaurant_id)

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
    summary="Get a reservation by ID (Dashboard)",
    description="""
Retrieve detailed information about a specific reservation.

**Authentication**: Required (admin or restaurant manager role)

**Authorization**:
- Admins can view any reservation
- Restaurant managers can only view reservations for their own restaurant
""",
    response_description="Reservation details including customer information and notes",
    responses={
        200: {
            "description": "Reservation retrieved successfully",
            "content": {
                "application/json": {
                    "example": {
                        "id": 123,
                        "reservation_type": "in-house",
                        "slot_booking_id": 456,
                        "user_id": 789,
                        "confirmation_number": "INH-1-A1B2C3D4",
                        "status": "confirmed",
                        "date_time": "2025-12-20T19:00:00",
                        "party_size": 4,
                        "restaurant_id": 1,
                        "name": "John Smith",
                        "phone_number": "+1234567890",
                        "email": "john@example.com",
                        "special_request": "Window seat preferred",
                        "notes": "VIP customer, birthday celebration",
                        "created_at": "2025-12-13T10:00:00",
                        "updated_at": "2025-12-13T10:00:00",
                    }
                }
            },
        },
        403: {"description": "Access denied - cannot access this restaurant's reservations"},
        404: {"description": "Reservation not found"},
    },
)
async def get_reservation_dashboard(
    reservation_id: int,
    current_user: dict = Depends(require_role(["admin", "client"])),
):
    """Get a reservation by ID with authorization check."""
    reservation = _check_reservation_access(current_user, reservation_id)
    return reservation


# ---------- UPDATE RESERVATION (Dashboard) ----------
@router.put(
    "/reservations/{reservation_id}",
    summary="Update a reservation (Dashboard)",
    description="""
Update reservation details including slot timing.

**Authentication**: Required (admin or restaurant manager role)

**Authorization**:
- Admins can update any reservation
- Restaurant managers can only update reservations for their own restaurant

**Updatable Fields**:

*Slot Booking (timing):*
- `date_time`: Reservation date and time (ISO format) - updates the slot timing

*Reservation Details:*
- `party_size`: Number of guests
- `special_request`: Guest's special requests
- `notes`: Internal staff notes
- `confirmation_number`: Override confirmation number
- `status`: Reservation status (pending, confirmed, cancelled, completed, no_show)
- `last_cancel_time`: Deadline for cancellation
- `manage_reservation_url`: URL for reservation management

**Note**: Only provided fields will be updated. Omit fields you don't want to change.
""",
    response_description="Updated reservation with all details",
    responses={
        200: {
            "description": "Reservation updated successfully",
            "content": {
                "application/json": {
                    "example": {
                        "id": 123,
                        "reservation_type": "in-house",
                        "slot_booking_id": 456,
                        "user_id": 789,
                        "confirmation_number": "INH-1-A1B2C3D4",
                        "status": "confirmed",
                        "date_time": "2025-12-20T19:30:00",
                        "party_size": 6,
                        "restaurant_id": 1,
                        "name": "John Smith",
                        "phone_number": "+1234567890",
                        "email": "john@example.com",
                        "special_request": "Allergic to nuts",
                        "notes": "VIP customer, birthday celebration",
                        "last_cancel_time": "2025-12-20T17:00:00",
                        "manage_reservation_url": None,
                        "created_at": "2025-12-13T10:00:00",
                        "updated_at": "2025-12-13T12:00:00",
                    }
                }
            },
        },
        400: {"description": "Invalid request data, status value, or time slot conflict"},
        403: {"description": "Access denied - cannot access this restaurant's reservations"},
        404: {"description": "Reservation not found"},
    },
)
async def update_reservation(
    reservation_id: int,
    request: UpdateReservationRequest,
    current_user: dict = Depends(require_role(["admin", "client"])),
):
    """Update reservation and slot booking details."""
    _check_reservation_access(current_user, reservation_id)

    try:
        result = reservation_service.update_reservation(
            reservation_id=reservation_id,
            date_time=request.date_time,
            party_size=request.party_size,
            special_request=request.special_request,
            notes=request.notes,
            confirmation_number=request.confirmation_number,
            status=request.status,
            last_cancel_time=request.last_cancel_time,
            manage_reservation_url=request.manage_reservation_url,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error updating reservation: {str(e)}")


# ---------- CANCEL RESERVATION (Dashboard) ----------
@router.put(
    "/reservations/{reservation_id}/cancel",
    summary="Cancel a reservation (Dashboard)",
    description="""
Cancel a reservation by changing its status to 'cancelled'.

This action will also release the associated time slot, making it available
for new bookings.

**Authentication**: Required (admin or restaurant manager role)

**Authorization**:
- Admins can cancel any reservation
- Restaurant managers can only cancel reservations for their own restaurant

**Note**: Only reservations with 'pending' or 'confirmed' status can be cancelled.
""",
    response_description="Cancellation confirmation",
    responses={
        200: {
            "description": "Reservation cancelled successfully",
            "content": {
                "application/json": {
                    "example": {
                        "reservation_id": 123,
                        "status": "cancelled",
                        "message": "Reservation cancelled successfully",
                    }
                }
            },
        },
        400: {"description": "Cannot cancel reservation (already cancelled or completed)"},
        403: {"description": "Access denied - cannot access this restaurant's reservations"},
        404: {"description": "Reservation not found"},
    },
)
async def cancel_reservation_dashboard(
    reservation_id: int,
    current_user: dict = Depends(require_role(["admin", "client"])),
):
    """Cancel a reservation."""
    _check_reservation_access(current_user, reservation_id)

    try:
        result = reservation_service.cancel_reservation(reservation_id=reservation_id)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error cancelling reservation: {str(e)}")
