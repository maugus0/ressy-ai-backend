"""Spam detection agent function.

Detects spam behavior during calls and creates notifications for restaurant admins.
AI does NOT mark users as spam - only creates notifications for admin review.
"""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict

from app.agent_fc.functions.function_context import split_call_context
from app.agent_fc.responses import AgentFunctionResult, AgentSideEffect
from app.services.notification_persistence_service import NotificationPersistenceService
from app.utils.logging_config import get_logger

logger = get_logger(__name__)


class DetectSpamBehaviorArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    restaurant_id: int
    customer_contact: str
    indicators: str  # Description of spam indicators detected
    confidence: Literal["low", "medium", "high"] = "medium"
    transcript_summary: Optional[str] = None  # Summary of suspicious conversation


async def detect_spam_behavior(**kwargs) -> AgentFunctionResult:
    """
    Detect spam behavior during a call and create notification for restaurant admin.

    This function:
    1. Creates a notification (type: "spam", subtype: "detected") for restaurant admin
    2. Disconnects the call immediately
    3. Does NOT mark the user as spam - only restaurant admins can do that via API

    Args:
        restaurant_id: Restaurant ID
        customer_contact: Caller's phone number
        indicators: Description of spam indicators (e.g., "Immediate DTMF tones, no background noise")
        confidence: Confidence level of spam detection
        transcript_summary: Optional summary of suspicious conversation

    Returns:
        AgentFunctionResult with side effect to disconnect call
    """
    context, model_kwargs = split_call_context(kwargs, DetectSpamBehaviorArgs)
    args = DetectSpamBehaviorArgs.model_validate(model_kwargs)
    call_sid = context.get("call_sid")
    call_id = context.get("call_id")
    user_id = context.get("user_id")

    logger.warning(
        "Spam detected: user_id=%s restaurant_id=%s call_sid=%s indicators=%s confidence=%s",
        user_id,
        args.restaurant_id,
        call_sid,
        args.indicators,
        args.confidence,
    )

    # Create notification for restaurant admin (AI detection - NOT marking as spam)
    try:
        notification_service = NotificationPersistenceService()
        notification_service.create_notification(
            restaurant_id=args.restaurant_id,
            type="spam",
            subtype="detected",
            data={
                "caller_phone": args.customer_contact,
                "user_id": user_id,
                "call_id": call_id,
                "call_sid": call_sid,
                "indicators": args.indicators,
                "confidence": args.confidence,
                "transcript_summary": args.transcript_summary,
                "ai_detected": True,
            },
            entity_id=int(call_id) if call_id else None,
        )
        logger.info(
            "Spam detection notification created: restaurant_id=%s user_id=%s",
            args.restaurant_id,
            user_id,
        )
    except Exception as exc:
        logger.exception("Failed to create spam detection notification: %s", exc)

    # Disconnect the call immediately
    message = "Thank you for calling. Goodbye."
    return AgentFunctionResult(
        content={
            "status": "SPAM_DETECTED",
            "restaurant_id": args.restaurant_id,
            "indicators": args.indicators,
            "confidence": args.confidence,
        },
        side_effects=[
            AgentSideEffect({"type": "InjectAgentMessage", "message": message}),
            AgentSideEffect({"type": "close"}, delay_seconds=0.5),
        ],
    )
