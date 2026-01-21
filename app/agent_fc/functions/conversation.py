"""Conversation-oriented agent functions (fillers, escalation, call termination)."""

from __future__ import annotations

import asyncio
import random
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict

from app.agent_fc.functions.common_restaurant import load_restaurant
from app.agent_fc.functions.function_context import split_call_context
from app.agent_fc.responses import AgentFunctionResult, AgentSideEffect
from app.services.call_service import CallService
from app.services.escalation_service import EscalationService
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
    feature_disabled: Optional[Literal["orders", "reservations", "faqs"]] = None


def _pick_message(message_set: list[str]) -> str:
    return random.choice(message_set)


def _get_sse_service() -> SSEService:
    """Create fresh SSE service instance per function call."""
    return SSEService()


def _build_escalation_message(args: EscalateToHumanArgs, should_forward: bool) -> str:
    if args.feature_disabled:
        if args.feature_disabled == "orders":
            if should_forward:
                return (
                    "I can't take pickup orders for this location, but I can connect you to the team right now. "
                    "One moment."
                )
            return "I can't take pickup orders for this location. I'll have the team call you back shortly."
        if args.feature_disabled == "reservations":
            if should_forward:
                return (
                    "I'm not able to book reservations for this location, but I can connect you to the team right now. "
                    "One moment."
                )
            return "I'm not able to book reservations for this location. I'll have the team call you back shortly."
        if args.feature_disabled == "faqs":
            if should_forward:
                return "I don't have the info to answer that here, but I can connect you to the team now. One moment."
            return "I don't have the info to answer that here. I'll have the team call you back shortly."

    if should_forward:
        return "Please hold while I connect you to a team member."
    return (
        "I'm looping in a team member to assist you now. You'll receive a call back from them shortly. "
        "Thank you for your patience."
    )


async def _emit_escalation_sse_event(
    restaurant_id: int,
    caller_phone: str,
    reason: str,
    urgency: Literal["standard", "urgent"],
    call_sid: Optional[str] = None,
) -> None:
    """Broadcast escalation to SSE subscribers; keep failures from affecting the call flow."""
    try:
        sse_service = _get_sse_service()
        await sse_service.emit_escalation_user_requested(
            restaurant_id=restaurant_id,
            caller_phone=caller_phone,
            reason=reason,
            data={"urgency": urgency},
        )
    except Exception as exc:  # noqa: BLE001 - defensive
        logger.warning("Failed to emit escalation SSE event call_sid=%s: %s", call_sid, exc)


async def agent_filler(**kwargs) -> AgentFunctionResult:
    context, model_kwargs = split_call_context(kwargs, AgentFillerArgs)
    args = AgentFillerArgs.model_validate(model_kwargs)
    call_sid = context.get("call_sid")
    options = FILLER_LIBRARY.get(args.filler_type) or FILLER_LIBRARY["general"]
    message = _pick_message(options)
    logger.info("agent_filler invoked filler_type=%s call_sid=%s", args.filler_type, call_sid)
    return AgentFunctionResult(
        content={"status": "QUEUED", "filler_type": args.filler_type},
        side_effects=[
            AgentSideEffect({"type": "InjectAgentMessage", "message": message}),
        ],
    )


async def end_call(**kwargs) -> AgentFunctionResult:
    context, model_kwargs = split_call_context(kwargs, EndCallArgs)
    args = EndCallArgs.model_validate(model_kwargs)
    call_sid = context.get("call_sid")
    message = FAREWELL_LIBRARY.get(args.farewell_style, FAREWELL_LIBRARY["general"])
    logger.info("end_call invoked style=%s call_sid=%s", args.farewell_style, call_sid)
    return AgentFunctionResult(
        content={"status": "CLOSING", "farewell_style": args.farewell_style},
        side_effects=[
            AgentSideEffect({"type": "InjectAgentMessage", "message": message}),
            AgentSideEffect({"type": "close"}, delay_seconds=max(args.delay_seconds, 0.2)),
        ],
    )


async def escalate_to_human(**kwargs) -> AgentFunctionResult:
    context, model_kwargs = split_call_context(kwargs, EscalateToHumanArgs)
    args = EscalateToHumanArgs.model_validate(model_kwargs)
    call_sid = context.get("call_sid")
    call_id = context.get("call_id")
    user_id = context.get("user_id")
    logger.info("escalate_to_human invoked urgency=%s reason=%s call_sid=%s", args.urgency, args.reason, call_sid)

    restaurant = await load_restaurant(args.restaurant_id)
    forward_escalations = False
    escalation_phone_number = None
    if restaurant:
        try:
            forward_escalations = bool(int(restaurant.get("forward_escalations", 0)))
        except (TypeError, ValueError):
            forward_escalations = False
        escalation_phone_number = restaurant.get("escalation_phone_number")

    escalation_service = EscalationService()
    try:
        escalation_service.create_escalation(
            {
                "call_id": call_id,
                "user_id": user_id,
                "restaurant_id": str(args.restaurant_id),
                "twilio_call_sid": call_sid,
                "caller_phone": args.customer_contact,
                "escalation_phone_number": escalation_phone_number,
                "urgency": args.urgency,
                "reason": args.reason,
                "status": "raised",
            }
        )
    except Exception as exc:  # noqa: BLE001 - defensive
        logger.warning("Failed to persist escalation call_sid=%s: %s", call_sid, exc)

    if call_id:
        try:
            CallService().mark_escalated(call_id)
        except Exception as exc:  # noqa: BLE001 - defensive
            logger.warning("Failed to mark call escalated call_id=%s call_sid=%s: %s", call_id, call_sid, exc)

    should_forward = forward_escalations and bool(escalation_phone_number)
    message = _build_escalation_message(args, should_forward)
    content = {
        "status": "HUMAN_ESCALATION_REQUESTED",
        "urgency": args.urgency,
        "reason": args.reason,
        "customer_contact": args.customer_contact,
        "forwarding": should_forward,
    }
    asyncio.create_task(
        _emit_escalation_sse_event(
            restaurant_id=int(args.restaurant_id),
            caller_phone=args.customer_contact,
            reason=args.reason,
            urgency=args.urgency,
            call_sid=call_sid,
        )
    )
    side_effects = [AgentSideEffect({"type": "InjectAgentMessage", "message": message})]
    if should_forward:
        side_effects.append(AgentSideEffect({"type": "close"}, delay_seconds=0.5))
    return AgentFunctionResult(content=content, side_effects=side_effects)
