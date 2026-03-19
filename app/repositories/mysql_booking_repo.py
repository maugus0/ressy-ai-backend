"""
MySQL Booking Repository for in-house booking operations.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from mysql.connector import Error

from app.repositories.mysql_base import MySQLBaseRepository
from app.utils.logging_config import get_logger


class MySQLBookingRepository(MySQLBaseRepository):
    """Repository for in-house booking data access in MySQL."""

    logger = get_logger(__name__)

    # Table Availability Requests
    def create_availability_request(
        self, business_id: int, start_date_time: datetime, party_size: int, booking_type: str = "in-house"
    ) -> int:
        """Create a table availability request."""
        query = """
            INSERT INTO Availability_Requests
            (business_id, start_date_time, party_size, reservation_type)
            VALUES (%s, %s, %s, %s)
        """
        return self._execute_insert(query, (business_id, start_date_time, party_size, booking_type))

    def get_availability_requests(
        self,
        business_id: int,
        start_date_time: Optional[datetime] = None,
        end_date_time: Optional[datetime] = None,
        booking_type: Optional[str] = None,
    ) -> List[Dict]:
        """Get availability requests for a restaurant."""
        query = """
            SELECT
                id,
                business_id,
                start_date_time,
                party_size,
                reservation_type,
                created_at,
                updated_at
            FROM Availability_Requests
            WHERE business_id = %s
        """
        params = [business_id]

        if booking_type:
            query += " AND reservation_type = %s"
            params.append(booking_type)

        if start_date_time:
            query += " AND start_date_time >= %s"
            params.append(start_date_time)

        if end_date_time:
            query += " AND start_date_time <= %s"
            params.append(end_date_time)

        query += " ORDER BY start_date_time ASC"

        return self._execute_query(query, tuple(params))

    # Slot Bookings
    def create_booking_slot(
        self,
        business_id: int,
        date_time: datetime,
        expires_at: datetime,
        booking_token: str,
        booking_type: str = "in-house",
        status: str = "available",
        party_size: Optional[int] = None,
    ) -> int:
        """Create a slot booking."""
        query = """
            INSERT INTO Booking_Slots
            (business_id, reservation_type, date_time, expires_at, status, booking_token, party_size)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """
        return self._execute_insert(
            query, (business_id, booking_type, date_time, expires_at, status, booking_token, party_size)
        )

    def get_available_booking_slots(
        self,
        business_id: int,
        start_date_time: datetime,
        end_date_time: datetime,
        party_size: Optional[int] = None,
        booking_type: Optional[str] = None,
    ) -> List[Dict]:
        """Get available slots for a restaurant within a time range."""
        query = """
            SELECT
                id,
                business_id,
                reservation_type,
                date_time,
                expires_at,
                status,
                booking_token,
                created_at,
                updated_at
            FROM Booking_Slots
            WHERE business_id = %s
                AND date_time >= %s
                AND date_time <= %s
                AND status = 'available'
                AND expires_at > NOW()
        """
        params = [business_id, start_date_time, end_date_time]

        if booking_type:
            query = query.replace("WHERE business_id = %s", "WHERE business_id = %s AND reservation_type = %s")
            params.insert(1, booking_type)

        if party_size:
            # For now, we'll assume slots can accommodate any party size
            # You might want to add a party_size column to Booking_Slots if needed
            pass

        query += " ORDER BY date_time ASC"
        return self._execute_query(query, tuple(params))

    def get_locked_booking_slots(
        self,
        business_id: int,
        start_date_time: datetime,
        end_date_time: datetime,
        booking_type: Optional[str] = None,
    ) -> List[Dict]:
        """Get locked/reserved slots for a restaurant within a time range."""
        query = """
            SELECT
                date_time
            FROM Booking_Slots
            WHERE business_id = %s
                AND date_time >= %s
                AND date_time <= %s
                AND status IN ('reserved', 'locked')
                AND (expires_at IS NULL OR expires_at > NOW())
        """
        params = [business_id, start_date_time, end_date_time]

        if booking_type:
            query = query.replace("WHERE business_id = %s", "WHERE business_id = %s AND reservation_type = %s")
            params.insert(1, booking_type)

        query += " ORDER BY date_time ASC"
        return self._execute_query(query, tuple(params))

    def get_confirmed_capacity_by_slot(
        self,
        business_id: int,
        start_date_time: datetime,
        end_date_time: datetime,
        booking_type: Optional[str] = None,
    ) -> Dict[datetime, int]:
        """
        Get used capacity (sum of party_size) for each time slot based on confirmed bookings only.
        Pending bookings are excluded from capacity calculation.
        """
        query = """
            SELECT
                bs.date_time,
                COALESCE(SUM(b.party_size), 0) as used_capacity
            FROM Booking_Slots bs
            INNER JOIN Bookings b ON bs.id = b.slot_booking_id
            WHERE bs.business_id = %s
                AND bs.date_time >= %s
                AND bs.date_time <= %s
                AND b.status = 'confirmed'
        """
        params: List[Any] = [business_id, start_date_time, end_date_time]

        if booking_type:
            query += " AND bs.reservation_type = %s"
            params.append(booking_type)

        query += " GROUP BY bs.date_time ORDER BY bs.date_time ASC"
        results = self._execute_query(query, tuple(params))

        capacity_map: Dict[datetime, int] = {}
        for row in results:
            slot_dt = row["date_time"]
            if isinstance(slot_dt, datetime):
                slot_dt = slot_dt.replace(second=0, microsecond=0)
            capacity_map[slot_dt] = int(row["used_capacity"])
        return capacity_map

    def get_slot_confirmed_capacity(
        self,
        business_id: int,
        date_time: datetime,
        booking_type: Optional[str] = None,
    ) -> int:
        """
        Get used capacity for a specific time slot based on confirmed bookings only.
        """
        query = """
            SELECT COALESCE(SUM(b.party_size), 0) as used_capacity
            FROM Booking_Slots bs
            INNER JOIN Bookings b ON bs.id = b.slot_booking_id
            WHERE bs.business_id = %s
                AND bs.date_time = %s
                AND b.status = 'confirmed'
        """
        params: List[Any] = [business_id, date_time]

        if booking_type:
            query += " AND bs.reservation_type = %s"
            params.append(booking_type)

        results = self._execute_query(query, tuple(params))
        return int(results[0]["used_capacity"]) if results else 0

    def get_booking_slot_by_token(self, booking_token: str, booking_type: Optional[str] = None) -> Optional[Dict]:
        """Get a slot booking by booking token."""
        query = """
            SELECT
                id,
                business_id,
                reservation_type,
                date_time,
                expires_at,
                status,
                booking_token,
                party_size,
                created_at,
                updated_at
            FROM Booking_Slots
            WHERE booking_token = %s
        """
        params = [booking_token]

        if booking_type:
            query += " AND reservation_type = %s"
            params.append(booking_type)

        query += " LIMIT 1"
        results = self._execute_query(query, tuple(params))
        return results[0] if results else None

    def lock_slot(self, slot_id: int, booking_token: str) -> bool:
        """Lock a slot by updating its status to 'reserved'."""
        query = """
            UPDATE Booking_Slots
            SET status = 'reserved',
                booking_token = %s,
                updated_at = NOW()
            WHERE id = %s AND status = 'available' AND expires_at > NOW()
        """
        affected = self._execute_update(query, (booking_token, slot_id))
        return affected > 0

    def update_booking_slot_status(self, slot_id: int, status: str) -> bool:
        """Update slot status."""
        query = """
            UPDATE Booking_Slots
            SET status = %s,
                updated_at = NOW()
            WHERE id = %s
        """
        affected = self._execute_update(query, (status, slot_id))
        return affected > 0

    def update_slot_booking_datetime(self, slot_id: int, date_time: datetime) -> bool:
        """
        Update slot booking date_time (booking timing).

        Args:
            slot_id: Slot booking ID
            date_time: New date and time for the booking

        Returns:
            True if updated successfully, False otherwise
        """
        query = """
            UPDATE Booking_Slots
            SET date_time = %s,
                updated_at = NOW()
            WHERE id = %s
        """
        affected = self._execute_update(query, (date_time, slot_id))
        return affected > 0

    def expire_slots(self) -> int:
        """Expire slots that have passed their expiration time."""
        query = """
            UPDATE Booking_Slots
            SET status = 'expired',
                updated_at = NOW()
            WHERE status IN ('available', 'reserved')
                AND expires_at <= NOW()
        """
        return self._execute_update(query)

    # Bookings
    def create_booking(
        self,
        slot_booking_id: int,
        user_id: int,
        confirmation_number: str,
        table_availability_request_id: Optional[int] = None,
        booking_type: str = "in-house",
        status: str = "pending",
        last_cancel_time: Optional[datetime] = None,
        manage_booking_url: Optional[str] = None,
        special_request: Optional[str] = None,
        party_size: Optional[int] = None,
        notes: Optional[str] = None,
    ) -> int:
        """Create a booking."""
        query = """
            INSERT INTO Bookings
            (reservation_type, table_availability_request_id, slot_booking_id, user_id,
             confirmation_number, status, last_cancel_time, manage_booking_url, special_request, party_size, notes)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        return self._execute_insert(
            query,
            (
                booking_type,
                table_availability_request_id,
                slot_booking_id,
                user_id,
                confirmation_number,
                status,
                last_cancel_time,
                manage_booking_url,
                special_request,
                party_size,
                notes,
            ),
        )

    def create_booking_direct(
        self,
        business_id: int,
        date_time: datetime,
        user_id: int,
        confirmation_number: str,
        party_size: int,
        booking_type: str = "in-house",
        special_request: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Create a booking directly in a single transaction (for dashboard).
        Creates slot booking and confirmed booking atomically.

        Returns:
            Dict with booking_id and slot_id
        """
        import uuid as uuid_module

        booking_token = str(uuid_module.uuid4())

        # Use connection pool with transaction
        connection = None
        cursor = None
        try:
            connection = self._get_connection()
            if connection is None:
                raise RuntimeError("Database connection unavailable")

            cursor = connection.cursor()

            # Insert slot booking
            slot_query = """
                INSERT INTO Booking_Slots
                (business_id, booking_type, date_time, expires_at, status, booking_token, party_size)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """
            cursor.execute(
                slot_query,
                (
                    business_id,
                    booking_type,
                    date_time,
                    date_time,  # expires_at same as date_time for direct bookings
                    "reserved",
                    booking_token,
                    party_size,
                ),
            )
            slot_id = cursor.lastrowid

            # Insert booking with slot_id
            cursor.execute(
                """
                INSERT INTO Bookings
                (reservation_type, slot_booking_id, user_id, confirmation_number, status, special_request, party_size, notes)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    booking_type,
                    slot_id,
                    user_id,
                    confirmation_number,
                    "confirmed",
                    special_request,
                    party_size,
                    notes,
                ),
            )
            booking_id = cursor.lastrowid

            connection.commit()
            return {"booking_id": booking_id, "slot_id": slot_id}
        except Error as e:
            if connection:
                try:
                    connection.rollback()
                except Exception:
                    # Rollback may fail if connection is already closed - safe to ignore
                    pass
            self.logger.exception("Error creating direct booking: %s", e)
            raise
        finally:
            if cursor:
                try:
                    cursor.close()
                except Exception:
                    # Cursor may already be closed or in invalid state - safe to ignore
                    pass
            self._return_connection(connection)

    def get_booking_business_id(self, booking_id: int) -> Optional[int]:
        """
        Get the business_id for a booking by joining with slot_bookings.
        This is used for authorization checks.

        Args:
            booking_id: Booking ID

        Returns:
            business_id if found, None otherwise
        """
        query = """
            SELECT bs.business_id
            FROM Bookings b
            INNER JOIN Booking_Slots bs ON b.slot_booking_id = bs.id
            WHERE b.id = %s
            LIMIT 1
        """
        results = self._execute_query(query, (booking_id,))
        if results and results[0].get("business_id") is not None:
            return int(results[0]["business_id"])
        return None

    def get_booking_by_id(self, booking_id: int, booking_type: Optional[str] = None) -> Optional[Dict]:
        """Get a booking by ID with full details including business_id from slot_bookings."""
        query = """
            SELECT
                b.id,
                b.reservation_type,
                b.availability_request_id,
                b.slot_booking_id,
                b.user_id,
                b.confirmation_number,
                b.last_cancel_time,
                b.manage_reservation_url,
                b.status,
                b.special_request,
                b.party_size,
                b.notes,
                b.created_at,
                b.updated_at,
                bs.date_time,
                bs.business_id,
                u.name,
                u.email,
                u.phone_number
            FROM Bookings b
            INNER JOIN Booking_Slots bs ON b.slot_booking_id = bs.id
            LEFT JOIN Users u ON b.user_id = u.id
            WHERE b.id = %s
        """
        params = [booking_id]

        if booking_type:
            query += " AND b.reservation_type = %s"
            params.append(booking_type)

        query += " LIMIT 1"
        results = self._execute_query(query, tuple(params))

        return results[0] if results else None

    def get_booking_by_confirmation(
        self, confirmation_number: str, booking_type: Optional[str] = None
    ) -> Optional[Dict]:
        """Get a booking by confirmation number."""
        query = """
            SELECT
                b.id,
                b.reservation_type,
                b.availability_request_id,
                b.slot_booking_id,
                b.user_id,
                b.confirmation_number,
                b.last_cancel_time,
                b.manage_reservation_url,
                b.status,
                b.special_request,
                b.party_size,
                b.notes,
                b.created_at,
                b.updated_at,
                bs.date_time,
                bs.business_id,
                u.name,
                u.email,
                u.phone_number
            FROM Bookings b
            INNER JOIN Booking_Slots bs ON b.slot_booking_id = bs.id
            LEFT JOIN Users u ON b.user_id = u.id
            WHERE b.confirmation_number = %s
        """
        params = [confirmation_number]

        if booking_type:
            query += " AND b.reservation_type = %s"
            params.append(booking_type)

        query += " LIMIT 1"
        results = self._execute_query(query, tuple(params))
        return results[0] if results else None

    def get_bookings_by_restaurant(
        self,
        business_id: int,
        booking_type: Optional[str] = None,
        status: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Dict]:
        """Get bookings for a restaurant."""
        query = """
            SELECT
                b.id,
                b.reservation_type,
                b.availability_request_id,
                b.slot_booking_id,
                b.user_id,
                b.confirmation_number,
                b.last_cancel_time,
                b.manage_reservation_url,
                b.status,
                b.special_request,
                b.party_size,
                b.notes,
                b.created_at,
                b.updated_at,
                bs.date_time,
                bs.business_id,
                u.name,
                u.email,
                u.phone_number
            FROM Bookings b
            INNER JOIN Booking_Slots bs ON b.slot_booking_id = bs.id
            LEFT JOIN Users u ON b.user_id = u.id
            WHERE bs.business_id = %s
        """
        params = [business_id]

        if booking_type:
            query += " AND b.reservation_type = %s"
            params.append(booking_type)

        if status:
            query += " AND b.status = %s"
            params.append(status)

        if start_date:
            query += " AND bs.date_time >= %s"
            params.append(start_date)

        if end_date:
            query += " AND bs.date_time <= %s"
            params.append(end_date)

        query += " ORDER BY bs.date_time DESC LIMIT %s OFFSET %s"
        params.extend([limit, offset])

        return self._execute_query(query, tuple(params))

    def update_booking_status(self, booking_id: int, status: str) -> bool:
        """Update booking status."""
        query = """
            UPDATE Bookings
            SET status = %s,
                updated_at = NOW()
            WHERE id = %s
        """
        affected = self._execute_update(query, (status, booking_id))
        return affected > 0

    def finalize_booking(self, booking_id: int, confirmation_number: Optional[str] = None) -> bool:
        """Finalize a booking by changing status from 'pending' to 'confirmed'."""
        if confirmation_number:
            query = """
                UPDATE Bookings
                SET status = 'confirmed',
                    confirmation_number = %s,
                    updated_at = NOW()
                WHERE id = %s AND status = 'pending'
            """
            affected = self._execute_update(query, (confirmation_number, booking_id))
        else:
            query = """
                UPDATE Bookings
                SET status = 'confirmed',
                    updated_at = NOW()
                WHERE id = %s AND status = 'pending'
            """
            affected = self._execute_update(query, (booking_id,))
        return affected > 0

    def cancel_booking(self, booking_id: int) -> bool:
        """Cancel a booking."""
        query = """
            UPDATE Bookings
            SET status = 'cancelled',
                updated_at = NOW()
            WHERE id = %s AND status IN ('pending', 'confirmed')
        """
        affected = self._execute_update(query, (booking_id,))
        return affected > 0

    def update_booking_notes(self, booking_id: int, notes: Optional[str]) -> bool:
        """Update booking notes."""
        query = """
            UPDATE Bookings
            SET notes = %s,
                updated_at = NOW()
            WHERE id = %s
        """
        affected = self._execute_update(query, (notes, booking_id))
        return affected > 0

    def update_booking(
        self,
        booking_id: int,
        party_size: Optional[int] = None,
        special_request: Optional[str] = None,
        notes: Optional[str] = None,
        confirmation_number: Optional[str] = None,
        status: Optional[str] = None,
        last_cancel_time: Optional[datetime] = None,
        manage_booking_url: Optional[str] = None,
    ) -> bool:
        """
        Update booking fields from the bookings table.

        Args:
            booking_id: Booking ID
            party_size: Number of guests
            special_request: Guest's special requests
            notes: Internal staff notes
            confirmation_number: Confirmation number
            status: Booking status
            last_cancel_time: Cancellation deadline
            manage_booking_url: Booking management URL

        Returns:
            True if at least one row was updated, False otherwise
        """
        # Whitelist of allowed field names to prevent SQL injection
        allowed_fields = {
            "party_size",
            "special_request",
            "notes",
            "confirmation_number",
            "status",
            "last_cancel_time",
            "manage_booking_url",
        }

        # Build update fields from provided parameters
        update_mapping = {
            "party_size": party_size,
            "special_request": special_request,
            "notes": notes,
            "confirmation_number": confirmation_number,
            "status": status,
            "last_cancel_time": last_cancel_time,
            "manage_booking_url": manage_booking_url,
        }

        fields = []
        params = []

        for field_name, value in update_mapping.items():
            if value is not None and field_name in allowed_fields:
                fields.append(f"{field_name} = %s")
                params.append(value)

        if not fields:
            return False

        fields.append("updated_at = NOW()")
        params.append(booking_id)

        # Safe query construction - field names are from whitelist only
        query = "UPDATE Bookings SET " + ", ".join(fields) + " WHERE id = %s"
        affected = self._execute_update(query, tuple(params))
        return affected > 0

    def get_latest_by_user(
        self, user_id: int, booking_type: Optional[str] = None, business_id: Optional[int] = None
    ) -> Optional[Dict]:
        """
        Get the most recent booking for a user.

        Args:
            user_id: User ID
            booking_type: Optional filter by booking type
            business_id: Optional filter by restaurant

        Returns:
            Latest booking dict or None if not found
        """
        query = """
            SELECT
                b.id,
                b.reservation_type,
                b.availability_request_id,
                b.slot_booking_id,
                b.user_id,
                b.confirmation_number,
                b.last_cancel_time,
                b.manage_reservation_url,
                b.status,
                b.special_request,
                b.party_size,
                b.notes,
                b.created_at,
                b.updated_at,
                bs.date_time,
                bs.business_id,
                u.name,
                u.email,
                u.phone_number
            FROM Bookings b
            INNER JOIN Booking_Slots bs ON b.slot_booking_id = bs.id
            LEFT JOIN Users u ON b.user_id = u.id
            WHERE b.user_id = %s
        """
        params = [user_id]

        if booking_type:
            query += " AND b.reservation_type = %s"
            params.append(booking_type)

        if business_id is not None:
            query += " AND bs.business_id = %s"
            params.append(business_id)

        query += " ORDER BY b.created_at DESC LIMIT 1"
        results = self._execute_query(query, tuple(params))
        return results[0] if results else None

    def get_booking_counts_by_status(
        self,
        business_id: int,
    ) -> Dict[str, int]:
        """
        Get booking counts grouped by status in a single query.

        Args:
            business_id: Restaurant ID

        Returns:
            Dictionary mapping status to count (lowercase keys)
        """
        query = """
            SELECT LOWER(b.status) as status, COUNT(*) as count
            FROM Bookings b
            INNER JOIN Booking_Slots bs ON b.slot_booking_id = bs.id
            WHERE bs.business_id = %s
            GROUP BY LOWER(b.status)
        """
        results = self._execute_query(query, (business_id,))
        return {row["status"]: row["count"] for row in results}

    def count_bookings_by_restaurant(
        self,
        business_id: int,
        status: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> int:
        """
        Count bookings for a restaurant with optional filters.

        Args:
            business_id: Restaurant ID
            status: Filter by status
            start_date: Filter by start date (date_time >= start_date)
            end_date: Filter by end date (date_time <= end_date)

        Returns:
            Count of matching bookings
        """
        query = """
            SELECT COUNT(*) as total
            FROM Bookings b
            INNER JOIN Booking_Slots bs ON b.slot_booking_id = bs.id
            WHERE bs.business_id = %s
        """
        params: List[Any] = [business_id]

        if status:
            query += " AND LOWER(b.status) = LOWER(%s)"
            params.append(status)

        if start_date:
            query += " AND bs.date_time >= %s"
            params.append(start_date)

        if end_date:
            query += " AND bs.date_time <= %s"
            params.append(end_date)

        results = self._execute_query(query, tuple(params))
        return results[0]["total"] if results else 0
