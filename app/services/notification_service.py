"""
Service for sending SMS notifications to customers (orders, reservations).

All SMS messages use warm, personalized "Ressy" brand voice with genuine care
for the customer. Messages end with "Yours sincerely, RessyAI" signature.
"""

import asyncio
import threading
from typing import Optional

from app.integrations.twilio_client import MessageResult, TwilioClient
from app.repositories.mysql_notification_log_repo import MySQLNotificationLogRepository
from app.utils.logging_config import get_logger
from app.utils.pii_masking import mask_phone_number

logger = get_logger(__name__)

# Signature appended to all SMS messages
SMS_SIGNATURE = "\n\nYours sincerely,\nRessyAI"

# Valid statuses for orders and reservations (for validation warnings)
VALID_ORDER_STATUSES = {"pending", "confirmed", "preparing", "ready", "completed", "cancelled"}
VALID_RESERVATION_STATUSES = {"pending", "confirmed", "seated", "completed", "cancelled", "no_show"}

# Thread-safe singleton pattern
_notification_repo: Optional[MySQLNotificationLogRepository] = None
_twilio_client: Optional[TwilioClient] = None
_init_lock = threading.Lock()


def _get_notification_repo() -> MySQLNotificationLogRepository:
    """Get or create singleton notification repository (thread-safe)."""
    global _notification_repo
    if _notification_repo is None:
        with _init_lock:
            if _notification_repo is None:
                _notification_repo = MySQLNotificationLogRepository()
    return _notification_repo


def _get_twilio_client() -> TwilioClient:
    """Get or create singleton Twilio client (thread-safe)."""
    global _twilio_client
    if _twilio_client is None:
        with _init_lock:
            if _twilio_client is None:
                _twilio_client = TwilioClient()
    return _twilio_client


class NotificationService:
    """Service for sending SMS notifications to customers.

    All messages use warm, personalized "Ressy" brand voice expressing genuine
    care for the customer. Messages are conversational, not robotic.
    """

    def __init__(
        self,
        notification_repo: Optional[MySQLNotificationLogRepository] = None,
        twilio_client: Optional[TwilioClient] = None,
    ):
        """Initialize with optional dependency injection for testing."""
        self.notification_repo = notification_repo or _get_notification_repo()
        self.twilio_client = twilio_client or _get_twilio_client()

    def _build_order_status_message(
        self,
        order_id: int,
        new_status: str,
        restaurant_name: str,
    ) -> str:
        """Build a warm, personalized SMS message for order status changes.

        Uses Ressy brand voice: friendly, caring, and conversational.
        """
        normalized_status = new_status.lower().strip()

        # Log warning for unknown statuses (still sends fallback message)
        if normalized_status not in VALID_ORDER_STATUSES:
            logger.warning(
                "Unknown order status '%s' for order %s - using fallback message",
                new_status,
                order_id,
            )

        status_messages = {
            "pending": (
                f"Hey there! Your order #{order_id} at {restaurant_name} is in - "
                f"we're just waiting for the team to confirm it. Sit tight!"
            ),
            "confirmed": (
                f"Awesome news! Your order #{order_id} at {restaurant_name} is confirmed! "
                f"The kitchen is excited to prepare something delicious for you."
            ),
            "preparing": (
                f"It's happening! Your order #{order_id} at {restaurant_name} is being "
                f"prepared with care right now. Can you smell it already?"
            ),
            "ready": (
                f"Your order #{order_id} at {restaurant_name} is ready and waiting for you! "
                f"Come grab it while it's fresh - we can't wait to see you!"
            ),
            "completed": (
                f"Thank you for choosing {restaurant_name}! We hope your order #{order_id} "
                f"hit the spot. See you again soon - your table (or takeout bag) is always ready!"
            ),
            "cancelled": (
                f"We're sorry to see your order #{order_id} at {restaurant_name} was cancelled. "
                f"Life happens - we totally get it! Whenever you're ready, we'd love to serve "
                f"you again. Take care!"
            ),
        }
        message = status_messages.get(
            normalized_status,
            f"Hi! Just a quick update: your order #{order_id} at {restaurant_name} "
            f"status is now: {new_status}. Questions? Give the restaurant a call!",
        )
        return message + SMS_SIGNATURE

    def _build_reservation_status_message(
        self,
        reservation_id: int,
        new_status: str,
        restaurant_name: str,
        confirmation_number: Optional[str] = None,
    ) -> str:
        """Build a warm, personalized SMS message for reservation status changes.

        Uses Ressy brand voice: friendly, caring, and conversational.
        """
        ref = confirmation_number if confirmation_number else f"#{reservation_id}"
        normalized_status = new_status.lower().strip()

        # Log warning for unknown statuses (still sends fallback message)
        if normalized_status not in VALID_RESERVATION_STATUSES:
            logger.warning(
                "Unknown reservation status '%s' for reservation %s - using fallback message",
                new_status,
                reservation_id,
            )

        status_messages = {
            "pending": (
                f"Thanks for choosing {restaurant_name}! Your reservation ({ref}) is pending - "
                f"we're reviewing it now and will confirm shortly. We're excited to "
                f"potentially host you!"
            ),
            "confirmed": (
                f"You're all set! Your reservation ({ref}) at {restaurant_name} is confirmed! "
                f"We're genuinely thrilled to host you - the team is already looking forward "
                f"to making your visit special. See you soon!"
            ),
            "seated": (
                f"Welcome to {restaurant_name}! We hope you have an absolutely wonderful time. "
                f"If there's anything we can do to make your experience better, just let us know!"
            ),
            "completed": (
                f"Thank you for dining with us at {restaurant_name}! We hope every bite was "
                f"worth it and that you left with a full belly and a happy heart. "
                f"We'd be honored to host you again - until next time!"
            ),
            "cancelled": (
                f"We understand - your reservation ({ref}) at {restaurant_name} has been "
                f"cancelled. We know plans change, and that's completely okay! "
                f"Whenever you're ready for a great meal, we'll be here with a warm welcome. "
                f"Take care of yourself!"
            ),
            "no_show": (
                f"We missed you at {restaurant_name} for your reservation ({ref})! "
                f"We had a spot all ready for you, but life doesn't always go as planned - "
                f"we get it. Please take care of yourself, and know that we'd still love to "
                f"host you sometime. You're always welcome here!"
            ),
        }
        message = status_messages.get(
            normalized_status,
            f"Hi! Quick update on your reservation ({ref}) at {restaurant_name}: "
            f"status is now {new_status}. Questions? Feel free to reach out to the restaurant!",
        )
        return message + SMS_SIGNATURE

    async def send_order_notification(
        self,
        restaurant_id: int,
        order_id: int,
        new_status: str,
        recipient_phone: str,
        restaurant_name: str,
        restaurant_twilio_number: str,
        twilio_account_sid: Optional[str] = None,
        twilio_auth_token: Optional[str] = None,
    ) -> Optional[int]:
        """Log and send SMS for order status change. Returns log id or None if skipped.

        Uses restaurant's twilio_account_sid/twilio_auth_token when provided so the
        'From' number matches that account; otherwise uses default Twilio client (.env).
        """
        if not (recipient_phone and recipient_phone.strip()):
            return None
        if not (restaurant_twilio_number and restaurant_twilio_number.strip()):
            return None

        recipient_phone = recipient_phone.strip()
        restaurant_twilio_number = restaurant_twilio_number.strip()
        message_content = self._build_order_status_message(order_id, new_status, restaurant_name)

        log_id: Optional[int] = None
        try:
            # Wrap sync DB call to avoid blocking event loop
            log_id = await asyncio.to_thread(
                self.notification_repo.create_log,
                restaurant_id=restaurant_id,
                entity_type="order",
                entity_id=order_id,
                recipient_phone=recipient_phone,
                message_content=message_content,
            )
            await self._send_notification(
                log_id=log_id,
                recipient_phone=recipient_phone,
                message_content=message_content,
                from_number=restaurant_twilio_number,
                account_sid=twilio_account_sid,
                auth_token=twilio_auth_token,
            )
            return log_id
        except Exception as exc:
            logger.exception(
                "Failed to send order notification for restaurant_id=%s, order_id=%s, recipient=%s",
                restaurant_id,
                order_id,
                mask_phone_number(recipient_phone),
            )
            # Ensure log doesn't remain stuck in 'pending' status
            if log_id is not None:
                try:
                    await asyncio.to_thread(
                        self.notification_repo.update_status,
                        log_id=log_id,
                        status="failed",
                        error_message=str(exc),
                    )
                except Exception as db_err:
                    logger.error(
                        "Failed to update notification log status to 'failed' for log_id=%s: %s",
                        log_id,
                        db_err,
                    )
            return log_id

    async def send_reservation_notification(
        self,
        restaurant_id: int,
        reservation_id: int,
        new_status: str,
        recipient_phone: str,
        restaurant_name: str,
        restaurant_twilio_number: str,
        confirmation_number: Optional[str] = None,
        twilio_account_sid: Optional[str] = None,
        twilio_auth_token: Optional[str] = None,
    ) -> Optional[int]:
        """Log and send SMS for reservation status change. Returns log id or None if skipped.

        Uses restaurant's twilio_account_sid/twilio_auth_token when provided so the
        'From' number matches that account; otherwise uses default Twilio client (.env).
        """
        if not (recipient_phone and recipient_phone.strip()):
            return None
        if not (restaurant_twilio_number and restaurant_twilio_number.strip()):
            return None

        recipient_phone = recipient_phone.strip()
        restaurant_twilio_number = restaurant_twilio_number.strip()
        message_content = self._build_reservation_status_message(
            reservation_id, new_status, restaurant_name, confirmation_number
        )

        log_id: Optional[int] = None
        try:
            # Wrap sync DB call to avoid blocking event loop
            log_id = await asyncio.to_thread(
                self.notification_repo.create_log,
                restaurant_id=restaurant_id,
                entity_type="reservation",
                entity_id=reservation_id,
                recipient_phone=recipient_phone,
                message_content=message_content,
            )
            await self._send_notification(
                log_id=log_id,
                recipient_phone=recipient_phone,
                message_content=message_content,
                from_number=restaurant_twilio_number,
                account_sid=twilio_account_sid,
                auth_token=twilio_auth_token,
            )
            return log_id
        except Exception as exc:
            logger.exception(
                "Failed to send reservation notification for restaurant_id=%s, reservation_id=%s, recipient=%s",
                restaurant_id,
                reservation_id,
                mask_phone_number(recipient_phone),
            )
            # Ensure log doesn't remain stuck in 'pending' status
            if log_id is not None:
                try:
                    await asyncio.to_thread(
                        self.notification_repo.update_status,
                        log_id=log_id,
                        status="failed",
                        error_message=str(exc),
                    )
                except Exception as db_err:
                    logger.error(
                        "Failed to update notification log status to 'failed' for log_id=%s: %s",
                        log_id,
                        db_err,
                    )
            return log_id

    async def send_sms(
        self,
        restaurant_id: int,
        entity_type: str,
        entity_id: int,
        recipient_phone: str,
        message_content: str,
        from_number: str,
        account_sid: Optional[str] = None,
        auth_token: Optional[str] = None,
    ) -> int:
        """Send an SMS notification and log it.

        This is the public interface for sending generic SMS notifications.

        Args:
            restaurant_id: Restaurant ID for logging
            entity_type: Type of entity ('order', 'reservation', 'sms_redirect')
            entity_id: ID of the entity (order_id, reservation_id, call_id)
            recipient_phone: Phone number to send SMS to
            message_content: SMS body content
            from_number: Twilio phone number to send from
            account_sid: Optional Twilio account SID (uses default if not provided)
            auth_token: Optional Twilio auth token (uses default if not provided)

        Returns:
            log_id: The notification log ID

        Raises:
            Exception: If SMS sending fails
        """
        # Create log entry first
        log_id = await asyncio.to_thread(
            self.notification_repo.create_log,
            restaurant_id=restaurant_id,
            entity_type=entity_type,
            entity_id=entity_id,
            recipient_phone=recipient_phone,
            message_content=message_content,
        )

        # Send the SMS
        await self._send_notification(
            log_id=log_id,
            recipient_phone=recipient_phone,
            message_content=message_content,
            from_number=from_number,
            account_sid=account_sid,
            auth_token=auth_token,
        )

        return log_id

    async def _send_notification(
        self,
        log_id: int,
        recipient_phone: str,
        message_content: str,
        from_number: str,
        account_sid: Optional[str] = None,
        auth_token: Optional[str] = None,
    ) -> None:
        """Send SMS and update log status (sent/failed).

        Uses account_sid/auth_token when both provided (restaurant's Twilio account).
        Database operations are wrapped with asyncio.to_thread() to avoid blocking.
        """
        logger.info(
            "Sending SMS notification log_id=%d to=%s from=%s message_length=%d",
            log_id,
            mask_phone_number(recipient_phone),
            from_number,
            len(message_content),
        )

        result: MessageResult = self.twilio_client.send_sms(
            to=recipient_phone,
            body=message_content,
            from_number=from_number,
            account_sid=account_sid,
            auth_token=auth_token,
        )

        if result.success:
            # Wrap sync DB call to avoid blocking event loop
            await asyncio.to_thread(
                self.notification_repo.update_status,
                log_id=log_id,
                status="sent",
                twilio_message_sid=result.message_sid,
            )
        else:
            await asyncio.to_thread(
                self.notification_repo.update_status,
                log_id=log_id,
                status="failed",
                error_message=result.error_message,
            )
            await asyncio.to_thread(
                self.notification_repo.increment_retry_count,
                log_id,
            )
