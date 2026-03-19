"""Booking-related function implementations backed by BookingService."""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from pydantic import BaseModel, ConfigDict

from app.agent_fc.functions.common_business import load_business
from app.agent_fc.functions.function_context import (
    NoArgs,
    context_customer_contact,
    context_business_id,
    split_call_context,
)
from app.config import settings
from app.repositories.mysql_booking_repo import MySQLBookingRepository
from app.repositories.mysql_business_repo import MySQLBusinessRepository
from app.repositories.mysql_user_repo import MySQLUserRepository
from app.repositories.mysql_user_business_metadata_repo import (
    MySQLUserRestaurantMetadataRepository,
)
from app.services.business_activity_history_service import BusinessActivityHistoryService
from app.services.business_notification_service import BusinessNotificationService
from app.services.booking_service import BookingService
from app.services.sse_service import BookingEventSubtype, SSEService
from app.utils.business_hours import (
    format_nearest_slot_label,
    format_operating_window,
    is_datetime_on_slot_boundary,
    is_datetime_within_operating_hours,
    resolve_business_timezone,
    snap_datetime_to_slot,
)
from app.utils.timezone import coerce_datetime, isoformat_z, parse_datetime

logger = logging.getLogger(__name__)


# ---------- Repository/Service Factory Functions ----------
# Create fresh instances per function call to ensure up-to-date data
# during active voice calls. This fixes mid-call updates not being detected.


def _get_booking_repo() -> MySQLBookingRepository:
    """Create fresh booking repository instance per function call."""
    return MySQLBookingRepository()


def _get_business_repo() -> MySQLBusinessRepository:
    """Create fresh business repository instance per function call."""
    return MySQLBusinessRepository()


def _get_user_repo() -> MySQLUserRepository:
    """Create fresh user repository instance per function call."""
    return MySQLUserRepository()


def _get_metadata_repo() -> MySQLUserRestaurantMetadataRepository:
    """Create fresh metadata repository instance per function call."""
    return MySQLUserRestaurantMetadataRepository()


def _get_history_service() -> BusinessActivityHistoryService:
    """Create fresh history service instance per function call."""
    return BusinessActivityHistoryService()


def _get_sse_service() -> SSEService:
    """Create fresh SSE service instance per function call."""
    return SSEService()


async def _emit_booking_sse_event(
    business_id: int,
    booking_id: int,
    subtype: BookingEventSubtype,
    data: Dict[str, Any],
) -> None:
    """
    Emit SSE booking event AND persist notification. Non-blocking, failure-tolerant.
    """
    try:
        sse_service = _get_sse_service()
        await sse_service.emit_booking_event(
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
        notification_service = BusinessNotificationService()
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


async def _send_voice_booking_sms(
    business: Dict[str, Any],
    booking_id: int,
    phone_number: str,
    confirmation_number: Optional[str] = None,
) -> None:
    """Send SMS notification for voice-agent-created booking.

    This is a fire-and-forget background task - SMS failures should not
    affect the voice call or booking creation.
    """
    import json

    try:
        twilio_number = (business.get("twilio_phone_number") or "").strip()
        if not twilio_number:
            logger.debug("No Twilio number configured for business %s", business.get("id"))
            return

        twilio_details = business.get("twilio_details") or {}
        if isinstance(twilio_details, str):
            try:
                twilio_details = json.loads(twilio_details) if twilio_details else {}
            except json.JSONDecodeError as e:
                logger.warning(
                    "Invalid JSON in twilio_details for business %s: %s",
                    business.get("id"),
                    e,
                )
                twilio_details = {}
            except Exception as e:
                logger.warning(
                    "Unexpected error parsing twilio_details for business %s: %s",
                    business.get("id"),
                    e,
                )
                twilio_details = {}

        sid = twilio_details.get("account_sid") or twilio_details.get("TWILIO_ACCOUNT_SID")
        token = twilio_details.get("auth_token") or twilio_details.get("TWILIO_AUTH_TOKEN")

        notification_service = BusinessNotificationService()
        await notification_service.send_booking_notification(
            business_id=business.get("id"),
            booking_id=booking_id,
            new_status="pending",  # Voice-created bookings start as pending
            recipient_phone=phone_number,
            business_name=business.get("name") or "",
            business_twilio_number=twilio_number,
            confirmation_number=confirmation_number,
            twilio_account_sid=sid,
            twilio_auth_token=token,
        )
        logger.info("SMS sent for voice booking %s", booking_id)
    except Exception as e:
        # Don't fail the voice call if SMS fails - just log
        logger.warning("Failed to send SMS for voice booking %s: %s", booking_id, e)


class CreateBookingArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    party_size: int
    datetime_iso: str
    customer_name: Optional[str] = None
    occasion: Optional[str] = None
    special_request: Optional[str] = None
    notes: Optional[str] = None


class UpdateBookingArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    customer_name: Optional[str] = None
    party_size: Optional[int] = None
    datetime_iso: Optional[str] = None
    special_request: Optional[str] = None
    notes: Optional[str] = None
    status: Optional[str] = None  # Allow status changes (e.g., "cancelled") within update window


class CheckAvailabilityArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    party_size: int
    date_start_iso: str


async def _run_service_call(func, *args, **kwargs):
    return await asyncio.to_thread(func, *args, **kwargs)


def _parse_datetime_str(value: str) -> datetime:
    """Parse ISO-ish datetime strings used by the agent."""
    try:
        return parse_datetime(value)
    except ValueError:
        naive = datetime.strptime(value, "%Y-%m-%d %H:%M")
        return naive.replace(tzinfo=timezone.utc)


def _coerce_datetime(value: Any) -> Optional[datetime]:
    """Convert DB or payload datetime representations to datetime."""
    return coerce_datetime(value)


def _generate_confirmation_number() -> str:
    """Generate a unique confirmation number for a booking."""
    return f"RES-{uuid.uuid4().hex[:8].upper()}"


async def create_booking(**kwargs) -> Dict[str, Any]:
    """
    Create a new booking for a customer.

    Flow:
    1. Validate capacity and advance booking limits
    2. Create or update user with customer details
    3. Create slot booking and booking in a single transaction
    4. Return booking details with pending status (business will confirm)
    """
    context, model_kwargs = split_call_context(kwargs, CreateBookingArgs)
    args = CreateBookingArgs.model_validate(model_kwargs)
    call_sid = context.get("call_sid")
    business_id = context_business_id(context)
    customer_contact = context_customer_contact(context)
    if business_id is None:
        return {"status": "FAILED", "message": "Missing business context."}
    if not customer_contact:
        return {"status": "FAILED", "message": "Missing caller contact context."}
    logger.info(
        "create_booking invoked business_id=%s party_size=%s call_sid=%s",
        business_id,
        args.party_size,
        call_sid,
    )
    business = await load_business(business_id)
    if not business:
        return {
            "status": "FAILED",
            "message": "Unable to load business information right now. Please try again shortly.",
        }
    try:
        booking_datetime = _parse_datetime_str(args.datetime_iso)
        booking_iso = isoformat_z(booking_datetime)
    except ValueError:
        return {
            "status": "FAILED",
            "message": "Invalid booking time format. Please provide a valid date and time.",
        }
    if not is_datetime_within_operating_hours(business, booking_datetime):
        tz_label = resolve_business_timezone(business)[1]
        return {
            "status": "OUT_OF_HOURS",
            "message": (
                "The requested booking time is outside the business's operating hours. "
                f"Please choose a time between {format_operating_window(business)} ({tz_label})."
            ),
        }

    # Validate advance booking limit
    advance_days = business.get("booking_advance_days", 30)
    max_booking_date = datetime.now(timezone.utc) + timedelta(days=advance_days)
    booking_dt_utc = booking_datetime
    if booking_datetime.tzinfo is None:
        booking_dt_utc = booking_datetime.replace(tzinfo=timezone.utc)
    if booking_dt_utc > max_booking_date:
        return {
            "status": "ADVANCE_BOOKING_EXCEEDED",
            "message": (
                f"Bookings can only be made up to {advance_days} days in advance. " "Please choose an earlier date."
            ),
        }

    # Check capacity - only confirmed bookings count against capacity
    seating_capacity = business.get("booking_seating_capacity", 50)

    def _check_capacity():
        booking_repo = _get_booking_repo()
        # Normalize datetime to minute precision for slot matching
        slot_dt = booking_datetime.replace(second=0, microsecond=0)
        if slot_dt.tzinfo:
            slot_dt = slot_dt.replace(tzinfo=None)
        used_capacity = booking_repo.get_slot_confirmed_capacity(
            business_id=business_id,
            date_time=slot_dt,
            booking_type="in-house",
        )
        return seating_capacity - used_capacity

    available_capacity = await _run_service_call(_check_capacity)
    if args.party_size > available_capacity:
        return {
            "status": "CAPACITY_EXCEEDED",
            "message": (
                f"Sorry, we cannot accommodate a party of {args.party_size} at that time. "
                f"We have space for up to {available_capacity} guests. "
                "Would you like to try a different time or a smaller party size?"
            ),
            "available_capacity": available_capacity,
            "requested_party_size": args.party_size,
        }

    def _create():
        # Create fresh repository instances for this operation
        user_repo = _get_user_repo()
        metadata_repo = _get_metadata_repo()
        booking_repo = _get_booking_repo()

        # 1. Create or update user with customer details
        user_id = user_repo.create_or_update_user(
            {
                "name": args.customer_name,
                "phone_number": customer_contact,
                "email": None,
                "address": None,
                "is_spam": False,
                "credit_card": None,
            }
        )

        # 1.5. Create user-business metadata mapping (for dashboard user visibility)
        try:
            metadata_repo.create_mapping(
                user_id=user_id,
                business_id=business_id,
                source="booking",
                notes="Created via voice agent booking",
            )
        except Exception as meta_err:
            # Log but don't fail booking creation if metadata mapping fails
            logger.warning("Failed to create user-business metadata call_sid=%s: %s", call_sid, meta_err)

        # 3. Generate confirmation number and booking token
        confirmation_number = _generate_confirmation_number()
        booking_token = str(uuid.uuid4())

        # 4. Combine special request and occasion into notes if provided
        combined_notes = []
        if args.occasion:
            combined_notes.append(f"Occasion: {args.occasion}")
        if args.special_request:
            combined_notes.append(f"Special request: {args.special_request}")
        if args.notes:
            combined_notes.append(args.notes)
        final_notes = " | ".join(combined_notes) if combined_notes else None

        # 5. Create slot booking with expires_at = date_time + 15 minutes
        expires_at = booking_datetime + timedelta(minutes=15)
        slot_id = booking_repo.create_booking_slot(
            business_id=business_id,
            date_time=booking_datetime,
            expires_at=expires_at,
            booking_token=booking_token,
            booking_type="in-house",
            status="reserved",
            party_size=args.party_size,
        )

        # 6. Create booking with status = "pending" (business will confirm)
        booking_id = booking_repo.create_booking(
            slot_booking_id=slot_id,
            user_id=user_id,
            confirmation_number=confirmation_number,
            booking_type="in-house",
            status="pending",
            special_request=args.special_request,
            party_size=args.party_size,
            notes=final_notes,
        )

        return {
            "booking_id": booking_id,
            "slot_id": slot_id,
            "user_id": user_id,
            "confirmation_number": confirmation_number,
            "party_size": args.party_size,
            "datetime": booking_iso,
            "customer_name": args.customer_name,
            "customer_contact": customer_contact,
            "occasion": args.occasion,
            "special_request": args.special_request,
            "notes": final_notes,
        }

    try:
        booking = await _run_service_call(_create)

        # Log activity history for voice agent booking creation (run in thread since it's a DB operation)
        def _log_history():
            try:
                logger.debug(
                    "[DEBUG] Logging booking creation history: booking_id=%s, business_id=%s",
                    booking["booking_id"],
                    business_id,
                )
                history_service = _get_history_service()
                history_id = history_service.log_booking_created(
                    booking_id=booking["booking_id"],
                    business_id=business_id,
                    booking_data={
                        "status": "pending",
                        "party_size": args.party_size,
                        "date_time": booking_iso,
                        "name": args.customer_name,
                    },
                    user_id=booking.get("user_id"),
                )
                logger.info("Activity history logged for booking creation: history_id=%s", history_id)
            except Exception as history_error:
                logger.exception(
                    "[ERROR] Failed to log history for voice agent booking creation call_sid=%s: %s",
                    call_sid,
                    history_error,
                )

        await _run_service_call(_log_history)

        # Emit SSE event for new booking (background task)
        asyncio.create_task(
            _emit_booking_sse_event(
                business_id=business_id,
                booking_id=booking["booking_id"],
                subtype=BookingEventSubtype.NEW_BOOKING,
                data={
                    "booking_id": booking["booking_id"],
                    "confirmation_number": booking.get("confirmation_number"),
                    "status": "pending",
                    "date_time": booking_iso,
                    "party_size": args.party_size,
                    "name": args.customer_name,
                },
            )
        )

        # Send SMS notification for voice-created booking (background task)
        if customer_contact:
            asyncio.create_task(
                _send_voice_booking_sms(
                    business=business,
                    booking_id=booking["booking_id"],
                    phone_number=customer_contact,
                    confirmation_number=booking.get("confirmation_number"),
                )
            )

        return {
            "status": "SUBMITTED",
            "message": "Booking request submitted. The business will confirm shortly.",
            "booking": booking,
        }
    except Exception as exc:
        logger.exception("[ERROR] create_booking failed: %s", exc)
        return {
            "status": "FAILED",
            "message": "Unable to create booking. Please try again or contact the business directly.",
            "error": str(exc),
        }


async def lookup_booking(**kwargs) -> Dict[str, Any]:
    """
    Look up the latest booking for a caller using their phone number.
    Similar to lookup_order but for bookings.
    """
    context, model_kwargs = split_call_context(kwargs, NoArgs)
    NoArgs.model_validate(model_kwargs)
    call_sid = context.get("call_sid")
    business_id = context_business_id(context)
    customer_contact = context_customer_contact(context)
    if business_id is None:
        return {"status": "FAILED", "message": "Missing business context."}
    if not customer_contact:
        return {"status": "FAILED", "message": "Missing caller contact context."}
    logger.info("lookup_booking invoked customer_contact=%s call_sid=%s", customer_contact, call_sid)

    def _lookup():
        user_repo = _get_user_repo()
        booking_repo = _get_booking_repo()

        # Find user by phone number
        user_id = user_repo.get_user_id_by_phone_or_email(customer_contact, None)
        if not user_id:
            return None

        # Get the latest booking for this user
        booking = booking_repo.get_latest_by_user(user_id, business_id=business_id)
        return booking

    booking = await _run_service_call(_lookup)
    if not booking:
        return {
            "status": "NOT_FOUND",
            "message": "Sorry, no booking found for your phone number at this business.",
        }
    return {"status": "FOUND", "booking": booking}


def _is_within_update_window(created_at: Any) -> bool:
    """
    Check if a booking is within the allowed update window.

    Args:
        created_at: The created_at timestamp (datetime or string)

    Returns:
        True if the booking can still be updated, False otherwise
    """
    if created_at is None:
        return False

    now = datetime.now(timezone.utc)
    update_window_seconds = settings.AGENT_UPDATE_WINDOW_SECONDS

    # Handle different formats of created_at
    created_at = coerce_datetime(created_at)
    if created_at is None:
        return False

    elapsed_seconds = (now - created_at).total_seconds()
    return elapsed_seconds <= update_window_seconds


async def update_booking(**kwargs) -> Dict[str, Any]:
    """
    Update the latest booking for a caller using their phone number.
    """
    context, model_kwargs = split_call_context(kwargs, UpdateBookingArgs)
    args = UpdateBookingArgs.model_validate(model_kwargs)
    call_sid = context.get("call_sid")
    business_id = context_business_id(context)
    customer_contact = context_customer_contact(context)
    if business_id is None:
        return {"status": "FAILED", "message": "Missing business context."}
    if not customer_contact:
        return {"status": "FAILED", "message": "Missing caller contact context."}
    logger.info("update_booking invoked customer_contact=%s call_sid=%s", customer_contact, call_sid)
    business = await load_business(business_id)
    if not business:
        return {
            "status": "FAILED",
            "message": "Unable to load business information right now. Please try again shortly.",
        }
    new_datetime: Optional[datetime] = None
    if args.datetime_iso:
        try:
            new_datetime = _parse_datetime_str(args.datetime_iso)
        except ValueError:
            return {
                "status": "FAILED",
                "message": "Invalid booking time format. Please provide a valid date and time.",
            }

    def _update():
        user_repo = _get_user_repo()
        booking_repo = _get_booking_repo()

        user_id = user_repo.get_user_id_by_phone_or_email(customer_contact, None)
        if not user_id:
            return None, None, None
        booking = booking_repo.get_latest_by_user(user_id, business_id=business_id)
        if not booking:
            return None, None, None

        booking_id = booking.get("id")
        if not booking_id:
            return None, None, None

        # Check if booking is within the allowed update window
        created_at = booking.get("created_at")
        if not _is_within_update_window(created_at):
            return "UPDATE_WINDOW_EXPIRED", None, booking

        candidate_datetime = new_datetime or _coerce_datetime(booking.get("date_time"))
        if candidate_datetime is None:
            return "INVALID_DATETIME", None, booking
        if not is_datetime_within_operating_hours(business, candidate_datetime):
            return "OUT_OF_HOURS", None, booking

        new_party_size = args.party_size or booking.get("party_size", 1)
        if new_datetime or args.party_size:
            seating_capacity = business.get("booking_seating_capacity", 50)
            slot_dt = candidate_datetime.replace(second=0, microsecond=0)
            if slot_dt.tzinfo:
                slot_dt = slot_dt.replace(tzinfo=None)
                used_capacity = booking_repo.get_slot_confirmed_capacity(
                    business_id=business_id,
                    date_time=slot_dt,
                    booking_type="in-house",
                )
            current_party_size = booking.get("party_size", 0)
            if booking.get("status") == "confirmed":
                used_capacity -= current_party_size
            available_capacity = seating_capacity - used_capacity
            if new_party_size > available_capacity:
                return "CAPACITY_EXCEEDED", available_capacity, booking

        # Update user's name if provided (align with order update behavior)
        if args.customer_name:
            user_repo.create_or_update_user(
                {
                    "name": args.customer_name,
                    "phone_number": customer_contact,
                    "email": None,
                    "address": None,
                    "is_spam": False,
                    "credit_card": None,
                }
            )

        # Capture previous state for activity history
        previous_data = {
            "status": booking.get("status"),
            "party_size": booking.get("party_size"),
            "date_time": (
                isoformat_z(booking.get("date_time"))
                if isinstance(booking.get("date_time"), datetime)
                else booking.get("date_time")
            ),
            "special_request": booking.get("special_request"),
            "notes": booking.get("notes"),
            "name": booking.get("name"),
        }

        # Update the booking with provided fields
        # Status changes (e.g., cancellation) are allowed within the update window
        booking_repo.update_booking(
            booking_id=booking_id,
            party_size=args.party_size,
            special_request=args.special_request,
            notes=args.notes,
            status=args.status,
        )

        # If datetime is being changed, update the slot booking
        if new_datetime and booking.get("slot_booking_id"):
            booking_repo.update_slot_booking_datetime(booking.get("slot_booking_id"), new_datetime)

        # Return updated booking and previous data for history logging
        updated_booking = booking_repo.get_booking_by_id(booking_id)
        return updated_booking, previous_data, booking.get("business_id")

    result, previous_data, extra = await _run_service_call(_update)

    # Handle update window expired
    if result == "UPDATE_WINDOW_EXPIRED":
        window_minutes = settings.AGENT_UPDATE_WINDOW_SECONDS // 60
        return {
            "status": "UPDATE_WINDOW_EXPIRED",
            "message": (
                f"This booking was made more than {window_minutes} minutes ago "
                "and can no longer be modified. Please contact the business directly "
                "for any changes."
            ),
        }

    if result == "OUT_OF_HOURS":
        tz_label = resolve_business_timezone(business)[1]
        return {
            "status": "OUT_OF_HOURS",
            "message": (
                "The requested booking time is outside the business's operating hours. "
                f"Please choose a time between {format_operating_window(business)} ({tz_label})."
            ),
        }

    if result == "INVALID_DATETIME":
        return {
            "status": "FAILED",
            "message": "Unable to process the booking time provided. Please try again with a valid time.",
        }

    if result == "CAPACITY_EXCEEDED":
        available_capacity = previous_data if isinstance(previous_data, int) else 0
        return {
            "status": "CAPACITY_EXCEEDED",
            "message": (
                f"Sorry, we cannot accommodate the requested party size at that time. "
                f"We have space for up to {available_capacity} guests. "
                "Would you like to try a different time or a smaller party size?"
            ),
            "available_capacity": available_capacity,
        }

    if not result:
        return {
            "status": "NOT_FOUND",
            "message": "Sorry, no booking found for your phone number at this business.",
        }

    updated = result
    business_id = extra or business_id

    # Log activity history for voice agent booking update (run in thread since it's a DB operation)
    def _log_history():
        try:
            if business_id:
                logger.debug(
                    "[DEBUG] Logging booking update history: booking_id=%s, business_id=%s",
                    updated.get("id"),
                    business_id,
                )
                history_service = _get_history_service()
                new_data = {
                    "status": updated.get("status"),
                    "party_size": updated.get("party_size"),
                    "date_time": (
                        isoformat_z(updated.get("date_time"))
                        if isinstance(updated.get("date_time"), datetime)
                        else updated.get("date_time")
                    ),
                    "special_request": updated.get("special_request"),
                    "notes": updated.get("notes"),
                    "name": updated.get("name"),
                }
                history_id = history_service.log_booking_updated(
                    booking_id=updated.get("id"),
                    business_id=int(business_id),
                    previous_data=previous_data or {},
                    new_data=new_data,
                    user_id=updated.get("user_id"),
                )
                logger.info("Activity history logged for booking update: history_id=%s", history_id)
            else:
                logger.warning(
                    "Cannot log history - business_id is None for booking %s call_sid=%s",
                    updated.get("id"),
                    call_sid,
                )
        except Exception as history_error:
            logger.exception(
                "[ERROR] Failed to log history for voice agent booking update call_sid=%s: %s",
                call_sid,
                history_error,
            )

    await _run_service_call(_log_history)

    # Emit SSE event for booking update (background task)
    if business_id:
        new_status = updated.get("status", "")
        event_subtype = (
            BookingEventSubtype.BOOKING_CANCELLED
            if new_status.lower() == "cancelled"
            else BookingEventSubtype.BOOKING_UPDATED
        )
        asyncio.create_task(
            _emit_booking_sse_event(
                business_id=int(business_id),
                booking_id=updated.get("id"),
                subtype=event_subtype,
                data={
                    "booking_id": updated.get("id"),
                    "status": new_status,
                    "date_time": (
                        isoformat_z(updated.get("date_time"))
                        if isinstance(updated.get("date_time"), datetime)
                        else updated.get("date_time")
                    ),
                    "party_size": updated.get("party_size"),
                },
            )
        )

    return {"status": "UPDATED", "booking": updated}


async def check_booking_availability(**kwargs) -> Dict[str, Any]:
    """
    Check booking availability for a party size over a specific date/time.

    This checks capacity based on confirmed bookings to determine
    if the business can accommodate the party.
    """
    context, model_kwargs = split_call_context(kwargs, CheckAvailabilityArgs)
    args = CheckAvailabilityArgs.model_validate(model_kwargs)
    call_sid = context.get("call_sid")
    business_id = context_business_id(context)
    if business_id is None:
        return {"status": "FAILED", "message": "Missing business context."}
    logger.info(
        "check_booking_availability invoked business_id=%s party_size=%s call_sid=%s",
        business_id,
        args.party_size,
        call_sid,
    )
    business = await load_business(business_id)
    if not business:
        return {
            "status": "FAILED",
            "message": "Unable to load business information right now. Please try again shortly.",
        }
    business_tz, _ = resolve_business_timezone(business)
    try:
        start_dt = _parse_datetime_str(args.date_start_iso)
    except ValueError:
        return {
            "status": "FAILED",
            "message": "Invalid date/time format. Please provide a valid start time.",
        }

    # Get business capacity settings
    seating_capacity = business.get("booking_seating_capacity", 50)
    advance_days = business.get("booking_advance_days", 30)
    forward_minutes = business.get("forward_minutes") or 0
    backward_minutes = business.get("backward_minutes") or 0
    if forward_minutes <= 0:
        forward_minutes = 1440
    if backward_minutes < 0:
        backward_minutes = 0
    slot_step_minutes = 30

    def _check():
        try:
            booking_service = BookingService()

            if start_dt.tzinfo:
                start_dt_utc = start_dt.astimezone(timezone.utc)
                requested_start = start_dt_utc.astimezone(business_tz).replace(tzinfo=None)
            else:
                requested_start = start_dt.replace(tzinfo=None)
            window_start = requested_start - timedelta(minutes=backward_minutes)
            window_end = requested_start + timedelta(minutes=forward_minutes)

            capacity_start = window_start.replace(tzinfo=business_tz).astimezone(timezone.utc).replace(tzinfo=None)
            capacity_end = window_end.replace(tzinfo=business_tz).astimezone(timezone.utc).replace(tzinfo=None)
            capacity_map_utc = booking_service.get_capacity_map(
                business_id=business_id,
                window_start=capacity_start,
                window_end=capacity_end,
            )
            capacity_map: Dict[datetime, int] = {}
            for slot_utc, used in capacity_map_utc.items():
                slot_local = slot_utc.replace(tzinfo=timezone.utc).astimezone(business_tz).replace(tzinfo=None)
                capacity_map[slot_local] = used

            now_local = datetime.now(timezone.utc).astimezone(business_tz).replace(tzinfo=None)
            max_booking_date = now_local + timedelta(days=advance_days)

            requested_slot = snap_datetime_to_slot(requested_start, slot_step_minutes, "floor")
            is_on_boundary = is_datetime_on_slot_boundary(requested_start, slot_step_minutes)
            requested_within_hours = is_datetime_within_operating_hours(business, requested_start)
            requested_in_range = requested_start <= max_booking_date
            requested_in_future = requested_start >= now_local
            used_capacity = capacity_map.get(requested_slot, 0) if is_on_boundary else 0
            available_capacity = seating_capacity - used_capacity
            available = (
                is_on_boundary
                and requested_within_hours
                and requested_in_range
                and requested_in_future
                and available_capacity >= args.party_size
            )
            nearest_forward_slot = None
            nearest_backward_slot = None
            if not available:
                nearest = booking_service.find_nearest_slots(
                    business=business,
                    requested_start_local=requested_start,
                    party_size=args.party_size,
                    window_start=window_start,
                    window_end=window_end,
                    capacity_map=capacity_map,
                    now_utc=datetime.now(timezone.utc),
                    slot_step_minutes=slot_step_minutes,
                )
                forward_slot = nearest.get("nearest_forward_slot")
                if forward_slot and forward_slot.get("datetime"):
                    forward_local = datetime.fromisoformat(forward_slot["datetime"])
                    nearest_forward_slot = format_nearest_slot_label(forward_local, now_local)

                backward_slot = nearest.get("nearest_backward_slot")
                if backward_slot and backward_slot.get("datetime"):
                    backward_local = datetime.fromisoformat(backward_slot["datetime"])
                    nearest_backward_slot = format_nearest_slot_label(backward_local, now_local)

            message = None
            if not available:
                if not requested_in_range:
                    message = (
                        f"Bookings can only be made up to {advance_days} days in advance. "
                        "Please choose an earlier date."
                    )
                elif not requested_in_future:
                    message = "The requested time has already passed. Please choose a future time."
                elif not requested_within_hours:
                    tz_label = resolve_business_timezone(business)[1]
                    message = (
                        f"The requested time is outside operating hours. "
                        f"Please choose a time between {format_operating_window(business)} ({tz_label})."
                    )
                else:
                    message = (
                        f"No availability for a party of {args.party_size} at the requested time. "
                        "Suggest the nearest available slots to the caller."
                    )

            return {
                "business_id": business_id,
                "party_size": args.party_size,
                "seating_capacity": seating_capacity,
                "date_time": args.date_start_iso,
                "requested_slot_available": available,
                "nearest_forward_slot": nearest_forward_slot,
                "nearest_backward_slot": nearest_backward_slot,
                "message": message,
            }
        except Exception as exc:
            logger.exception("[ERROR] check_booking_availability failed: %s", exc)
            return {
                "business_id": business_id,
                "party_size": args.party_size,
                "requested_slot_available": None,
                "nearest_forward_slot": None,
                "nearest_backward_slot": None,
                "message": "Unable to verify availability, but timeslot is likely available.",
            }

    return await _run_service_call(_check)
