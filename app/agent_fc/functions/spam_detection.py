"""Mark potential spam agent function.

Marks potential spam behavior during calls and creates notifications for restaurant admins.
"""

from __future__ import annotations

import asyncio
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict

from app.agent_fc.functions.function_context import split_call_context
from app.agent_fc.responses import AgentFunctionResult, AgentSideEffect
from app.services.notification_persistence_service import NotificationPersistenceService
from app.services.sse_service import SSEService
from app.utils.logging_config import get_logger

logger = get_logger(__name__)


def _get_sse_service() -> SSEService:
    """Create fresh SSE service instance per function call."""
    return SSEService()


class MarkPotentialSpamArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    indicators: str  # Description of spam indicators detected
    confidence: Literal["low", "medium", "high"] = "medium"
    transcript_summary: Optional[str] = None  # Summary of suspicious conversation


async def mark_potential_spam(**kwargs) -> AgentFunctionResult:
    """
    Mark potential spam during a call and create notification for restaurant admin.

    This function:
    1. Creates a notification (type: "escalation", subtype: "suspected_spam") for restaurant admin
    2. Disconnects the call immediately

    Args:
        indicators: Description of spam indicators (e.g., "Repeated unrelated questions")
        confidence: Confidence level of spam detection
        transcript_summary: Optional summary of suspicious conversation

    Returns:
        AgentFunctionResult with side effect to disconnect call
    """
    context, model_kwargs = split_call_context(kwargs, MarkPotentialSpamArgs)
    args = MarkPotentialSpamArgs.model_validate(model_kwargs)
    call_sid = context.get("call_sid")
    call_id = context.get("call_id")
    user_id = context.get("user_id")
    restaurant_id = context.get("restaurant_id")
    customer_contact = context.get("customer_contact")

    if not restaurant_id:
        logger.error("mark_potential_spam: restaurant_id not found in context")
        return AgentFunctionResult(
            content={"status": "ERROR", "message": "Restaurant ID not found"},
            side_effects=[AgentSideEffect({"type": "close"}, delay_seconds=0.5)],
        )

    logger.warning(
        "Spam detected: user_id=%s restaurant_id=%s call_sid=%s indicators=%s confidence=%s",
        user_id,
        restaurant_id,
        call_sid,
        args.indicators,
        args.confidence,
    )

    # Emit SSE event and create notification (similar to escalation pattern)
    asyncio.create_task(
        _emit_spam_sse_event_and_notification(
            restaurant_id=int(restaurant_id),
            caller_phone=customer_contact,
            indicators=args.indicators,
            confidence=args.confidence,
            transcript_summary=args.transcript_summary,
            call_sid=call_sid,
            call_id=call_id,
            user_id=user_id,
        )
    )

    # Disconnect the call immediately
    message = "Thank you for calling. Goodbye."
    return AgentFunctionResult(
        content={
            "status": "SPAM_DETECTED",
            "restaurant_id": restaurant_id,
            "indicators": args.indicators,
            "confidence": args.confidence,
        },
        side_effects=[
            AgentSideEffect({"type": "InjectAgentMessage", "message": message}),
            AgentSideEffect({"type": "close"}, delay_seconds=0.5),
        ],
    )


async def _emit_spam_sse_event_and_notification(
    restaurant_id: int,
    caller_phone: str,
    indicators: str,
    confidence: Literal["low", "medium", "high"],
    transcript_summary: Optional[str],
    call_sid: Optional[str] = None,
    call_id: Optional[int] = None,
    user_id: Optional[int] = None,
) -> None:
    """Broadcast spam detection to SSE subscribers and persist notification; keep failures from affecting the call flow."""
    # Emit SSE event
    try:
        sse_service = _get_sse_service()
        spam_score = 0.9 if confidence == "high" else 0.7 if confidence == "medium" else 0.5
        indicators_list = [indicators] if isinstance(indicators, str) else indicators
        await sse_service.emit_escalation_suspected_spam(
            restaurant_id=restaurant_id,
            call_id=str(call_id) if call_id else None,
            caller_phone=caller_phone,
            spam_score=spam_score,
            indicators=indicators_list,
            data={
                "confidence": confidence,
                "user_id": user_id,
                "call_sid": call_sid,
                "transcript_summary": transcript_summary,
                "ai_detected": True,
            },
        )
    except Exception as exc:  # noqa: BLE001 - defensive
        logger.warning("Failed to emit spam detection SSE event call_sid=%s: %s", call_sid, exc)

    # Create notification
    try:
        notification_service = NotificationPersistenceService()
        notification_service.create_notification(
            restaurant_id=restaurant_id,
            type="escalation",
            subtype="suspected_spam",
            data={
                "caller_phone": caller_phone,
                "user_id": user_id,
                "call_id": call_id,
                "call_sid": call_sid,
                "indicators": [indicators] if isinstance(indicators, str) else indicators,
                "confidence": confidence,
                "spam_score": 0.9 if confidence == "high" else 0.7 if confidence == "medium" else 0.5,
                "reason": f"AI detected spam behavior: {indicators}",
                "transcript_summary": transcript_summary,
                "ai_detected": True,
            },
            entity_id=int(call_id) if call_id else None,
        )
        logger.info(
            "Spam detection notification created: restaurant_id=%s user_id=%s",
            restaurant_id,
            user_id,
        )
    except Exception as exc:  # noqa: BLE001 - defensive
        logger.warning("Spam detection notification persistence failed call_sid=%s: %s", call_sid, exc)
