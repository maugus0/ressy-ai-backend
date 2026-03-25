# Plivo client utilities
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


class PlivoClient:
    """Client for Plivo API integration (SMS)."""

    def __init__(self, auth_id: Optional[str] = None, auth_token: Optional[str] = None):
        self._auth_id = auth_id
        self._auth_token = auth_token
        self.client: Any = None
        self._init_client()

    def _init_client(self) -> None:
        try:
            from plivo import RestClient

            auth_id = self._auth_id
            auth_token = self._auth_token
            if not auth_id or not auth_token:
                import os

                auth_id = auth_id or os.getenv("PLIVO_AUTH_ID", "")
                auth_token = auth_token or os.getenv("PLIVO_AUTH_TOKEN", "")
            if auth_id and auth_token:
                self.client = RestClient(auth_id, auth_token)
            else:
                self.client = None
        except ImportError:
            logger.warning("Plivo SDK not installed - SMS functionality disabled")
            self.client = None

    def send_sms(
        self,
        to: str,
        body: str,
        from_number: str,
        auth_id: Optional[str] = None,
        auth_token: Optional[str] = None,
    ) -> MessageResult:
        """
        Send SMS. Uses auth_id/auth_token if both provided (e.g. restaurant's
        plivo_details); otherwise uses this client's credentials (e.g. .env).
        The 'From' number must belong to the Plivo account whose credentials are used.
        """
        client = self.client

        # Use restaurant-specific credentials if provided
        if auth_id and auth_token:
            try:
                from plivo import RestClient

                logger.debug(
                    "Using provided Plivo credentials (auth_id: %s...)",
                    auth_id[:10] if auth_id else "None",
                )
                client = RestClient(auth_id, auth_token)
            except ImportError:
                logger.error("Plivo SDK not installed - run: pip install plivo")
                return MessageResult(
                    success=False,
                    error_message="Plivo SDK not installed. Please install the plivo package.",
                )
            except Exception as e:
                logger.warning(
                    "Could not create Plivo client with provided credentials: %s",
                    e,
                )
                return MessageResult(
                    success=False,
                    error_message=f"Invalid Plivo credentials: {str(e)}",
                )
        else:
            if auth_id or auth_token:
                logger.warning(
                    "Incomplete Plivo credentials provided - need both auth_id and auth_token. "
                    "Falling back to default client. auth_id present: %s, auth_token present: %s",
                    bool(auth_id),
                    bool(auth_token),
                )
            else:
                logger.debug("No Plivo credentials provided, using default client from environment")

        if not client:
            if not auth_id and not auth_token:
                return MessageResult(
                    success=False,
                    error_message="Plivo not configured. Set PLIVO_AUTH_ID and PLIVO_AUTH_TOKEN in environment.",
                )
            return MessageResult(
                success=False,
                error_message="Plivo client initialization failed. Check credentials.",
            )

        is_valid, error_msg = _validate_phone_number(to)
        if not is_valid:
            logger.warning("Invalid phone number: %s", error_msg)
            return MessageResult(success=False, error_message=error_msg)

        # Truncate at word boundary if message too long
        # Plivo supports up to 1600 characters per SMS
        if len(body) > 1600:
            logger.warning("SMS message too long (%d chars), truncating to 1600", len(body))
            body = _truncate_at_word_boundary(body, 1597) + "..."

        try:
            response = client.messages.create(
                src=from_number,
                dst=to,
                text=body,
            )
            message_uuid = response.get("message_uuid", [None])[0] if isinstance(response.get("message_uuid"), list) else response.get("message_uuid")
            logger.info(
                "SMS sent successfully uuid=%s to=%s from=%s",
                message_uuid,
                mask_phone_number(to),
                from_number,
            )
            return MessageResult(success=True, message_sid=message_uuid)
        except Exception as e:
            err_msg = str(e)
            logger.exception("Unexpected error sending SMS to=%s: %s", mask_phone_number(to), err_msg)
            return MessageResult(success=False, error_message=err_msg)
