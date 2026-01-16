from datetime import date, datetime, time, timezone
from decimal import Decimal
from enum import Enum

from app.utils.encoding import install_utc_jsonable_encoder, utc_jsonable_encoder


class _TestEnum(Enum):
    VALUE = "value"


def test_utc_jsonable_encoder_serializes_types():
    value = {
        "dt": datetime(2024, 1, 1, 0, 0, tzinfo=timezone.utc),
        "date": date(2024, 1, 1),
        "time": time(10, 20, 30),
        "amount": Decimal("2.5"),
        "enum": _TestEnum.VALUE,
    }
    encoded = utc_jsonable_encoder(value)
    assert encoded["dt"] == "2024-01-01T00:00:00Z"
    assert encoded["date"] == "2024-01-01"
    assert encoded["time"] == "10:20:30"
    assert encoded["amount"] == 2.5
    assert encoded["enum"] == "value"


def test_install_utc_jsonable_encoder_patches_global():
    import fastapi.encoders as encoders

    original = encoders.jsonable_encoder
    try:
        install_utc_jsonable_encoder()
        encoded = encoders.jsonable_encoder(datetime(2024, 1, 1, 0, 0, tzinfo=timezone.utc))
        assert encoded == "2024-01-01T00:00:00Z"
    finally:
        encoders.jsonable_encoder = original
