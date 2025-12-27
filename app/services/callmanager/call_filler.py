from __future__ import annotations

import asyncio
import json
import random
from typing import Optional

from app.config import settings
from app.services.callmanager.call_state import StreamState
from app.utils.logging_config import get_logger

logger = get_logger(__name__)


class FillerManager:
    def __init__(self, filler_messages: Optional[list[str]] = None):
        self._filler_messages = filler_messages or [
            "Okay...",
            "Just a sec...",
            "Please hold on...",
            "Just a moment...",
        ]

    def cancel(self, state: StreamState) -> None:
        task = state.filler_task
        if task and not task.done():
            task.cancel()
        state.filler_task = None

    def schedule(self, state: StreamState, sts_ws) -> None:
        self.cancel(state)
        if not state.awaiting_tool_result:
            return
        delay = self._delay_seconds()
        if delay <= 0:
            return
        user_turn_marker = state.last_user_text_time
        state.filler_injected = False
        state.filler_task = asyncio.create_task(self._timer(delay, state, sts_ws, user_turn_marker))

    def _delay_seconds(self) -> float:
        default_delay = 1.8
        try:
            return float(getattr(settings, "FILLER_DELAY_SECONDS", default_delay))
        except Exception:
            return default_delay

    def _choose_message(self, last_message: Optional[str]) -> str:
        options = [msg for msg in self._filler_messages if msg != last_message] or self._filler_messages
        return random.choice(options)

    async def _timer(
        self,
        delay_seconds: float,
        state: StreamState,
        sts_ws,
        user_turn_marker: Optional[float],
    ) -> None:
        try:
            await asyncio.sleep(delay_seconds)
            if state.closing_after_farewell or state.filler_injected:
                return
            if not state.awaiting_tool_result:
                return
            if user_turn_marker is not None and state.last_user_text_time != user_turn_marker:
                return  # Newer user turn superseded this timer
            if state.last_assistant_text_time and state.last_assistant_text_time >= (user_turn_marker or 0):
                return
            if state.last_assistant_audio_start_time and state.last_assistant_audio_start_time >= (
                user_turn_marker or 0
            ):
                return
            if state.agent_speaking:
                logger.debug("[Filler] Agent speaking; skip filler")
                return
            message = self._choose_message(state.last_filler_message)
            payload = {"type": "InjectAgentMessage", "message": message}
            await sts_ws.send(json.dumps(payload))
            state.filler_injected = True
            state.last_filler_message = message
            logger.info("[Filler] Sent filler message: %s", message)
        except asyncio.CancelledError:
            return
        except Exception as exc:
            logger.warning("[Filler] Failed to send filler message: %s", exc)
