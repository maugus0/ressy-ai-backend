"""
In-House Reservation Service for handling table reservations.
"""

import uuid
from datetime import datetime, time, timedelta, timezone
from typing import Any, Dict, Optional

from app.repositories.mysql_reservation_repo import MySQLReservationRepository
from app.repositories.mysql_restaurant_repo import MySQLRestaurantRepository
from app.repositories.mysql_user_repo import MySQLUserRepository
from app.repositories.mysql_user_restaurant_metadata_repo import (
    MySQLUserRestaurantMetadataRepository,
)
from app.utils.logging_config import get_logger
from app.utils.restaurant_hours import (
    _parse_operating_time,
    format_operating_window,
    get_day_operating_hours,
    is_datetime_within_operating_hours,
    resolve_restaurant_timezone,
)
from app.utils.timezone import isoformat_z, parse_datetime


class ReservationService:
    """Service for in-house reservation operations."""

    RESERVATION_TYPE = "in-house"
    SLOT_DURATION_MINUTES = 90  # Default slot duration
    SLOT_EXPIRY_MINUTES = 15  # Time before slot expires
    SLOT_INTERVAL_MINUTES = 15  # Interval between slots

    def __init__(self):
        self.logger = get_logger(__name__)
        self.reservation_repo = MySQLReservationRepository()
        self.restaurant_repo = MySQLRestaurantRepository()
        self.user_repo = MySQLUserRepository()
        self.metadata_repo = MySQLUserRestaurantMetadataRepository()

    def _parse_time(self, time_str: Any, default: str = "09:00:00") -> time:
        """Parse time string or timedelta to time object using shared utility."""
        parsed = _parse_operating_time(time_str)
        if parsed is not None:
            return parsed
        return datetime.strptime(default, "%H:%M:%S").time()

    def _validate_advance_booking(self, slot_dt: datetime, restaurant: Dict[str, Any]) -> None:
        """Validate that reservation is within advance booking limit."""
        advance_days = restaurant.get("reservation_advance_days", 30)
        max_booking_date = datetime.now() + timedelta(days=advance_days)
        if slot_dt > max_booking_date:
            raise ValueError(f"Reservations can only be made up to {advance_days} days in advance")

    def _validate_opening_hours(self, slot_dt: datetime, restaurant: Dict[str, Any]) -> None:
        """Validate that reservation is during opening hours using shared utility."""
        if not is_datetime_within_operating_hours(restaurant, slot_dt):
            day_name = slot_dt.strftime("%A").lower()
            hours_display = format_operating_window(restaurant, day_name)
            raise ValueError(f"Reservations can only be made during opening hours ({hours_display})")

    def _check_capacity(self, restaurant_id: int, slot_dt: datetime, party_size: int, seating_capacity: int) -> None:
        """Check if there's enough capacity for the party size."""
        used_capacity = self.reservation_repo.get_slot_confirmed_capacity(
            restaurant_id=restaurant_id,
            date_time=slot_dt,
            reservation_type=self.RESERVATION_TYPE,
        )
        available_capacity = seating_capacity - used_capacity
        if party_size > available_capacity:
            raise ValueError(f"Not enough capacity for party of {party_size}. Available: {available_capacity}")

    def get_availability(
        self,
        restaurant_id: int,
        start_date_time: str,
        forward_minutes: Optional[int] = None,
        backward_minutes: Optional[int] = None,
        party_size: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Get table availability for a restaurant.
        Only confirmed reservations reduce available capacity.

        Args:
            restaurant_id: Restaurant ID
            start_date_time: Start date and time (ISO format)
            forward_minutes: Forward booking window
            backward_minutes: Backward booking window
            party_size: Party size to check capacity for

        Returns:
            Availability response with available slots
        """
        restaurant = self.restaurant_repo.get_by_id(restaurant_id)
        if not restaurant:
            raise ValueError(f"Restaurant with ID {restaurant_id} not found")
        restaurant_tz, _ = resolve_restaurant_timezone(restaurant)

        seating_capacity = restaurant.get("reservation_seating_capacity", 50)
        advance_days = restaurant.get("reservation_advance_days", 30)

        forward = forward_minutes if forward_minutes is not None else restaurant.get("forward_minutes", 1440)
        backward = backward_minutes if backward_minutes is not None else restaurant.get("backward_minutes", 0)

        try:
            start_dt_utc = parse_datetime(start_date_time)
            start_dt_local = start_dt_utc.astimezone(restaurant_tz).replace(tzinfo=None)
        except ValueError:
            raise ValueError(f"Invalid date_time format: {start_date_time}")

        # Calculate time range
        end_dt_local = start_dt_local + timedelta(minutes=forward)
        search_start_dt_local = start_dt_local - timedelta(minutes=backward)

        def _local_naive_to_utc_naive(local_dt: datetime) -> datetime:
            return local_dt.replace(tzinfo=restaurant_tz).astimezone(timezone.utc).replace(tzinfo=None)

        end_dt_utc = _local_naive_to_utc_naive(end_dt_local)
        search_start_dt_utc = _local_naive_to_utc_naive(search_start_dt_local)

        max_booking_date = datetime.now() + timedelta(days=advance_days)
        if end_dt_local > max_booking_date:
            end_dt_local = max_booking_date

        capacity_map = self.reservation_repo.get_confirmed_capacity_by_slot(
            restaurant_id=restaurant_id,
            start_date_time=search_start_dt_utc,
            end_date_time=end_dt_utc,
            reservation_type=self.RESERVATION_TYPE,
        )

        # Generate all possible slots based on per-day operating hours
        slots = []
        current_date = search_start_dt_local.date()
        end_date = end_dt_local.date()

        while current_date <= end_date:
            # Get operating hours for this specific day
            day_name = current_date.strftime("%A").lower()
            day_open_time, day_close_time, day_is_closed = get_day_operating_hours(restaurant, day_name)

            # Skip closed days
            if day_is_closed or not day_open_time or not day_close_time:
                current_date += timedelta(days=1)
                continue

            day_start = datetime.combine(current_date, day_open_time)
            day_end = datetime.combine(current_date, day_close_time)

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

            # Determine the effective end time for this day
            if current_date == end_dt_local.date():
                # Last day: end at end_dt_local or closing time, whichever is earlier
                slot_end = min(end_dt_local.replace(second=0, microsecond=0), day_end)
            else:
                slot_end = day_end

            current_slot = slot_start
            while current_slot < slot_end:
                slot_dt_normalized = current_slot.replace(second=0, microsecond=0)
                # Convert local slot to UTC for capacity lookup
                slot_utc = slot_dt_normalized.replace(tzinfo=restaurant_tz).astimezone(timezone.utc)
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
            "restaurant_id": restaurant_id,
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
        self, restaurant_id: int, party_size: int, date_time: str, reservation_attribute: str = "default"
    ) -> Dict[str, Any]:
        """
        Lock a booking slot.

        Args:
            restaurant_id: Restaurant ID
            party_size: Party size
            date_time: Date and time (ISO format)
            reservation_attribute: Reservation attribute

        Returns:
            Slot lock response with reservation_token
        """
        restaurant = self.restaurant_repo.get_by_id(restaurant_id)
        if not restaurant:
            raise ValueError(f"Restaurant with ID {restaurant_id} not found")
        restaurant_tz, _ = resolve_restaurant_timezone(restaurant)

        seating_capacity = restaurant.get("reservation_seating_capacity", 50)

        try:
            slot_dt_utc = parse_datetime(date_time)
            slot_dt_local = slot_dt_utc.astimezone(restaurant_tz).replace(tzinfo=None)
            slot_dt_local = slot_dt_local.replace(second=0, microsecond=0)
        except ValueError:
            raise ValueError(f"Invalid date_time format: {date_time}")

        self._validate_opening_hours(slot_dt_local, restaurant)

        slot_dt_utc = slot_dt_local.replace(tzinfo=restaurant_tz).astimezone(timezone.utc)
        slot_dt_utc_naive = slot_dt_utc.replace(tzinfo=None)

        # Check capacity - only confirmed reservations count against capacity
        self._check_capacity(restaurant_id, slot_dt_utc_naive, party_size, seating_capacity)

        reservation_token = str(uuid.uuid4())
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=self.SLOT_EXPIRY_MINUTES)

        slot_id = self.reservation_repo.create_slot_booking(
            restaurant_id=restaurant_id,
            date_time=slot_dt_utc_naive,
            expires_at=expires_at,
            reservation_token=reservation_token,
            reservation_type=self.RESERVATION_TYPE,
            status="reserved",
            party_size=party_size,
        )

        return {
            "reservation_token": reservation_token,
            "date_time": isoformat_z(slot_dt_utc),
            "party_size": party_size,
            "expires_at": isoformat_z(expires_at),
            "slot_id": slot_id,
        }

    def create_reservation(
        self,
        restaurant_id: int,
        reservation_token: str,
        name: str,
        phone_number: str,
        email_address: Optional[str] = None,
        special_request: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Create a reservation (pending status).

        Args:
            restaurant_id: Restaurant ID
            reservation_token: Token from slot lock
            name: Full name
            phone_number: Phone number
            email_address: Email address (optional)
            special_request: Special request (optional)

        Returns:
            Reservation response
        """
        # Get slot by token
        slot = self.reservation_repo.get_slot_by_token(
            reservation_token=reservation_token, reservation_type=self.RESERVATION_TYPE
        )

        if not slot:
            raise ValueError("Invalid or expired reservation token")

        # Validate that the slot belongs to the specified restaurant
        if slot["restaurant_id"] != restaurant_id:
            raise ValueError("Reservation token does not belong to the specified restaurant")

        if slot["status"] != "reserved":
            raise ValueError("Slot is not reserved or has expired")

        # Check if slot has expired
        if isinstance(slot["expires_at"], datetime):
            if slot["expires_at"] < datetime.now():
                raise ValueError("Reservation token has expired")

        # Create or get user
        user_data = {"name": name, "phone_number": phone_number}
        # Add email if provided
        if email_address:
            user_data["email"] = email_address
        user_id = self.user_repo.create_or_update_user(user_data)

        # Create user-restaurant metadata mapping (for dashboard user visibility)
        try:
            self.metadata_repo.create_mapping(
                user_id=user_id,
                restaurant_id=restaurant_id,
                source="reservation",
                notes="Created via API reservation",
            )
        except Exception as meta_err:
            # Log but don't fail reservation creation if metadata mapping fails
            self.logger.warning("Failed to create user-restaurant metadata: %s", meta_err)

        # Generate confirmation number
        confirmation_number = f"INH-{restaurant_id}-{uuid.uuid4().hex[:8].upper()}"

        # Create reservation with pending status
        # Get party_size from slot if available
        party_size = slot.get("party_size")
        reservation_id = self.reservation_repo.create_reservation(
            slot_booking_id=slot["id"],
            user_id=user_id,
            confirmation_number=confirmation_number,
            reservation_type=self.RESERVATION_TYPE,
            status="pending",
            special_request=special_request,
            party_size=party_size,
        )

        return {
            "reservation_id": reservation_id,
            "confirmation_number": confirmation_number,
            "status": "pending",
            "date_time": (
                isoformat_z(slot["date_time"]) if isinstance(slot["date_time"], datetime) else slot["date_time"]
            ),
            "message": "Reservation created successfully. Awaiting confirmation from restaurant.",
        }

    def finalize_reservation(self, reservation_id: int, confirmation_number: Optional[str] = None) -> Dict[str, Any]:
        """
        Finalize a reservation (dashboard only).
        Changes status from 'pending' to 'confirmed'.

        Args:
            reservation_id: Reservation ID
            confirmation_number: Optional confirmation number override

        Returns:
            Finalized reservation response
        """
        reservation = self.reservation_repo.get_reservation_by_id(
            reservation_id=reservation_id, reservation_type=self.RESERVATION_TYPE
        )

        if not reservation:
            raise ValueError(f"Reservation with ID {reservation_id} not found")

        if reservation["status"] != "pending":
            raise ValueError(f"Reservation is not in pending status. Current status: {reservation['status']}")

        # Finalize reservation
        if not self.reservation_repo.finalize_reservation(
            reservation_id=reservation_id, confirmation_number=confirmation_number
        ):
            raise ValueError("Failed to finalize reservation")

        # Get updated reservation
        updated_reservation = self.reservation_repo.get_reservation_by_id(
            reservation_id=reservation_id, reservation_type=self.RESERVATION_TYPE
        )

        return {
            "reservation_id": reservation_id,
            "confirmation_number": updated_reservation["confirmation_number"],
            "status": "confirmed",
            "message": "Reservation confirmed successfully",
        }

    def get_reservation(self, reservation_id: int) -> Dict[str, Any]:
        """
        Get a reservation by ID.

        Args:
            reservation_id: Reservation ID

        Returns:
            Reservation details
        """
        reservation = self.reservation_repo.get_reservation_by_id(
            reservation_id=reservation_id, reservation_type=self.RESERVATION_TYPE
        )

        if not reservation:
            raise ValueError(f"Reservation with ID {reservation_id} not found")

        return reservation

    def get_reservations_by_restaurant(
        self,
        restaurant_id: int,
        status: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> Dict[str, Any]:
        """
        Get reservations for a restaurant.

        Args:
            restaurant_id: Restaurant ID
            status: Filter by status
            start_date: Filter by start date
            end_date: Filter by end date
            limit: Limit results
            offset: Offset for pagination

        Returns:
            List of reservations
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

        reservations = self.reservation_repo.get_reservations_by_restaurant(
            restaurant_id=restaurant_id,
            reservation_type=self.RESERVATION_TYPE,
            status=status,
            start_date=start_dt,
            end_date=end_dt,
            limit=limit,
            offset=offset,
        )

        return {"restaurant_id": restaurant_id, "reservations": reservations, "total": len(reservations)}

    def cancel_reservation(self, reservation_id: int) -> Dict[str, Any]:
        """
        Cancel a reservation.

        Args:
            reservation_id: Reservation ID

        Returns:
            Cancellation response
        """
        reservation = self.reservation_repo.get_reservation_by_id(
            reservation_id=reservation_id, reservation_type=self.RESERVATION_TYPE
        )

        if not reservation:
            raise ValueError(f"Reservation with ID {reservation_id} not found")

        if reservation["status"] in ["cancelled", "completed"]:
            raise ValueError(f"Cannot cancel reservation with status: {reservation['status']}")

        if not self.reservation_repo.cancel_reservation(reservation_id):
            raise ValueError("Failed to cancel reservation")

        # Update slot status back to available
        self.reservation_repo.update_slot_status(slot_id=reservation["slot_booking_id"], status="available")

        return {
            "reservation_id": reservation_id,
            "status": "cancelled",
            "message": "Reservation cancelled successfully",
        }

    # ---------- Dashboard-specific methods ----------

    def create_reservation_direct(
        self,
        restaurant_id: int,
        date_time: str,
        party_size: int,
        name: str,
        phone_number: str,
        email_address: Optional[str] = None,
        special_request: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Create a reservation directly (for dashboard).
        Creates slot booking and confirmed reservation in a single transaction.
        Validates capacity and opening hours.

        Args:
            restaurant_id: Restaurant ID
            date_time: Date and time (ISO format)
            party_size: Party size
            name: Guest name
            phone_number: Guest phone number
            email_address: Guest email (optional)
            special_request: Special request (optional)
            notes: Notes (optional)

        Returns:
            Reservation response with confirmation details
        """
        restaurant = self.restaurant_repo.get_by_id(restaurant_id)
        if not restaurant:
            raise ValueError(f"Restaurant with ID {restaurant_id} not found")
        restaurant_tz, _ = resolve_restaurant_timezone(restaurant)

        seating_capacity = restaurant.get("reservation_seating_capacity", 50)

        try:
            slot_dt_utc = parse_datetime(date_time)
            slot_dt_local = slot_dt_utc.astimezone(restaurant_tz).replace(tzinfo=None)
            slot_dt_local = slot_dt_local.replace(second=0, microsecond=0)
        except ValueError:
            raise ValueError(f"Invalid date_time format: {date_time}")

        self._validate_opening_hours(slot_dt_local, restaurant)

        slot_dt_utc = slot_dt_local.replace(tzinfo=restaurant_tz).astimezone(timezone.utc)
        slot_dt_utc_naive = slot_dt_utc.replace(tzinfo=None)

        self._validate_advance_booking(slot_dt_utc_naive, restaurant)
        self._check_capacity(restaurant_id, slot_dt_utc_naive, party_size, seating_capacity)

        user_data = {"name": name, "phone_number": phone_number}
        if email_address:
            user_data["email"] = email_address
        user_id = self.user_repo.create_or_update_user(user_data)

        try:
            self.metadata_repo.create_mapping(
                user_id=user_id,
                restaurant_id=restaurant_id,
                source="reservation",
                notes="Created via dashboard direct reservation",
            )
        except Exception as meta_err:
            self.logger.warning("Failed to create user-restaurant metadata: %s", meta_err)

        confirmation_number = f"INH-{restaurant_id}-{uuid.uuid4().hex[:8].upper()}"

        result = self.reservation_repo.create_reservation_direct(
            restaurant_id=restaurant_id,
            date_time=slot_dt_utc_naive,
            user_id=user_id,
            confirmation_number=confirmation_number,
            party_size=party_size,
            reservation_type=self.RESERVATION_TYPE,
            special_request=special_request,
            notes=notes,
        )

        return {
            "reservation_id": result["reservation_id"],
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
            "message": "Reservation created and confirmed successfully",
        }

    def update_reservation_notes(self, reservation_id: int, notes: Optional[str]) -> Dict[str, Any]:
        """
        Update reservation notes.

        Args:
            reservation_id: Reservation ID
            notes: Notes text (can be None to clear notes)

        Returns:
            Updated reservation response
        """
        reservation = self.reservation_repo.get_reservation_by_id(
            reservation_id=reservation_id, reservation_type=self.RESERVATION_TYPE
        )

        if not reservation:
            raise ValueError(f"Reservation with ID {reservation_id} not found")

        if not self.reservation_repo.update_reservation_notes(reservation_id, notes):
            raise ValueError("Failed to update reservation notes")

        return {
            "reservation_id": reservation_id,
            "notes": notes,
            "message": "Notes updated successfully",
        }

    def update_reservation(
        self,
        reservation_id: int,
        date_time: Optional[str] = None,
        party_size: Optional[int] = None,
        special_request: Optional[str] = None,
        notes: Optional[str] = None,
        confirmation_number: Optional[str] = None,
        status: Optional[str] = None,
        last_cancel_time: Optional[str] = None,
        manage_reservation_url: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Update reservation and slot booking details.

        Args:
            reservation_id: Reservation ID
            date_time: New reservation date/time in ISO format (updates slot_bookings)
            party_size: Number of guests (optional)
            special_request: Guest's special requests (optional)
            notes: Internal staff notes (optional)
            confirmation_number: Confirmation number override (optional)
            status: Reservation status (optional)
            last_cancel_time: Cancellation deadline in ISO format (optional)
            manage_reservation_url: Reservation management URL (optional)

        Returns:
            Updated reservation with all details

        Raises:
            ValueError: If reservation not found, invalid status, or time slot conflict
        """
        reservation = self.reservation_repo.get_reservation_by_id(
            reservation_id=reservation_id, reservation_type=self.RESERVATION_TYPE
        )

        if not reservation:
            raise ValueError(f"Reservation with ID {reservation_id} not found")

        # Validate status if provided
        valid_statuses = ["pending", "confirmed", "cancelled", "completed", "no_show"]
        if status is not None and status not in valid_statuses:
            raise ValueError(f"Invalid status '{status}'. Must be one of: {', '.join(valid_statuses)}")

        # Parse and update date_time (slot timing) if provided
        if date_time is not None:
            try:
                new_date_time = parse_datetime(date_time)
                # Normalize to minute precision
                new_date_time = new_date_time.replace(second=0, microsecond=0).replace(tzinfo=None)
            except ValueError:
                raise ValueError(f"Invalid date_time format: {date_time}. Use ISO format.")

            # Get the slot_booking_id from the reservation
            slot_booking_id = reservation.get("slot_booking_id")
            if not slot_booking_id:
                raise ValueError("Reservation has no associated slot booking")

            # Update the slot booking date_time
            if not self.reservation_repo.update_slot_booking_datetime(slot_booking_id, new_date_time):
                raise ValueError("Failed to update slot timing")

        # Parse last_cancel_time if provided
        last_cancel_time_dt = None
        if last_cancel_time is not None:
            try:
                last_cancel_time_dt = parse_datetime(last_cancel_time).replace(tzinfo=None)
            except ValueError:
                raise ValueError(f"Invalid last_cancel_time format: {last_cancel_time}. Use ISO format.")

        # Update reservation fields (if any provided)
        has_reservation_updates = any(
            [
                party_size is not None,
                special_request is not None,
                notes is not None,
                confirmation_number is not None,
                status is not None,
                last_cancel_time_dt is not None,
                manage_reservation_url is not None,
            ]
        )

        if has_reservation_updates:
            if not self.reservation_repo.update_reservation(
                reservation_id=reservation_id,
                party_size=party_size,
                special_request=special_request,
                notes=notes,
                confirmation_number=confirmation_number,
                status=status,
                last_cancel_time=last_cancel_time_dt,
                manage_reservation_url=manage_reservation_url,
            ):
                raise ValueError("Failed to update reservation fields")

        # Get updated reservation
        updated_reservation = self.reservation_repo.get_reservation_by_id(
            reservation_id=reservation_id, reservation_type=self.RESERVATION_TYPE
        )

        return updated_reservation

    def get_reservation_with_restaurant_check(self, reservation_id: int) -> Dict[str, Any]:
        """
        Get reservation by ID with restaurant_id included for authorization checks.
        The restaurant_id is obtained from the slot_bookings table via INNER JOIN.

        Args:
            reservation_id: Reservation ID

        Returns:
            Reservation details including restaurant_id (guaranteed to be an int)

        Raises:
            ValueError: If reservation not found or has no associated slot_booking
        """
        reservation = self.reservation_repo.get_reservation_by_id(
            reservation_id=reservation_id, reservation_type=self.RESERVATION_TYPE
        )

        if not reservation:
            raise ValueError(f"Reservation with ID {reservation_id} not found")

        # Ensure restaurant_id is properly typed as int for authorization checks
        restaurant_id = reservation.get("restaurant_id")
        if restaurant_id is not None:
            reservation["restaurant_id"] = int(restaurant_id)

        return reservation

    def get_reservation_restaurant_id(self, reservation_id: int) -> Optional[int]:
        """
        Get just the restaurant_id for a reservation (for authorization checks).
        More efficient than fetching the full reservation.

        Args:
            reservation_id: Reservation ID

        Returns:
            restaurant_id if found, None otherwise
        """
        return self.reservation_repo.get_reservation_restaurant_id(reservation_id)
