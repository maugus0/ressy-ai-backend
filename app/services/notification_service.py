import asyncio
from typing import Optional

from app.integrations.twilio_client import TwilioClient
from app.repositories.mysql_notification_log_repo import MySQLNotificationLogRepository
from app.utils.logging_config import get_logger

logger = get_logger(__name__)


class NotificationService:

    def __init__(self):
        self.notification_repo = MySQLNotificationLogRepository()
        self.twilio_client = TwilioClient()

    def _build_order_status_message(
        self,
        order_id: int,
        new_status: str,
        restaurant_name: str,
    ) -> str:
        status_messages = {
            "pending": f"Your order #{order_id} at {restaurant_name} has been received and is pending confirmation.",
            "confirmed": f"Great news! Your order #{order_id} at {restaurant_name} has been confirmed.",
            "preparing": f"Your order #{order_id} at {restaurant_name} is now being prepared.",
            "ready": f"Your order #{order_id} at {restaurant_name} is ready for pickup!",
            "completed": f"Your order #{order_id} at {restaurant_name} has been completed. Thank you!",
            "cancelled": f"Your order #{order_id} at {restaurant_name} has been cancelled. Please contact the restaurant for more details.",
        }
        return status_messages.get(
            new_status.lower(),
            f"Your order #{order_id} at {restaurant_name} status has been updated to: {new_status}",
        )

    def _build_reservation_status_message(
        self,
        reservation_id: int,
        new_status: str,
        restaurant_name: str,
        confirmation_number: Optional[str] = None,
    ) -> str:
        ref = confirmation_number or f"#{reservation_id}"
        status_messages = {
            "pending": f"Your reservation {ref} at {restaurant_name} has been received and is awaiting confirmation.",
            "confirmed": f"Great news! Your reservation {ref} at {restaurant_name} has been confirmed. See you soon!",
            "cancelled": f"Your reservation {ref} at {restaurant_name} has been cancelled. Please contact the restaurant for more details.",
            "completed": f"Thank you for visiting {restaurant_name}! We hope you enjoyed your experience.",
            "no_show": f"We missed you at {restaurant_name} for your reservation {ref}. Please contact us to reschedule.",
        }
        return status_messages.get(
            new_status.lower(),
            f"Your reservation {ref} at {restaurant_name} status has been updated to: {new_status}",
        )

    async def send_order_notification(
        self,
        restaurant_id: int,
        order_id: int,
        new_status: str,
        recipient_phone: str,
        restaurant_name: str,
        restaurant_twilio_number: str,
    ) -> Optional[int]:
        if not recipient_phone:
            logger.debug("No recipient phone for order %d notification", order_id)
            return None

        if not restaurant_twilio_number:
            logger.warning("No Twilio number configured for restaurant %d", restaurant_id)
            return None

        message_content = self._build_order_status_message(
            order_id=order_id,
            new_status=new_status,
            restaurant_name=restaurant_name,
        )

        log_id = self.notification_repo.create_log(
            restaurant_id=restaurant_id,
            entity_type="order",
            entity_id=order_id,
            recipient_phone=recipient_phone,
            message_content=message_content,
            status="pending",
        )

        await self._send_notification(log_id, recipient_phone, message_content, restaurant_twilio_number)
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
    ) -> Optional[int]:
        if not recipient_phone:
            logger.debug("No recipient phone for reservation %d notification", reservation_id)
            return None

        if not restaurant_twilio_number:
            logger.warning("No Twilio number configured for restaurant %d", restaurant_id)
            return None

        message_content = self._build_reservation_status_message(
            reservation_id=reservation_id,
            new_status=new_status,
            restaurant_name=restaurant_name,
            confirmation_number=confirmation_number,
        )

        log_id = self.notification_repo.create_log(
            restaurant_id=restaurant_id,
            entity_type="reservation",
            entity_id=reservation_id,
            recipient_phone=recipient_phone,
            message_content=message_content,
            status="pending",
        )

        await self._send_notification(log_id, recipient_phone, message_content, restaurant_twilio_number)
        return log_id

    async def _send_notification(
        self,
        log_id: int,
        recipient_phone: str,
        message_content: str,
        from_number: str,
    ) -> bool:
        logger.info(
            "Sending SMS notification log_id=%d to=%s from=%s message_length=%d",
            log_id,
            recipient_phone,
            from_number,
            len(message_content),
        )
        try:
            result = await asyncio.to_thread(
                self.twilio_client.send_sms,
                to=recipient_phone,
                body=message_content,
                from_number=from_number,
            )

            if result.success:
                logger.info(
                    "SMS sent successfully log_id=%d message_sid=%s to=%s",
                    log_id,
                    result.message_sid,
                    recipient_phone,
                )
                try:
                    self.notification_repo.update_status(
                        log_id=log_id,
                        status="sent",
                        twilio_message_sid=result.message_sid,
                    )
                except Exception as db_e:
                    logger.error(
                        "Failed to update notification status after successful send log_id=%d: %s",
                        log_id,
                        db_e,
                    )
                return True
            else:
                logger.error(
                    "SMS send failed log_id=%d to=%s error=%s",
                    log_id,
                    recipient_phone,
                    result.error_message,
                )
                try:
                    self.notification_repo.update_status(
                        log_id=log_id,
                        status="failed",
                        error_message=result.error_message,
                    )
                except Exception as db_e:
                    logger.error(
                        "Failed to update notification status after failed send log_id=%d: %s",
                        log_id,
                        db_e,
                    )
                try:
                    self.notification_repo.increment_retry_count(log_id)
                except Exception as db_e:
                    logger.error(
                        "Failed to increment retry count after failed send log_id=%d: %s",
                        log_id,
                        db_e,
                    )
                return False

        except Exception as e:
            logger.exception("Error sending notification log_id=%d to=%s: %s", log_id, recipient_phone, e)
            try:
                self.notification_repo.update_status(
                    log_id=log_id,
                    status="failed",
                    error_message=str(e),
                )
            except Exception as db_e:
                logger.error(
                    "Failed to update notification status after send error log_id=%d: %s",
                    log_id,
                    db_e,
                )
            try:
                self.notification_repo.increment_retry_count(log_id)
            except Exception as db_e:
                logger.error(
                    "Failed to increment retry count after send error log_id=%d: %s",
                    log_id,
                    db_e,
                )
            return False


async def send_order_status_notification_async(
    restaurant_id: int,
    order_id: int,
    new_status: str,
    recipient_phone: str,
    restaurant_name: str,
    restaurant_twilio_number: str,
) -> None:
    try:
        service = NotificationService()
        await service.send_order_notification(
            restaurant_id=restaurant_id,
            order_id=order_id,
            new_status=new_status,
            recipient_phone=recipient_phone,
            restaurant_name=restaurant_name,
            restaurant_twilio_number=restaurant_twilio_number,
        )
    except Exception as e:
        logger.error(
            "Failed to send order notification order_id=%d status=%s: %s",
            order_id,
            new_status,
            e,
        )


async def send_reservation_status_notification_async(
    restaurant_id: int,
    reservation_id: int,
    new_status: str,
    recipient_phone: str,
    restaurant_name: str,
    restaurant_twilio_number: str,
    confirmation_number: Optional[str] = None,
) -> None:
    try:
        service = NotificationService()
        await service.send_reservation_notification(
            restaurant_id=restaurant_id,
            reservation_id=reservation_id,
            new_status=new_status,
            recipient_phone=recipient_phone,
            restaurant_name=restaurant_name,
            restaurant_twilio_number=restaurant_twilio_number,
            confirmation_number=confirmation_number,
        )
    except Exception as e:
        logger.error(
            "Failed to send reservation notification reservation_id=%d status=%s: %s",
            reservation_id,
            new_status,
            e,
        )
