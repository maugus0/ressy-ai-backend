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
    """Create a restaurant with the same hours for all days."""
    days = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
    restaurant = {"timezone": tz}
    for day in days:
        restaurant[f"{day}_open"] = open_time
        restaurant[f"{day}_close"] = close_time
        restaurant[f"{day}_closed"] = False
    return restaurant


def test_is_restaurant_open_now_standard_hours_open(monkeypatch):
    restaurant = make_restaurant("09:00:00", "17:00:00")
    now = datetime.datetime(2024, 1, 1, 12, 0, tzinfo=datetime.timezone.utc)  # Monday
    assert restaurant_hours.is_restaurant_open_now(restaurant, now_utc=now) is True


def test_is_restaurant_open_now_standard_hours_closed(monkeypatch):
    restaurant = make_restaurant("09:00:00", "17:00:00")
    now = datetime.datetime(2024, 1, 1, 2, 0, tzinfo=datetime.timezone.utc)  # Monday 2am
    assert restaurant_hours.is_restaurant_open_now(restaurant, now_utc=now) is False


def test_is_restaurant_open_now_overnight_before_midnight():
    restaurant = make_restaurant("18:00:00", "02:00:00")
    now = datetime.datetime(2024, 1, 1, 23, 0, tzinfo=datetime.timezone.utc)  # Monday 11pm
    assert restaurant_hours.is_restaurant_open_now(restaurant, now_utc=now) is True


def test_is_restaurant_open_now_overnight_after_midnight():
    restaurant = make_restaurant("18:00:00", "02:00:00")
    now = datetime.datetime(2024, 1, 1, 12, 0, tzinfo=datetime.timezone.utc)  # Monday noon
    assert restaurant_hours.is_restaurant_open_now(restaurant, now_utc=now) is False


def test_is_restaurant_open_now_missing_hours_defaults_open():
    restaurant = make_restaurant(None, None)
    now = datetime.datetime(2024, 1, 1, 9, 0, tzinfo=datetime.timezone.utc)
    assert restaurant_hours.is_restaurant_open_now(restaurant, now_utc=now) is True


def test_is_restaurant_open_now_day_is_closed():
    restaurant = make_restaurant("09:00:00", "17:00:00")
    restaurant["monday_closed"] = True  # Closed on Monday
    now = datetime.datetime(2024, 1, 1, 12, 0, tzinfo=datetime.timezone.utc)  # Monday
    assert restaurant_hours.is_restaurant_open_now(restaurant, now_utc=now) is False


@pytest.mark.parametrize(
    "target_time,expected",
    [
        (datetime.datetime(2024, 1, 1, 12, 0), True),  # Monday noon
        (datetime.datetime(2024, 1, 1, 8, 59), False),  # Before open
        (datetime.datetime(2024, 1, 1, 17, 0), False),  # At close time
    ],
)
def test_is_datetime_within_operating_hours_standard(target_time, expected):
    restaurant = make_restaurant("09:00:00", "17:00:00")
    assert restaurant_hours.is_datetime_within_operating_hours(restaurant, target_time) is expected


@pytest.mark.parametrize(
    "target_time,expected",
    [
        (datetime.datetime(2024, 1, 1, 19, 0), True),  # Monday 7pm
        (datetime.datetime(2024, 1, 2, 1, 30), True),  # Tuesday 1:30am
        (datetime.datetime(2024, 1, 1, 12, 0), False),  # Monday noon
    ],
)
def test_is_datetime_within_operating_hours_overnight(target_time, expected):
    restaurant = make_restaurant("18:00:00", "02:00:00")
    assert restaurant_hours.is_datetime_within_operating_hours(restaurant, target_time) is expected


def test_is_datetime_within_operating_hours_missing_defaults_true():
    restaurant = make_restaurant(None, None)
    target_time = datetime.datetime(2024, 1, 1, 12, 0)
    assert restaurant_hours.is_datetime_within_operating_hours(restaurant, target_time) is True


def test_is_datetime_within_operating_hours_closed_day():
    restaurant = make_restaurant("09:00:00", "17:00:00")
    restaurant["monday_closed"] = True
    target_time = datetime.datetime(2024, 1, 1, 12, 0)  # Monday
    assert restaurant_hours.is_datetime_within_operating_hours(restaurant, target_time) is False
