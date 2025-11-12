import websockets
import ssl
import certifi
from app.config import settings

class DeepGramService:
    def __init__(self):
        self.api_key = settings.DEEPGRAM_API_KEY
    
    def sts_connect(self):
        """Create a DeepGram STS connection."""
        if not self.api_key:
            raise ValueError("DEEPGRAM_API_KEY environment variable is not set")

        ssl_context = ssl.create_default_context(cafile=certifi.where())

        return websockets.connect(
            "wss://agent.deepgram.com/v1/agent/converse",
            extra_headers={"Authorization": f"Token {self.api_key}"},
            ssl=ssl_context
        )
    
    def load_config(self):
        """Load Deepgram configuration from environment variables."""
        return {
            "type": "Settings",
            "audio": {
                "input": {
                    "encoding": settings.DEEPGRAM_AUDIO_INPUT_ENCODING or "linear16",
                    "sample_rate": settings.DEEPGRAM_AUDIO_INPUT_SAMPLE_RATE or 16000,
                },
                "output": {
                    "encoding": settings.DEEPGRAM_AUDIO_OUTPUT_ENCODING or "linear16",
                    "sample_rate": settings.DEEPGRAM_AUDIO_OUTPUT_SAMPLE_RATE or 16000,
                    "container": settings.DEEPGRAM_AUDIO_OUTPUT_CONTAINER or "none",
                },
            },
            "agent": {
                "language": settings.DEEPGRAM_AGENT_LANGUAGE,
                "listen": {
                    "provider": {
                        "type": "deepgram",
                        "model": settings.DEEPGRAM_LISTEN_MODEL,
                        "keyterms": settings.DEEPGRAM_LISTEN_KEYTERMS,
                    }
                },
                "think": {
                    "provider": {
                        "type": settings.DEEPGRAM_THINK_PROVIDER_TYPE,
                        "model": settings.DEEPGRAM_THINK_MODEL,
                        "temperature": settings.DEEPGRAM_THINK_TEMPERATURE,
                    },
                    "prompt": settings.DEEPGRAM_THINK_PROMPT,
                },
                "speak": {
                    "provider": {
                        "type": "deepgram",
                        "model": settings.DEEPGRAM_SPEAK_MODEL,
                    }
                },
                "greeting": settings.DEEPGRAM_AGENT_GREETING,
            },
        }