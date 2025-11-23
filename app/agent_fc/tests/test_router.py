from __future__ import annotations

import asyncio
import json
from typing import Any, Dict, List

import pytest
from pydantic import BaseModel

from app.agent_fc.config import Settings
from app.agent_fc.registry import FunctionRegistry
from app.agent_fc.responses import AgentFunctionResult, AgentSideEffect
from app.agent_fc.router import FunctionCallRouter
from app.agent_fc.transport import Transport


class DummyTransport(Transport):
    def __init__(self) -> None:
        super().__init__(lambda _: None)
        self.sent_payloads: List[dict[str, Any]] = []

    def send(self, payload: dict[str, Any]) -> None:  # type: ignore[override]
        self.sent_payloads.append(payload)


class FooArgs(BaseModel):
    value: int


async def foo_handler(value: int) -> Dict[str, Any]:
    return {"value": value}


async def filler_handler(value: int) -> AgentFunctionResult:
    return AgentFunctionResult(
        content={"value": value},
        side_effects=[AgentSideEffect({"type": "InjectAgentMessage", "message": "Working on it"})],
    )


@pytest.mark.asyncio
async def test_router_executes_registered_function() -> None:
    registry = FunctionRegistry()
    registry.register("foo", foo_handler, FooArgs)
    transport = DummyTransport()
    router = FunctionCallRouter(registry, transport, Settings(call_timeout_ms=1000, max_retries=0, log_level="INFO"))

    frame = {
        "type": "FunctionCallRequest",
        "functions": [
            {
                "id": "call-1",
                "name": "foo",
                "arguments": {"value": 3},
                "client_side": True,
            }
        ],
    }

    result = await router.handle_frame(frame)
    assert result is not None
    first = transport.sent_payloads[0]
    assert json.loads(first["content"])["value"] == 3
    assert result["side_effects"] == []


@pytest.mark.asyncio
async def test_router_returns_error_on_validation_failure() -> None:
    registry = FunctionRegistry()
    registry.register("foo", foo_handler, FooArgs)
    transport = DummyTransport()
    router = FunctionCallRouter(registry, transport, Settings(call_timeout_ms=1000, max_retries=0, log_level="INFO"))

    frame = {
        "type": "FunctionCallRequest",
        "functions": [
            {
                "id": "call-2",
                "name": "foo",
                "arguments": {},
                "client_side": True,
            }
        ],
    }

    result = await router.handle_frame(frame)
    assert result is not None
    payload = transport.sent_payloads[0]
    body = json.loads(payload["content"])
    assert "value" in body["error"]
    assert result["side_effects"] == []


@pytest.mark.asyncio
async def test_router_retries_on_timeout() -> None:
    calls: List[str] = []

    async def slow_handler(value: int) -> Dict[str, Any]:
        calls.append("call")
        await asyncio.sleep(0.05)
        return {"value": value}

    registry = FunctionRegistry()
    registry.register("foo", slow_handler, FooArgs)
    transport = DummyTransport()
    router = FunctionCallRouter(registry, transport, Settings(call_timeout_ms=10, max_retries=1, log_level="INFO"))

    frame = {
        "type": "FunctionCallRequest",
        "functions": [
            {
                "id": "call-3",
                "name": "foo",
                "arguments": {"value": 1},
                "client_side": True,
            }
        ],
    }

    result = await router.handle_frame(frame)
    assert len(calls) == 2
    payload = transport.sent_payloads[0]
    body = json.loads(payload["content"])
    assert body["error"] == "Function timed out"
    assert result is not None
    assert result["side_effects"] == []


@pytest.mark.asyncio
async def test_router_ignores_non_client_side_request() -> None:
    registry = FunctionRegistry()
    registry.register("foo", foo_handler, FooArgs)
    transport = DummyTransport()
    router = FunctionCallRouter(registry, transport, Settings(call_timeout_ms=1000, max_retries=0, log_level="INFO"))

    frame = {
        "type": "FunctionCallRequest",
        "functions": [
            {
                "id": "call-4",
                "name": "foo",
                "arguments": {"value": 7},
                "client_side": False,
            }
        ],
    }

    result = await router.handle_frame(frame)
    assert result is None
    assert not transport.sent_payloads


@pytest.mark.asyncio
async def test_router_emits_side_effects() -> None:
    registry = FunctionRegistry()
    registry.register("filler", filler_handler, FooArgs)
    transport = DummyTransport()
    router = FunctionCallRouter(registry, transport, Settings(call_timeout_ms=1000, max_retries=0, log_level="INFO"))

    frame = {
        "type": "FunctionCallRequest",
        "functions": [
            {
                "id": "call-5",
                "name": "filler",
                "arguments": {"value": 9},
                "client_side": True,
            }
        ],
    }

    result = await router.handle_frame(frame)
    assert result is not None
    assert len(transport.sent_payloads) == 1
    assert json.loads(transport.sent_payloads[0]["content"])["value"] == 9
    assert len(result["side_effects"]) == 1
    assert result["side_effects"][0].payload["type"] == "InjectAgentMessage"
