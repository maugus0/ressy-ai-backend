from __future__ import annotations

from typing import Any, Mapping

from pydantic import BaseModel, ConfigDict


class NoArgs(BaseModel):
    """Shared empty args model for functions that rely entirely on default context."""

    model_config = ConfigDict(extra="forbid")


def split_call_context(
    kwargs: Mapping[str, Any],
    model: type[BaseModel],
) -> tuple[dict[str, Any], dict[str, Any]]:
    model_fields = set(model.model_fields)
    model_kwargs = {key: value for key, value in kwargs.items() if key in model_fields}
    context = {key: value for key, value in kwargs.items() if key not in model_fields}
    return context, model_kwargs
