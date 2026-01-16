"""Pydantic models for client-side function calling."""

from __future__ import annotations

import json
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Mapping, Optional, Union

from pydantic import BaseModel, ConfigDict, RootModel, field_validator

from app.utils.timezone import isoformat_z


class FunctionCallRequest(BaseModel):
    """Function call request issued by the agent."""

    model_config = ConfigDict(extra="forbid")
    id: str
    name: str
    arguments: dict[str, Any]
    client_side: bool
    ts: Optional[str] = None

    @field_validator("arguments", mode="before")
    @classmethod
    def _coerce_arguments(cls, value: Any) -> dict[str, Any]:
        if isinstance(value, Mapping):
            return dict(value)
        if isinstance(value, str):
            try:
                parsed = json.loads(value)
            except json.JSONDecodeError as exc:
                raise ValueError("arguments must be valid JSON") from exc
            if not isinstance(parsed, Mapping):
                raise ValueError("arguments JSON must decode to an object")
            return dict(parsed)
        raise TypeError("arguments must be an object or JSON string")


class FunctionCallResponse(BaseModel):
    """Function call response to send back to the agent."""

    model_config = ConfigDict(extra="forbid")
    id: str
    name: str
    content: dict[str, Any]

    @staticmethod
    def _json_default(value: Any) -> Any:
        if isinstance(value, Decimal):
            return float(value)
        if isinstance(value, (datetime, date)):
            if isinstance(value, datetime):
                return isoformat_z(value)
            return value.isoformat()
        return str(value)

    def to_wire(self) -> dict[str, Any]:
        return {
            "type": "FunctionCallResponse",
            "id": self.id,
            "name": self.name,
            "content": json.dumps(self.content, default=self._json_default),
        }


class GenericAgentFrame(BaseModel):
    """Pass-through container for frames that are not function call requests."""

    model_config = ConfigDict(extra="allow")
    payload: dict[str, Any]


class AgentFrame(RootModel[Union[FunctionCallRequest, GenericAgentFrame]]):
    """Union type that represents either a function call request or any other frame."""

    root: Union[FunctionCallRequest, GenericAgentFrame]

    @property
    def function_call(self) -> Optional[FunctionCallRequest]:
        if isinstance(self.root, FunctionCallRequest):
            return self.root
        return None

    @classmethod
    def parse(cls, frame: Mapping[str, Any]) -> "AgentFrame":
        if not isinstance(frame, Mapping):
            raise TypeError("Agent frames must be dictionary-like")

        payload: dict[str, Any] = dict(frame)
        type_hint = str(payload.get("type") or "").lower()

        if type_hint == "functioncallrequest":
            functions = payload.get("functions")
            if isinstance(functions, list) and functions:
                first = functions[0]
                if isinstance(first, Mapping):
                    request = FunctionCallRequest.model_validate(first)
                    return cls(root=request)
            raise ValueError("FunctionCallRequest frames must include at least one function")

        return cls(root=GenericAgentFrame(payload=payload))
