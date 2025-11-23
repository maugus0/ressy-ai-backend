from typing import List, Optional

from app.repositories.mysql_reservation_repo import MySQLReservationRepository
from app.services.restaurant_service import RestaurantService


class ReservationService:
    """Domain service orchestrating reservation logic using MySQL."""

    def __init__(self) -> None:
        self.repo = MySQLReservationRepository()
        self.restaurant_service = RestaurantService()

    def create_reservation(self, restaurant_id: str, data: dict) -> dict:
        slot_id = self.repo.create_slot_booking(int(restaurant_id), data["reservation_datetime"])
        reservation = self.repo.create_reservation(
            user_id=data["user_id"],
            slot_booking_id=slot_id,
            status="confirmed",
            table_availability_request_id=data.get("table_availability_request_id"),
            last_cancel_time=data.get("last_cancel_time"),
            manage_reservation_url=data.get("manage_reservation_url"),
        )
        reservation["party_size"] = data.get("party_size")
        reservation["customer_name"] = data.get("customer_name")
        reservation["customer_contact"] = data.get("customer_contact")
        return reservation

    def update_reservation(self, reservation_id: str, updates: dict) -> Optional[dict]:
        self.repo.update_reservation(int(reservation_id), updates)
        # No direct fetch by id in schema; return merged view where possible
        return None

    def get_reservation(self, reservation_id: str) -> dict:
        # Not implemented in MySQL repo; placeholder
        return {}

    def list_reservations(self, restaurant_id: str) -> List[dict]:
        # Listing requires join; not implemented
        return []

    def check_reservation_availability(
            self,
            restaurant_id: str,
            party_size: int,
            start_iso: str,
            end_iso: str,
    ) -> dict:
        restaurant = self.restaurant_service.get_restaurant(restaurant_id)
        if not restaurant:
            raise ValueError(f"Restaurant {restaurant_id} not found")

        max_party_size = int(restaurant.get("max_party_size", 12))
        if party_size > max_party_size:
            return {
                "restaurant_id": restaurant_id,
                "party_size": party_size,
                "available": False,
                "reason": f"Maximum party size is {max_party_size}",
            }

        slots = self.repo.list_available_slots(int(restaurant_id), start_iso, end_iso)
        return {
            "restaurant_id": restaurant_id,
            "party_size": party_size,
            "available": bool(slots),
            "slots": slots[:10],
        }
