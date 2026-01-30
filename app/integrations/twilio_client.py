from dataclasses import dataclass
from typing import Optional

from twilio.base.exceptions import TwilioRestException
from twilio.rest import Client

from app.config import settings
from app.utils.logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class MessageResult:
    success: bool
    message_sid: Optional[str] = None
    error_message: Optional[str] = None


class TwilioClient:

    def __init__(self):
        self._client: Optional[Client] = None

    @property
    def client(self) -> Optional[Client]:
        if self._client is None:
            if settings.TWILIO_ACCOUNT_SID and settings.TWILIO_AUTH_TOKEN:
                self._client = Client(
                    settings.TWILIO_ACCOUNT_SID,
                    settings.TWILIO_AUTH_TOKEN,
                )
            else:
                logger.warning("Twilio credentials not configured")
        return self._client

    def send_sms(
        self,
        to: str,
        body: str,
        from_number: str,
    ) -> MessageResult:
        if not self.client:
            return MessageResult(
                success=False,
                error_message="Twilio client not configured",
            )

        if not from_number:
            return MessageResult(
                success=False,
                error_message="No sender number provided",
            )

        try:
            message = self.client.messages.create(
                body=body,
                from_=from_number,
                to=to,
            )
            logger.info("SMS sent successfully sid=%s to=%s from=%s", message.sid, to, from_number)
            return MessageResult(
                success=True,
                message_sid=message.sid,
            )
        except TwilioRestException as e:
            logger.error("Twilio SMS error: %s", e.msg)
            return MessageResult(
                success=False,
                error_message=str(e.msg),
            )
        except Exception as e:
            logger.exception("Unexpected error sending SMS: %s", e)
            return MessageResult(
                success=False,
                error_message=str(e),
            )
