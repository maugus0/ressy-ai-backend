"""
In-House Reservation Service for handling table reservations.
"""

from typing import Dict, Optional, Any
from datetime import datetime, timedelta
import uuid
from app.repositories.mysql_reservation_repo import MySQLReservationRepository
from app.repositories.mysql_restaurant_repo import MySQLRestaurantRepository
from app.repositories.mysql_user_repo import MySQLUserRepository


class ReservationService:
    """Service for in-house reservation operations."""

    RESERVATION_TYPE = "inhouse"
    SLOT_DURATION_MINUTES = 90  # Default slot duration
    SLOT_EXPIRY_MINUTES = 15  # Time before slot expires
    SLOT_INTERVAL_MINUTES = 15  # Interval between slots

    def __init__(self):
        self.reservation_repo = MySQLReservationRepository()
        self.restaurant_repo = MySQLRestaurantRepository()
        self.user_repo = MySQLUserRepository()

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

        Args:
            restaurant_id: Restaurant ID
            start_date_time: Start date and time (ISO format)
            forward_minutes: Forward booking window
            backward_minutes: Backward booking window
            party_size: Party size

        Returns:
            Availability response with available slots
        """
        # Get restaurant configuration
        restaurant = self.restaurant_repo.get_by_id(restaurant_id)
        if not restaurant:
            raise ValueError(f"Restaurant with ID {restaurant_id} not found")

        # Get opening and closing times
        opening_time_str = restaurant.get("opening_time", "09:00:00")
        closing_time_str = restaurant.get("closing_time", "22:00:00")

        # Parse opening and closing times
        try:
            opening_time = datetime.strptime(str(opening_time_str), "%H:%M:%S").time()
            closing_time = datetime.strptime(str(closing_time_str), "%H:%M:%S").time()
        except (ValueError, TypeError):
            # Default to 9 AM - 10 PM if parsing fails
            opening_time = datetime.strptime("09:00:00", "%H:%M:%S").time()
            closing_time = datetime.strptime("22:00:00", "%H:%M:%S").time()

        # Use restaurant's forward/backward minutes if not provided
        forward = forward_minutes or restaurant.get("forward_minutes", 1440)  # Default 24 hours
        backward = backward_minutes or restaurant.get("backward_minutes", 0)

        # Parse start date time
        try:
            start_dt = datetime.fromisoformat(start_date_time.replace("Z", "+00:00"))
            # Remove timezone info for local time calculations
            if start_dt.tzinfo:
                start_dt = start_dt.replace(tzinfo=None)
        except ValueError:
            raise ValueError(f"Invalid date_time format: {start_date_time}")

        # Calculate time range
        end_dt = start_dt + timedelta(minutes=forward)
        search_start_dt = start_dt - timedelta(minutes=backward)

        # Get locked slots from Slot_Bookings table
        locked_slots = self.reservation_repo.get_locked_slots(
            restaurant_id=restaurant_id,
            start_date_time=search_start_dt,
            end_date_time=end_dt,
            reservation_type=self.RESERVATION_TYPE,
        )

        # Create a set of locked slot datetimes for quick lookup
        locked_datetimes = set()
        for locked_slot in locked_slots:
            slot_dt = locked_slot["date_time"]
            if isinstance(slot_dt, datetime):
                # Normalize to minute precision (remove seconds/microseconds)
                slot_dt = slot_dt.replace(second=0, microsecond=0)
            locked_datetimes.add(slot_dt)

        # Generate all possible slots based on opening/closing times
        slots = []
        current_date = start_dt.date()
        end_date = end_dt.date()

        # Generate slots for each day in the range
        while current_date <= end_date:
            # Combine date with opening time
            day_start = datetime.combine(current_date, opening_time)
            day_end = datetime.combine(current_date, closing_time)

            # Adjust start time if it's the first day and start_dt is later
            if current_date == start_dt.date():
                # Start from the provided start_date_time rounded up to next 15-minute interval, or opening time, whichever is later
                normalized_start = start_dt.replace(second=0, microsecond=0)
                # Round up to next 15-minute interval
                minutes = normalized_start.minute
                remainder = minutes % self.SLOT_INTERVAL_MINUTES
                if remainder == 0:
                    # Already on a 15-minute interval
                    rounded_start = normalized_start
                else:
                    # Round up to next 15-minute interval
                    minutes_to_add = self.SLOT_INTERVAL_MINUTES - remainder
                    rounded_start = normalized_start + timedelta(minutes=minutes_to_add)
                slot_start = max(rounded_start, day_start)
            else:
                slot_start = day_start

            # Adjust end time if it's the last day and end_dt is earlier
            if current_date == end_dt.date():
                slot_end = min(end_dt.replace(second=0, microsecond=0), day_end)
            else:
                slot_end = day_end

            # Generate slots with 15-minute intervals
            current_slot = slot_start
            while current_slot < slot_end:
                # Check if slot is locked
                slot_dt_normalized = current_slot.replace(second=0, microsecond=0)
                if slot_dt_normalized not in locked_datetimes:
                    slots.append({"date_time": current_slot.isoformat(), "available": True})

                # Move to next slot (15 minutes later)
                current_slot += timedelta(minutes=self.SLOT_INTERVAL_MINUTES)

            # Move to next day
            current_date += timedelta(days=1)

        return {
            "restaurant_id": restaurant_id,
            "start_date_time": start_date_time,
            "forward_minutes": forward,
            "backward_minutes": backward,
            "party_size": party_size,
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
        # Get restaurant configuration
        restaurant = self.restaurant_repo.get_by_id(restaurant_id)
        if not restaurant:
            raise ValueError(f"Restaurant with ID {restaurant_id} not found")

        # Get opening and closing times
        opening_time_str = restaurant.get("opening_time", "09:00:00")
        closing_time_str = restaurant.get("closing_time", "22:00:00")

        # Parse opening and closing times
        try:
            opening_time = datetime.strptime(str(opening_time_str), "%H:%M:%S").time()
            closing_time = datetime.strptime(str(closing_time_str), "%H:%M:%S").time()
        except (ValueError, TypeError):
            # Default to 9 AM - 10 PM if parsing fails
            opening_time = datetime.strptime("09:00:00", "%H:%M:%S").time()
            closing_time = datetime.strptime("22:00:00", "%H:%M:%S").time()

        # Parse date time
        try:
            slot_dt = datetime.fromisoformat(date_time.replace("Z", "+00:00"))
            # Remove timezone info for local time calculations
            if slot_dt.tzinfo:
                slot_dt = slot_dt.replace(tzinfo=None)
            # Normalize to minute precision (remove seconds/microseconds)
            slot_dt = slot_dt.replace(second=0, microsecond=0)
        except ValueError:
            raise ValueError(f"Invalid date_time format: {date_time}")

        # Validate slot is within opening/closing hours
        slot_time = slot_dt.time()
        if slot_time < opening_time or slot_time >= closing_time:
            raise ValueError(
                f"Slot time {slot_time} is outside restaurant operating hours ({opening_time} - {closing_time})"
            )

        # Check if slot is already locked
        locked_slots = self.reservation_repo.get_locked_slots(
            restaurant_id=restaurant_id,
            start_date_time=slot_dt,
            end_date_time=slot_dt + timedelta(minutes=1),
            reservation_type=self.RESERVATION_TYPE,
        )

        if locked_slots:
            raise ValueError("Slot is already locked/reserved")

        reservation_token = str(uuid.uuid4())
        expires_at = datetime.now() + timedelta(minutes=self.SLOT_EXPIRY_MINUTES)

        # Create new slot with locked status
        slot_id = self.reservation_repo.create_slot_booking(
            restaurant_id=restaurant_id,
            date_time=slot_dt,
            expires_at=expires_at,
            reservation_token=reservation_token,
            reservation_type=self.RESERVATION_TYPE,
            status="reserved",
        )

        return {
            "reservation_token": reservation_token,
            "date_time": date_time,
            "party_size": party_size,
            "expires_at": expires_at.isoformat(),
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

        # Generate confirmation number
        confirmation_number = f"INH-{restaurant_id}-{uuid.uuid4().hex[:8].upper()}"

        # Create reservation with pending status
        reservation_id = self.reservation_repo.create_reservation(
            slot_booking_id=slot["id"],
            user_id=user_id,
            confirmation_number=confirmation_number,
            reservation_type=self.RESERVATION_TYPE,
            status="pending",
        )

        return {
            "reservation_id": reservation_id,
            "confirmation_number": confirmation_number,
            "status": "pending",
            "date_time": (
                slot["date_time"].isoformat() if isinstance(slot["date_time"], datetime) else slot["date_time"]
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
                start_dt = datetime.fromisoformat(start_date.replace("Z", "+00:00"))
            except ValueError:
                raise ValueError(f"Invalid start_date format: {start_date}")

        if end_date:
            try:
                end_dt = datetime.fromisoformat(end_date.replace("Z", "+00:00"))
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

        total_count = self.reservation_repo.get_reservations_count_by_restaurant(
            restaurant_id=restaurant_id,
            reservation_type=self.RESERVATION_TYPE,
            status=status,
            start_date=start_dt,
            end_date=end_dt,
        )

        return {"restaurant_id": restaurant_id, "reservations": reservations, "total": total_count}

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
