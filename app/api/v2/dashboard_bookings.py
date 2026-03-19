"""
Dashboard API routes for in-house booking management.
Includes RBAC: admins can access all, managers can only access their business's bookings.
"""

import json
import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from fastapi.security import HTTPBearer
from pydantic import BaseModel, Field

from app.middleware.auth_middleware import require_role
from app.services.activity_history_service import ActivityHistoryService
from app.services.notification_service import NotificationService
from app.services.booking_service import BookingService
from app.services.business_service import BusinessService
from app.services.sse_service import BookingEventSubtype, SSEService

logger = logging.getLogger(__name__)

security = HTTPBearer(
    scheme_name="HTTPBearer",  # Standardized security scheme name
    description="Enter your JWT access token obtained from login endpoints",
)

router = APIRouter(
    dependencies=[Depends(security)],  # Apply security to all endpoints in this router
)


# ---------- Service dependencies ----------


def get_booking_service() -> BookingService:
    """Dependency to get a fresh booking service instance per request."""
    return BookingService()


def get_sse_service() -> SSEService:
    """Dependency to get SSE service instance."""
    return SSEService()


def get_history_service() -> ActivityHistoryService:
    """Dependency to get activity history service instance."""
    return ActivityHistoryService()


def get_business_service() -> BusinessService:
    """Dependency to get business service instance."""
    return BusinessService()


def get_notification_service() -> NotificationService:
    """Dependency to get notification service instance."""
    return NotificationService()


async def _emit_booking_sse_event(
    business_id: int,
    booking_id: int,
    subtype: BookingEventSubtype,
    data: Dict[str, Any],
) -> None:
    """
    Emit SSE booking event AND persist notification. Non-blocking, failure-tolerant.
    Logs errors but does not raise; SSE and notification persistence are independent.
    """
    try:
        sse_svc = SSEService()
        await sse_svc.emit_booking_event(
            business_id=business_id,
            booking_id=booking_id,
            subtype=subtype,
            data=data,
        )
    except Exception as sse_error:
        logger.error(
            "[SSE] Booking event emission failed for booking %s (%s): %s",
            booking_id,
            subtype.value,
            sse_error,
        )

    try:
        from app.services.notification_persistence_service import NotificationPersistenceService

        notification_service = NotificationPersistenceService()
        notification_service.create_notification(
            business_id=business_id,
            type="booking",
            subtype=subtype.value if hasattr(subtype, "value") else subtype,
            data={"booking_id": booking_id, **(data or {})},
            entity_id=booking_id,
        )
    except Exception as e:
        logger.error(
            "[Notification] Booking notification persistence failed for booking %s: %s",
            booking_id,
            e,
        )


def _queue_booking_sms(
    background_tasks: BackgroundTasks,
    notification_service: NotificationService,
    business_service: BusinessService,
    business_id: Optional[int],
    booking_id: int,
    new_status: str,
    recipient_phone: Optional[str],
    confirmation_number: Optional[str],
) -> None:
    """Queue SMS notification as a background task (non-blocking).

    Restaurant lookup is performed inside the background task to avoid
    blocking the API response on database queries.
    """
    if not business_id or not (recipient_phone and str(recipient_phone).strip()):
        return

    async def _send_booking_sms_notification() -> None:
        try:
            # Restaurant lookup moved inside background task for non-blocking API response
            business = business_service.get_business(business_id)
            if not business:
                logger.warning("Restaurant %s not found for booking SMS", business_id)
                return

            twilio_number = (business.get("twilio_phone_number") or "").strip()
            if not twilio_number:
                logger.debug("No Twilio number configured for business %s", business_id)
                return

            twilio_details = business.get("twilio_details") or {}
            if isinstance(twilio_details, str):
                try:
                    twilio_details = json.loads(twilio_details) if twilio_details else {}
                except json.JSONDecodeError as e:
                    logger.warning(
                        "Invalid JSON in twilio_details for business %s: %s",
                        business_id,
                        e,
                    )
                    twilio_details = {}
                except Exception as e:
                    logger.warning(
                        "Unexpected error parsing twilio_details for business %s: %s",
                        business_id,
                        e,
                    )
                    twilio_details = {}

            sid = twilio_details.get("account_sid") or twilio_details.get("TWILIO_ACCOUNT_SID")
            token = twilio_details.get("auth_token") or twilio_details.get("TWILIO_AUTH_TOKEN")

            await notification_service.send_booking_notification(
                business_id=business_id,
                booking_id=booking_id,
                new_status=new_status,
                recipient_phone=str(recipient_phone).strip(),
                business_name=business.get("name") or "",
                business_twilio_number=twilio_number,
                confirmation_number=confirmation_number,
                twilio_account_sid=sid,
                twilio_auth_token=token,
            )
        except Exception as sms_err:
            logger.warning("SMS notification for booking %s failed: %s", booking_id, sms_err)

    background_tasks.add_task(_send_booking_sms_notification)


# ---------- Pydantic models for request validation ----------


class CreateBookingDirectRequest(BaseModel):
    """Request model for creating a booking directly from the dashboard."""

    date_time: str = Field(
        ...,
        description="Booking date and time in ISO format",
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


class FinalizeBookingRequest(BaseModel):
    """Request model for finalizing a pending booking."""

    confirmation_number: Optional[str] = Field(
        None,
        max_length=100,
        description="Optional confirmation number override",
        json_schema_extra={"example": "INH-1-CUSTOM123"},
    )


class UpdateBookingRequest(BaseModel):
    """Request model for updating booking and slot booking details."""

    # Slot booking fields (from slot_bookings table)
    date_time: Optional[str] = Field(
        None,
        description="Booking date and time in ISO format (updates slot_bookings.date_time)",
        json_schema_extra={"example": "2025-12-20T19:30:00Z"},
    )

    # Booking fields (from bookings table)
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
        description="Booking status (pending, confirmed, cancelled, completed, no_show)",
        json_schema_extra={"example": "confirmed"},
    )
    last_cancel_time: Optional[str] = Field(
        None,
        description="Last time booking can be cancelled (ISO format)",
        json_schema_extra={"example": "2025-12-20T17:00:00Z"},
    )
    manage_booking_url: Optional[str] = Field(
        None,
        max_length=500,
        description="URL for managing booking",
        json_schema_extra={"example": "https://example.com/manage/abc123"},
    )


class HistoryEntryResponse(BaseModel):
    """Response model for a history entry in booking detail."""

    id: int = Field(..., description="History entry ID")
    action: str = Field(..., description="Action performed (created, updated, cancelled, etc.)")
    previous_value: Optional[Dict[str, Any]] = Field(None, description="Previous state")
    new_value: Optional[Dict[str, Any]] = Field(None, description="New state")
    change_summary: Optional[str] = Field(None, description="Human-readable summary")
    created_at: str = Field(..., description="Timestamp of the action")


# ---------- Helper functions for RBAC ----------


def _check_business_access(current_user: dict, business_id: int):
    """
    Check if the current user has access to the specified business.
    Admins have access to all businesss.
    Restaurant users (managers) can only access their own business.

    Args:
        current_user: JWT claims dict containing user_type, business_id (for business users)
        business_id: The business ID to check access for (from path param or booking)

    Raises:
        HTTPException 403: If user doesn't have access to this business
    """
    user_type = current_user.get("user_type")

    # Admins (Ressy platform admins) can access all businesss
    if user_type == "admin":
        return

    # Restaurant users (managers/staff) can only access their own business
    if user_type == "business":
        user_business_id = current_user.get("business_id")

        # Check if user has a business assigned
        if user_business_id is None:
            raise HTTPException(
                status_code=403,
                detail="Your account is not associated with any business",
            )

        # Compare as integers to handle string/int type differences from JWT
        if int(user_business_id) != int(business_id):
            raise HTTPException(
                status_code=403,
                detail=f"You can only access bookings for your own business (ID: {user_business_id})",
            )
        return

    raise HTTPException(status_code=403, detail="Access denied - unknown user type")


def _check_booking_access(current_user: dict, booking_id: int, booking_service: BookingService):
    """
    Check if the current user has access to the specified booking.
    Fetches the booking with its associated business_id from slot_bookings
    and validates that the user has access to that business.

    The business_id is obtained from the slot_bookings table via JOIN since
    the bookings table doesn't have a direct business_id column.

    Args:
        current_user: JWT claims dict
        booking_id: The booking ID to check access for
        booking_service: The booking service instance to use

    Returns:
        The booking dict if access is granted

    Raises:
        HTTPException 404: If booking not found
        HTTPException 403: If user doesn't have access
        HTTPException 500: If booking has no associated business
    """
    try:
        booking = booking_service.get_booking_with_business_check(booking_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    # business_id comes from slot_bookings table via JOIN
    business_id = booking.get("business_id")

    if business_id is None:
        raise HTTPException(
            status_code=500,
            detail="Booking has no associated business - slot_booking may be missing or corrupted",
        )

    _check_business_access(current_user, business_id)
    return booking


# ---------- CREATE RESERVATION (Dashboard Only) ----------
@router.post(
    "/businesss/{business_id}/bookings",
    summary="Create a confirmed booking (Dashboard only)",
    description="""
Create a new booking directly from the dashboard with confirmed status.

This endpoint performs slot booking and booking creation in a single transaction,
making it ideal for walk-in customers or phone bookings managed by staff.

**Authentication**: Required (admin or business manager role)

**Authorization**:
- Admins can create bookings for any business
- Restaurant managers can only create bookings for their own business

**Request Body**:
- `date_time`: Booking date and time in ISO format
- `party_size`: Number of guests (1-20)
- `name`: Guest's full name
- `phone_number`: Guest's phone number
- `email_address`: Guest's email (optional)
- `special_request`: Special requests from the guest (optional)
- `notes`: Internal notes for staff (optional)
""",
    response_description="Created and confirmed booking with all details",
    responses={
        200: {
            "description": "Booking created successfully",
            "content": {
                "application/json": {
                    "example": {
                        "booking_id": 123,
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
                        "message": "Booking created and confirmed successfully",
                    }
                }
            },
        },
        400: {"description": "Invalid request data or slot already booked"},
        403: {"description": "Access denied - cannot access this business's bookings"},
        404: {"description": "Restaurant not found"},
    },
)
async def create_booking_direct(
    business_id: int,
    request: CreateBookingDirectRequest,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(require_role(["admin", "client"])),
    booking_service: BookingService = Depends(get_booking_service),
    history_service: ActivityHistoryService = Depends(get_history_service),
    business_service: BusinessService = Depends(get_business_service),
    notification_service: NotificationService = Depends(get_notification_service),
):
    """Create a confirmed booking directly from the dashboard."""
    _check_business_access(current_user, business_id)

    try:
        result = booking_service.create_booking_direct(
            business_id=business_id,
            date_time=request.date_time,
            party_size=request.party_size,
            name=request.name,
            phone_number=request.phone_number,
            email_address=request.email_address,
            special_request=request.special_request,
            notes=request.notes,
        )

        # Log activity history for booking creation
        try:
            history_service.log_booking_created(
                booking_id=result["booking_id"],
                business_id=int(business_id),
                booking_data={
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
                f"Failed to log history for booking creation {result['booking_id']}: {history_error}"
            )

        # Emit SSE event for new booking (background task, properly managed by FastAPI)
        background_tasks.add_task(
            _emit_booking_sse_event,
            business_id=business_id,
            booking_id=result["booking_id"],
            subtype=BookingEventSubtype.NEW_BOOKING,
            data={
                "booking_id": result["booking_id"],
                "confirmation_number": result.get("confirmation_number"),
                "status": result.get("status"),
                "date_time": result.get("date_time"),
                "party_size": result.get("party_size"),
                "name": result.get("name"),
            },
        )

        # SMS on booking created (status confirmed)
        _queue_booking_sms(
            background_tasks,
            notification_service,
            business_service,
            business_id,
            result["booking_id"],
            result.get("status", "confirmed"),
            request.phone_number,
            result.get("confirmation_number"),
        )

        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creating booking: {str(e)}")


# ---------- FINALIZE RESERVATION (Dashboard Only) ----------
@router.put(
    "/bookings/{booking_id}/finalize",
    summary="Finalize a pending booking (Dashboard only)",
    description="""
Finalize a booking by changing its status from 'pending' to 'confirmed'.

This is used for bookings created through the voice agent or API that require
manual confirmation by business staff.

**Authentication**: Required (admin or business manager role)

**Authorization**:
- Admins can finalize bookings for any business
- Restaurant managers can only finalize bookings for their own business
""",
    response_description="Finalized booking with confirmed status",
    responses={
        200: {
            "description": "Booking finalized successfully",
            "content": {
                "application/json": {
                    "example": {
                        "booking_id": 123,
                        "confirmation_number": "INH-1-A1B2C3D4",
                        "status": "confirmed",
                        "message": "Booking confirmed successfully",
                    }
                }
            },
        },
        400: {"description": "Booking is not in pending status"},
        403: {"description": "Access denied - cannot access this business's bookings"},
        404: {"description": "Booking not found"},
    },
)
async def finalize_booking(
    booking_id: int,
    request: FinalizeBookingRequest,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(require_role(["admin", "client"])),
    booking_service: BookingService = Depends(get_booking_service),
    business_service: BusinessService = Depends(get_business_service),
    notification_service: NotificationService = Depends(get_notification_service),
):
    """Finalize a booking by changing status from 'pending' to 'confirmed'."""
    booking = _check_booking_access(current_user, booking_id, booking_service)

    try:
        result = booking_service.finalize_booking(
            booking_id=booking_id, confirmation_number=request.confirmation_number
        )
        # SMS on status change to confirmed
        _queue_booking_sms(
            background_tasks,
            notification_service,
            business_service,
            booking.get("business_id"),
            booking_id,
            result.get("status", "confirmed"),
            booking.get("phone_number"),
            result.get("confirmation_number"),
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error finalizing booking: {str(e)}")


# ---------- GET RESERVATIONS BY RESTAURANT (Dashboard) ----------
@router.get(
    "/businesss/{business_id}/bookings",
    summary="Get bookings for a business (Dashboard)",
    description="""
Retrieve all bookings for a specific business with optional filters.

**Authentication**: Required (admin or business manager role)

**Authorization**:
- Admins can view bookings for any business
- Restaurant managers can only view bookings for their own business

**Query Parameters**:
- `status`: Filter by status (pending, confirmed, cancelled, completed)
- `start_date`: Filter bookings from this date (ISO format)
- `end_date`: Filter bookings until this date (ISO format)
- `limit`: Maximum number of results (default: 100, max: 1000)
- `offset`: Pagination offset (default: 0)
""",
    response_description="List of bookings with customer and booking details",
    responses={
        200: {
            "description": "Bookings retrieved successfully",
            "content": {
                "application/json": {
                    "example": {
                        "business_id": 1,
                        "bookings": [
                            {
                                "id": 123,
                                "booking_type": "in-house",
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
        403: {"description": "Access denied - cannot access this business's bookings"},
    },
)
async def get_business_bookings(
    business_id: int,
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
    booking_service: BookingService = Depends(get_booking_service),
):
    """Get bookings for a business with optional filters."""
    _check_business_access(current_user, business_id)

    try:
        result = booking_service.get_bookings_by_business(
            business_id=business_id,
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
        raise HTTPException(status_code=500, detail=f"Error fetching bookings: {str(e)}")


# ---------- GET RESERVATION BY ID (Dashboard) ----------
@router.get(
    "/bookings/{booking_id}",
    summary="Get a booking by ID (Dashboard)",
    description="""
Retrieve detailed information about a specific booking, including its change history.

**Authentication**: Required (admin or business manager role)

**Authorization**:
- Admins can view any booking
- Restaurant managers can only view bookings for their own business

**History**: The `history` field contains an array of all changes made to this booking,
ordered from most recent to oldest. Each entry includes the action performed,
previous and new values, and a human-readable summary.
""",
    response_description="Booking details including customer information, notes, and change history",
    responses={
        200: {
            "description": "Booking retrieved successfully",
            "content": {
                "application/json": {
                    "example": {
                        "id": 123,
                        "booking_type": "in-house",
                        "slot_booking_id": 456,
                        "user_id": 789,
                        "confirmation_number": "INH-1-A1B2C3D4",
                        "status": "confirmed",
                        "date_time": "2025-12-20T19:00:00Z",
                        "party_size": 4,
                        "business_id": 1,
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
                                "change_summary": "Booking #123 status changed: pending → confirmed",
                                "created_at": "2025-12-13T10:05:00Z",
                            },
                            {
                                "id": 2,
                                "action": "created",
                                "previous_value": None,
                                "new_value": {"status": "pending", "party_size": 4},
                                "change_summary": "Booking #123 created for 4 guests",
                                "created_at": "2025-12-13T10:00:00Z",
                            },
                        ],
                    }
                }
            },
        },
        403: {"description": "Access denied - cannot access this business's bookings"},
        404: {"description": "Booking not found"},
    },
)
async def get_booking_dashboard(
    booking_id: int,
    current_user: dict = Depends(require_role(["admin", "client"])),
    booking_service: BookingService = Depends(get_booking_service),
    history_service: ActivityHistoryService = Depends(get_history_service),
):
    """Get a booking by ID with authorization check and history."""
    booking = _check_booking_access(current_user, booking_id, booking_service)

    # Fetch history entries for this booking
    try:
        history_result = history_service.get_booking_history(booking_id, limit=100, offset=0)
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
        logger.warning(f"Failed to fetch history for booking {booking_id}: {e}")
        history_entries = []

    # Add history to booking response
    booking["history"] = history_entries
    return booking


# ---------- UPDATE RESERVATION (Dashboard) ----------
@router.put(
    "/bookings/{booking_id}",
    summary="Update a booking (Dashboard)",
    description="""
Update booking details including slot timing.

**Authentication**: Required (admin or business manager role)

**Authorization**:
- Admins can update any booking
- Restaurant managers can only update bookings for their own business

**Updatable Fields**:

*Slot Booking (timing):*
- `date_time`: Booking date and time (ISO format) - updates the slot timing

*Booking Details:*
- `party_size`: Number of guests
- `special_request`: Guest's special requests
- `notes`: Internal staff notes
- `confirmation_number`: Override confirmation number
- `status`: Booking status (pending, confirmed, cancelled, completed, no_show)
- `last_cancel_time`: Deadline for cancellation
- `manage_booking_url`: URL for booking management

**Note**: Only provided fields will be updated. Omit fields you don't want to change.
""",
    response_description="Updated booking with all details",
    responses={
        200: {
            "description": "Booking updated successfully",
            "content": {
                "application/json": {
                    "example": {
                        "id": 123,
                        "booking_type": "in-house",
                        "slot_booking_id": 456,
                        "user_id": 789,
                        "confirmation_number": "INH-1-A1B2C3D4",
                        "status": "confirmed",
                        "date_time": "2025-12-20T19:30:00Z",
                        "party_size": 6,
                        "business_id": 1,
                        "name": "John Smith",
                        "phone_number": "+1234567890",
                        "email": "john@example.com",
                        "special_request": "Allergic to nuts",
                        "notes": "VIP customer, birthday celebration",
                        "last_cancel_time": "2025-12-20T17:00:00Z",
                        "manage_booking_url": None,
                        "created_at": "2025-12-13T10:00:00Z",
                        "updated_at": "2025-12-13T12:00:00Z",
                    }
                }
            },
        },
        400: {"description": "Invalid request data, status value, or time slot conflict"},
        403: {"description": "Access denied - cannot access this business's bookings"},
        404: {"description": "Booking not found"},
    },
)
async def update_booking(
    booking_id: int,
    request: UpdateBookingRequest,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(require_role(["admin", "client"])),
    booking_service: BookingService = Depends(get_booking_service),
    history_service: ActivityHistoryService = Depends(get_history_service),
    business_service: BusinessService = Depends(get_business_service),
    notification_service: NotificationService = Depends(get_notification_service),
):
    """Update booking and slot booking details."""
    booking = _check_booking_access(current_user, booking_id, booking_service)
    business_id = booking.get("business_id")
    # Store previous state for history logging
    previous_data = {
        "status": booking.get("status"),
        "party_size": booking.get("party_size"),
        "date_time": str(booking.get("date_time")) if booking.get("date_time") else None,
        "special_request": booking.get("special_request"),
        "notes": booking.get("notes"),
    }

    try:
        result = booking_service.update_booking(
            booking_id=booking_id,
            date_time=request.date_time,
            party_size=request.party_size,
            special_request=request.special_request,
            notes=request.notes,
            confirmation_number=request.confirmation_number,
            status=request.status,
            last_cancel_time=request.last_cancel_time,
            manage_booking_url=request.manage_booking_url,
        )

        # Log activity history for booking update
        try:
            if business_id:
                new_data = {
                    "status": result.get("status"),
                    "party_size": result.get("party_size"),
                    "date_time": str(result.get("date_time")) if result.get("date_time") else None,
                    "special_request": result.get("special_request"),
                    "notes": result.get("notes"),
                }
                history_service.log_booking_updated(
                    booking_id=booking_id,
                    business_id=int(business_id),
                    previous_data=previous_data,
                    new_data=new_data,
                    user_id=result.get("user_id"),
                    performed_by=current_user,
                )
        except Exception as history_error:
            logger.warning(f"Failed to log history for booking update {booking_id}: {history_error}")

        # Emit SSE event for booking update
        if business_id:
            new_status = result.get("status", "")
            event_subtype = (
                BookingEventSubtype.BOOKING_CANCELLED
                if new_status.lower() == "cancelled"
                else BookingEventSubtype.BOOKING_UPDATED
            )
            background_tasks.add_task(
                _emit_booking_sse_event,
                business_id=business_id,
                booking_id=booking_id,
                subtype=event_subtype,
                data={
                    "booking_id": booking_id,
                    "status": new_status,
                    "date_time": result.get("date_time"),
                    "party_size": result.get("party_size"),
                },
            )
            # SMS on status change (when status was updated)
            previous_status = (booking.get("status") or "").strip().lower()
            current_status = (result.get("status") or "").strip().lower()
            if current_status and previous_status != current_status:
                _queue_booking_sms(
                    background_tasks,
                    notification_service,
                    business_service,
                    business_id,
                    booking_id,
                    result.get("status", ""),
                    booking.get("phone_number"),
                    result.get("confirmation_number"),
                )

        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error updating booking: {str(e)}")


# ---------- CANCEL RESERVATION (Dashboard) ----------
@router.put(
    "/bookings/{booking_id}/cancel",
    summary="Cancel a booking (Dashboard)",
    description="""
Cancel a booking by changing its status to 'cancelled'.

This action will also release the associated time slot, making it available
for new bookings.

**Authentication**: Required (admin or business manager role)

**Authorization**:
- Admins can cancel any booking
- Restaurant managers can only cancel bookings for their own business

**Note**: Only bookings with 'pending' or 'confirmed' status can be cancelled.
""",
    response_description="Cancellation confirmation",
    responses={
        200: {
            "description": "Booking cancelled successfully",
            "content": {
                "application/json": {
                    "example": {
                        "booking_id": 123,
                        "status": "cancelled",
                        "message": "Booking cancelled successfully",
                    }
                }
            },
        },
        400: {"description": "Cannot cancel booking (already cancelled or completed)"},
        403: {"description": "Access denied - cannot access this business's bookings"},
        404: {"description": "Booking not found"},
    },
)
async def cancel_booking_dashboard(
    booking_id: int,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(require_role(["admin", "client"])),
    booking_service: BookingService = Depends(get_booking_service),
    history_service: ActivityHistoryService = Depends(get_history_service),
    business_service: BusinessService = Depends(get_business_service),
    notification_service: NotificationService = Depends(get_notification_service),
):
    """Cancel a booking."""
    booking = _check_booking_access(current_user, booking_id, booking_service)
    business_id = booking.get("business_id")
    previous_status = booking.get("status")

    try:
        result = booking_service.cancel_booking(booking_id=booking_id)

        # Log activity history for booking cancellation
        try:
            if business_id:
                history_service.log_booking_cancelled(
                    booking_id=booking_id,
                    business_id=int(business_id),
                    previous_status=previous_status or "unknown",
                    user_id=booking.get("user_id"),
                    performed_by=current_user,
                )
        except Exception as history_error:
            logger.warning(f"Failed to log history for booking cancellation {booking_id}: {history_error}")

        # Emit SSE event for booking cancellation
        if business_id:
            background_tasks.add_task(
                _emit_booking_sse_event,
                business_id=business_id,
                booking_id=booking_id,
                subtype=BookingEventSubtype.BOOKING_CANCELLED,
                data={
                    "booking_id": booking_id,
                    "status": "cancelled",
                },
            )
            # SMS on status change to cancelled
            _queue_booking_sms(
                background_tasks,
                notification_service,
                business_service,
                business_id,
                booking_id,
                "cancelled",
                booking.get("phone_number"),
                booking.get("confirmation_number") or result.get("confirmation_number"),
            )

        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error cancelling booking: {str(e)}")
