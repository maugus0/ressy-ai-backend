"""Reservation-related function implementations backed by ReservationService."""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from pydantic import BaseModel, ConfigDict

from app.agent_fc.functions.common_restaurant import load_restaurant
from app.agent_fc.functions.function_context import (
    NoArgs,
    context_customer_contact,
    context_restaurant_id,
    split_call_context,
)
from app.config import settings
from app.repositories.mysql_reservation_repo import MySQLReservationRepository
from app.repositories.mysql_restaurant_repo import MySQLRestaurantRepository
from app.repositories.mysql_user_repo import MySQLUserRepository
from app.repositories.mysql_user_restaurant_metadata_repo import (
    MySQLUserRestaurantMetadataRepository,
)
from app.services.activity_history_service import ActivityHistoryService
from app.services.notification_service import NotificationService
from app.services.reservation_service import ReservationService
from app.services.sse_service import ReservationEventSubtype, SSEService
from app.utils.restaurant_hours import (
    format_nearest_slot_label,
    format_operating_window,
    is_datetime_on_slot_boundary,
    is_datetime_within_operating_hours,
    resolve_restaurant_timezone,
    snap_datetime_to_slot,
)
from app.utils.timezone import coerce_datetime, isoformat_z, parse_datetime

logger = logging.getLogger(__name__)


# ---------- Repository/Service Factory Functions ----------
# Create fresh instances per function call to ensure up-to-date data
# during active voice calls. This fixes mid-call updates not being detected.


def _get_reservation_repo() -> MySQLReservationRepository:
    """Create fresh reservation repository instance per function call."""
    return MySQLReservationRepository()


def _get_restaurant_repo() -> MySQLRestaurantRepository:
    """Create fresh restaurant repository instance per function call."""
    return MySQLRestaurantRepository()


def _get_user_repo() -> MySQLUserRepository:
    """Create fresh user repository instance per function call."""
    return MySQLUserRepository()


def _get_metadata_repo() -> MySQLUserRestaurantMetadataRepository:
    """Create fresh metadata repository instance per function call."""
    return MySQLUserRestaurantMetadataRepository()


def _get_history_service() -> ActivityHistoryService:
    """Create fresh history service instance per function call."""
    return ActivityHistoryService()


def _get_sse_service() -> SSEService:
    """Create fresh SSE service instance per function call."""
    return SSEService()


async def _emit_reservation_sse_event(
    restaurant_id: int,
    reservation_id: int,
    subtype: ReservationEventSubtype,
    data: Dict[str, Any],
) -> None:
    """
    Emit SSE reservation event AND persist notification. Non-blocking, failure-tolerant.
    """
    try:
        sse_service = _get_sse_service()
        await sse_service.emit_reservation_event(
            restaurant_id=restaurant_id,
            reservation_id=reservation_id,
            subtype=subtype,
            data=data,
        )
    except Exception as sse_error:
        logger.error(
            "[SSE] Reservation event emission failed for reservation %s (%s): %s",
            reservation_id,
            subtype.value,
            sse_error,
        )

    try:
        from app.services.notification_persistence_service import NotificationPersistenceService

        notification_service = NotificationPersistenceService()
        notification_service.create_notification(
            restaurant_id=restaurant_id,
            type="reservation",
            subtype=subtype.value if hasattr(subtype, "value") else subtype,
            data={"reservation_id": reservation_id, **(data or {})},
            entity_id=reservation_id,
        )
    except Exception as e:
        logger.error(
            "[Notification] Reservation notification persistence failed for reservation %s: %s",
            reservation_id,
            e,
        )


async def _send_voice_reservation_sms(
    restaurant: Dict[str, Any],
    reservation_id: int,
    phone_number: str,
    confirmation_number: Optional[str] = None,
) -> None:
    """Send SMS notification for voice-agent-created reservation.

    This is a fire-and-forget background task - SMS failures should not
    affect the voice call or reservation creation.
    """
    import json

    try:
        twilio_number = (restaurant.get("twilio_phone_number") or "").strip()
        if not twilio_number:
            logger.debug("No Twilio number configured for restaurant %s", restaurant.get("id"))
            return

        twilio_details = restaurant.get("twilio_details") or {}
        if isinstance(twilio_details, str):
            try:
                twilio_details = json.loads(twilio_details) if twilio_details else {}
            except json.JSONDecodeError as e:
                logger.warning(
                    "Invalid JSON in twilio_details for restaurant %s: %s",
                    restaurant.get("id"),
                    e,
                )
                twilio_details = {}
            except Exception as e:
                logger.warning(
                    "Unexpected error parsing twilio_details for restaurant %s: %s",
                    restaurant.get("id"),
                    e,
                )
                twilio_details = {}

        sid = twilio_details.get("account_sid") or twilio_details.get("TWILIO_ACCOUNT_SID")
        token = twilio_details.get("auth_token") or twilio_details.get("TWILIO_AUTH_TOKEN")

        notification_service = NotificationService()
        await notification_service.send_reservation_notification(
            restaurant_id=restaurant.get("id"),
            reservation_id=reservation_id,
            new_status="pending",  # Voice-created reservations start as pending
            recipient_phone=phone_number,
            restaurant_name=restaurant.get("name") or "",
            restaurant_twilio_number=twilio_number,
            confirmation_number=confirmation_number,
            twilio_account_sid=sid,
            twilio_auth_token=token,
        )
        logger.info("SMS sent for voice reservation %s", reservation_id)
    except Exception as e:
        # Don't fail the voice call if SMS fails - just log
        logger.warning("Failed to send SMS for voice reservation %s: %s", reservation_id, e)


class CreateReservationArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    party_size: int
    datetime_iso: str
    customer_name: Optional[str] = None
    occasion: Optional[str] = None
    special_request: Optional[str] = None
    notes: Optional[str] = None


class UpdateReservationArgs(BaseModel):
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
    """Generate a unique confirmation number for a reservation."""
    return f"RES-{uuid.uuid4().hex[:8].upper()}"


async def create_reservation(**kwargs) -> Dict[str, Any]:
    """
    Create a new reservation for a customer.

    Flow:
    1. Validate capacity and advance booking limits
    2. Create or update user with customer details
    3. Create slot booking and reservation in a single transaction
    4. Return reservation details with pending status (restaurant will confirm)
    """
    context, model_kwargs = split_call_context(kwargs, CreateReservationArgs)
    args = CreateReservationArgs.model_validate(model_kwargs)
    call_sid = context.get("call_sid")
    restaurant_id = context_restaurant_id(context)
    customer_contact = context_customer_contact(context)
    if restaurant_id is None:
        return {"status": "FAILED", "message": "Missing restaurant context."}
    if not customer_contact:
        return {"status": "FAILED", "message": "Missing caller contact context."}
    logger.info(
        "create_reservation invoked restaurant_id=%s party_size=%s call_sid=%s",
        restaurant_id,
        args.party_size,
        call_sid,
    )
    restaurant = await load_restaurant(restaurant_id)
    if not restaurant:
        return {
            "status": "FAILED",
            "message": "Unable to load restaurant information right now. Please try again shortly.",
        }
    try:
        reservation_datetime = _parse_datetime_str(args.datetime_iso)
        reservation_iso = isoformat_z(reservation_datetime)
    except ValueError:
        return {
            "status": "FAILED",
            "message": "Invalid reservation time format. Please provide a valid date and time.",
        }
    if not is_datetime_within_operating_hours(restaurant, reservation_datetime):
        tz_label = resolve_restaurant_timezone(restaurant)[1]
        return {
            "status": "OUT_OF_HOURS",
            "message": (
                "The requested reservation time is outside the restaurant's operating hours. "
                f"Please choose a time between {format_operating_window(restaurant)} ({tz_label})."
            ),
        }

    # Validate advance booking limit
    advance_days = restaurant.get("reservation_advance_days", 30)
    max_booking_date = datetime.now(timezone.utc) + timedelta(days=advance_days)
    reservation_dt_utc = reservation_datetime
    if reservation_datetime.tzinfo is None:
        reservation_dt_utc = reservation_datetime.replace(tzinfo=timezone.utc)
    if reservation_dt_utc > max_booking_date:
        return {
            "status": "ADVANCE_BOOKING_EXCEEDED",
            "message": (
                f"Reservations can only be made up to {advance_days} days in advance. " "Please choose an earlier date."
            ),
        }

    # Check capacity - only confirmed reservations count against capacity
    seating_capacity = restaurant.get("reservation_seating_capacity", 50)

    def _check_capacity():
        reservation_repo = _get_reservation_repo()
        # Normalize datetime to minute precision for slot matching
        slot_dt = reservation_datetime.replace(second=0, microsecond=0)
        if slot_dt.tzinfo:
            slot_dt = slot_dt.replace(tzinfo=None)
        used_capacity = reservation_repo.get_slot_confirmed_capacity(
            restaurant_id=restaurant_id,
            date_time=slot_dt,
            reservation_type="in-house",
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
        reservation_repo = _get_reservation_repo()

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

        # 1.5. Create user-restaurant metadata mapping (for dashboard user visibility)
        try:
            metadata_repo.create_mapping(
                user_id=user_id,
                restaurant_id=restaurant_id,
                source="reservation",
                notes="Created via voice agent reservation",
            )
        except Exception as meta_err:
            # Log but don't fail reservation creation if metadata mapping fails
            logger.warning("Failed to create user-restaurant metadata call_sid=%s: %s", call_sid, meta_err)

        # 3. Generate confirmation number and reservation token
        confirmation_number = _generate_confirmation_number()
        reservation_token = str(uuid.uuid4())

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
        expires_at = reservation_datetime + timedelta(minutes=15)
        slot_id = reservation_repo.create_slot_booking(
            restaurant_id=restaurant_id,
            date_time=reservation_datetime,
            expires_at=expires_at,
            reservation_token=reservation_token,
            reservation_type="in-house",
            status="reserved",
            party_size=args.party_size,
        )

        # 6. Create reservation with status = "pending" (restaurant will confirm)
        reservation_id = reservation_repo.create_reservation(
            slot_booking_id=slot_id,
            user_id=user_id,
            confirmation_number=confirmation_number,
            reservation_type="in-house",
            status="pending",
            special_request=args.special_request,
            party_size=args.party_size,
            notes=final_notes,
        )

        return {
            "reservation_id": reservation_id,
            "slot_id": slot_id,
            "user_id": user_id,
            "confirmation_number": confirmation_number,
            "party_size": args.party_size,
            "datetime": reservation_iso,
            "customer_name": args.customer_name,
            "customer_contact": customer_contact,
            "occasion": args.occasion,
            "special_request": args.special_request,
            "notes": final_notes,
        }

    try:
        reservation = await _run_service_call(_create)

        # Log activity history for voice agent reservation creation (run in thread since it's a DB operation)
        def _log_history():
            try:
                logger.debug(
                    "[DEBUG] Logging reservation creation history: reservation_id=%s, restaurant_id=%s",
                    reservation["reservation_id"],
                    restaurant_id,
                )
                history_service = _get_history_service()
                history_id = history_service.log_reservation_created(
                    reservation_id=reservation["reservation_id"],
                    restaurant_id=restaurant_id,
                    reservation_data={
                        "status": "pending",
                        "party_size": args.party_size,
                        "date_time": reservation_iso,
                        "name": args.customer_name,
                    },
                    user_id=reservation.get("user_id"),
                )
                logger.info("Activity history logged for reservation creation: history_id=%s", history_id)
            except Exception as history_error:
                logger.exception(
                    "[ERROR] Failed to log history for voice agent reservation creation call_sid=%s: %s",
                    call_sid,
                    history_error,
                )

        await _run_service_call(_log_history)

        # Emit SSE event for new reservation (background task)
        asyncio.create_task(
            _emit_reservation_sse_event(
                restaurant_id=restaurant_id,
                reservation_id=reservation["reservation_id"],
                subtype=ReservationEventSubtype.NEW_RESERVATION,
                data={
                    "reservation_id": reservation["reservation_id"],
                    "confirmation_number": reservation.get("confirmation_number"),
                    "status": "pending",
                    "date_time": reservation_iso,
                    "party_size": args.party_size,
                    "name": args.customer_name,
                },
            )
        )

        # Send SMS notification for voice-created reservation (background task)
        if customer_contact:
            asyncio.create_task(
                _send_voice_reservation_sms(
                    restaurant=restaurant,
                    reservation_id=reservation["reservation_id"],
                    phone_number=customer_contact,
                    confirmation_number=reservation.get("confirmation_number"),
                )
            )

        return {
            "status": "SUBMITTED",
            "message": "Reservation request submitted. The restaurant will confirm shortly.",
            "reservation": reservation,
        }
    except Exception as exc:
        logger.exception("[ERROR] create_reservation failed: %s", exc)
        return {
            "status": "FAILED",
            "message": "Unable to create reservation. Please try again or contact the restaurant directly.",
            "error": str(exc),
        }


async def lookup_reservation(**kwargs) -> Dict[str, Any]:
    """
    Look up the latest reservation for a caller using their phone number.
    Similar to lookup_order but for reservations.
    """
    context, model_kwargs = split_call_context(kwargs, NoArgs)
    NoArgs.model_validate(model_kwargs)
    call_sid = context.get("call_sid")
    restaurant_id = context_restaurant_id(context)
    customer_contact = context_customer_contact(context)
    if restaurant_id is None:
        return {"status": "FAILED", "message": "Missing restaurant context."}
    if not customer_contact:
        return {"status": "FAILED", "message": "Missing caller contact context."}
    logger.info("lookup_reservation invoked customer_contact=%s call_sid=%s", customer_contact, call_sid)

    def _lookup():
        user_repo = _get_user_repo()
        reservation_repo = _get_reservation_repo()

        # Find user by phone number
        user_id = user_repo.get_user_id_by_phone_or_email(customer_contact, None)
        if not user_id:
            return None

        # Get the latest reservation for this user
        reservation = reservation_repo.get_latest_by_user(user_id, restaurant_id=restaurant_id)
        return reservation

    reservation = await _run_service_call(_lookup)
    if not reservation:
        return {
            "status": "NOT_FOUND",
            "message": "Sorry, no reservation found for your phone number at this restaurant.",
        }
    return {"status": "FOUND", "reservation": reservation}


def _is_within_update_window(created_at: Any) -> bool:
    """
    Check if a reservation is within the allowed update window.

    Args:
        created_at: The created_at timestamp (datetime or string)

    Returns:
        True if the reservation can still be updated, False otherwise
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


async def update_reservation(**kwargs) -> Dict[str, Any]:
    """
    Update the latest reservation for a caller using their phone number.
    """
    context, model_kwargs = split_call_context(kwargs, UpdateReservationArgs)
    args = UpdateReservationArgs.model_validate(model_kwargs)
    call_sid = context.get("call_sid")
    restaurant_id = context_restaurant_id(context)
    customer_contact = context_customer_contact(context)
    if restaurant_id is None:
        return {"status": "FAILED", "message": "Missing restaurant context."}
    if not customer_contact:
        return {"status": "FAILED", "message": "Missing caller contact context."}
    logger.info("update_reservation invoked customer_contact=%s call_sid=%s", customer_contact, call_sid)
    restaurant = await load_restaurant(restaurant_id)
    if not restaurant:
        return {
            "status": "FAILED",
            "message": "Unable to load restaurant information right now. Please try again shortly.",
        }
    new_datetime: Optional[datetime] = None
    if args.datetime_iso:
        try:
            new_datetime = _parse_datetime_str(args.datetime_iso)
        except ValueError:
            return {
                "status": "FAILED",
                "message": "Invalid reservation time format. Please provide a valid date and time.",
            }

    def _update():
        user_repo = _get_user_repo()
        reservation_repo = _get_reservation_repo()

        user_id = user_repo.get_user_id_by_phone_or_email(customer_contact, None)
        if not user_id:
            return None, None, None
        reservation = reservation_repo.get_latest_by_user(user_id, restaurant_id=restaurant_id)
        if not reservation:
            return None, None, None

        reservation_id = reservation.get("id")
        if not reservation_id:
            return None, None, None

        # Check if reservation is within the allowed update window
        created_at = reservation.get("created_at")
        if not _is_within_update_window(created_at):
            return "UPDATE_WINDOW_EXPIRED", None, reservation

        candidate_datetime = new_datetime or _coerce_datetime(reservation.get("date_time"))
        if candidate_datetime is None:
            return "INVALID_DATETIME", None, reservation
        if not is_datetime_within_operating_hours(restaurant, candidate_datetime):
            return "OUT_OF_HOURS", None, reservation

        new_party_size = args.party_size or reservation.get("party_size", 1)
        if new_datetime or args.party_size:
            seating_capacity = restaurant.get("reservation_seating_capacity", 50)
            slot_dt = candidate_datetime.replace(second=0, microsecond=0)
            if slot_dt.tzinfo:
                slot_dt = slot_dt.replace(tzinfo=None)
                used_capacity = reservation_repo.get_slot_confirmed_capacity(
                    restaurant_id=restaurant_id,
                    date_time=slot_dt,
                    reservation_type="in-house",
                )
            current_party_size = reservation.get("party_size", 0)
            if reservation.get("status") == "confirmed":
                used_capacity -= current_party_size
            available_capacity = seating_capacity - used_capacity
            if new_party_size > available_capacity:
                return "CAPACITY_EXCEEDED", available_capacity, reservation

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
            "status": reservation.get("status"),
            "party_size": reservation.get("party_size"),
            "date_time": (
                isoformat_z(reservation.get("date_time"))
                if isinstance(reservation.get("date_time"), datetime)
                else reservation.get("date_time")
            ),
            "special_request": reservation.get("special_request"),
            "notes": reservation.get("notes"),
            "name": reservation.get("name"),
        }

        # Update the reservation with provided fields
        # Status changes (e.g., cancellation) are allowed within the update window
        reservation_repo.update_reservation(
            reservation_id=reservation_id,
            party_size=args.party_size,
            special_request=args.special_request,
            notes=args.notes,
            status=args.status,
        )

        # If datetime is being changed, update the slot booking
        if new_datetime and reservation.get("slot_booking_id"):
            reservation_repo.update_slot_booking_datetime(reservation.get("slot_booking_id"), new_datetime)

        # Return updated reservation and previous data for history logging
        updated_reservation = reservation_repo.get_reservation_by_id(reservation_id)
        return updated_reservation, previous_data, reservation.get("restaurant_id")

    result, previous_data, extra = await _run_service_call(_update)

    # Handle update window expired
    if result == "UPDATE_WINDOW_EXPIRED":
        window_minutes = settings.AGENT_UPDATE_WINDOW_SECONDS // 60
        return {
            "status": "UPDATE_WINDOW_EXPIRED",
            "message": (
                f"This reservation was made more than {window_minutes} minutes ago "
                "and can no longer be modified. Please contact the restaurant directly "
                "for any changes."
            ),
        }

    if result == "OUT_OF_HOURS":
        tz_label = resolve_restaurant_timezone(restaurant)[1]
        return {
            "status": "OUT_OF_HOURS",
            "message": (
                "The requested reservation time is outside the restaurant's operating hours. "
                f"Please choose a time between {format_operating_window(restaurant)} ({tz_label})."
            ),
        }

    if result == "INVALID_DATETIME":
        return {
            "status": "FAILED",
            "message": "Unable to process the reservation time provided. Please try again with a valid time.",
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
            "message": "Sorry, no reservation found for your phone number at this restaurant.",
        }

    updated = result
    restaurant_id = extra or restaurant_id

    # Log activity history for voice agent reservation update (run in thread since it's a DB operation)
    def _log_history():
        try:
            if restaurant_id:
                logger.debug(
                    "[DEBUG] Logging reservation update history: reservation_id=%s, restaurant_id=%s",
                    updated.get("id"),
                    restaurant_id,
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
                history_id = history_service.log_reservation_updated(
                    reservation_id=updated.get("id"),
                    restaurant_id=int(restaurant_id),
                    previous_data=previous_data or {},
                    new_data=new_data,
                    user_id=updated.get("user_id"),
                )
                logger.info("Activity history logged for reservation update: history_id=%s", history_id)
            else:
                logger.warning(
                    "Cannot log history - restaurant_id is None for reservation %s call_sid=%s",
                    updated.get("id"),
                    call_sid,
                )
        except Exception as history_error:
            logger.exception(
                "[ERROR] Failed to log history for voice agent reservation update call_sid=%s: %s",
                call_sid,
                history_error,
            )

    await _run_service_call(_log_history)

    # Emit SSE event for reservation update (background task)
    if restaurant_id:
        new_status = updated.get("status", "")
        event_subtype = (
            ReservationEventSubtype.RESERVATION_CANCELLED
            if new_status.lower() == "cancelled"
            else ReservationEventSubtype.RESERVATION_UPDATED
        )
        asyncio.create_task(
            _emit_reservation_sse_event(
                restaurant_id=int(restaurant_id),
                reservation_id=updated.get("id"),
                subtype=event_subtype,
                data={
                    "reservation_id": updated.get("id"),
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

    return {"status": "UPDATED", "reservation": updated}


async def check_reservation_availability(**kwargs) -> Dict[str, Any]:
    """
    Check reservation availability for a party size over a specific date/time.

    This checks capacity based on confirmed reservations to determine
    if the restaurant can accommodate the party.
    """
    context, model_kwargs = split_call_context(kwargs, CheckAvailabilityArgs)
    args = CheckAvailabilityArgs.model_validate(model_kwargs)
    call_sid = context.get("call_sid")
    restaurant_id = context_restaurant_id(context)
    if restaurant_id is None:
        return {"status": "FAILED", "message": "Missing restaurant context."}
    logger.info(
        "check_reservation_availability invoked restaurant_id=%s party_size=%s call_sid=%s",
        restaurant_id,
        args.party_size,
        call_sid,
    )
    restaurant = await load_restaurant(restaurant_id)
    if not restaurant:
        return {
            "status": "FAILED",
            "message": "Unable to load restaurant information right now. Please try again shortly.",
        }
    restaurant_tz, _ = resolve_restaurant_timezone(restaurant)
    try:
        start_dt = _parse_datetime_str(args.date_start_iso)
    except ValueError:
        return {
            "status": "FAILED",
            "message": "Invalid date/time format. Please provide a valid start time.",
        }

    # Get restaurant capacity settings
    seating_capacity = restaurant.get("reservation_seating_capacity", 50)
    advance_days = restaurant.get("reservation_advance_days", 30)
    forward_minutes = restaurant.get("forward_minutes") or 0
    backward_minutes = restaurant.get("backward_minutes") or 0
    if forward_minutes <= 0:
        forward_minutes = 1440
    if backward_minutes < 0:
        backward_minutes = 0
    slot_step_minutes = 30

    def _check():
        try:
            reservation_service = ReservationService()

            if start_dt.tzinfo:
                start_dt_utc = start_dt.astimezone(timezone.utc)
                requested_start = start_dt_utc.astimezone(restaurant_tz).replace(tzinfo=None)
            else:
                requested_start = start_dt.replace(tzinfo=None)
            window_start = requested_start - timedelta(minutes=backward_minutes)
            window_end = requested_start + timedelta(minutes=forward_minutes)

            capacity_start = window_start.replace(tzinfo=restaurant_tz).astimezone(timezone.utc).replace(tzinfo=None)
            capacity_end = window_end.replace(tzinfo=restaurant_tz).astimezone(timezone.utc).replace(tzinfo=None)
            capacity_map_utc = reservation_service.get_capacity_map(
                restaurant_id=restaurant_id,
                window_start=capacity_start,
                window_end=capacity_end,
            )
            capacity_map: Dict[datetime, int] = {}
            for slot_utc, used in capacity_map_utc.items():
                slot_local = slot_utc.replace(tzinfo=timezone.utc).astimezone(restaurant_tz).replace(tzinfo=None)
                capacity_map[slot_local] = used

            now_local = datetime.now(timezone.utc).astimezone(restaurant_tz).replace(tzinfo=None)
            max_booking_date = now_local + timedelta(days=advance_days)

            requested_slot = snap_datetime_to_slot(requested_start, slot_step_minutes, "floor")
            is_on_boundary = is_datetime_on_slot_boundary(requested_start, slot_step_minutes)
            requested_within_hours = is_datetime_within_operating_hours(restaurant, requested_start)
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
                nearest = reservation_service.find_nearest_slots(
                    restaurant=restaurant,
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
                        f"Reservations can only be made up to {advance_days} days in advance. "
                        "Please choose an earlier date."
                    )
                elif not requested_in_future:
                    message = "The requested time has already passed. Please choose a future time."
                elif not requested_within_hours:
                    tz_label = resolve_restaurant_timezone(restaurant)[1]
                    message = (
                        f"The requested time is outside operating hours. "
                        f"Please choose a time between {format_operating_window(restaurant)} ({tz_label})."
                    )
                else:
                    message = (
                        f"No availability for a party of {args.party_size} at the requested time. "
                        "Suggest the nearest available slots to the caller."
                    )

            return {
                "restaurant_id": restaurant_id,
                "party_size": args.party_size,
                "seating_capacity": seating_capacity,
                "date_time": args.date_start_iso,
                "requested_slot_available": available,
                "nearest_forward_slot": nearest_forward_slot,
                "nearest_backward_slot": nearest_backward_slot,
                "message": message,
            }
        except Exception as exc:
            logger.exception("[ERROR] check_reservation_availability failed: %s", exc)
            return {
                "restaurant_id": restaurant_id,
                "party_size": args.party_size,
                "requested_slot_available": None,
                "nearest_forward_slot": None,
                "nearest_backward_slot": None,
                "message": "Unable to verify availability, but timeslot is likely available.",
            }

    return await _run_service_call(_check)
