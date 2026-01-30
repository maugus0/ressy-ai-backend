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


def test_is_datetime_within_operating_hours_overnight():
    """Overnight hours: Monday 18:00-02:00, Tuesday 09:00-17:00.

    Tuesday 1:30am must be open from Monday's overnight, not from Tuesday's hours.
    Uses different hours per day so the test validates the overnight-boundary logic.
    """
    restaurant = make_restaurant_per_day(
        {
            "monday": {"open": "18:00:00", "close": "02:00:00"},
            "tuesday": {"open": "09:00:00", "close": "17:00:00"},
        }
    )
    # Monday 7pm - within Monday's 18:00-02:00
    assert restaurant_hours.is_datetime_within_operating_hours(restaurant, datetime.datetime(2024, 1, 1, 19, 0)) is True
    # Tuesday 1:30am - open only because Monday's overnight extends here (Tuesday is 09:00-17:00)
    assert restaurant_hours.is_datetime_within_operating_hours(restaurant, datetime.datetime(2024, 1, 2, 1, 30)) is True
    # Monday noon - outside Monday's 18:00-02:00
    assert (
        restaurant_hours.is_datetime_within_operating_hours(restaurant, datetime.datetime(2024, 1, 1, 12, 0)) is False
    )


def test_is_datetime_within_operating_hours_missing_defaults_true():
    restaurant = make_restaurant(None, None)
    target_time = datetime.datetime(2024, 1, 1, 12, 0)
    assert restaurant_hours.is_datetime_within_operating_hours(restaurant, target_time) is True


def test_is_datetime_within_operating_hours_closed_day():
    restaurant = make_restaurant("09:00:00", "17:00:00")
    restaurant["monday_closed"] = True
    target_time = datetime.datetime(2024, 1, 1, 12, 0)  # Monday
    assert restaurant_hours.is_datetime_within_operating_hours(restaurant, target_time) is False


# ---------- Per-day operating hours tests ----------


def make_restaurant_per_day(hours_by_day: dict, tz: str = "UTC") -> dict:
    """Create a restaurant with different hours per day.

    hours_by_day format: {
        "monday": {"open": "09:00:00", "close": "17:00:00", "closed": False},
        ...
    }
    """
    restaurant = {"timezone": tz}
    for day in ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]:
        if day in hours_by_day:
            day_hours = hours_by_day[day]
            restaurant[f"{day}_open"] = day_hours.get("open")
            restaurant[f"{day}_close"] = day_hours.get("close")
            restaurant[f"{day}_closed"] = day_hours.get("closed", False)
        else:
            # Default hours
            restaurant[f"{day}_open"] = "09:00:00"
            restaurant[f"{day}_close"] = "22:00:00"
            restaurant[f"{day}_closed"] = False
    return restaurant


class TestPerDayOperatingHours:
    """Tests for restaurants with different hours on different days."""

    def test_different_hours_per_day(self):
        """Test that each day uses its own hours."""
        restaurant = make_restaurant_per_day(
            {
                "monday": {"open": "09:00:00", "close": "17:00:00"},
                "tuesday": {"open": "10:00:00", "close": "22:00:00"},
            }
        )

        # Monday 10am - should be open (09:00-17:00)
        monday_10am = datetime.datetime(2024, 1, 1, 10, 0)  # Monday
        assert restaurant_hours.is_datetime_within_operating_hours(restaurant, monday_10am) is True

        # Monday 6pm - should be closed (closes at 17:00)
        monday_6pm = datetime.datetime(2024, 1, 1, 18, 0)
        assert restaurant_hours.is_datetime_within_operating_hours(restaurant, monday_6pm) is False

        # Tuesday 6pm - should be open (10:00-22:00)
        tuesday_6pm = datetime.datetime(2024, 1, 2, 18, 0)  # Tuesday
        assert restaurant_hours.is_datetime_within_operating_hours(restaurant, tuesday_6pm) is True

    def test_closed_day_among_open_days(self):
        """Test that a closed day is properly handled."""
        restaurant = make_restaurant_per_day(
            {
                "monday": {"open": "09:00:00", "close": "22:00:00"},
                "tuesday": {"closed": True},
                "wednesday": {"open": "09:00:00", "close": "22:00:00"},
            }
        )

        # Monday - should be open
        monday = datetime.datetime(2024, 1, 1, 12, 0)
        assert restaurant_hours.is_datetime_within_operating_hours(restaurant, monday) is True

        # Tuesday - should be closed
        tuesday = datetime.datetime(2024, 1, 2, 12, 0)
        assert restaurant_hours.is_datetime_within_operating_hours(restaurant, tuesday) is False

        # Wednesday - should be open
        wednesday = datetime.datetime(2024, 1, 3, 12, 0)
        assert restaurant_hours.is_datetime_within_operating_hours(restaurant, wednesday) is True


class TestOvernightHoursAcrossDays:
    """Tests for overnight hours with different schedules per day."""

    def test_overnight_monday_into_tuesday_morning(self):
        """
        Monday 18:00-02:00 overnight, Tuesday 09:00-17:00 normal.
        At Tuesday 1:30am, should still be open from Monday's overnight.
        """
        restaurant = make_restaurant_per_day(
            {
                "monday": {"open": "18:00:00", "close": "02:00:00"},
                "tuesday": {"open": "09:00:00", "close": "17:00:00"},
            }
        )

        # Tuesday 1:30am - should be open (Monday's overnight extends here)
        tuesday_130am = datetime.datetime(2024, 1, 2, 1, 30)
        assert restaurant_hours.is_datetime_within_operating_hours(restaurant, tuesday_130am) is True

        # Tuesday 3:00am - should be closed (after Monday's 02:00 close, before Tuesday's 09:00 open)
        tuesday_3am = datetime.datetime(2024, 1, 2, 3, 0)
        assert restaurant_hours.is_datetime_within_operating_hours(restaurant, tuesday_3am) is False

        # Tuesday 10:00am - should be open (Tuesday's normal hours)
        tuesday_10am = datetime.datetime(2024, 1, 2, 10, 0)
        assert restaurant_hours.is_datetime_within_operating_hours(restaurant, tuesday_10am) is True

    def test_overnight_into_closed_day(self):
        """
        Monday 18:00-02:00 overnight, Tuesday closed.
        At Tuesday 1:30am, should still be open from Monday's overnight.
        """
        restaurant = make_restaurant_per_day(
            {
                "monday": {"open": "18:00:00", "close": "02:00:00"},
                "tuesday": {"closed": True},
            }
        )

        # Tuesday 1:30am - should be open (Monday's overnight)
        tuesday_130am = datetime.datetime(2024, 1, 2, 1, 30)
        assert restaurant_hours.is_datetime_within_operating_hours(restaurant, tuesday_130am) is True

        # Tuesday 12:00pm - should be closed (Tuesday is closed, Monday's overnight ended)
        tuesday_noon = datetime.datetime(2024, 1, 2, 12, 0)
        assert restaurant_hours.is_datetime_within_operating_hours(restaurant, tuesday_noon) is False

    def test_is_restaurant_open_now_overnight_into_next_day(self):
        """Test is_restaurant_open_now with overnight hours extending to next day."""
        restaurant = make_restaurant_per_day(
            {
                "monday": {"open": "18:00:00", "close": "02:00:00"},
                "tuesday": {"open": "09:00:00", "close": "17:00:00"},
            }
        )

        # Tuesday 1:30am UTC - should still be open from Monday's overnight
        now_utc = datetime.datetime(2024, 1, 2, 1, 30, tzinfo=datetime.timezone.utc)
        assert restaurant_hours.is_restaurant_open_now(restaurant, now_utc) is True

        # Tuesday 3:00am UTC - should be closed
        now_utc = datetime.datetime(2024, 1, 2, 3, 0, tzinfo=datetime.timezone.utc)
        assert restaurant_hours.is_restaurant_open_now(restaurant, now_utc) is False

    def test_sunday_overnight_into_monday(self):
        """Test overnight hours that wrap from Sunday to Monday."""
        restaurant = make_restaurant_per_day(
            {
                "sunday": {"open": "18:00:00", "close": "02:00:00"},
                "monday": {"open": "09:00:00", "close": "17:00:00"},
            }
        )

        # Monday 1:00am - should be open (Sunday's overnight)
        monday_1am = datetime.datetime(2024, 1, 1, 1, 0)  # Monday
        assert restaurant_hours.is_datetime_within_operating_hours(restaurant, monday_1am) is True

        # Monday 3:00am - should be closed
        monday_3am = datetime.datetime(2024, 1, 1, 3, 0)
        assert restaurant_hours.is_datetime_within_operating_hours(restaurant, monday_3am) is False


class TestHelperFunctions:
    """Tests for helper functions."""

    def test_get_previous_day(self):
        """Test _get_previous_day helper."""
        assert restaurant_hours._get_previous_day("monday") == "sunday"
        assert restaurant_hours._get_previous_day("tuesday") == "monday"
        assert restaurant_hours._get_previous_day("sunday") == "saturday"

    def test_is_overnight_hours(self):
        """Test _is_overnight_hours helper."""
        # Normal hours: 09:00 - 17:00
        assert restaurant_hours._is_overnight_hours(datetime.time(9, 0), datetime.time(17, 0)) is False

        # Overnight hours: 18:00 - 02:00
        assert restaurant_hours._is_overnight_hours(datetime.time(18, 0), datetime.time(2, 0)) is True

        # Midnight close: 18:00 - 00:00 (not overnight by this logic)
        assert restaurant_hours._is_overnight_hours(datetime.time(18, 0), datetime.time(0, 0)) is True
