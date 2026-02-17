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


class SendSMSRedirectArgs(BaseModel):
    """Arguments for sending an SMS redirect link to a customer.

    Note: customer_phone is optional - if not provided, the caller's phone
    (from customer_contact in context) will be used automatically.
    """

    model_config = ConfigDict(extra="forbid")

    restaurant_id: int
    redirect_type: Literal["orders", "reservations"]
    # Optional: if not provided, uses caller's phone from context
    customer_phone: Optional[str] = None


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
    call_id: Optional[int] = None,
) -> None:
    """Broadcast escalation to SSE subscribers and persist notification; keep failures from affecting the call flow."""
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

    try:
        from app.services.notification_persistence_service import NotificationPersistenceService

        notification_service = NotificationPersistenceService()
        notification_service.create_notification(
            restaurant_id=restaurant_id,
            type="escalation",
            subtype="user_requested",
            data={
                "caller_phone": caller_phone,
                "reason": reason,
                "urgency": urgency,
            },
            entity_id=int(call_id) if call_id is not None else None,
        )
    except Exception as exc:  # noqa: BLE001 - defensive
        logger.warning("Escalation notification persistence failed call_sid=%s: %s", call_sid, exc)


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
            call_id=call_id,
        )
    )
    side_effects = [AgentSideEffect({"type": "InjectAgentMessage", "message": message})]
    if should_forward:
        side_effects.append(AgentSideEffect({"type": "close"}, delay_seconds=0.5))
    return AgentFunctionResult(content=content, side_effects=side_effects)


# Default redirect message text (just the instruction, not the full SMS)
DEFAULT_ORDERS_REDIRECT_MESSAGE = "Please place your order using the link below."
DEFAULT_RESERVATIONS_REDIRECT_MESSAGE = "Please make your reservation using the link below."


def _get_sms_redirect_message(
    redirect_type: str,
    redirect_url: str,
    custom_message: Optional[str],
    restaurant_name: str,
) -> str:
    """Build the SMS message with a consistent format.

    SMS Format:
    ```
    Hello.
    {redirect_message}

    {redirect_url}

    Yours sincerely,
    {restaurant_name} via RessyAI
    ```

    If custom_message is provided, it's used as the redirect message.
    Otherwise, the default message for the redirect type is used.
    """
    # Use custom message or default based on redirect type
    if custom_message and custom_message.strip():
        redirect_message = custom_message.strip()
    else:
        redirect_message = (
            DEFAULT_ORDERS_REDIRECT_MESSAGE if redirect_type == "orders" else DEFAULT_RESERVATIONS_REDIRECT_MESSAGE
        )

    # Build the SMS with consistent format
    sms = f"""Hello.
{redirect_message}

{redirect_url}

Yours sincerely,
{restaurant_name} via RessyAI"""

    return sms


async def send_sms_redirect(**kwargs) -> AgentFunctionResult:
    """Send an SMS with a redirect link to the customer for orders or reservations.

    This function is triggered automatically when:
    - orders_sms_redirect is enabled and customer wants to place an order
    - reservations_sms_redirect is enabled and customer wants to make a reservation

    The customer's phone number is taken from the caller's phone (customer_contact in context)
    automatically - the agent does NOT need to ask for the phone number.

    SMS notifications are logged to the Notification_Logs table for audit and retry.
    """
    import asyncio
    import json

    from app.repositories.mysql_notification_log_repo import MySQLNotificationLogRepository
    from app.repositories.mysql_restaurant_features_repo import MySQLRestaurantFeaturesRepository
    from app.services.notification_service import NotificationService

    context, model_kwargs = split_call_context(kwargs, SendSMSRedirectArgs)
    args = SendSMSRedirectArgs.model_validate(model_kwargs)
    call_sid = context.get("call_sid")
    call_id = context.get("call_id")

    # Use caller's phone from context if not explicitly provided
    # The caller's phone is automatically passed as customer_contact in default_args
    customer_phone = args.customer_phone or context.get("customer_contact")

    if not customer_phone:
        logger.warning("No customer phone available for SMS redirect: call_sid=%s", call_sid)
        return AgentFunctionResult(
            content={"status": "ERROR", "error": "No customer phone available"},
            side_effects=[
                AgentSideEffect(
                    {
                        "type": "InjectAgentMessage",
                        "message": "I apologize, but I don't have your phone number to send the link. "
                        "Let me connect you with the team to help you directly.",
                    }
                )
            ],
        )

    logger.info(
        "send_sms_redirect invoked type=%s customer_phone=%s call_sid=%s",
        args.redirect_type,
        f"****{customer_phone[-4:]}" if customer_phone and len(customer_phone) >= 4 else "****",
        call_sid,
    )

    # Load restaurant and features
    try:
        restaurant = await load_restaurant(args.restaurant_id)
    except Exception as exc:
        logger.error(
            "Failed to load restaurant for SMS redirect: restaurant_id=%s error=%s",
            args.restaurant_id,
            exc,
        )
        restaurant = None

    if not restaurant:
        logger.warning("Restaurant not found for SMS redirect: restaurant_id=%s", args.restaurant_id)
        return AgentFunctionResult(
            content={"status": "ERROR", "error": "Restaurant not found"},
            side_effects=[
                AgentSideEffect(
                    {
                        "type": "InjectAgentMessage",
                        "message": "I'm sorry, I'm having trouble sending that link. Let me connect you with the team.",
                    }
                )
            ],
        )

    restaurant_id = int(args.restaurant_id)
    restaurant_name = restaurant.get("name", "the restaurant")
    twilio_phone_number = restaurant.get("twilio_phone_number")

    # Fetch features from features repo (includes SMS redirect config)
    features_repo = MySQLRestaurantFeaturesRepository()
    try:
        features = await asyncio.to_thread(features_repo.get_by_restaurant_id, restaurant_id)
    except Exception as exc:
        logger.warning("Failed to fetch features for restaurant_id=%s: %s", restaurant_id, exc)
        features = {}
    features = features or {}
    sms_config_key = f"{args.redirect_type}_sms_redirect"
    sms_config = features.get(sms_config_key, {})

    if not sms_config.get("enabled"):
        logger.warning(
            "SMS redirect not enabled for %s: restaurant_id=%s",
            args.redirect_type,
            restaurant_id,
        )
        return AgentFunctionResult(
            content={"status": "ERROR", "error": f"SMS redirect not enabled for {args.redirect_type}"},
            side_effects=[
                AgentSideEffect(
                    {
                        "type": "InjectAgentMessage",
                        "message": "I apologize, but I'm unable to send that link right now. Let me connect you with staff.",
                    }
                )
            ],
        )

    redirect_url = sms_config.get("redirect_url")
    custom_message = sms_config.get("redirect_message")

    if not redirect_url:
        logger.error("No redirect URL configured for %s: restaurant_id=%s", args.redirect_type, restaurant_id)
        return AgentFunctionResult(
            content={"status": "ERROR", "error": "Redirect URL not configured"},
            side_effects=[
                AgentSideEffect(
                    {
                        "type": "InjectAgentMessage",
                        "message": "I apologize, but I'm unable to send that link right now. Let me connect you with staff.",
                    }
                )
            ],
        )

    # Build the SMS message
    sms_body = _get_sms_redirect_message(
        redirect_type=args.redirect_type,
        redirect_url=redirect_url,
        custom_message=custom_message,
        restaurant_name=restaurant_name,
    )

    # Get Twilio credentials from restaurant
    # twilio_details may be a JSON string or already parsed dict
    twilio_details = restaurant.get("twilio_details")
    if isinstance(twilio_details, str):
        try:
            twilio_details = json.loads(twilio_details)
        except (json.JSONDecodeError, TypeError):
            twilio_details = {}
    twilio_details = twilio_details or {}
    account_sid = twilio_details.get("account_sid")
    auth_token = twilio_details.get("auth_token")

    # Fallback to restaurant's twilio phone or error
    from_number = twilio_phone_number
    if not from_number:
        logger.error("No Twilio phone number configured for restaurant_id=%s", restaurant_id)
        return AgentFunctionResult(
            content={"status": "ERROR", "error": "No SMS sender configured"},
            side_effects=[
                AgentSideEffect(
                    {
                        "type": "InjectAgentMessage",
                        "message": "I apologize, but I'm unable to send that link right now. Let me connect you with staff.",
                    }
                )
            ],
        )

    # Use NotificationService to send SMS and log to Notification_Logs table
    # This follows the same pattern as order/reservation status notifications
    notification_repo = MySQLNotificationLogRepository()
    notification_service = NotificationService(notification_repo=notification_repo)

    # Create log entry first (entity_type = 'sms_redirect', entity_id = call_id or 0)
    entity_id = int(call_id) if call_id else 0
    log_id: Optional[int] = None

    try:
        # Create notification log entry
        log_id = await asyncio.to_thread(
            notification_repo.create_log,
            restaurant_id=restaurant_id,
            entity_type="sms_redirect",
            entity_id=entity_id,
            recipient_phone=customer_phone,
            message_content=sms_body,
        )

        # Send SMS using the notification service's internal method
        await notification_service._send_notification(
            log_id=log_id,
            recipient_phone=customer_phone,
            message_content=sms_body,
            from_number=from_number,
            account_sid=account_sid,
            auth_token=auth_token,
        )

        logger.info(
            "SMS redirect sent successfully log_id=%s type=%s call_sid=%s",
            log_id,
            args.redirect_type,
            call_sid,
        )
        # Build a helpful message based on the redirect type
        # We do NOT use InjectAgentMessage here because that causes duplicate messages -
        # the injected message plays, then the agent also generates its own response
        # based on the function result. By only returning content, the agent will
        # naturally respond based on this content alone.
        if args.redirect_type == "orders":
            message_to_customer = (
                "I've just sent you a text with a link to place your order. "
                "But I'm still here on the call if you have any questions! "
                "Feel free to ask me about our menu items, ingredients, prices, "
                "or anything else about the restaurant - I'm happy to help."
            )
        else:  # reservations
            message_to_customer = (
                "I've just sent you a text with a link to make your reservation. "
                "But I'm still here if you need anything! "
                "You can ask me about our hours, location, menu, "
                "or any other details about the restaurant."
            )

        return AgentFunctionResult(
            content={
                "status": "success",
                "message_to_customer": message_to_customer,
            },
            side_effects=[],  # No InjectAgentMessage - let agent speak naturally from the content
        )

    except Exception as exc:
        logger.error(
            "Failed to send SMS redirect: error=%s type=%s call_sid=%s",
            str(exc),
            args.redirect_type,
            call_sid,
        )
        # Update log status to failed if we created one
        if log_id is not None:
            try:
                await asyncio.to_thread(
                    notification_repo.update_status,
                    log_id=log_id,
                    status="failed",
                    error_message=str(exc),
                )
            except Exception as db_err:
                logger.error("Failed to update notification log status: %s", db_err)

        return AgentFunctionResult(
            content={"status": "ERROR", "error": str(exc)},
            side_effects=[
                AgentSideEffect(
                    {
                        "type": "InjectAgentMessage",
                        "message": "I apologize, but I wasn't able to send the text message. "
                        "Let me connect you with the team to help you directly.",
                    }
                )
            ],
        )
