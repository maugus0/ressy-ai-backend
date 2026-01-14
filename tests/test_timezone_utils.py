from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from enum import Enum

from app.utils.timezone import coerce_datetime, ensure_utc, isoformat_z, json_default, parse_datetime


class _TestEnum(Enum):
    ONE = "one"


def test_ensure_utc_naive_assumes_utc():
    value = datetime(2024, 1, 1, 12, 0)
    result = ensure_utc(value)
    assert result.tzinfo == timezone.utc
    assert result.hour == 12


def test_ensure_utc_converts_offset():
    value = datetime(2024, 1, 1, 12, 0, tzinfo=timezone(timedelta(hours=5, minutes=30)))
    result = ensure_utc(value)
    assert result.tzinfo == timezone.utc
    assert result.hour == 6
    assert result.minute == 30


def test_isoformat_z_formats_utc():
    value = datetime(2024, 1, 1, 0, 0, tzinfo=timezone.utc)
    assert isoformat_z(value) == "2024-01-01T00:00:00Z"


def test_parse_datetime_with_z():
    value = parse_datetime("2024-01-01T12:00:00Z")
    assert value.tzinfo == timezone.utc
    assert value.hour == 12


def test_parse_datetime_naive_default_tz():
    value = parse_datetime("2024-01-01T12:00:00", default_tz=timezone(timedelta(hours=2)))
    assert value.tzinfo == timezone.utc
    assert value.hour == 10


def test_coerce_datetime_invalid_returns_none():
    assert coerce_datetime("not-a-date") is None


def test_json_default_serializes_types():
    dt = datetime(2024, 1, 1, 0, 0, tzinfo=timezone.utc)
    assert json_default(dt) == "2024-01-01T00:00:00Z"
    assert json_default(date(2024, 1, 1)) == "2024-01-01"
    assert json_default(time(12, 30, 15)) == "12:30:15"
    assert json_default(Decimal("12.5")) == 12.5
    assert json_default(_TestEnum.ONE) == "one"
