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


def _truncate_at_word_boundary(text: str, max_length: int) -> str:
    """Truncate text at word boundary to avoid cutting words mid-way."""
    if len(text) <= max_length:
        return text
    truncated = text[:max_length]
    # Find last space to avoid cutting mid-word
    last_space = truncated.rfind(" ")
    if last_space > max_length * 0.8:  # Only use word boundary if not too far back
        return truncated[:last_space]
    return truncated


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
            logger.warning("Twilio SDK not installed - SMS functionality disabled")
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

        # Use restaurant-specific credentials if provided
        if account_sid and auth_token:
            try:
                from twilio.rest import Client

                logger.debug(
                    "Using provided Twilio credentials (account_sid: %s...)",
                    account_sid[:10] if account_sid else "None",
                )
                client = Client(account_sid, auth_token)
            except ImportError:
                logger.error("Twilio SDK not installed - run: pip install twilio")
                return MessageResult(
                    success=False,
                    error_message="Twilio SDK not installed. Please install the twilio package.",
                )
            except Exception as e:
                logger.warning(
                    "Could not create Twilio client with provided credentials: %s",
                    e,
                )
                return MessageResult(
                    success=False,
                    error_message=f"Invalid Twilio credentials: {str(e)}",
                )
        else:
            if account_sid or auth_token:
                logger.warning(
                    "Incomplete Twilio credentials provided - need both account_sid and auth_token. "
                    "Falling back to default client. account_sid present: %s, auth_token present: %s",
                    bool(account_sid),
                    bool(auth_token),
                )
            else:
                logger.debug("No Twilio credentials provided, using default client from environment")

        if not client:
            if not account_sid and not auth_token:
                return MessageResult(
                    success=False,
                    error_message="Twilio not configured. Set TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN in environment.",
                )
            return MessageResult(
                success=False,
                error_message="Twilio client initialization failed. Check credentials.",
            )

        is_valid, error_msg = _validate_phone_number(to)
        if not is_valid:
            logger.warning("Invalid phone number: %s", error_msg)
            return MessageResult(success=False, error_message=error_msg)

        # Truncate at word boundary if message too long
        if len(body) > 1600:
            logger.warning("SMS message too long (%d chars), truncating to 1600", len(body))
            body = _truncate_at_word_boundary(body, 1597) + "..."

        try:
            from twilio.base.exceptions import TwilioRestException

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
        except TwilioRestException as e:
            logger.error(
                "Twilio API error: code=%s msg=%s to=%s",
                e.code,
                e.msg,
                mask_phone_number(to),
            )
            return MessageResult(
                success=False,
                error_message=f"Twilio error ({e.code}): {e.msg}",
            )
        except Exception as e:
            err_msg = str(e)
            logger.exception("Unexpected error sending SMS to=%s: %s", mask_phone_number(to), err_msg)
            return MessageResult(success=False, error_message=err_msg)
