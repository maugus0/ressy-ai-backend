import datetime

import pytest

from app.utils import restaurant_hours


@pytest.fixture(autouse=True)
def force_utc_timezone(monkeypatch):
    """Force timezone resolution to UTC to avoid OS tzdata differences."""
    monkeypatch.setattr(
        restaurant_hours, "resolve_restaurant_timezone", lambda restaurant: (datetime.timezone.utc, "UTC")
    )


def make_restaurant(open_time: str, close_time: str, tz: str = "UTC") -> dict:
    return {"opening_time": open_time, "closing_time": close_time, "timezone": tz}


def test_is_restaurant_open_now_standard_hours_open(monkeypatch):
    restaurant = make_restaurant("09:00:00", "17:00:00")
    now = datetime.datetime(2024, 1, 1, 12, 0, tzinfo=datetime.timezone.utc)
    assert restaurant_hours.is_restaurant_open_now(restaurant, now_utc=now) is True


def test_is_restaurant_open_now_standard_hours_closed(monkeypatch):
    restaurant = make_restaurant("09:00:00", "17:00:00")
    now = datetime.datetime(2024, 1, 1, 2, 0, tzinfo=datetime.timezone.utc)
    assert restaurant_hours.is_restaurant_open_now(restaurant, now_utc=now) is False


def test_is_restaurant_open_now_overnight_before_midnight():
    restaurant = make_restaurant("18:00:00", "02:00:00")
    now = datetime.datetime(2024, 1, 1, 23, 0, tzinfo=datetime.timezone.utc)
    assert restaurant_hours.is_restaurant_open_now(restaurant, now_utc=now) is True


def test_is_restaurant_open_now_overnight_after_midnight():
    restaurant = make_restaurant("18:00:00", "02:00:00")
    now = datetime.datetime(2024, 1, 1, 12, 0, tzinfo=datetime.timezone.utc)
    assert restaurant_hours.is_restaurant_open_now(restaurant, now_utc=now) is False


def test_is_restaurant_open_now_missing_hours_defaults_open():
    restaurant = make_restaurant(None, None)
    now = datetime.datetime(2024, 1, 1, 9, 0, tzinfo=datetime.timezone.utc)
    assert restaurant_hours.is_restaurant_open_now(restaurant, now_utc=now) is True


@pytest.mark.parametrize(
    "target_time,expected",
    [
        (datetime.datetime(2024, 1, 1, 12, 0), True),
        (datetime.datetime(2024, 1, 1, 8, 59), False),
        (datetime.datetime(2024, 1, 1, 17, 0), False),
    ],
)
def test_is_datetime_within_operating_hours_standard(target_time, expected):
    restaurant = make_restaurant("09:00:00", "17:00:00")
    assert restaurant_hours.is_datetime_within_operating_hours(restaurant, target_time) is expected


@pytest.mark.parametrize(
    "target_time,expected",
    [
        (datetime.datetime(2024, 1, 1, 19, 0), True),
        (datetime.datetime(2024, 1, 2, 1, 30), True),
        (datetime.datetime(2024, 1, 1, 12, 0), False),
    ],
)
def test_is_datetime_within_operating_hours_overnight(target_time, expected):
    restaurant = make_restaurant("18:00:00", "02:00:00")
    assert restaurant_hours.is_datetime_within_operating_hours(restaurant, target_time) is expected


def test_is_datetime_within_operating_hours_missing_defaults_true():
    restaurant = make_restaurant(None, None)
    target_time = datetime.datetime(2024, 1, 1, 12, 0)
    assert restaurant_hours.is_datetime_within_operating_hours(restaurant, target_time) is True
