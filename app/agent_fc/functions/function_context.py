from __future__ import annotations

from typing import Any, Mapping, Optional

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


def context_restaurant_id(context: Mapping[str, Any]) -> Optional[int]:
    raw = context.get("restaurant_id")
    if raw is None:
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def context_business_id(context: Mapping[str, Any]) -> Optional[int]:
    raw = context.get("business_id")
    if raw is None:
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def context_customer_contact(context: Mapping[str, Any]) -> Optional[str]:
    value = context.get("customer_contact") or context.get("caller_phone")
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def context_order_session_state(context: Mapping[str, Any]) -> dict[str, Any]:
    value = context.get("order_session_state")
    if isinstance(value, dict):
        return value
    return {}
