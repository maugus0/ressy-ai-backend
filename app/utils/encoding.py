from __future__ import annotations

from datetime import date, datetime, time
from decimal import Decimal
from enum import Enum
from typing import Any, Callable, Dict

from fastapi.encoders import jsonable_encoder as _jsonable_encoder

from app.utils.timezone import isoformat_z


def utc_jsonable_encoder(obj: Any, **kwargs) -> Any:
    """Wrap FastAPI's jsonable_encoder with UTC datetime serialization."""
    custom_encoder: Dict[type, Callable[[Any], Any]] = dict(kwargs.pop("custom_encoder", {}) or {})
    custom_encoder.setdefault(datetime, isoformat_z)
    custom_encoder.setdefault(date, lambda value: value.isoformat())
    custom_encoder.setdefault(time, lambda value: value.isoformat())
    custom_encoder.setdefault(Decimal, float)
    custom_encoder.setdefault(Enum, lambda value: value.value)
    return _jsonable_encoder(obj, custom_encoder=custom_encoder, **kwargs)


def install_utc_jsonable_encoder() -> None:
    """Install the UTC-aware encoder globally for FastAPI."""
    import fastapi.encoders as encoders

    encoders.jsonable_encoder = utc_jsonable_encoder
