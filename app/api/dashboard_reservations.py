"""
Dashboard API routes for in-house reservation management.
Includes RBAC: admins can access all, managers can only access their restaurant's reservations.
"""

import json
import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from fastapi.security import HTTPBearer
from pydantic import BaseModel, Field

from app.middleware.auth_middleware import require_role
from app.repositories.mysql_user_repo import MySQLUserRepository
from app.services.activity_history_service import ActivityHistoryService
from app.services.notification_service import NotificationService
from app.services.reservation_service import ReservationService
from app.services.restaurant_service import RestaurantService
from app.services.sse_service import ReservationEventSubtype, SSEService

logger = logging.getLogger(__name__)

security = HTTPBearer(
    scheme_name="HTTPBearer",  # Standardized security scheme name
    description="Enter your JWT access token obtained from login endpoints",
)

router = APIRouter(
    dependencies=[Depends(security)],  # Apply security to all endpoints in this router
)


# ---------- Service dependencies ----------


def get_reservation_service() -> ReservationService:
    """Dependency to get a fresh reservation service instance per request."""
    return ReservationService()


def get_sse_service() -> SSEService:
    """Dependency to get SSE service instance."""
    return SSEService()


def get_history_service() -> ActivityHistoryService:
    """Dependency to get activity history service instance."""
    return ActivityHistoryService()


def get_restaurant_service() -> RestaurantService:
    """Dependency to get restaurant service instance."""
    return RestaurantService()


def get_notification_service() -> NotificationService:
    """Dependency to get notification service instance."""
    return NotificationService()


# ---------- Background task helpers ----------


async def _send_reservation_notification(
    restaurant_id: int,
    reservation_id: int,
    new_status: str,
    phone_number: Optional[str],
    user_id: Optional[int] = None,
    confirmation_number: Optional[str] = None,
) -> None:
    if not phone_number and user_id:
        try:
            user_repo = MySQLUserRepository()
            user = user_repo.get_user_by_id(user_id)
            if user and user.get("phone_number"):
                phone_number = user.get("phone_number")
                logger.info(f"Reservation {reservation_id}: Retrieved phone {phone_number} from user_id {user_id}")
        except Exception as e:
            logger.warning(f"Reservation {reservation_id}: Failed to lookup user {user_id} for phone number: {e}")

    if not phone_number:
        logger.info(f"Reservation {reservation_id}: No phone_number found (user_id={user_id}), skipping notification")
        return
    try:
        restaurant_service = RestaurantService()
        restaurant = restaurant_service.get_restaurant(restaurant_id)
        if not restaurant:
            logger.warning(f"Restaurant {restaurant_id} not found for reservation notification")
            return
        restaurant_name = restaurant.get("name", "the restaurant")
        restaurant_twilio_number = restaurant.get("twilio_phone_number")
        if not restaurant_twilio_number:
            logger.warning(f"No Twilio number configured for restaurant {restaurant_id}")
            return
        logger.info(
            f"Sending SMS notification for reservation {reservation_id} to {phone_number} from {restaurant_twilio_number}"
        )
        await send_reservation_status_notification_async(
            restaurant_id=restaurant_id,
            reservation_id=reservation_id,
            new_status=new_status,
            recipient_phone=phone_number,
            restaurant_name=restaurant_name,
            restaurant_twilio_number=restaurant_twilio_number,
            confirmation_number=confirmation_number,
        )
    except Exception as e:
        logger.error(f"Failed to send reservation notification for reservation {reservation_id}: {e}", exc_info=True)


async def _emit_reservation_sse_event(
    restaurant_id: int,
    reservation_id: int,
    subtype: ReservationEventSubtype,
    data: Dict[str, Any],
) -> None:
    """
    Background task to emit SSE reservation events.
    Logs errors but does not raise exceptions to avoid affecting other operations.
    Creates its own SSE service instance since background tasks run outside request context.
    """
    try:
        sse_svc = SSEService()
        await sse_svc.emit_reservation_event(
            restaurant_id=restaurant_id,
            reservation_id=reservation_id,
            subtype=subtype,
            data=data,
        )
    except Exception as sse_error:
        logger.error(f"Failed to emit SSE event for reservation {reservation_id} ({subtype.value}): {sse_error}")


def _queue_reservation_sms(
    background_tasks: BackgroundTasks,
    notification_service: NotificationService,
    restaurant_service: RestaurantService,
    restaurant_id: Optional[int],
    reservation_id: int,
    new_status: str,
    recipient_phone: Optional[str],
    confirmation_number: Optional[str],
) -> None:
    """Queue SMS notification as a background task (non-blocking).

    Restaurant lookup is performed inside the background task to avoid
    blocking the API response on database queries.
    """
    if not restaurant_id or not (recipient_phone and str(recipient_phone).strip()):
        return

    async def _send_reservation_sms_notification() -> None:
        try:
            # Restaurant lookup moved inside background task for non-blocking API response
            restaurant = restaurant_service.get_restaurant(restaurant_id)
            if not restaurant:
                logger.warning("Restaurant %s not found for reservation SMS", restaurant_id)
                return

            twilio_number = (restaurant.get("twilio_phone_number") or "").strip()
            if not twilio_number:
                logger.debug("No Twilio number configured for restaurant %s", restaurant_id)
                return

            twilio_details = restaurant.get("twilio_details") or {}
            if isinstance(twilio_details, str):
                try:
                    twilio_details = json.loads(twilio_details) if twilio_details else {}
                except json.JSONDecodeError as e:
                    logger.warning(
                        "Invalid JSON in twilio_details for restaurant %s: %s",
                        restaurant_id,
                        e,
                    )
                    twilio_details = {}
                except Exception as e:
                    logger.warning(
                        "Unexpected error parsing twilio_details for restaurant %s: %s",
                        restaurant_id,
                        e,
                    )
                    twilio_details = {}

            sid = twilio_details.get("account_sid") or twilio_details.get("TWILIO_ACCOUNT_SID")
            token = twilio_details.get("auth_token") or twilio_details.get("TWILIO_AUTH_TOKEN")

            await notification_service.send_reservation_notification(
                restaurant_id=restaurant_id,
                reservation_id=reservation_id,
                new_status=new_status,
                recipient_phone=str(recipient_phone).strip(),
                restaurant_name=restaurant.get("name") or "",
                restaurant_twilio_number=twilio_number,
                confirmation_number=confirmation_number,
                twilio_account_sid=sid,
                twilio_auth_token=token,
            )
        except Exception as sms_err:
            logger.warning("SMS notification for reservation %s failed: %s", reservation_id, sms_err)

    background_tasks.add_task(_send_reservation_sms_notification)


# ---------- Pydantic models for request validation ----------


class CreateReservationDirectRequest(BaseModel):
    """Request model for creating a reservation directly from the dashboard."""

    date_time: str = Field(
        ...,
        description="Reservation date and time in ISO format",
        json_schema_extra={"example": "2025-12-20T19:00:00Z"},
    )
    party_size: int = Field(..., gt=0, le=20, description="Number of guests", json_schema_extra={"example": 4})
    name: str = Field(
        ..., min_length=1, max_length=200, description="Guest name", json_schema_extra={"example": "John Smith"}
    )
    phone_number: str = Field(
        ..., min_length=1, max_length=20, description="Guest phone number", json_schema_extra={"example": "+1234567890"}
    )
    email_address: Optional[str] = Field(
        None,
        max_length=255,
        description="Guest email address (optional)",
        json_schema_extra={"example": "john@example.com"},
    )
    special_request: Optional[str] = Field(
        None,
        max_length=500,
        description="Special requests from the guest",
        json_schema_extra={"example": "Window seat preferred"},
    )
    notes: Optional[str] = Field(
        None,
        max_length=1000,
        description="Internal notes for staff",
        json_schema_extra={"example": "VIP customer, birthday celebration"},
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
        json_schema_extra={"example": "2025-12-20T19:30:00Z"},
    )

    # Reservation fields (from reservations table)
    party_size: Optional[int] = Field(
        None, gt=0, le=20, description="Number of guests", json_schema_extra={"example": 6}
    )
    special_request: Optional[str] = Field(
        None,
        max_length=500,
        description="Special requests from the guest",
        json_schema_extra={"example": "Allergic to nuts"},
    )
    notes: Optional[str] = Field(
        None,
        max_length=1000,
        description="Internal notes for staff",
        json_schema_extra={"example": "VIP customer, birthday celebration"},
    )
    confirmation_number: Optional[str] = Field(
        None,
        max_length=100,
        description="Confirmation number (override)",
        json_schema_extra={"example": "INH-1-CUSTOM123"},
    )
    status: Optional[str] = Field(
        None,
        description="Reservation status (pending, confirmed, cancelled, completed, no_show)",
        json_schema_extra={"example": "confirmed"},
    )
    last_cancel_time: Optional[str] = Field(
        None,
        description="Last time reservation can be cancelled (ISO format)",
        json_schema_extra={"example": "2025-12-20T17:00:00Z"},
    )
    manage_reservation_url: Optional[str] = Field(
        None,
        max_length=500,
        description="URL for managing reservation",
        json_schema_extra={"example": "https://example.com/manage/abc123"},
    )


class HistoryEntryResponse(BaseModel):
    """Response model for a history entry in reservation detail."""

    id: int = Field(..., description="History entry ID")
    action: str = Field(..., description="Action performed (created, updated, cancelled, etc.)")
    previous_value: Optional[Dict[str, Any]] = Field(None, description="Previous state")
    new_value: Optional[Dict[str, Any]] = Field(None, description="New state")
    change_summary: Optional[str] = Field(None, description="Human-readable summary")
    created_at: str = Field(..., description="Timestamp of the action")


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

        # Check if user has a restaurant assigned
        if user_restaurant_id is None:
            raise HTTPException(
                status_code=403,
                detail="Your account is not associated with any restaurant",
            )

        # Compare as integers to handle string/int type differences from JWT
        if int(user_restaurant_id) != int(restaurant_id):
            raise HTTPException(
                status_code=403,
                detail=f"You can only access reservations for your own restaurant (ID: {user_restaurant_id})",
            )
        return

    raise HTTPException(status_code=403, detail="Access denied - unknown user type")


def _check_reservation_access(current_user: dict, reservation_id: int, reservation_service: ReservationService):
    """
    Check if the current user has access to the specified reservation.
    Fetches the reservation with its associated restaurant_id from slot_bookings
    and validates that the user has access to that restaurant.

    The restaurant_id is obtained from the slot_bookings table via JOIN since
    the reservations table doesn't have a direct restaurant_id column.

    Args:
        current_user: JWT claims dict
        reservation_id: The reservation ID to check access for
        reservation_service: The reservation service instance to use

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
                        "date_time": "2025-12-20T19:00:00Z",
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
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(require_role(["admin", "client"])),
    reservation_service: ReservationService = Depends(get_reservation_service),
    history_service: ActivityHistoryService = Depends(get_history_service),
    restaurant_service: RestaurantService = Depends(get_restaurant_service),
    notification_service: NotificationService = Depends(get_notification_service),
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

        # Log activity history for reservation creation
        try:
            history_service.log_reservation_created(
                reservation_id=result["reservation_id"],
                restaurant_id=int(restaurant_id),
                reservation_data={
                    "status": result.get("status"),
                    "party_size": result.get("party_size"),
                    "date_time": result.get("date_time"),
                    "name": result.get("name"),
                },
                user_id=result.get("user_id"),
                performed_by=current_user,
            )
        except Exception as history_error:
            logger.warning(
                f"Failed to log history for reservation creation {result['reservation_id']}: {history_error}"
            )

        # Emit SSE event for new reservation (background task, properly managed by FastAPI)
        background_tasks.add_task(
            _emit_reservation_sse_event,
            restaurant_id=restaurant_id,
            reservation_id=result["reservation_id"],
            subtype=ReservationEventSubtype.NEW_RESERVATION,
            data={
                "reservation_id": result["reservation_id"],
                "confirmation_number": result.get("confirmation_number"),
                "status": result.get("status"),
                "date_time": result.get("date_time"),
                "party_size": result.get("party_size"),
                "name": result.get("name"),
            },
        )

        # SMS on reservation created (status confirmed)
        _queue_reservation_sms(
            background_tasks,
            notification_service,
            restaurant_service,
            restaurant_id,
            result["reservation_id"],
            result.get("status", "confirmed"),
            request.phone_number,
            result.get("confirmation_number"),
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
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(require_role(["admin", "client"])),
    reservation_service: ReservationService = Depends(get_reservation_service),
    restaurant_service: RestaurantService = Depends(get_restaurant_service),
    notification_service: NotificationService = Depends(get_notification_service),
):
    """Finalize a reservation by changing status from 'pending' to 'confirmed'."""
    reservation = _check_reservation_access(current_user, reservation_id, reservation_service)
    restaurant_id = reservation.get("restaurant_id")
    phone_number = reservation.get("phone_number")
    user_id = reservation.get("user_id")
    confirmation_number = reservation.get("confirmation_number")

    logger.info(f"Finalizing reservation {reservation_id}, phone_number={phone_number}, user_id={user_id}")

    try:
        result = reservation_service.finalize_reservation(
            reservation_id=reservation_id, confirmation_number=request.confirmation_number
        )
        # SMS on status change to confirmed
        _queue_reservation_sms(
            background_tasks,
            notification_service,
            restaurant_service,
            reservation.get("restaurant_id"),
            reservation_id,
            result.get("status", "confirmed"),
            reservation.get("phone_number"),
            result.get("confirmation_number"),
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
                                "date_time": "2025-12-20T19:00:00Z",
                                "party_size": 4,
                                "name": "John Smith",
                                "phone_number": "+1234567890",
                                "email": "john@example.com",
                                "special_request": "Window seat preferred",
                                "notes": "VIP customer",
                                "created_at": "2025-12-13T10:00:00Z",
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
        json_schema_extra={"example": "2025-12-01T00:00:00Z"},
    ),
    end_date: Optional[str] = Query(
        None,
        description="Filter by end date (ISO format)",
        json_schema_extra={"example": "2025-12-31T23:59:59Z"},
    ),
    limit: int = Query(100, ge=1, le=1000, description="Limit results"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    current_user: dict = Depends(require_role(["admin", "client"])),
    reservation_service: ReservationService = Depends(get_reservation_service),
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
Retrieve detailed information about a specific reservation, including its change history.

**Authentication**: Required (admin or restaurant manager role)

**Authorization**:
- Admins can view any reservation
- Restaurant managers can only view reservations for their own restaurant

**History**: The `history` field contains an array of all changes made to this reservation,
ordered from most recent to oldest. Each entry includes the action performed,
previous and new values, and a human-readable summary.
""",
    response_description="Reservation details including customer information, notes, and change history",
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
                        "date_time": "2025-12-20T19:00:00Z",
                        "party_size": 4,
                        "restaurant_id": 1,
                        "name": "John Smith",
                        "phone_number": "+1234567890",
                        "email": "john@example.com",
                        "special_request": "Window seat preferred",
                        "notes": "VIP customer, birthday celebration",
                        "created_at": "2025-12-13T10:00:00Z",
                        "updated_at": "2025-12-13T10:00:00Z",
                        "history": [
                            {
                                "id": 1,
                                "action": "status_changed",
                                "previous_value": {"status": "pending"},
                                "new_value": {"status": "confirmed"},
                                "change_summary": "Reservation #123 status changed: pending → confirmed",
                                "created_at": "2025-12-13T10:05:00Z",
                            },
                            {
                                "id": 2,
                                "action": "created",
                                "previous_value": None,
                                "new_value": {"status": "pending", "party_size": 4},
                                "change_summary": "Reservation #123 created for 4 guests",
                                "created_at": "2025-12-13T10:00:00Z",
                            },
                        ],
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
    reservation_service: ReservationService = Depends(get_reservation_service),
    history_service: ActivityHistoryService = Depends(get_history_service),
):
    """Get a reservation by ID with authorization check and history."""
    reservation = _check_reservation_access(current_user, reservation_id, reservation_service)

    # Fetch history entries for this reservation
    try:
        history_result = history_service.get_reservation_history(reservation_id, limit=100, offset=0)
        history_entries = [
            {
                "id": entry.get("id"),
                "action": entry.get("action"),
                "previous_value": entry.get("previous_value"),
                "new_value": entry.get("new_value"),
                "change_summary": entry.get("change_summary"),
                "created_at": str(entry.get("created_at")) if entry.get("created_at") else None,
            }
            for entry in history_result.get("entries", [])
        ]
    except Exception as e:
        logger.warning(f"Failed to fetch history for reservation {reservation_id}: {e}")
        history_entries = []

    # Add history to reservation response
    reservation["history"] = history_entries
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
                        "date_time": "2025-12-20T19:30:00Z",
                        "party_size": 6,
                        "restaurant_id": 1,
                        "name": "John Smith",
                        "phone_number": "+1234567890",
                        "email": "john@example.com",
                        "special_request": "Allergic to nuts",
                        "notes": "VIP customer, birthday celebration",
                        "last_cancel_time": "2025-12-20T17:00:00Z",
                        "manage_reservation_url": None,
                        "created_at": "2025-12-13T10:00:00Z",
                        "updated_at": "2025-12-13T12:00:00Z",
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
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(require_role(["admin", "client"])),
    reservation_service: ReservationService = Depends(get_reservation_service),
    history_service: ActivityHistoryService = Depends(get_history_service),
    restaurant_service: RestaurantService = Depends(get_restaurant_service),
    notification_service: NotificationService = Depends(get_notification_service),
):
    """Update reservation and slot booking details."""
    reservation = _check_reservation_access(current_user, reservation_id, reservation_service)
    restaurant_id = reservation.get("restaurant_id")
    old_status = reservation.get("status")
    phone_number = reservation.get("phone_number")
    user_id = reservation.get("user_id")
    confirmation_number = reservation.get("confirmation_number")

    logger.info(
        f"Updating reservation {reservation_id} status: {old_status} -> {request.status if request.status else 'unchanged'}, phone_number={phone_number}, user_id={user_id}"
    )

    # Store previous state for history logging
    previous_data = {
        "status": reservation.get("status"),
        "party_size": reservation.get("party_size"),
        "date_time": str(reservation.get("date_time")) if reservation.get("date_time") else None,
        "special_request": reservation.get("special_request"),
        "notes": reservation.get("notes"),
    }

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

        # Log activity history for reservation update
        try:
            if restaurant_id:
                new_data = {
                    "status": result.get("status"),
                    "party_size": result.get("party_size"),
                    "date_time": str(result.get("date_time")) if result.get("date_time") else None,
                    "special_request": result.get("special_request"),
                    "notes": result.get("notes"),
                }
                history_service.log_reservation_updated(
                    reservation_id=reservation_id,
                    restaurant_id=int(restaurant_id),
                    previous_data=previous_data,
                    new_data=new_data,
                    user_id=result.get("user_id"),
                    performed_by=current_user,
                )
        except Exception as history_error:
            logger.warning(f"Failed to log history for reservation update {reservation_id}: {history_error}")

        # Emit SSE event for reservation update
        if restaurant_id:
            new_status = result.get("status", "")
            event_subtype = (
                ReservationEventSubtype.RESERVATION_CANCELLED
                if new_status.lower() == "cancelled"
                else ReservationEventSubtype.RESERVATION_UPDATED
            )
            background_tasks.add_task(
                _emit_reservation_sse_event,
                restaurant_id=restaurant_id,
                reservation_id=reservation_id,
                subtype=event_subtype,
                data={
                    "reservation_id": reservation_id,
                    "status": new_status,
                    "date_time": result.get("date_time"),
                    "party_size": result.get("party_size"),
                },
            )
            # SMS on status change (when status was updated)
            previous_status = (reservation.get("status") or "").strip().lower()
            current_status = (result.get("status") or "").strip().lower()
            if current_status and previous_status != current_status:
                _queue_reservation_sms(
                    background_tasks,
                    notification_service,
                    restaurant_service,
                    restaurant_id,
                    reservation_id,
                    result.get("status", ""),
                    reservation.get("phone_number"),
                    result.get("confirmation_number"),
                )

            if request.status and request.status != old_status:
                background_tasks.add_task(
                    _send_reservation_notification,
                    restaurant_id=restaurant_id,
                    reservation_id=reservation_id,
                    new_status=request.status,
                    phone_number=phone_number,
                    user_id=user_id,
                    confirmation_number=result.get("confirmation_number") or confirmation_number,
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
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(require_role(["admin", "client"])),
    reservation_service: ReservationService = Depends(get_reservation_service),
    history_service: ActivityHistoryService = Depends(get_history_service),
    restaurant_service: RestaurantService = Depends(get_restaurant_service),
    notification_service: NotificationService = Depends(get_notification_service),
):
    """Cancel a reservation."""
    reservation = _check_reservation_access(current_user, reservation_id, reservation_service)
    restaurant_id = reservation.get("restaurant_id")
    previous_status = reservation.get("status")
    phone_number = reservation.get("phone_number")
    user_id = reservation.get("user_id")
    confirmation_number = reservation.get("confirmation_number")

    logger.info(f"Cancelling reservation {reservation_id}, phone_number={phone_number}, user_id={user_id}")

    try:
        result = reservation_service.cancel_reservation(reservation_id=reservation_id)

        # Log activity history for reservation cancellation
        try:
            if restaurant_id:
                history_service.log_reservation_cancelled(
                    reservation_id=reservation_id,
                    restaurant_id=int(restaurant_id),
                    previous_status=previous_status or "unknown",
                    user_id=reservation.get("user_id"),
                    performed_by=current_user,
                )
        except Exception as history_error:
            logger.warning(f"Failed to log history for reservation cancellation {reservation_id}: {history_error}")

        # Emit SSE event for reservation cancellation
        if restaurant_id:
            background_tasks.add_task(
                _emit_reservation_sse_event,
                restaurant_id=restaurant_id,
                reservation_id=reservation_id,
                subtype=ReservationEventSubtype.RESERVATION_CANCELLED,
                data={
                    "reservation_id": reservation_id,
                    "status": "cancelled",
                },
            )
            # SMS on status change to cancelled
            _queue_reservation_sms(
                background_tasks,
                notification_service,
                restaurant_service,
                restaurant_id,
                reservation_id,
                "cancelled",
                reservation.get("phone_number"),
                reservation.get("confirmation_number") or result.get("confirmation_number"),
            )

            background_tasks.add_task(
                _send_reservation_notification,
                restaurant_id=restaurant_id,
                reservation_id=reservation_id,
                new_status="cancelled",
                phone_number=phone_number,
                user_id=user_id,
                confirmation_number=confirmation_number,
            )

        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error cancelling reservation: {str(e)}")
