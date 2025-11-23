"""Conversation-oriented agent functions (fillers, escalation, call termination)."""

from __future__ import annotations

import random
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict

from app.agent_fc.responses import AgentFunctionResult, AgentSideEffect

FILLER_LIBRARY = {
    "menu_lookup": [
        "Let me pull up the menu for you real quick...",
        "One moment while I double-check which dishes we are serving right now...",
    ],
    "table_availability_check": [
        "Give me a second to see what tables we still have open...",
        "Let me double-check our reservation grid for that time...",
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
    "apologetic": "I'm sorry I wasn't able to help out much. We'd love to hear from you again!"
}


class AgentFillerArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    filler_type: Literal[
        "menu_lookup",
        "table_availability_check",
        "order_review",
        "payment_lookup",
        "general",
    ] = "general"


class EndCallArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    farewell_style: Literal["general", "positive", "busy"] = "general"
    delay_seconds: float = 0.7


class EscalateToHumanArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    restaurant_id: int
    reason: Optional[str] = None
    urgency: Literal["standard", "urgent"] = "standard"


def _pick_message(message_set: list[str]) -> str:
    return random.choice(message_set)


async def agent_filler(**kwargs) -> AgentFunctionResult:
    args = AgentFillerArgs.model_validate(kwargs)
    options = FILLER_LIBRARY.get(args.filler_type) or FILLER_LIBRARY["general"]
    message = _pick_message(options)
    print(f"[INFO] agent_filler invoked filler_type={args.filler_type}")
    return AgentFunctionResult(
        content={"status": "QUEUED", "filler_type": args.filler_type},
        side_effects=[
            AgentSideEffect({"type": "InjectAgentMessage", "message": message}),
        ],
    )


async def end_call(**kwargs) -> AgentFunctionResult:
    args = EndCallArgs.model_validate(kwargs)
    message = FAREWELL_LIBRARY.get(args.farewell_style, FAREWELL_LIBRARY["general"])
    print(f"[INFO] end_call invoked style={args.farewell_style}")
    return AgentFunctionResult(
        content={"status": "CLOSING", "farewell_style": args.farewell_style},
        side_effects=[
            AgentSideEffect({"type": "InjectAgentMessage", "message": message}),
            AgentSideEffect({"type": "close"}, delay_seconds=max(args.delay_seconds, 0.2)),
        ],
    )


async def escalate_to_human(**kwargs) -> AgentFunctionResult:
    args = EscalateToHumanArgs.model_validate(kwargs)
    print(f"[INFO] escalate_to_human invoked urgency={args.urgency} reason={args.reason}")
    message = (
        "It sounds like you'd prefer to speak with one of our team members. Please allow me to connect you."
    )
    content = {
        "status": "HUMAN_ESCALATION_REQUESTED",
        "urgency": args.urgency,
        "reason": args.reason,
    }
    return AgentFunctionResult(
        content=content,
        side_effects=[
            AgentSideEffect({"type": "InjectAgentMessage", "message": message}),
        ],
    )
