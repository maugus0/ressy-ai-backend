from datetime import datetime, timezone

import pytest

from app.services import reservation_service as reservation_service_module
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
            "timezone": "UTC",
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


def test_update_reservation_checks_capacity_before_slot_update(monkeypatch):
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

    fixed_now = datetime(2026, 1, 31, 12, 0, 0, tzinfo=timezone.utc)

    class FixedDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            if tz:
                return fixed_now.astimezone(tz)
            return fixed_now.replace(tzinfo=None)

    monkeypatch.setattr(reservation_service_module, "datetime", FixedDateTime)

    with pytest.raises(ValueError, match="Not enough capacity"):
        service.update_reservation(
            reservation_id=1,
            date_time="2026-01-31T17:30:00",
            party_size=3,
        )

    assert reservation_repo.update_slot_called is False


def test_lock_slot_rejects_past_time(monkeypatch):
    service = ReservationService()
    reservation_repo = _ReservationRepoStub()
    restaurant_repo = _RestaurantRepoStub()
    service.reservation_repo = reservation_repo
    service.restaurant_repo = restaurant_repo

    fixed_now = datetime(2026, 1, 31, 12, 0, 0, tzinfo=timezone.utc)

    class FixedDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            if tz:
                return fixed_now.astimezone(tz)
            return fixed_now.replace(tzinfo=None)

    monkeypatch.setattr(reservation_service_module, "datetime", FixedDateTime)

    with pytest.raises(ValueError, match="past"):
        service.lock_slot(
            restaurant_id=1,
            party_size=2,
            date_time="2026-01-31T10:00:00Z",
        )


def test_create_reservation_direct_rejects_past_time(monkeypatch):
    service = ReservationService()
    reservation_repo = _ReservationRepoStub()
    restaurant_repo = _RestaurantRepoStub()
    service.reservation_repo = reservation_repo
    service.restaurant_repo = restaurant_repo

    fixed_now = datetime(2026, 1, 31, 12, 0, 0, tzinfo=timezone.utc)

    class FixedDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            if tz:
                return fixed_now.astimezone(tz)
            return fixed_now.replace(tzinfo=None)

    monkeypatch.setattr(reservation_service_module, "datetime", FixedDateTime)

    with pytest.raises(ValueError, match="past"):
        service.create_reservation_direct(
            restaurant_id=1,
            date_time="2026-01-31T10:00:00Z",
            party_size=2,
            name="Test",
            phone_number="123",
        )


def test_update_reservation_rejects_past_time(monkeypatch):
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

    fixed_now = datetime(2026, 1, 31, 12, 0, 0, tzinfo=timezone.utc)

    class FixedDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            if tz:
                return fixed_now.astimezone(tz)
            return fixed_now.replace(tzinfo=None)

    monkeypatch.setattr(reservation_service_module, "datetime", FixedDateTime)

    with pytest.raises(ValueError, match="past"):
        service.update_reservation(
            reservation_id=1,
            date_time="2026-01-31T10:00:00Z",
        )
