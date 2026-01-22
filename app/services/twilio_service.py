from app.integrations.twilio_client import MessageResult, TwilioClient


class TwilioService:

    def __init__(self):
        self._client = TwilioClient()

    def send_sms(
        self,
        to: str,
        body: str,
        from_number: str,
    ) -> MessageResult:
        return self._client.send_sms(to=to, body=body, from_number=from_number)
