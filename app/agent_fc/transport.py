"""Transport adapter for the existing websocket connection."""

from __future__ import annotations

import asyncio
import inspect
import json
from typing import Any, Awaitable, Callable, Optional

MessageCallback = Callable[[dict[str, Any]], Awaitable[None]]
SendCallable = Callable[[str], Any]


class Transport:
    """Lightweight adapter that knows how to send/receive JSON over the socket."""

    def __init__(self, send_callable: SendCallable) -> None:
        self._send_callable = send_callable
        self._message_callback: Optional[MessageCallback] = None

    def send(self, payload: dict[str, Any]) -> None:
        """Serialize and send the payload over the existing socket."""

        message = json.dumps(payload)
        result = self._send_callable(message)
        if inspect.isawaitable(result):
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                asyncio.run(result)
            else:
                loop.create_task(result)

    def on_message(self, callback: MessageCallback) -> None:
        """Register the coroutine the socket layer should call for each raw frame."""

        self._message_callback = callback

    async def emit(self, payload: dict[str, Any]) -> Any:
        """Utility helper so the socket layer (or tests) can deliver a frame."""

        if self._message_callback is None:
            raise RuntimeError("No on_message callback has been registered")
        return await self._message_callback(payload)
