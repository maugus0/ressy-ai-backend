from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class StreamState:
    audio_buffer: bytearray = field(default_factory=bytearray)
    last_agent_audio_time: Optional[float] = None
    barge_in_active: bool = False
    agent_speaking: bool = False
    barge_in_start_time: Optional[float] = None
    barge_in_reported: bool = False
    last_user_text_time: Optional[float] = None
    last_user_started_speaking_time: Optional[float] = None
    last_function_response_time: Optional[float] = None
    in_function_chain: bool = False
    closing_after_farewell: bool = False
    farewell_expected_text: Optional[str] = None
    farewell_started: bool = False
    farewell_shutdown_complete: bool = False
    message_seq: int = 0
    conversation_history: list[dict[str, Any]] = field(default_factory=list)
    last_assistant_text_time: Optional[float] = None
    last_assistant_audio_start_time: Optional[float] = None
    agent_audio_latency_logged: bool = False
    filler_task: Optional[asyncio.Task] = None
    filler_injected: bool = False
    last_filler_message: Optional[str] = None
