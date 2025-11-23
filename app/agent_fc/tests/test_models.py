from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.agent_fc.models import AgentFrame, FunctionCallRequest


def test_function_call_request_requires_id_name_arguments() -> None:
    with pytest.raises(ValidationError):
        FunctionCallRequest.model_validate({"name": "create_order", "arguments": {}, "client_side": True})


def test_agent_frame_parses_function_request() -> None:
    payload = {
        "type": "FunctionCallRequest",
        "functions": [
            {
                "id": "123",
                "name": "create_order",
                "arguments": {"customer_id": "c1", "items": []},
                "client_side": True,
            }
        ],
    }
    frame = AgentFrame.parse(payload)
    assert frame.function_call is not None
    assert frame.function_call.id == "123"


def test_agent_frame_passes_through_non_function_frames() -> None:
    payload = {"type": "event", "data": {"foo": "bar"}}
    frame = AgentFrame.parse(payload)
    assert frame.function_call is None
    assert frame.root.payload == payload
