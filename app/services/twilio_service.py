"""
Twilio service wrapper.

Note: This class exists for backward compatibility. New code should use
TwilioClient directly or NotificationService for SMS notifications.
"""

from app.integrations.twilio_client import MessageResult, TwilioClient


class TwilioService:
    """Thin wrapper around TwilioClient for backward compatibility."""

    def __init__(self):
        self._client = TwilioClient()

    def send_sms(self, to: str, body: str, from_number: str) -> MessageResult:
        return self._client.send_sms(to=to, body=body, from_number=from_number)
