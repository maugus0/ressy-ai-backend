from __future__ import annotations

import pytest
from pydantic import BaseModel, ValidationError

from app.agent_fc.registry import FunctionRegistry


class SampleArgs(BaseModel):
    value: int


def sample_handler(value: int) -> dict[str, int]:
    return {"value": value}


def test_register_and_get_function() -> None:
    registry = FunctionRegistry()
    registry.register("sample", sample_handler, SampleArgs)

    entry = registry.get("sample")
    args = entry.validate_arguments({"value": 7})
    assert args.value == 7


def test_duplicate_registration_guard() -> None:
    registry = FunctionRegistry()
    registry.register("sample", sample_handler, SampleArgs)
    with pytest.raises(ValueError):
        registry.register("sample", sample_handler, SampleArgs)


def test_argument_validation_error_contains_field() -> None:
    registry = FunctionRegistry()
    registry.register("sample", sample_handler, SampleArgs)
    entry = registry.get("sample")
    with pytest.raises(ValidationError) as exc:
        entry.validate_arguments({})
    assert "value" in str(exc.value)
