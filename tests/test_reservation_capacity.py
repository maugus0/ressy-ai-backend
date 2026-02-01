from datetime import datetime

import pytest

from app.services.reservation_service import ReservationService


class _ReservationRepoStub:
    def __init__(self):
        self.finalize_called = False
        self.update_slot_called = False

    def get_slot_confirmed_capacity(self, restaurant_id: int, date_time: datetime, reservation_type: str) -> int:
        return 4

    def get_reservation_by_id(self, reservation_id: int, reservation_type: str):
        return {
            "id": reservation_id,
            "restaurant_id": 1,
            "status": "pending",
            "date_time": datetime(2026, 1, 31, 17, 0, 0),
            "party_size": 2,
            "slot_booking_id": 10,
        }

    def finalize_reservation(self, reservation_id: int, confirmation_number=None) -> bool:
        self.finalize_called = True
        return True

    def update_slot_booking_datetime(self, slot_booking_id: int, new_date_time: datetime) -> bool:
        self.update_slot_called = True
        return True

    def update_reservation(self, **kwargs) -> bool:
        return True


class _RestaurantRepoStub:
    def get_by_id(self, restaurant_id: int):
        return {
            "id": restaurant_id,
            "reservation_seating_capacity": 4,
        }


def test_finalize_reservation_blocks_over_capacity():
    service = ReservationService()
    reservation_repo = _ReservationRepoStub()
    restaurant_repo = _RestaurantRepoStub()
    service.reservation_repo = reservation_repo
    service.restaurant_repo = restaurant_repo

    with pytest.raises(ValueError, match="Not enough capacity"):
        service.finalize_reservation(reservation_id=1)

    assert reservation_repo.finalize_called is False


def test_update_reservation_checks_capacity_before_slot_update():
    service = ReservationService()
    reservation_repo = _ReservationRepoStub()
    restaurant_repo = _RestaurantRepoStub()
    service.reservation_repo = reservation_repo
    service.restaurant_repo = restaurant_repo

    reservation_repo.get_reservation_by_id = lambda reservation_id, reservation_type: {
        "id": reservation_id,
        "restaurant_id": 1,
        "status": "confirmed",
        "date_time": datetime(2026, 1, 31, 17, 0, 0),
        "party_size": 2,
        "slot_booking_id": 10,
    }

    with pytest.raises(ValueError, match="Not enough capacity"):
        service.update_reservation(
            reservation_id=1,
            date_time="2026-01-31T17:30:00",
            party_size=3,
        )

    assert reservation_repo.update_slot_called is False
