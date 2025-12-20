"""
MySQL Reservation Repository for in-house reservation operations.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from mysql.connector import Error

from app.repositories.mysql_base import MySQLBaseRepository


class MySQLReservationRepository(MySQLBaseRepository):
    """Repository for in-house reservation data access in MySQL."""

    # Table Availability Requests
    def create_availability_request(
        self, restaurant_id: int, start_date_time: datetime, party_size: int, reservation_type: str = "in-house"
    ) -> int:
        """Create a table availability request."""
        query = """
            INSERT INTO Table_Availability_Requests
            (restaurant_id, start_date_time, party_size, reservation_type)
            VALUES (%s, %s, %s, %s)
        """
        return self._execute_insert(query, (restaurant_id, start_date_time, party_size, reservation_type))

    def get_availability_requests(
        self,
        restaurant_id: int,
        start_date_time: Optional[datetime] = None,
        end_date_time: Optional[datetime] = None,
        reservation_type: Optional[str] = None,
    ) -> List[Dict]:
        """Get availability requests for a restaurant."""
        query = """
            SELECT
                id,
                restaurant_id,
                start_date_time,
                party_size,
                reservation_type,
                created_at,
                updated_at
            FROM Table_Availability_Requests
            WHERE restaurant_id = %s
        """
        params = [restaurant_id]

        if reservation_type:
            query += " AND reservation_type = %s"
            params.append(reservation_type)

        if start_date_time:
            query += " AND start_date_time >= %s"
            params.append(start_date_time)

        if end_date_time:
            query += " AND start_date_time <= %s"
            params.append(end_date_time)

        query += " ORDER BY start_date_time ASC"

        return self._execute_query(query, tuple(params))

    # Slot Bookings
    def create_slot_booking(
        self,
        restaurant_id: int,
        date_time: datetime,
        expires_at: datetime,
        reservation_token: str,
        reservation_type: str = "in-house",
        status: str = "available",
        party_size: Optional[int] = None,
    ) -> int:
        """Create a slot booking."""
        query = """
            INSERT INTO Slot_Bookings
            (restaurant_id, reservation_type, date_time, expires_at, status, reservation_token, party_size)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """
        return self._execute_insert(
            query, (restaurant_id, reservation_type, date_time, expires_at, status, reservation_token, party_size)
        )

    def get_available_slots(
        self,
        restaurant_id: int,
        start_date_time: datetime,
        end_date_time: datetime,
        party_size: Optional[int] = None,
        reservation_type: Optional[str] = None,
    ) -> List[Dict]:
        """Get available slots for a restaurant within a time range."""
        query = """
            SELECT
                id,
                restaurant_id,
                reservation_type,
                date_time,
                expires_at,
                status,
                reservation_token,
                created_at,
                updated_at
            FROM Slot_Bookings
            WHERE restaurant_id = %s
                AND date_time >= %s
                AND date_time <= %s
                AND status = 'available'
                AND expires_at > NOW()
        """
        params = [restaurant_id, start_date_time, end_date_time]

        if reservation_type:
            query = query.replace("WHERE restaurant_id = %s", "WHERE restaurant_id = %s AND reservation_type = %s")
            params.insert(1, reservation_type)

        if party_size:
            # For now, we'll assume slots can accommodate any party size
            # You might want to add a party_size column to Slot_Bookings if needed
            pass

        query += " ORDER BY date_time ASC"
        return self._execute_query(query, tuple(params))

    def get_locked_slots(
        self,
        restaurant_id: int,
        start_date_time: datetime,
        end_date_time: datetime,
        reservation_type: Optional[str] = None,
    ) -> List[Dict]:
        """Get locked/reserved slots for a restaurant within a time range."""
        query = """
            SELECT
                date_time
            FROM Slot_Bookings
            WHERE restaurant_id = %s
                AND date_time >= %s
                AND date_time <= %s
                AND status IN ('reserved', 'locked')
                AND (expires_at IS NULL OR expires_at > NOW())
        """
        params = [restaurant_id, start_date_time, end_date_time]

        if reservation_type:
            query = query.replace("WHERE restaurant_id = %s", "WHERE restaurant_id = %s AND reservation_type = %s")
            params.insert(1, reservation_type)

        query += " ORDER BY date_time ASC"
        return self._execute_query(query, tuple(params))

    def get_slot_by_token(self, reservation_token: str, reservation_type: Optional[str] = None) -> Optional[Dict]:
        """Get a slot booking by reservation token."""
        query = """
            SELECT
                id,
                restaurant_id,
                reservation_type,
                date_time,
                expires_at,
                status,
                reservation_token,
                party_size,
                created_at,
                updated_at
            FROM Slot_Bookings
            WHERE reservation_token = %s
        """
        params = [reservation_token]

        if reservation_type:
            query += " AND reservation_type = %s"
            params.append(reservation_type)

        query += " LIMIT 1"
        results = self._execute_query(query, tuple(params))
        return results[0] if results else None

    def lock_slot(self, slot_id: int, reservation_token: str) -> bool:
        """Lock a slot by updating its status to 'reserved'."""
        query = """
            UPDATE Slot_Bookings
            SET status = 'reserved',
                reservation_token = %s,
                updated_at = NOW()
            WHERE id = %s AND status = 'available' AND expires_at > NOW()
        """
        affected = self._execute_update(query, (reservation_token, slot_id))
        return affected > 0

    def update_slot_status(self, slot_id: int, status: str) -> bool:
        """Update slot status."""
        query = """
            UPDATE Slot_Bookings
            SET status = %s,
                updated_at = NOW()
            WHERE id = %s
        """
        affected = self._execute_update(query, (status, slot_id))
        return affected > 0

    def update_slot_booking_datetime(self, slot_id: int, date_time: datetime) -> bool:
        """
        Update slot booking date_time (reservation timing).

        Args:
            slot_id: Slot booking ID
            date_time: New date and time for the reservation

        Returns:
            True if updated successfully, False otherwise
        """
        query = """
            UPDATE Slot_Bookings
            SET date_time = %s,
                updated_at = NOW()
            WHERE id = %s
        """
        affected = self._execute_update(query, (date_time, slot_id))
        return affected > 0

    def expire_slots(self) -> int:
        """Expire slots that have passed their expiration time."""
        query = """
            UPDATE Slot_Bookings
            SET status = 'expired',
                updated_at = NOW()
            WHERE status IN ('available', 'reserved')
                AND expires_at <= NOW()
        """
        return self._execute_update(query)

    # Reservations
    def create_reservation(
        self,
        slot_booking_id: int,
        user_id: int,
        confirmation_number: str,
        table_availability_request_id: Optional[int] = None,
        reservation_type: str = "in-house",
        status: str = "pending",
        last_cancel_time: Optional[datetime] = None,
        manage_reservation_url: Optional[str] = None,
        special_request: Optional[str] = None,
        party_size: Optional[int] = None,
        notes: Optional[str] = None,
    ) -> int:
        """Create a reservation."""
        query = """
            INSERT INTO Reservations
            (reservation_type, table_availability_request_id, slot_booking_id, user_id,
             confirmation_number, status, last_cancel_time, manage_reservation_url, special_request, party_size, notes)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        return self._execute_insert(
            query,
            (
                reservation_type,
                table_availability_request_id,
                slot_booking_id,
                user_id,
                confirmation_number,
                status,
                last_cancel_time,
                manage_reservation_url,
                special_request,
                party_size,
                notes,
            ),
        )

    def create_reservation_direct(
        self,
        restaurant_id: int,
        date_time: datetime,
        user_id: int,
        confirmation_number: str,
        party_size: int,
        reservation_type: str = "in-house",
        special_request: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Create a reservation directly in a single transaction (for dashboard).
        Creates slot booking and confirmed reservation atomically.

        Returns:
            Dict with reservation_id and slot_id
        """
        # Create slot booking query
        slot_query = """
            INSERT INTO Slot_Bookings
            (restaurant_id, reservation_type, date_time, expires_at, status, reservation_token, party_size)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """
        import uuid

        reservation_token = str(uuid.uuid4())

        self._ensure_connected()
        cursor = None
        try:
            cursor = self.connection.cursor()

            # Insert slot booking
            cursor.execute(
                slot_query,
                (
                    restaurant_id,
                    reservation_type,
                    date_time,
                    date_time,  # expires_at same as date_time for direct bookings
                    "reserved",
                    reservation_token,
                    party_size,
                ),
            )
            slot_id = cursor.lastrowid

            # Insert reservation with slot_id
            cursor.execute(
                """
                INSERT INTO Reservations
                (reservation_type, slot_booking_id, user_id, confirmation_number, status, special_request, party_size, notes)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    reservation_type,
                    slot_id,
                    user_id,
                    confirmation_number,
                    "confirmed",
                    special_request,
                    party_size,
                    notes,
                ),
            )
            reservation_id = cursor.lastrowid

            self.connection.commit()
            return {"reservation_id": reservation_id, "slot_id": slot_id}
        except Error as e:
            self.connection.rollback()
            print(f"Error creating direct reservation: {e}")
            raise
        finally:
            if cursor:
                try:
                    cursor.close()
                except Exception:
                    pass

    def get_reservation_restaurant_id(self, reservation_id: int) -> Optional[int]:
        """
        Get the restaurant_id for a reservation by joining with slot_bookings.
        This is used for authorization checks.

        Args:
            reservation_id: Reservation ID

        Returns:
            restaurant_id if found, None otherwise
        """
        query = """
            SELECT sb.restaurant_id
            FROM Reservations r
            INNER JOIN Slot_Bookings sb ON r.slot_booking_id = sb.id
            WHERE r.id = %s
            LIMIT 1
        """
        results = self._execute_query(query, (reservation_id,))
        if results and results[0].get("restaurant_id") is not None:
            return int(results[0]["restaurant_id"])
        return None

    def get_reservation_by_id(self, reservation_id: int, reservation_type: Optional[str] = None) -> Optional[Dict]:
        """Get a reservation by ID with full details including restaurant_id from slot_bookings."""
        query = """
            SELECT
                r.id,
                r.reservation_type,
                r.table_availability_request_id,
                r.slot_booking_id,
                r.user_id,
                r.confirmation_number,
                r.last_cancel_time,
                r.manage_reservation_url,
                r.status,
                r.special_request,
                r.party_size,
                r.notes,
                r.created_at,
                r.updated_at,
                sb.date_time,
                sb.restaurant_id,
                u.name,
                u.email,
                u.phone_number
            FROM Reservations r
            INNER JOIN Slot_Bookings sb ON r.slot_booking_id = sb.id
            LEFT JOIN Users u ON r.user_id = u.id
            WHERE r.id = %s
        """
        params = [reservation_id]

        if reservation_type:
            query += " AND r.reservation_type = %s"
            params.append(reservation_type)

        query += " LIMIT 1"
        results = self._execute_query(query, tuple(params))

        return results[0] if results else None

    def get_reservation_by_confirmation(
        self, confirmation_number: str, reservation_type: Optional[str] = None
    ) -> Optional[Dict]:
        """Get a reservation by confirmation number."""
        query = """
            SELECT
                r.id,
                r.reservation_type,
                r.table_availability_request_id,
                r.slot_booking_id,
                r.user_id,
                r.confirmation_number,
                r.last_cancel_time,
                r.manage_reservation_url,
                r.status,
                r.special_request,
                r.party_size,
                r.notes,
                r.created_at,
                r.updated_at,
                sb.date_time,
                sb.restaurant_id,
                u.name,
                u.email,
                u.phone_number
            FROM Reservations r
            INNER JOIN Slot_Bookings sb ON r.slot_booking_id = sb.id
            LEFT JOIN Users u ON r.user_id = u.id
            WHERE r.confirmation_number = %s
        """
        params = [confirmation_number]

        if reservation_type:
            query += " AND r.reservation_type = %s"
            params.append(reservation_type)

        query += " LIMIT 1"
        results = self._execute_query(query, tuple(params))
        return results[0] if results else None

    def get_reservations_by_restaurant(
        self,
        restaurant_id: int,
        reservation_type: Optional[str] = None,
        status: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Dict]:
        """Get reservations for a restaurant."""
        query = """
            SELECT
                r.id,
                r.reservation_type,
                r.table_availability_request_id,
                r.slot_booking_id,
                r.user_id,
                r.confirmation_number,
                r.last_cancel_time,
                r.manage_reservation_url,
                r.status,
                r.special_request,
                r.party_size,
                r.notes,
                r.created_at,
                r.updated_at,
                sb.date_time,
                sb.restaurant_id,
                u.name,
                u.email,
                u.phone_number
            FROM Reservations r
            INNER JOIN Slot_Bookings sb ON r.slot_booking_id = sb.id
            LEFT JOIN Users u ON r.user_id = u.id
            WHERE sb.restaurant_id = %s
        """
        params = [restaurant_id]

        if reservation_type:
            query += " AND r.reservation_type = %s"
            params.append(reservation_type)

        if status:
            query += " AND r.status = %s"
            params.append(status)

        if start_date:
            query += " AND sb.date_time >= %s"
            params.append(start_date)

        if end_date:
            query += " AND sb.date_time <= %s"
            params.append(end_date)

        query += " ORDER BY sb.date_time DESC LIMIT %s OFFSET %s"
        params.extend([limit, offset])

        return self._execute_query(query, tuple(params))

    def update_reservation_status(self, reservation_id: int, status: str) -> bool:
        """Update reservation status."""
        query = """
            UPDATE Reservations
            SET status = %s,
                updated_at = NOW()
            WHERE id = %s
        """
        affected = self._execute_update(query, (status, reservation_id))
        return affected > 0

    def finalize_reservation(self, reservation_id: int, confirmation_number: Optional[str] = None) -> bool:
        """Finalize a reservation by changing status from 'pending' to 'confirmed'."""
        if confirmation_number:
            query = """
                UPDATE Reservations
                SET status = 'confirmed',
                    confirmation_number = %s,
                    updated_at = NOW()
                WHERE id = %s AND status = 'pending'
            """
            affected = self._execute_update(query, (confirmation_number, reservation_id))
        else:
            query = """
                UPDATE Reservations
                SET status = 'confirmed',
                    updated_at = NOW()
                WHERE id = %s AND status = 'pending'
            """
            affected = self._execute_update(query, (reservation_id,))
        return affected > 0

    def cancel_reservation(self, reservation_id: int) -> bool:
        """Cancel a reservation."""
        query = """
            UPDATE Reservations
            SET status = 'cancelled',
                updated_at = NOW()
            WHERE id = %s AND status IN ('pending', 'confirmed')
        """
        affected = self._execute_update(query, (reservation_id,))
        return affected > 0

    def update_reservation_notes(self, reservation_id: int, notes: Optional[str]) -> bool:
        """Update reservation notes."""
        query = """
            UPDATE Reservations
            SET notes = %s,
                updated_at = NOW()
            WHERE id = %s
        """
        affected = self._execute_update(query, (notes, reservation_id))
        return affected > 0

    def update_reservation(
        self,
        reservation_id: int,
        party_size: Optional[int] = None,
        special_request: Optional[str] = None,
        notes: Optional[str] = None,
        confirmation_number: Optional[str] = None,
        status: Optional[str] = None,
        last_cancel_time: Optional[datetime] = None,
        manage_reservation_url: Optional[str] = None,
    ) -> bool:
        """
        Update reservation fields from the reservations table.

        Args:
            reservation_id: Reservation ID
            party_size: Number of guests
            special_request: Guest's special requests
            notes: Internal staff notes
            confirmation_number: Confirmation number
            status: Reservation status
            last_cancel_time: Cancellation deadline
            manage_reservation_url: Reservation management URL

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
            "manage_reservation_url",
        }

        # Build update fields from provided parameters
        update_mapping = {
            "party_size": party_size,
            "special_request": special_request,
            "notes": notes,
            "confirmation_number": confirmation_number,
            "status": status,
            "last_cancel_time": last_cancel_time,
            "manage_reservation_url": manage_reservation_url,
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
        params.append(reservation_id)

        # Safe query construction - field names are from whitelist only
        query = "UPDATE Reservations SET " + ", ".join(fields) + " WHERE id = %s"
        affected = self._execute_update(query, tuple(params))
        return affected > 0

    def get_latest_by_user(self, user_id: int, reservation_type: Optional[str] = None) -> Optional[Dict]:
        """
        Get the most recent reservation for a user.

        Args:
            user_id: User ID
            reservation_type: Optional filter by reservation type

        Returns:
            Latest reservation dict or None if not found
        """
        query = """
            SELECT
                r.id,
                r.reservation_type,
                r.table_availability_request_id,
                r.slot_booking_id,
                r.user_id,
                r.confirmation_number,
                r.last_cancel_time,
                r.manage_reservation_url,
                r.status,
                r.special_request,
                r.party_size,
                r.notes,
                r.created_at,
                r.updated_at,
                sb.date_time,
                sb.restaurant_id,
                u.name,
                u.email,
                u.phone_number
            FROM Reservations r
            INNER JOIN Slot_Bookings sb ON r.slot_booking_id = sb.id
            LEFT JOIN Users u ON r.user_id = u.id
            WHERE r.user_id = %s
        """
        params = [user_id]

        if reservation_type:
            query += " AND r.reservation_type = %s"
            params.append(reservation_type)

        query += " ORDER BY r.created_at DESC LIMIT 1"
        results = self._execute_query(query, tuple(params))
        return results[0] if results else None

    def get_reservation_counts_by_status(
        self,
        restaurant_id: int,
    ) -> Dict[str, int]:
        """
        Get reservation counts grouped by status in a single query.

        Args:
            restaurant_id: Restaurant ID

        Returns:
            Dictionary mapping status to count (lowercase keys)
        """
        query = """
            SELECT LOWER(r.status) as status, COUNT(*) as count
            FROM Reservations r
            INNER JOIN Slot_Bookings sb ON r.slot_booking_id = sb.id
            WHERE sb.restaurant_id = %s
            GROUP BY LOWER(r.status)
        """
        results = self._execute_query(query, (restaurant_id,))
        return {row["status"]: row["count"] for row in results}

    def count_reservations_by_restaurant(
        self,
        restaurant_id: int,
        status: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> int:
        """
        Count reservations for a restaurant with optional filters.

        Args:
            restaurant_id: Restaurant ID
            status: Filter by status
            start_date: Filter by start date (date_time >= start_date)
            end_date: Filter by end date (date_time <= end_date)

        Returns:
            Count of matching reservations
        """
        query = """
            SELECT COUNT(*) as total
            FROM Reservations r
            INNER JOIN Slot_Bookings sb ON r.slot_booking_id = sb.id
            WHERE sb.restaurant_id = %s
        """
        params: List[Any] = [restaurant_id]

        if status:
            query += " AND LOWER(r.status) = LOWER(%s)"
            params.append(status)

        if start_date:
            query += " AND sb.date_time >= %s"
            params.append(start_date)

        if end_date:
            query += " AND sb.date_time <= %s"
            params.append(end_date)

        results = self._execute_query(query, tuple(params))
        return results[0]["total"] if results else 0
