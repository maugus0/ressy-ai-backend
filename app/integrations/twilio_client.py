# Twilio client utilities
import re
from dataclasses import dataclass
from typing import Any, Optional

from app.utils.logging_config import get_logger
from app.utils.pii_masking import mask_phone_number

logger = get_logger(__name__)

E164_PATTERN = re.compile(r"^\+[1-9]\d{1,14}$")


def _validate_phone_number(phone: str) -> tuple[bool, str]:
    """Validate phone number format.

    Returns (is_valid, error_message).
    """
    if not phone:
        return False, "Phone number is empty"

    phone = phone.strip()

    if E164_PATTERN.match(phone):
        return True, ""

    digits_only = re.sub(r"[^\d]", "", phone)
    if len(digits_only) >= 10 and len(digits_only) <= 15:
        return True, ""

    return False, f"Invalid phone number format: {phone}"


@dataclass
class MessageResult:
    """Result of an SMS send attempt."""

    success: bool
    message_sid: Optional[str] = None
    error_message: Optional[str] = None


class TwilioClient:
    """Client for Twilio API integration (SMS)."""

    def __init__(self, account_sid: Optional[str] = None, auth_token: Optional[str] = None):
        self._account_sid = account_sid
        self._auth_token = auth_token
        self.client: Any = None
        self._init_client()

    def _init_client(self) -> None:
        try:
            from twilio.rest import Client

            sid = self._account_sid
            token = self._auth_token
            if not sid or not token:
                import os

                sid = sid or os.getenv("TWILIO_ACCOUNT_SID", "")
                token = token or os.getenv("TWILIO_AUTH_TOKEN", "")
            if sid and token:
                self.client = Client(sid, token)
            else:
                self.client = None
        except ImportError:
            self.client = None

    def send_sms(
        self,
        to: str,
        body: str,
        from_number: str,
        account_sid: Optional[str] = None,
        auth_token: Optional[str] = None,
    ) -> MessageResult:
        """
        Send SMS. Uses account_sid/auth_token if both provided (e.g. restaurant's
        twilio_details); otherwise uses this client's credentials (e.g. .env).
        The 'From' number must belong to the Twilio account whose credentials are used.
        """
        client = self.client
        if account_sid and auth_token:
            try:
                from twilio.rest import Client

                client = Client(account_sid, auth_token)
            except ImportError:
                client = None
            except Exception as e:
                logger.warning("Could not create Twilio client from provided credentials: %s", e)
                client = None

        if not client:
            logger.warning("Twilio client not initialized, skipping SMS")
            return MessageResult(success=False, error_message="Twilio not configured")

        is_valid, error_msg = _validate_phone_number(to)
        if not is_valid:
            logger.warning("Invalid phone number: %s", error_msg)
            return MessageResult(success=False, error_message=error_msg)

        if len(body) > 1600:
            logger.warning("SMS message too long (%d chars), truncating to 1600", len(body))
            body = body[:1597] + "..."

        try:
            message = client.messages.create(
                body=body,
                from_=from_number,
                to=to,
            )
            logger.info(
                "SMS sent successfully sid=%s to=%s from=%s",
                message.sid,
                mask_phone_number(to),
                from_number,
            )
            return MessageResult(success=True, message_sid=message.sid)
        except Exception as e:
            err_msg = str(e)
            logger.exception("SMS send failed to=%s: %s", mask_phone_number(to), err_msg)
            return MessageResult(success=False, error_message=err_msg)
