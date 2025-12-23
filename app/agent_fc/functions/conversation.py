"""Conversation-oriented agent functions (fillers, escalation, call termination)."""

from __future__ import annotations

import asyncio
import random
from typing import Literal

from pydantic import BaseModel, ConfigDict

from app.agent_fc.responses import AgentFunctionResult, AgentSideEffect
from app.services.sse_service import SSEService
from app.utils.logging_config import get_logger

logger = get_logger(__name__)

FILLER_LIBRARY = {
    "menu_lookup": [
        "Let me pull up the menu for you real quick...",
        "One moment while I double-check which dishes we are serving right now...",
    ],
    "table_availability_check": [
        "Give me a second to see what tables we still have open...",
        "Let me double-check our reservation grid for that time...",
    ],
    "reservation_booking": [
        "Let me get that reservation set up for you...",
        "Just a moment while I book that table for you...",
    ],
    "reservation_lookup": [
        "Let me look up your reservation...",
        "One moment while I find your booking details...",
    ],
    "order_review": [
        "Let me make sure I captured everything correctly...",
        "Hang tight while I confirm those items with the kitchen...",
    ],
    "payment_lookup": [
        "Just a moment while I total that up...",
        "Let me get the order total for you...",
    ],
    "general": [
        "One moment please...",
        "Thanks for waiting just a second...",
    ],
}

FAREWELL_LIBRARY = {
    "general": "You're all set. Thanks for calling and have a great day!",
    "positive": "Wonderful! We can't wait to see you. Have an amazing day!",
    "apologetic": "I'm sorry I wasn't able to help out much. We'd love to hear from you again!",
}


class AgentFillerArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    filler_type: Literal[
        "menu_lookup",
        "table_availability_check",
        "reservation_booking",
        "reservation_lookup",
        "order_review",
        "payment_lookup",
        "general",
    ] = "general"


class EndCallArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    farewell_style: Literal["general", "positive", "apologetic"] = "general"
    delay_seconds: float = 0.7


class EscalateToHumanArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    restaurant_id: int
    customer_contact: str
    reason: str
    urgency: Literal["standard", "urgent"] = "standard"


def _pick_message(message_set: list[str]) -> str:
    return random.choice(message_set)


_sse_service = SSEService()


async def _emit_escalation_sse_event(
    restaurant_id: int,
    caller_phone: str,
    reason: str,
    urgency: Literal["standard", "urgent"],
) -> None:
    """Broadcast escalation to SSE subscribers; keep failures from affecting the call flow."""
    try:
        await _sse_service.emit_escalation_user_requested(
            restaurant_id=restaurant_id,
            caller_phone=caller_phone,
            reason=reason,
            data={"urgency": urgency},
        )
    except Exception as exc:  # noqa: BLE001 - defensive
        logger.warning("Failed to emit escalation SSE event: %s", exc)


async def agent_filler(**kwargs) -> AgentFunctionResult:
    args = AgentFillerArgs.model_validate(kwargs)
    options = FILLER_LIBRARY.get(args.filler_type) or FILLER_LIBRARY["general"]
    message = _pick_message(options)
    logger.info("agent_filler invoked filler_type=%s", args.filler_type)
    return AgentFunctionResult(
        content={"status": "QUEUED", "filler_type": args.filler_type},
        side_effects=[
            AgentSideEffect({"type": "InjectAgentMessage", "message": message}),
        ],
    )


async def end_call(**kwargs) -> AgentFunctionResult:
    args = EndCallArgs.model_validate(kwargs)
    message = FAREWELL_LIBRARY.get(args.farewell_style, FAREWELL_LIBRARY["general"])
    logger.info("end_call invoked style=%s", args.farewell_style)
    return AgentFunctionResult(
        content={"status": "CLOSING", "farewell_style": args.farewell_style},
        side_effects=[
            AgentSideEffect({"type": "InjectAgentMessage", "message": message}),
            AgentSideEffect({"type": "close"}, delay_seconds=max(args.delay_seconds, 0.2)),
        ],
    )


async def escalate_to_human(**kwargs) -> AgentFunctionResult:
    args = EscalateToHumanArgs.model_validate(kwargs)
    logger.info("escalate_to_human invoked urgency=%s reason=%s", args.urgency, args.reason)
    message = "I’m looping in a team member to assist you now. You'll receive a call back from them shortly. Thank you for your patience."
    content = {
        "status": "HUMAN_ESCALATION_REQUESTED",
        "urgency": args.urgency,
        "reason": args.reason,
        "customer_contact": args.customer_contact,
    }
    asyncio.create_task(
        _emit_escalation_sse_event(
            restaurant_id=int(args.restaurant_id),
            caller_phone=args.customer_contact,
            reason=args.reason,
            urgency=args.urgency,
        )
    )
    return AgentFunctionResult(
        content=content,
        side_effects=[
            AgentSideEffect({"type": "InjectAgentMessage", "message": message}),
        ],
    )
