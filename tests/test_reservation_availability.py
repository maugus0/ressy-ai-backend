import asyncio
from datetime import datetime, timedelta, timezone

from app.agent_fc.functions import reservations as reservations_fn
from app.services.reservation_service import ReservationService


def _restaurant_stub():
    return {
        "id": 1,
        "name": "Testaurant",
        "timezone": "UTC",
        "opening_time": "09:00:00",
        "closing_time": "22:00:00",
        "reservation_seating_capacity": 5,
        "reservation_advance_days": 30,
        "forward_minutes": 120,
        "backward_minutes": 60,
    }


def test_find_nearest_slots_forward_and_backward():
    service = ReservationService()
    restaurant = _restaurant_stub()
    requested_start = datetime(2026, 1, 31, 14, 0, 0)
    window_start = requested_start - timedelta(minutes=60)
    window_end = requested_start + timedelta(minutes=120)
    capacity_map = {
        requested_start.replace(second=0, microsecond=0): 5,
        (requested_start - timedelta(minutes=30)).replace(second=0, microsecond=0): 0,
        (requested_start + timedelta(minutes=30)).replace(second=0, microsecond=0): 0,
    }
    result = service.find_nearest_slots(
        restaurant=restaurant,
        requested_start_local=requested_start,
        party_size=5,
        window_start=window_start,
        window_end=window_end,
        capacity_map=capacity_map,
        now_utc=datetime(2026, 1, 31, 13, 0, tzinfo=timezone.utc),
    )
    assert result["nearest_forward_slot"]["datetime"] == "2026-01-31T14:30:00"
    assert result["nearest_backward_slot"]["datetime"] == "2026-01-31T13:30:00"


def test_check_reservation_availability_returns_nearest_slots(monkeypatch):
    restaurant = _restaurant_stub()

    async def fake_load_restaurant(restaurant_id: int):
        return restaurant

    monkeypatch.setattr(reservations_fn, "load_restaurant", fake_load_restaurant)

    capacity_map = {
        datetime(2026, 1, 31, 14, 0, 0): 5,
        datetime(2026, 1, 31, 13, 30, 0): 0,
        datetime(2026, 1, 31, 14, 30, 0): 0,
    }

    def fake_get_capacity_map(self, restaurant_id, window_start, window_end):
        return capacity_map

    monkeypatch.setattr(ReservationService, "get_capacity_map", fake_get_capacity_map)

    fixed_now = datetime(2026, 1, 31, 13, 0, tzinfo=timezone.utc)

    class FixedDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            if tz:
                return fixed_now.astimezone(tz)
            return fixed_now.replace(tzinfo=None)

    monkeypatch.setattr(reservations_fn, "datetime", FixedDateTime)

    result = asyncio.run(
        reservations_fn.check_reservation_availability(
            restaurant_id=1,
            party_size=5,
            date_start_iso="2026-01-31T14:00:00",
        )
    )

    assert result["requested_slot_available"] is False
    assert "available_slots" not in result
    assert result["nearest_forward_slot"] == "Today 2:30 PM"
    assert result["nearest_backward_slot"] == "Today 1:30 PM"


def test_find_nearest_slots_next_day_forward_only():
    service = ReservationService()
    restaurant = _restaurant_stub()
    restaurant["operating_hours"] = {
        "saturday": {"open": "09:00:00", "close": "21:00:00", "is_closed": False, "is_24_hours": False},
        "sunday": {"open": "09:00:00", "close": "22:00:00", "is_closed": False, "is_24_hours": False},
    }
    requested_start = datetime(2026, 1, 31, 21, 30, 0)
    window_start = requested_start
    window_end = requested_start + timedelta(minutes=24 * 60)
    capacity_map = {
        datetime(2026, 2, 1, 9, 0, 0): 0,
    }
    result = service.find_nearest_slots(
        restaurant=restaurant,
        requested_start_local=requested_start,
        party_size=5,
        window_start=window_start,
        window_end=window_end,
        capacity_map=capacity_map,
        now_utc=datetime(2026, 1, 31, 20, 0, tzinfo=timezone.utc),
    )
    assert result["nearest_forward_slot"]["datetime"] == "2026-02-01T09:00:00"
    assert result["nearest_backward_slot"] is None


def test_find_nearest_slots_snaps_to_boundary():
    service = ReservationService()
    restaurant = _restaurant_stub()
    requested_start = datetime(2026, 1, 31, 14, 10, 0)
    window_start = requested_start - timedelta(minutes=60)
    window_end = requested_start + timedelta(minutes=120)
    capacity_map = {
        datetime(2026, 1, 31, 14, 30, 0): 0,
        datetime(2026, 1, 31, 15, 0, 0): 0,
    }
    result = service.find_nearest_slots(
        restaurant=restaurant,
        requested_start_local=requested_start,
        party_size=5,
        window_start=window_start,
        window_end=window_end,
        capacity_map=capacity_map,
        now_utc=datetime(2026, 1, 31, 13, 0, tzinfo=timezone.utc),
    )
    assert result["nearest_forward_slot"]["datetime"] == "2026-01-31T14:30:00"


def test_check_reservation_availability_no_backward_slot(monkeypatch):
    restaurant = _restaurant_stub()

    async def fake_load_restaurant(restaurant_id: int):
        return restaurant

    monkeypatch.setattr(reservations_fn, "load_restaurant", fake_load_restaurant)

    capacity_map = {
        datetime(2026, 1, 31, 14, 0, 0): 5,
        datetime(2026, 1, 31, 14, 30, 0): 0,
    }

    def fake_get_capacity_map(self, restaurant_id, window_start, window_end):
        return capacity_map

    monkeypatch.setattr(ReservationService, "get_capacity_map", fake_get_capacity_map)

    fixed_now = datetime(2026, 1, 31, 14, 15, tzinfo=timezone.utc)

    class FixedDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            if tz:
                return fixed_now.astimezone(tz)
            return fixed_now.replace(tzinfo=None)

    monkeypatch.setattr(reservations_fn, "datetime", FixedDateTime)

    result = asyncio.run(
        reservations_fn.check_reservation_availability(
            restaurant_id=1,
            party_size=5,
            date_start_iso="2026-01-31T14:00:00",
        )
    )

    assert result["nearest_forward_slot"] == "Today 2:30 PM"
    assert result["nearest_backward_slot"] is None


def test_check_reservation_availability_requires_boundary(monkeypatch):
    restaurant = _restaurant_stub()

    async def fake_load_restaurant(restaurant_id: int):
        return restaurant

    monkeypatch.setattr(reservations_fn, "load_restaurant", fake_load_restaurant)

    capacity_map = {
        datetime(2026, 1, 31, 14, 30, 0): 0,
        datetime(2026, 1, 31, 15, 0, 0): 0,
    }

    def fake_get_capacity_map(self, restaurant_id, window_start, window_end):
        return capacity_map

    monkeypatch.setattr(ReservationService, "get_capacity_map", fake_get_capacity_map)

    fixed_now = datetime(2026, 1, 31, 13, 0, tzinfo=timezone.utc)

    class FixedDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            if tz:
                return fixed_now.astimezone(tz)
            return fixed_now.replace(tzinfo=None)

    monkeypatch.setattr(reservations_fn, "datetime", FixedDateTime)

    result = asyncio.run(
        reservations_fn.check_reservation_availability(
            restaurant_id=1,
            party_size=5,
            date_start_iso="2026-01-31T14:10:00",
        )
    )

    assert result["requested_slot_available"] is False
    assert result["nearest_forward_slot"] == "Today 2:30 PM"
