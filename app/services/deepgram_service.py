import ssl

import certifi
import websockets

from app.agent_fc.function_definitions import get_function_definitions
from app.config import settings
from app.utils import prompt_loader


class DeepgramService:
    def __init__(self, api_key: str | None = None):
        """
        Initialize DeepgramService with optional API key override.
        """
        self.api_key = self._normalize_api_key(api_key) or self._normalize_api_key(settings.DEEPGRAM_API_KEY)

    @staticmethod
    def _normalize_api_key(key: str | None) -> str | None:
        """Return a clean API key string or None if missing/blank."""
        if key is None:
            return None
        if not isinstance(key, str):
            key = str(key)
        key = key.strip()
        return key or None

    def sts_connect(self, api_key: str | None = None):
        """Create a Deepgram STS connection."""
        effective_api_key = self._normalize_api_key(api_key) or self.api_key
        if not effective_api_key:
            raise ValueError("DEEPGRAM_API_KEY not provided and environment variable is not set")

        ssl_context = ssl.create_default_context(cafile=certifi.where())

        return websockets.connect(
            "wss://agent.deepgram.com/v1/agent/converse",
            extra_headers={"Authorization": f"Token {effective_api_key}"},
            ssl=ssl_context,
        )

    def load_config(self, think_prompt: str | None, key_terms: list[str], restaurant_name: str | None):
        """Load Deepgram configuration from environment variables."""

        greeting_template = settings.DEEPGRAM_AGENT_GREETING or ""
        if restaurant_name:
            greeting = greeting_template.replace("{RESTAURANT_NAME}", restaurant_name)
        else:
            greeting = greeting_template
        listen_keyterms = key_terms if key_terms is not None else settings.DEEPGRAM_LISTEN_KEYTERMS
        return {
            "type": "Settings",
            "flags": {
                "history": settings.DEEPGRAM_HISTORY,
            },
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
                        "keyterms": listen_keyterms,
                        # TODO: Try endpointing and utterance-end to fix agent-freeze issue.
                        # "endpointing": settings.DEEPGRAM_ENDPOINTING_MS,
                        # "interim_results": settings.DEEPGRAM_INTERIM_RESULTS,
                        # "utterance_end_ms": settings.DEEPGRAM_UTTERANCE_END_MS,
                    }
                },
                "think": {
                    "provider": {
                        "type": settings.DEEPGRAM_THINK_PROVIDER_TYPE,
                        "model": settings.DEEPGRAM_THINK_MODEL,
                        "temperature": settings.DEEPGRAM_THINK_TEMPERATURE,
                    },
                    # Custom prompt loaded from file (if provided)
                    "prompt": think_prompt if think_prompt is not None else prompt_loader.load_think_prompt(),
                    # Client-side function definitions for the agent to call
                    "functions": get_function_definitions(),
                },
                "speak": {
                    "provider": {
                        "type": "deepgram",
                        "model": settings.DEEPGRAM_SPEAK_MODEL,
                    }
                },
                "greeting": greeting,
            },
        }
