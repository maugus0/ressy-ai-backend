"""
Voice Provider Service - Abstraction layer for Twilio and Plivo voice providers.
"""
from typing import Any, Dict, Optional
from xml.sax.saxutils import escape

from app.integrations.plivo_client import PlivoClient
from app.integrations.twilio_client import TwilioClient
from app.utils.logging_config import get_logger

logger = get_logger(__name__)


class VoiceProviderService:
    """Service to handle voice provider operations (Twilio or Plivo)."""

    def __init__(self, restaurant: Dict[str, Any]):
        """
        Initialize voice provider service based on restaurant configuration.

        Args:
            restaurant: Restaurant dictionary with voice_provider, twilio_details, plivo_details
        """
        self.restaurant = restaurant
        self.provider = restaurant.get("voice_provider", "twilio").lower()
        if self.provider not in ("twilio", "plivo"):
            logger.warning("Invalid voice_provider '%s', defaulting to 'twilio'", self.provider)
            self.provider = "twilio"

    def get_phone_number(self) -> Optional[str]:
        """Get the provider-specific phone number for this restaurant."""
        if self.provider == "plivo":
            return self.restaurant.get("plivo_phone_number")
        return self.restaurant.get("twilio_phone_number")

    def get_sms_client(self):
        """Get the appropriate SMS client (TwilioClient or PlivoClient)."""
        if self.provider == "plivo":
            plivo_details = self.restaurant.get("plivo_details") or {}
            if isinstance(plivo_details, str):
                import json

                try:
                    plivo_details = json.loads(plivo_details)
                except json.JSONDecodeError:
                    plivo_details = {}
            auth_id = plivo_details.get("auth_id") or plivo_details.get("authId")
            auth_token = plivo_details.get("auth_token") or plivo_details.get("authToken")
            return PlivoClient(auth_id=auth_id, auth_token=auth_token)
        else:
            twilio_details = self.restaurant.get("twilio_details") or {}
            if isinstance(twilio_details, str):
                import json

                try:
                    twilio_details = json.loads(twilio_details)
                except json.JSONDecodeError:
                    twilio_details = {}
            account_sid = twilio_details.get("account_sid") or twilio_details.get("accountSid")
            auth_token = twilio_details.get("auth_token") or twilio_details.get("authToken")
            return TwilioClient(account_sid=account_sid, auth_token=auth_token)

    def generate_webhook_xml(
        self,
        stream_url: str,
        from_number: Optional[str] = None,
        to_number: Optional[str] = None,
        redirect_url: Optional[str] = None,
        kill_switch_redirect: Optional[str] = None,
    ) -> str:
        """
        Generate webhook XML response for incoming calls.

        Args:
            stream_url: WebSocket URL for audio streaming
            from_number: Caller's phone number
            to_number: Restaurant's phone number
            redirect_url: URL to redirect after call ends
            kill_switch_redirect: Phone number to redirect to if kill switch is active

        Returns:
            XML string for TwiML or Plivo XML
        """
        if kill_switch_redirect:
            return self._generate_kill_switch_xml(kill_switch_redirect, to_number)

        if self.provider == "plivo":
            return self._generate_plivo_xml(stream_url, from_number, to_number, redirect_url)
        else:
            return self._generate_twilio_xml(stream_url, from_number, to_number, redirect_url)

    def _generate_twilio_xml(
        self,
        stream_url: str,
        from_number: Optional[str],
        to_number: Optional[str],
        redirect_url: Optional[str],
    ) -> str:
        """Generate TwiML XML for Twilio."""
        stream_url_escaped = escape(stream_url)
        from_number_xml = escape(from_number) if from_number else ""
        to_number_xml = escape(to_number) if to_number else ""
        redirect_url_escaped = escape(redirect_url) if redirect_url else ""

        xml = f"""<Response>
            <Say language="en">"This call may be monitored or recorded."</Say>
            <Connect>
                <Stream url="{stream_url_escaped}">
                    <Parameter name="fromNumber" value="{from_number_xml}"/>
                    <Parameter name="toNumber" value="{to_number_xml}"/>
                </Stream>
            </Connect>"""
        if redirect_url:
            xml += f'\n            <Redirect method="POST">{redirect_url_escaped}</Redirect>'
        xml += "\n        </Response>"
        return xml.strip()

    def _generate_plivo_xml(
        self,
        stream_url: str,
        from_number: Optional[str],
        to_number: Optional[str],
        redirect_url: Optional[str],
    ) -> str:
        """
        Generate Plivo XML for incoming calls.

        Note: Plivo uses a different WebSocket protocol than Twilio.
        This is a placeholder implementation that may need adjustment based on
        Plivo's actual WebSocket streaming API.
        """
        try:
            from plivo import plivoxml

            response = plivoxml.ResponseElement()
            # Add recording notice
            response.add(plivoxml.SpeakElement("This call may be monitored or recorded."))

            # Note: Plivo WebSocket streaming may require different XML structure
            # This is a basic implementation - may need to be adjusted based on Plivo's API
            # For now, we'll use a similar structure to Twilio
            # Plivo might use <Stream> or a different element for WebSocket connections

            # If Plivo doesn't support WebSocket streaming directly, we might need to:
            # 1. Use <Dial> with a SIP endpoint
            # 2. Use Plivo's media streaming API differently
            # 3. Implement a different approach for real-time audio

            # For now, return a basic response that connects to WebSocket
            # This will need to be verified and adjusted based on Plivo's documentation
            return response.to_string()
        except ImportError:
            logger.error("Plivo SDK not installed - cannot generate Plivo XML")
            # Fallback to basic XML
            return """<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Speak>This call may be monitored or recorded.</Speak>
</Response>"""

    def _generate_kill_switch_xml(self, escalation_phone: str, caller_id: Optional[str]) -> str:
        """Generate XML to forward call to escalation number."""
        if self.provider == "plivo":
            try:
                from plivo import plivoxml

                response = plivoxml.ResponseElement()
                dial = plivoxml.DialElement(caller_id=caller_id or "", timeout=25)
                dial.add(plivoxml.NumberElement(escalation_phone))
                response.add(dial)
                return response.to_string()
            except ImportError:
                logger.error("Plivo SDK not installed - cannot generate Plivo XML")
                # Fallback XML
                escalation_phone_escaped = escape(escalation_phone)
                caller_id_escaped = escape(caller_id) if caller_id else ""
                return f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Dial callerId="{caller_id_escaped}" timeout="25">
        <Number>{escalation_phone_escaped}</Number>
    </Dial>
</Response>"""
        else:
            # Twilio XML
            dial_number = escape(escalation_phone)
            caller_id_escaped = escape(caller_id) if caller_id else ""
            return f"""<Response>
                <Dial callerId="{caller_id_escaped}" timeout="25">
                    <Number>{dial_number}</Number>
                </Dial>
            </Response>"""

    def get_restaurant_by_phone(self, phone_number: str, restaurant_service) -> Optional[Dict[str, Any]]:
        """
        Get restaurant by phone number using the appropriate provider field.

        Args:
            phone_number: Phone number to search for
            restaurant_service: RestaurantService instance

        Returns:
            Restaurant dictionary or None
        """
        if self.provider == "plivo":
            # For Plivo, we need to search by plivo_phone_number
            # This might require updating RestaurantService
            return restaurant_service.get_restaurant_by_plivo(phone_number)
        else:
            return restaurant_service.get_restaurant_by_twilio(phone_number)
