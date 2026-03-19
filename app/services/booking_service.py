"""
In-House Booking Service for handling table bookings.
"""

import uuid
from datetime import datetime, time, timedelta, timezone
from typing import Any, Dict, Optional

from app.repositories.mysql_booking_repo import MySQLBookingRepository
from app.repositories.mysql_business_repo import MySQLBusinessRepository
from app.repositories.mysql_user_repo import MySQLUserRepository
from app.repositories.mysql_user_business_metadata_repo import (
    MySQLUserRestaurantMetadataRepository,
)
from app.utils.logging_config import get_logger
from app.utils.business_hours import (
    _parse_operating_time,
    format_operating_window,
    get_day_operating_hours,
    is_datetime_on_slot_boundary,
    is_datetime_within_operating_hours,
    resolve_business_timezone,
    snap_datetime_to_slot,
)
from app.utils.timezone import isoformat_z, parse_datetime


class BookingService:
    """Service for in-house booking operations."""

    RESERVATION_TYPE = "in-house"
    SLOT_DURATION_MINUTES = 90  # Default slot duration
    SLOT_EXPIRY_MINUTES = 15  # Time before slot expires
    SLOT_INTERVAL_MINUTES = 15  # Interval between slots

    def __init__(self):
        self.logger = get_logger(__name__)
        self.booking_repo = MySQLBookingRepository()
        self.business_repo = MySQLBusinessRepository()
        self.user_repo = MySQLUserRepository()
        self.metadata_repo = MySQLUserRestaurantMetadataRepository()

    def _parse_time(self, time_str: Any, default: str = "09:00:00") -> time:
        """Parse time string or timedelta to time object using shared utility."""
        parsed = _parse_operating_time(time_str)
        if parsed is not None:
            return parsed
        return datetime.strptime(default, "%H:%M:%S").time()

    def _validate_advance_booking(self, slot_dt: datetime, business: Dict[str, Any]) -> None:
        """Validate that booking is within advance booking limit."""
        advance_days = business.get("booking_advance_days", 30)
        max_booking_date = datetime.now() + timedelta(days=advance_days)
        if slot_dt > max_booking_date:
            raise ValueError(f"Bookings can only be made up to {advance_days} days in advance")

    def _validate_opening_hours(self, slot_dt: datetime, business: Dict[str, Any]) -> None:
        """Validate that booking is during opening hours using shared utility."""
        if not is_datetime_within_operating_hours(business, slot_dt):
            day_name = slot_dt.strftime("%A").lower()
            hours_display = format_operating_window(business, day_name)
            raise ValueError(f"Bookings can only be made during opening hours ({hours_display})")

    def _validate_future_time(self, slot_dt: datetime, business: Dict[str, Any]) -> None:
        """Validate that booking is not in the past using business local time."""
        business_tz, _ = resolve_business_timezone(business)
        slot_local = slot_dt.replace(tzinfo=business_tz)
        now_local = datetime.now(timezone.utc).astimezone(business_tz)
        if slot_local < now_local:
            raise ValueError("Bookings cannot be made for times in the past.")

    def _check_capacity(self, business_id: int, slot_dt: datetime, party_size: int, seating_capacity: int) -> None:
        """Check if there's enough capacity for the party size."""
        used_capacity = self.booking_repo.get_slot_confirmed_capacity(
            business_id=business_id,
            date_time=slot_dt,
            booking_type=self.RESERVATION_TYPE,
        )
        available_capacity = seating_capacity - used_capacity
        if party_size > available_capacity:
            raise ValueError(f"Not enough capacity for party of {party_size}. Available: {available_capacity}")

    def get_capacity_map(self, business_id: int, window_start: datetime, window_end: datetime) -> Dict[datetime, int]:
        """Return confirmed capacity per slot within the window."""
        return self.booking_repo.get_confirmed_capacity_by_slot(
            business_id=business_id,
            start_date_time=window_start,
            end_date_time=window_end,
            booking_type=self.RESERVATION_TYPE,
        )

    def find_nearest_slots(
        self,
        business: Dict[str, Any],
        requested_start_local: datetime,
        party_size: int,
        window_start: datetime,
        window_end: datetime,
        capacity_map: Dict[datetime, int],
        now_utc: Optional[datetime] = None,
        slot_step_minutes: int = 30,
    ) -> Dict[str, Optional[Dict[str, Any]]]:
        """Return nearest forward/backward available slots within the window."""
        business_tz, _ = resolve_business_timezone(business)
        now_utc = now_utc or datetime.now(timezone.utc)
        now_local = now_utc.astimezone(business_tz)
        if now_local.tzinfo:
            now_local = now_local.replace(tzinfo=None)

        advance_days = business.get("booking_advance_days", 30)
        seating_capacity = business.get("booking_seating_capacity", 50)
        max_booking_date_local = now_local + timedelta(days=advance_days)

        nearest_forward_slot = None
        nearest_backward_slot = None

        forward_start = snap_datetime_to_slot(max(requested_start_local, now_local), slot_step_minutes, "ceil")
        if (
            is_datetime_on_slot_boundary(requested_start_local, slot_step_minutes)
            and forward_start == requested_start_local
        ):
            forward_start += timedelta(minutes=slot_step_minutes)
        forward_end = snap_datetime_to_slot(min(window_end, max_booking_date_local), slot_step_minutes, "floor")
        candidate = forward_start
        while candidate <= forward_end:
            if is_datetime_within_operating_hours(business, candidate):
                slot_normalized = candidate.replace(second=0, microsecond=0)
                used_capacity = capacity_map.get(slot_normalized, 0)
                available_capacity = seating_capacity - used_capacity
                if available_capacity >= party_size:
                    nearest_forward_slot = {
                        "datetime": candidate.isoformat(),
                        "available_capacity": available_capacity,
                        "party_size_available": True,
                    }
                    break
            candidate += timedelta(minutes=slot_step_minutes)

        if window_start < requested_start_local:
            backward_start = snap_datetime_to_slot(max(window_start, now_local), slot_step_minutes, "ceil")
            candidate = snap_datetime_to_slot(requested_start_local, slot_step_minutes, "floor")
            if (
                is_datetime_on_slot_boundary(requested_start_local, slot_step_minutes)
                and candidate == requested_start_local
            ):
                candidate -= timedelta(minutes=slot_step_minutes)
            while candidate >= backward_start:
                if is_datetime_within_operating_hours(business, candidate):
                    slot_normalized = candidate.replace(second=0, microsecond=0)
                    used_capacity = capacity_map.get(slot_normalized, 0)
                    available_capacity = seating_capacity - used_capacity
                    if available_capacity >= party_size:
                        nearest_backward_slot = {
                            "datetime": candidate.isoformat(),
                            "available_capacity": available_capacity,
                            "party_size_available": True,
                        }
                        break
                candidate -= timedelta(minutes=slot_step_minutes)

        return {
            "nearest_forward_slot": nearest_forward_slot,
            "nearest_backward_slot": nearest_backward_slot,
        }

    def get_availability(
        self,
        business_id: int,
        start_date_time: str,
        forward_minutes: Optional[int] = None,
        backward_minutes: Optional[int] = None,
        party_size: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Get table availability for a business.
        Only confirmed bookings reduce available capacity.

        Args:
            business_id: Restaurant ID
            start_date_time: Start date and time (ISO format)
            forward_minutes: Forward booking window
            backward_minutes: Backward booking window
            party_size: Party size to check capacity for

        Returns:
            Availability response with available slots
        """
        business = self.business_repo.get_by_id(business_id)
        if not business:
            raise ValueError(f"Restaurant with ID {business_id} not found")
        business_tz, _ = resolve_business_timezone(business)

        seating_capacity = business.get("booking_seating_capacity", 50)
        advance_days = business.get("booking_advance_days", 30)

        forward = forward_minutes if forward_minutes is not None else business.get("forward_minutes", 1440)
        backward = backward_minutes if backward_minutes is not None else business.get("backward_minutes", 0)

        try:
            start_dt_utc = parse_datetime(start_date_time)
            start_dt_local = start_dt_utc.astimezone(business_tz).replace(tzinfo=None)
        except ValueError:
            raise ValueError(f"Invalid date_time format: {start_date_time}")

        # Calculate time range
        end_dt_local = start_dt_local + timedelta(minutes=forward)
        search_start_dt_local = start_dt_local - timedelta(minutes=backward)

        def _local_naive_to_utc_naive(local_dt: datetime) -> datetime:
            return local_dt.replace(tzinfo=business_tz).astimezone(timezone.utc).replace(tzinfo=None)

        end_dt_utc = _local_naive_to_utc_naive(end_dt_local)
        search_start_dt_utc = _local_naive_to_utc_naive(search_start_dt_local)

        max_booking_date = datetime.now() + timedelta(days=advance_days)
        if end_dt_local > max_booking_date:
            end_dt_local = max_booking_date

        capacity_map = self.booking_repo.get_confirmed_capacity_by_slot(
            business_id=business_id,
            start_date_time=search_start_dt_utc,
            end_date_time=end_dt_utc,
            booking_type=self.RESERVATION_TYPE,
        )

        # Generate all possible slots based on per-day operating hours
        slots = []
        current_date = search_start_dt_local.date()
        end_date = end_dt_local.date()

        def _is_overnight(open_t: time, close_t: time) -> bool:
            """Check if hours span overnight (close time is before open time)."""
            return close_t < open_t

        # Track which dates we've already generated slots for to avoid duplicates
        processed_slots = set()

        while current_date <= end_date:
            # Get operating hours for this specific day
            day_name = current_date.strftime("%A").lower()
            day_open_time, day_close_time, day_is_closed, day_is_24_hours = get_day_operating_hours(
                business, day_name
            )

            # Skip closed days
            if day_is_closed:
                current_date += timedelta(days=1)
                continue

            # Handle 24-hour days - generate slots for entire day
            if day_is_24_hours:
                day_start = datetime.combine(current_date, time(0, 0, 0))
                day_end = datetime.combine(current_date, time(23, 59, 59))
            elif day_open_time and day_close_time:
                day_start = datetime.combine(current_date, day_open_time)
                # Handle overnight hours: close time is on the NEXT day
                if _is_overnight(day_open_time, day_close_time):
                    day_end = datetime.combine(current_date + timedelta(days=1), day_close_time)
                else:
                    day_end = datetime.combine(current_date, day_close_time)
            else:
                current_date += timedelta(days=1)
                continue

            # Determine the effective start time for this day
            if current_date == search_start_dt_local.date():
                # First day: start from search_start_dt_local (rounded up) or opening time, whichever is later
                normalized_start = search_start_dt_local.replace(second=0, microsecond=0)
                minutes = normalized_start.minute
                remainder = minutes % self.SLOT_INTERVAL_MINUTES
                if remainder == 0:
                    rounded_start = normalized_start
                else:
                    minutes_to_add = self.SLOT_INTERVAL_MINUTES - remainder
                    rounded_start = normalized_start + timedelta(minutes=minutes_to_add)
                slot_start = max(rounded_start, day_start)
            else:
                slot_start = day_start

            # Determine the effective end time
            slot_end = day_end
            # For the last day in search range, cap at end_dt_local
            if day_end.date() > end_dt_local.date():
                # Overnight extends past end_date - cap it
                slot_end = min(end_dt_local.replace(second=0, microsecond=0), day_end)
            elif (
                current_date == end_dt_local.date()
                and not day_is_24_hours
                and day_open_time
                and day_close_time
                and not _is_overnight(day_open_time, day_close_time)
            ):
                slot_end = min(end_dt_local.replace(second=0, microsecond=0), day_end)

            current_slot = slot_start
            while current_slot < slot_end:
                slot_key = current_slot.replace(second=0, microsecond=0)
                if slot_key not in processed_slots:
                    processed_slots.add(slot_key)
                    # Convert local slot to UTC for capacity lookup
                    slot_utc = slot_key.replace(tzinfo=business_tz).astimezone(timezone.utc)
                    slot_utc_naive = slot_utc.replace(tzinfo=None)
                    used_capacity = capacity_map.get(slot_utc_naive, 0)
                    available_capacity = seating_capacity - used_capacity

                    requested_size = party_size or 1
                    if available_capacity >= requested_size:
                        slots.append(
                            {
                                "date_time": isoformat_z(slot_utc),
                                "available": True,
                                "available_capacity": available_capacity,
                            }
                        )

                current_slot += timedelta(minutes=self.SLOT_INTERVAL_MINUTES)

            current_date += timedelta(days=1)

        return {
            "business_id": business_id,
            "start_date_time": start_date_time,
            "forward_minutes": forward,
            "backward_minutes": backward,
            "party_size": party_size,
            "seating_capacity": seating_capacity,
            "advance_days": advance_days,
            "slots": slots,
            "total_available": len(slots),
        }

    def lock_slot(
        self, business_id: int, party_size: int, date_time: str, booking_attribute: str = "default"
    ) -> Dict[str, Any]:
        """
        Lock a booking slot.

        Args:
            business_id: Restaurant ID
            party_size: Party size
            date_time: Date and time (ISO format)
            booking_attribute: Booking attribute

        Returns:
            Slot lock response with booking_token
        """
        business = self.business_repo.get_by_id(business_id)
        if not business:
            raise ValueError(f"Restaurant with ID {business_id} not found")
        business_tz, _ = resolve_business_timezone(business)

        seating_capacity = business.get("booking_seating_capacity", 50)

        try:
            slot_dt_utc = parse_datetime(date_time)
            slot_dt_local = slot_dt_utc.astimezone(business_tz).replace(tzinfo=None)
            slot_dt_local = slot_dt_local.replace(second=0, microsecond=0)
        except ValueError:
            raise ValueError(f"Invalid date_time format: {date_time}")

        self._validate_future_time(slot_dt_local, business)
        self._validate_opening_hours(slot_dt_local, business)

        slot_dt_utc = slot_dt_local.replace(tzinfo=business_tz).astimezone(timezone.utc)
        slot_dt_utc_naive = slot_dt_utc.replace(tzinfo=None)

        # Check capacity - only confirmed bookings count against capacity
        self._check_capacity(business_id, slot_dt_utc_naive, party_size, seating_capacity)

        booking_token = str(uuid.uuid4())
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=self.SLOT_EXPIRY_MINUTES)

        slot_id = self.booking_repo.create_slot_booking(
            business_id=business_id,
            date_time=slot_dt_utc_naive,
            expires_at=expires_at,
            booking_token=booking_token,
            booking_type=self.RESERVATION_TYPE,
            status="reserved",
            party_size=party_size,
        )

        return {
            "booking_token": booking_token,
            "date_time": isoformat_z(slot_dt_utc),
            "party_size": party_size,
            "expires_at": isoformat_z(expires_at),
            "slot_id": slot_id,
        }

    def create_booking(
        self,
        business_id: int,
        booking_token: str,
        name: str,
        phone_number: str,
        email_address: Optional[str] = None,
        special_request: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Create a booking (pending status).

        Args:
            business_id: Restaurant ID
            booking_token: Token from slot lock
            name: Full name
            phone_number: Phone number
            email_address: Email address (optional)
            special_request: Special request (optional)

        Returns:
            Booking response
        """
        # Get slot by token
        slot = self.booking_repo.get_slot_by_token(
            booking_token=booking_token, booking_type=self.RESERVATION_TYPE
        )

        if not slot:
            raise ValueError("Invalid or expired booking token")

        # Validate that the slot belongs to the specified business
        if slot["business_id"] != business_id:
            raise ValueError("Booking token does not belong to the specified business")

        if slot["status"] != "reserved":
            raise ValueError("Slot is not reserved or has expired")

        # Check if slot has expired
        if isinstance(slot["expires_at"], datetime):
            if slot["expires_at"] < datetime.now():
                raise ValueError("Booking token has expired")

        # Create or get user
        user_data = {"name": name, "phone_number": phone_number}
        # Add email if provided
        if email_address:
            user_data["email"] = email_address
        user_id = self.user_repo.create_or_update_user(user_data)

        # Create user-business metadata mapping (for dashboard user visibility)
        try:
            self.metadata_repo.create_mapping(
                user_id=user_id,
                business_id=business_id,
                source="booking",
                notes="Created via API booking",
            )
        except Exception as meta_err:
            # Log but don't fail booking creation if metadata mapping fails
            self.logger.warning("Failed to create user-business metadata: %s", meta_err)

        # Generate confirmation number
        confirmation_number = f"INH-{business_id}-{uuid.uuid4().hex[:8].upper()}"

        # Create booking with pending status
        # Get party_size from slot if available
        party_size = slot.get("party_size")
        booking_id = self.booking_repo.create_booking(
            slot_booking_id=slot["id"],
            user_id=user_id,
            confirmation_number=confirmation_number,
            booking_type=self.RESERVATION_TYPE,
            status="pending",
            special_request=special_request,
            party_size=party_size,
        )

        return {
            "booking_id": booking_id,
            "confirmation_number": confirmation_number,
            "status": "pending",
            "date_time": (
                isoformat_z(slot["date_time"]) if isinstance(slot["date_time"], datetime) else slot["date_time"]
            ),
            "message": "Booking created successfully. Awaiting confirmation from business.",
        }

    def finalize_booking(self, booking_id: int, confirmation_number: Optional[str] = None) -> Dict[str, Any]:
        """
        Finalize a booking (dashboard only).
        Changes status from 'pending' to 'confirmed'.

        Args:
            booking_id: Booking ID
            confirmation_number: Optional confirmation number override

        Returns:
            Finalized booking response
        """
        booking = self.booking_repo.get_booking_by_id(
            booking_id=booking_id, booking_type=self.RESERVATION_TYPE
        )

        if not booking:
            raise ValueError(f"Booking with ID {booking_id} not found")

        if booking["status"] != "pending":
            raise ValueError(f"Booking is not in pending status. Current status: {booking['status']}")

        business = self.business_repo.get_by_id(booking["business_id"])
        if not business:
            raise ValueError(f"Restaurant with ID {booking['business_id']} not found")

        slot_dt = booking.get("date_time")
        if isinstance(slot_dt, datetime):
            slot_dt = slot_dt.replace(second=0, microsecond=0)
        else:
            slot_dt = parse_datetime(str(slot_dt)).replace(tzinfo=None, second=0, microsecond=0)

        seating_capacity = business.get("booking_seating_capacity", 50)
        used_capacity = self.booking_repo.get_slot_confirmed_capacity(
            business_id=int(booking["business_id"]),
            date_time=slot_dt,
            booking_type=self.RESERVATION_TYPE,
        )
        party_size = booking.get("party_size") or 0
        if party_size > seating_capacity - used_capacity:
            raise ValueError("Not enough capacity to confirm this booking at the requested time.")

        # Finalize booking
        if not self.booking_repo.finalize_booking(
            booking_id=booking_id, confirmation_number=confirmation_number
        ):
            raise ValueError("Failed to finalize booking")

        # Get updated booking
        updated_booking = self.booking_repo.get_booking_by_id(
            booking_id=booking_id, booking_type=self.RESERVATION_TYPE
        )

        return {
            "booking_id": booking_id,
            "confirmation_number": updated_booking["confirmation_number"],
            "status": "confirmed",
            "message": "Booking confirmed successfully",
        }

    def get_booking(self, booking_id: int) -> Dict[str, Any]:
        """
        Get a booking by ID.

        Args:
            booking_id: Booking ID

        Returns:
            Booking details
        """
        booking = self.booking_repo.get_booking_by_id(
            booking_id=booking_id, booking_type=self.RESERVATION_TYPE
        )

        if not booking:
            raise ValueError(f"Booking with ID {booking_id} not found")

        return booking

    def get_bookings_by_business(
        self,
        business_id: int,
        status: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> Dict[str, Any]:
        """
        Get bookings for a business.

        Args:
            business_id: Restaurant ID
            status: Filter by status
            start_date: Filter by start date
            end_date: Filter by end date
            limit: Limit results
            offset: Offset for pagination

        Returns:
            List of bookings
        """
        start_dt = None
        end_dt = None

        if start_date:
            try:
                start_dt = parse_datetime(start_date).replace(tzinfo=None)
            except ValueError:
                raise ValueError(f"Invalid start_date format: {start_date}")

        if end_date:
            try:
                end_dt = parse_datetime(end_date).replace(tzinfo=None)
            except ValueError:
                raise ValueError(f"Invalid end_date format: {end_date}")

        bookings = self.booking_repo.get_bookings_by_business(
            business_id=business_id,
            booking_type=self.RESERVATION_TYPE,
            status=status,
            start_date=start_dt,
            end_date=end_dt,
            limit=limit,
            offset=offset,
        )

        return {"business_id": business_id, "bookings": bookings, "total": len(bookings)}

    def cancel_booking(self, booking_id: int) -> Dict[str, Any]:
        """
        Cancel a booking.

        Args:
            booking_id: Booking ID

        Returns:
            Cancellation response
        """
        booking = self.booking_repo.get_booking_by_id(
            booking_id=booking_id, booking_type=self.RESERVATION_TYPE
        )

        if not booking:
            raise ValueError(f"Booking with ID {booking_id} not found")

        if booking["status"] in ["cancelled", "completed"]:
            raise ValueError(f"Cannot cancel booking with status: {booking['status']}")

        if not self.booking_repo.cancel_booking(booking_id):
            raise ValueError("Failed to cancel booking")

        # Update slot status back to available
        self.booking_repo.update_slot_status(slot_id=booking["slot_booking_id"], status="available")

        return {
            "booking_id": booking_id,
            "status": "cancelled",
            "message": "Booking cancelled successfully",
        }

    # ---------- Dashboard-specific methods ----------

    def create_booking_direct(
        self,
        business_id: int,
        date_time: str,
        party_size: int,
        name: str,
        phone_number: str,
        email_address: Optional[str] = None,
        special_request: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Create a booking directly (for dashboard).
        Creates slot booking and confirmed booking in a single transaction.
        Validates capacity and opening hours.

        Args:
            business_id: Restaurant ID
            date_time: Date and time (ISO format)
            party_size: Party size
            name: Guest name
            phone_number: Guest phone number
            email_address: Guest email (optional)
            special_request: Special request (optional)
            notes: Notes (optional)

        Returns:
            Booking response with confirmation details
        """
        business = self.business_repo.get_by_id(business_id)
        if not business:
            raise ValueError(f"Restaurant with ID {business_id} not found")
        business_tz, _ = resolve_business_timezone(business)

        seating_capacity = business.get("booking_seating_capacity", 50)

        try:
            slot_dt_utc = parse_datetime(date_time)
            slot_dt_local = slot_dt_utc.astimezone(business_tz).replace(tzinfo=None)
            slot_dt_local = slot_dt_local.replace(second=0, microsecond=0)
        except ValueError:
            raise ValueError(f"Invalid date_time format: {date_time}")

        self._validate_future_time(slot_dt_local, business)
        self._validate_opening_hours(slot_dt_local, business)

        slot_dt_utc = slot_dt_local.replace(tzinfo=business_tz).astimezone(timezone.utc)
        slot_dt_utc_naive = slot_dt_utc.replace(tzinfo=None)

        self._validate_advance_booking(slot_dt_utc_naive, business)
        self._check_capacity(business_id, slot_dt_utc_naive, party_size, seating_capacity)

        user_data = {"name": name, "phone_number": phone_number}
        if email_address:
            user_data["email"] = email_address
        user_id = self.user_repo.create_or_update_user(user_data)

        try:
            self.metadata_repo.create_mapping(
                user_id=user_id,
                business_id=business_id,
                source="booking",
                notes="Created via dashboard direct booking",
            )
        except Exception as meta_err:
            self.logger.warning("Failed to create user-business metadata: %s", meta_err)

        confirmation_number = f"INH-{business_id}-{uuid.uuid4().hex[:8].upper()}"

        result = self.booking_repo.create_booking_direct(
            business_id=business_id,
            date_time=slot_dt_utc_naive,
            user_id=user_id,
            confirmation_number=confirmation_number,
            party_size=party_size,
            booking_type=self.RESERVATION_TYPE,
            special_request=special_request,
            notes=notes,
        )

        return {
            "booking_id": result["booking_id"],
            "slot_id": result["slot_id"],
            "confirmation_number": confirmation_number,
            "status": "confirmed",
            "date_time": isoformat_z(slot_dt_utc),
            "party_size": party_size,
            "name": name,
            "phone_number": phone_number,
            "email_address": email_address,
            "special_request": special_request,
            "notes": notes,
            "message": "Booking created and confirmed successfully",
        }

    def update_booking_notes(self, booking_id: int, notes: Optional[str]) -> Dict[str, Any]:
        """
        Update booking notes.

        Args:
            booking_id: Booking ID
            notes: Notes text (can be None to clear notes)

        Returns:
            Updated booking response
        """
        booking = self.booking_repo.get_booking_by_id(
            booking_id=booking_id, booking_type=self.RESERVATION_TYPE
        )

        if not booking:
            raise ValueError(f"Booking with ID {booking_id} not found")

        if not self.booking_repo.update_booking_notes(booking_id, notes):
            raise ValueError("Failed to update booking notes")

        return {
            "booking_id": booking_id,
            "notes": notes,
            "message": "Notes updated successfully",
        }

    def update_booking(
        self,
        booking_id: int,
        date_time: Optional[str] = None,
        party_size: Optional[int] = None,
        special_request: Optional[str] = None,
        notes: Optional[str] = None,
        confirmation_number: Optional[str] = None,
        status: Optional[str] = None,
        last_cancel_time: Optional[str] = None,
        manage_booking_url: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Update booking and slot booking details.

        Args:
            booking_id: Booking ID
            date_time: New booking date/time in ISO format (updates slot_bookings)
            party_size: Number of guests (optional)
            special_request: Guest's special requests (optional)
            notes: Internal staff notes (optional)
            confirmation_number: Confirmation number override (optional)
            status: Booking status (optional)
            last_cancel_time: Cancellation deadline in ISO format (optional)
            manage_booking_url: Booking management URL (optional)

        Returns:
            Updated booking with all details

        Raises:
            ValueError: If booking not found, invalid status, or time slot conflict
        """
        booking = self.booking_repo.get_booking_by_id(
            booking_id=booking_id, booking_type=self.RESERVATION_TYPE
        )

        if not booking:
            raise ValueError(f"Booking with ID {booking_id} not found")

        # Validate status if provided
        valid_statuses = ["pending", "confirmed", "cancelled", "completed", "no_show"]
        if status is not None and status not in valid_statuses:
            raise ValueError(f"Invalid status '{status}'. Must be one of: {', '.join(valid_statuses)}")

        # Parse date_time (slot timing) if provided
        if date_time is not None:
            try:
                new_date_time = parse_datetime(date_time)
                # Normalize to minute precision
                new_date_time = new_date_time.replace(second=0, microsecond=0).replace(tzinfo=None)
            except ValueError:
                raise ValueError(f"Invalid date_time format: {date_time}. Use ISO format.")
        else:
            new_date_time = None

        party_size_value = party_size if party_size is not None else booking.get("party_size")
        candidate_status = status or booking.get("status")
        if candidate_status == "confirmed":
            business = self.business_repo.get_by_id(booking.get("business_id"))
            if not business:
                raise ValueError(f"Restaurant with ID {booking.get('business_id')} not found")
            slot_dt = new_date_time if new_date_time is not None else booking.get("date_time")
            original_slot_dt = booking.get("date_time")
            if isinstance(slot_dt, datetime):
                slot_dt = slot_dt.replace(second=0, microsecond=0)
            else:
                slot_dt = parse_datetime(str(slot_dt)).replace(tzinfo=None, second=0, microsecond=0)
            if isinstance(original_slot_dt, datetime):
                original_slot_dt = original_slot_dt.replace(second=0, microsecond=0)
            else:
                original_slot_dt = parse_datetime(str(original_slot_dt)).replace(tzinfo=None, second=0, microsecond=0)
            if new_date_time is not None:
                self._validate_future_time(slot_dt, business)
            seating_capacity = business.get("booking_seating_capacity", 50)
            used_capacity = self.booking_repo.get_slot_confirmed_capacity(
                business_id=int(booking.get("business_id")),
                date_time=slot_dt,
                booking_type=self.RESERVATION_TYPE,
            )
            if booking.get("status") == "confirmed" and slot_dt == original_slot_dt:
                used_capacity -= booking.get("party_size") or 0
            if (party_size_value or 0) > seating_capacity - used_capacity:
                raise ValueError("Not enough capacity to confirm this booking at the requested time.")

        # Update slot booking date_time after validation
        if new_date_time is not None:
            slot_booking_id = booking.get("slot_booking_id")
            if not slot_booking_id:
                raise ValueError("Booking has no associated slot booking")
            if not self.booking_repo.update_slot_booking_datetime(slot_booking_id, new_date_time):
                raise ValueError("Failed to update slot timing")

        # Parse last_cancel_time if provided
        last_cancel_time_dt = None
        if last_cancel_time is not None:
            try:
                last_cancel_time_dt = parse_datetime(last_cancel_time).replace(tzinfo=None)
            except ValueError:
                raise ValueError(f"Invalid last_cancel_time format: {last_cancel_time}. Use ISO format.")

        # Update booking fields (if any provided)
        has_booking_updates = any(
            [
                party_size is not None,
                special_request is not None,
                notes is not None,
                confirmation_number is not None,
                status is not None,
                last_cancel_time_dt is not None,
                manage_booking_url is not None,
            ]
        )

        if has_booking_updates:
            if not self.booking_repo.update_booking(
                booking_id=booking_id,
                party_size=party_size,
                special_request=special_request,
                notes=notes,
                confirmation_number=confirmation_number,
                status=status,
                last_cancel_time=last_cancel_time_dt,
                manage_booking_url=manage_booking_url,
            ):
                raise ValueError("Failed to update booking fields")

        # Get updated booking
        updated_booking = self.booking_repo.get_booking_by_id(
            booking_id=booking_id, booking_type=self.RESERVATION_TYPE
        )

        return updated_booking

    def get_booking_with_business_check(self, booking_id: int) -> Dict[str, Any]:
        """
        Get booking by ID with business_id included for authorization checks.
        The business_id is obtained from the slot_bookings table via INNER JOIN.

        Args:
            booking_id: Booking ID

        Returns:
            Booking details including business_id (guaranteed to be an int)

        Raises:
            ValueError: If booking not found or has no associated slot_booking
        """
        booking = self.booking_repo.get_booking_by_id(
            booking_id=booking_id, booking_type=self.RESERVATION_TYPE
        )

        if not booking:
            raise ValueError(f"Booking with ID {booking_id} not found")

        # Ensure business_id is properly typed as int for authorization checks
        business_id = booking.get("business_id")
        if business_id is not None:
            booking["business_id"] = int(business_id)

        return booking

    def get_booking_business_id(self, booking_id: int) -> Optional[int]:
        """
        Get just the business_id for a booking (for authorization checks).
        More efficient than fetching the full booking.

        Args:
            booking_id: Booking ID

        Returns:
            business_id if found, None otherwise
        """
        return self.booking_repo.get_booking_business_id(booking_id)
