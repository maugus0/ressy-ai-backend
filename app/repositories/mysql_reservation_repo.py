"""
MySQL Reservation Repository for in-house reservation operations.
"""

from app.repositories.mysql_base import MySQLBaseRepository
from typing import Dict, List, Optional
from datetime import datetime


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
    ) -> int:
        """Create a slot booking."""
        query = """
            INSERT INTO Slot_Bookings
            (restaurant_id, reservation_type, date_time, expires_at, status, reservation_token)
            VALUES (%s, %s, %s, %s, %s, %s)
        """
        return self._execute_insert(
            query, (restaurant_id, reservation_type, date_time, expires_at, status, reservation_token)
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
    ) -> int:
        """Create a reservation."""
        query = """
            INSERT INTO Reservations
            (reservation_type, table_availability_request_id, slot_booking_id, user_id,
             confirmation_number, status, last_cancel_time, manage_reservation_url)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
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
            ),
        )

    def get_reservation_by_id(self, reservation_id: int, reservation_type: Optional[str] = None) -> Optional[Dict]:
        """Get a reservation by ID."""
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
                r.created_at,
                r.updated_at,
                sb.date_time,
                u.name,
                u.email,
                u.phone_number
            FROM Reservations r
            LEFT JOIN Slot_Bookings sb ON r.slot_booking_id = sb.id
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
                r.created_at,
                r.updated_at,
                sb.date_time,
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
                r.created_at,
                r.updated_at,
                sb.date_time,
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
