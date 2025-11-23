"""
MySQL Reservation Repository for reservation operations.
"""
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from app.repositories.mysql_base import MySQLBaseRepository


class MySQLReservationRepository(MySQLBaseRepository):
    """Repository for reservation data access in MySQL."""

    def create_slot_booking(self, restaurant_id: int, date_time_iso: str) -> int:
        """
        Create a slot booking entry for a reservation window.
        Expires one hour after the requested slot by default.
        """
        date_time = datetime.fromisoformat(date_time_iso)
        expires_at = date_time + timedelta(hours=1)
        query = """
			INSERT INTO Slot_Bookings (restaurant_id, date_time, expires_at, status, reservation_token, created_at, updated_at)
			VALUES (%s, %s, %s, %s, %s, NOW(), NOW())
		"""
        token = str(uuid.uuid4())
        return self._execute_insert(
            query,
            (restaurant_id, date_time, expires_at, "reserved", token),
        )

    def create_reservation(self, user_id: int, slot_booking_id: int, status: str = "confirmed",
                           table_availability_request_id: Optional[int] = None,
                           last_cancel_time: Optional[str] = None,
                           manage_reservation_url: Optional[str] = None) -> Dict[str, Any]:
        confirmation_number = str(uuid.uuid4())
        query = """
			INSERT INTO Reservations (
				table_availability_request_id,
				slot_booking_id,
				user_id,
				confirmation_number,
				last_cancel_time,
				manage_reservation_url,
				status,
				created_at,
				updated_at
			)
			VALUES (%s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
		"""
        reservation_id = self._execute_insert(
            query,
            (
                table_availability_request_id,
                slot_booking_id,
                user_id,
                confirmation_number,
                last_cancel_time,
                manage_reservation_url,
                status,
            ),
        )
        return {
            "id": reservation_id,
            "user_id": user_id,
            "slot_booking_id": slot_booking_id,
            "confirmation_number": confirmation_number,
            "status": status,
        }

    def get_latest_by_user(self, user_id: int) -> Dict[str, Any]:
        query = """
			SELECT
				id,
				table_availability_request_id,
				slot_booking_id,
				user_id,
				confirmation_number,
				last_cancel_time,
				manage_reservation_url,
				status,
				created_at,
				updated_at
			FROM Reservations
			WHERE user_id = %s
			ORDER BY created_at DESC
			LIMIT 1
		"""
        results = self._execute_query(query, (user_id,))
        return results[0] if results else {}

    def update_reservation(self, reservation_id: int, updates: Dict[str, Any]) -> int:
        if not updates:
            return 0
        fields = []
        params: List[Any] = []
        for key, value in updates.items():
            fields.append(f"{key} = %s")
            params.append(value)
        fields.append("updated_at = NOW()")
        params.append(reservation_id)
        query = f"UPDATE Reservations SET {', '.join(fields)} WHERE id = %s"
        return self._execute_update(query, tuple(params))

    def list_available_slots(self, restaurant_id: int, start_iso: str, end_iso: str) -> List[Dict[str, Any]]:
        """Return available slots within the window."""
        query = """
			SELECT id, restaurant_id, date_time, expires_at, status, reservation_token
			FROM Slot_Bookings
			WHERE restaurant_id = %s
			  AND status = 'available'
			  AND date_time BETWEEN %s AND %s
			ORDER BY date_time ASC
		"""
        return self._execute_query(query, (restaurant_id, start_iso, end_iso))
