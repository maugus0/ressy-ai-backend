import ssl

import certifi
import websockets

from app.config import settings


class DeepgramClient:
    """Client for Deepgram API integration."""

    def __init__(self):
        self.api_key = settings.DEEPGRAM_API_KEY

    def connect(self):
        """Connect to Deepgram WebSocket."""
        if not self.api_key:
            raise ValueError("DEEPGRAM_API_KEY environment variable is not set")

        ssl_context = ssl.create_default_context(cafile=certifi.where())
        return websockets.connect(
            "wss://agent.deepgram.com/v1/agent/converse",
            subprotocols=["token", self.api_key],  # type: ignore
            ssl=ssl_context,
        )

    def get_config(self):
        """Get Deepgram configuration from environment variables."""
        return {
            "type": "Settings",
            "audio": {
                "input": {
                    "encoding": settings.DEEPGRAM_AUDIO_INPUT_ENCODING,
                    "sample_rate": settings.DEEPGRAM_AUDIO_INPUT_SAMPLE_RATE,
                },
                "output": {
                    "encoding": settings.DEEPGRAM_AUDIO_OUTPUT_ENCODING,
                    "sample_rate": settings.DEEPGRAM_AUDIO_OUTPUT_SAMPLE_RATE,
                    "container": settings.DEEPGRAM_AUDIO_OUTPUT_CONTAINER,
                },
            },
        }
