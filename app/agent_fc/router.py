"""Router that handles function call frames coming from the agent socket."""

from __future__ import annotations

import asyncio
import inspect
import time
from typing import Any, Mapping, Optional

from pydantic import ValidationError

from app.utils.logging_config import get_logger

from .config import Settings
from .models import AgentFrame, FunctionCallRequest, FunctionCallResponse
from .registry import FunctionRegistry
from .responses import AgentFunctionResult, AgentSideEffect
from .transport import Transport


class FunctionCallRouter:
    """Routes incoming frames to registered client-side functions."""

    def __init__(
        self,
        registry: FunctionRegistry,
        transport: Transport,
        settings: Settings,
        default_arguments: Optional[Mapping[str, Any]] = None,
    ) -> None:
        self._registry = registry
        self._transport = transport
        self._settings = settings
        self._default_arguments = dict(default_arguments or {})
        self._logger = get_logger(__name__)
        self._logger.setLevel(settings.log_level)  # Override level for FC.

    def set_default_arguments(self, default_arguments: Optional[Mapping[str, Any]]) -> None:
        self._default_arguments = dict(default_arguments or {})

    async def handle_frame(self, raw_json: Mapping[str, Any]) -> Optional[dict[str, Any]]:
        """Handle a raw JSON frame from the socket."""

        try:
            frame = AgentFrame.parse(raw_json)
        except (ValidationError, TypeError) as exc:
            self._logger.warning("Invalid agent frame: %s", exc)
            return None

        request = frame.function_call
        if request is None:
            return None
        if not request.client_side:
            self._logger.warning("Skipping server-side request id=%s name=%s", request.id, request.name)
            return None

        start_time = time.perf_counter()
        self._logger.debug(
            "Function request received id=%s name=%s args=%s", request.id, request.name, request.arguments
        )

        try:
            registered = self._registry.get(request.name)
        except KeyError:
            response = self._error_response(request, f"Unknown function '{request.name}'")
            envelope = self._dispatch_response(response, start_time)
            return {"response": envelope, "side_effects": []}

        arguments = dict(request.arguments or {})
        for key, value in self._default_arguments.items():
            if key in registered.arg_model.model_fields:
                arguments[key] = value
        try:
            arg_model = registered.validate_arguments(arguments)
        except ValidationError as exc:
            error_msg = self._format_validation_error(exc)
            self._logger.warning("Validation failed for id=%s name=%s: %s", request.id, request.name, error_msg)
            response = self._error_response(request, error_msg)
            envelope = self._dispatch_response(response, start_time)
            return {"response": envelope, "side_effects": []}

        payload = arg_model.model_dump()
        merged_payload = {**payload, **self._default_arguments}
        attempts = 1 + max(self._settings.max_retries, 0)

        for attempt in range(1, attempts + 1):
            try:
                content = await self._execute_with_timeout(registered.handler, merged_payload)
            except asyncio.TimeoutError:
                if attempt < attempts:
                    self._logger.warning(
                        "Function %s timed out on attempt %s/%s (id=%s); retrying",
                        request.name,
                        attempt,
                        attempts,
                        request.id,
                    )
                    continue
                response = self._error_response(request, "Function timed out")
                envelope = self._dispatch_response(response, start_time)
                return {"response": envelope, "side_effects": []}
            except Exception as exc:  # noqa: BLE001 - need to capture all failures
                self._logger.exception(
                    "[ERROR] Function %s raised on attempt %s/%s (id=%s): %s",
                    request.name,
                    attempt,
                    attempts,
                    request.id,
                    exc,
                )
                response = self._error_response(request, "Function execution failed")
                envelope = self._dispatch_response(response, start_time)
                return {"response": envelope, "side_effects": []}

            normalized_content, side_effects = self._normalize_result(content)
            response = FunctionCallResponse(
                id=request.id,
                name=request.name,
                content=normalized_content,
            )
            envelope = self._dispatch_response(response, start_time)
            return {"response": envelope, "side_effects": side_effects}

        return None

    async def _execute_with_timeout(self, handler: Any, arguments: Mapping[str, Any]) -> Any:
        async def _invoke() -> Any:
            result = handler(**arguments)
            if inspect.isawaitable(result):
                return await result
            return result

        timeout_seconds = self._settings.call_timeout_ms / 1000
        return await asyncio.wait_for(_invoke(), timeout=timeout_seconds)

    def _dispatch_response(self, response: FunctionCallResponse, start_time: float) -> dict[str, Any]:
        envelope = response.to_wire()
        self._transport.send(envelope)

        duration_ms = (time.perf_counter() - start_time) * 1000
        self._logger.debug(
            "Function request finished id=%s name=%s duration_ms=%.2f", response.id, response.name, duration_ms
        )
        self._logger.debug("Function response id=%s payload=%s", response.id, envelope)
        return envelope

    def _error_response(self, request: FunctionCallRequest, error: str) -> FunctionCallResponse:
        return FunctionCallResponse(
            id=request.id,
            name=request.name,
            content={"error": error},
        )

    @staticmethod
    def _format_validation_error(exc: ValidationError) -> str:
        first_error = exc.errors()[0]
        loc = ".".join(str(part) for part in first_error.get("loc", ()))
        msg = first_error.get("msg", "Invalid arguments")
        return f"{loc}: {msg}" if loc else msg

    @staticmethod
    def _ensure_dict(content: Any) -> dict[str, Any]:
        if isinstance(content, dict):
            return content
        return {"result": content}

    def _normalize_result(self, raw_result: Any) -> tuple[dict[str, Any], list[AgentSideEffect]]:
        if isinstance(raw_result, AgentFunctionResult):
            return self._ensure_dict(raw_result.content), raw_result.side_effects
        return self._ensure_dict(raw_result), []
