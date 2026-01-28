import os

from dotenv import load_dotenv

load_dotenv()


class Settings:
    AWS_REGION = os.getenv("AWS_REGION", "ca-central-1")
    # Deprecated (legacy HS256). Retained for backward compatibility with any remaining consumers.
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "your-super-secret-jwt-key-change-in-production")
    JWT_ALGORITHM = "RS256"
    # Deprecated in favor of JWT_ACCESS_TOKEN_EXP_SECONDS.
    JWT_EXPIRE_HOURS = 24
    JWT_PRIVATE_KEY = os.getenv("JWT_PRIVATE_KEY", "").replace("\\n", "\n")
    JWT_PUBLIC_KEY = os.getenv("JWT_PUBLIC_KEY", "").replace("\\n", "\n")
    JWT_ACCESS_TOKEN_EXP_SECONDS = int(os.getenv("JWT_ACCESS_TOKEN_EXP_SECONDS", 3600))
    JWT_REFRESH_TOKEN_EXP_SECONDS = int(os.getenv("JWT_REFRESH_TOKEN_EXP_SECONDS", 30 * 24 * 3600))
    JWT_ISSUER = os.getenv("JWT_ISSUER", "ressy.ai/auth")
    JWT_ADMIN_AUDIENCE = os.getenv("JWT_ADMIN_AUDIENCE", "ressy-admin-api")
    JWT_CLIENT_AUDIENCE = os.getenv("JWT_CLIENT_AUDIENCE", "ressy-client-api")
    JWT_AUTH_AUDIENCE = os.getenv("JWT_AUTH_AUDIENCE", "ressy-auth")
    USE_MOCK_DATA = os.getenv("USE_MOCK_DATA", "true").lower() in {"1", "true", "yes", "on"}
    DEEPGRAM_API_KEY = os.getenv("DEEPGRAM_API_KEY")

    # Deepgram Audio Configuration
    DEEPGRAM_AUDIO_INPUT_ENCODING = os.getenv("DEEPGRAM_AUDIO_INPUT_ENCODING", "mulaw")
    DEEPGRAM_AUDIO_INPUT_SAMPLE_RATE = int(os.getenv("DEEPGRAM_AUDIO_INPUT_SAMPLE_RATE", "8000"))
    DEEPGRAM_AUDIO_OUTPUT_ENCODING = os.getenv("DEEPGRAM_AUDIO_OUTPUT_ENCODING", "mulaw")
    DEEPGRAM_AUDIO_OUTPUT_SAMPLE_RATE = int(os.getenv("DEEPGRAM_AUDIO_OUTPUT_SAMPLE_RATE", "8000"))
    DEEPGRAM_AUDIO_OUTPUT_CONTAINER = os.getenv("DEEPGRAM_AUDIO_OUTPUT_CONTAINER", "none")

    # Deepgram Agent Configuration
    DEEPGRAM_HISTORY = os.getenv("DEEPGRAM_HISTORY", "false").lower() in {"1", "true", "yes", "on"}
    DEEPGRAM_AGENT_LANGUAGE = os.getenv("DEEPGRAM_AGENT_LANGUAGE", "en")
    DEEPGRAM_LISTEN_MODEL = os.getenv("DEEPGRAM_LISTEN_MODEL", "nova-3")
    DEEPGRAM_ENDPOINTING_MS = int(os.getenv("DEEPGRAM_ENDPOINTING_MS", 700))
    DEEPGRAM_INTERIM_RESULTS = os.getenv("DEEPGRAM_INTERIM_RESULTS", "true").lower() in {"1", "true", "yes", "on"}
    DEEPGRAM_UTTERANCE_END_MS = int(os.getenv("DEEPGRAM_UTTERANCE_END_MS", "1400"))
    DEEPGRAM_LISTEN_KEYTERMS = os.getenv("DEEPGRAM_LISTEN_KEYTERMS", "hello,goodbye").split(",")
    DEEPGRAM_THINK_PROVIDER_TYPE = os.getenv("DEEPGRAM_THINK_PROVIDER_TYPE", "open_ai")
    DEEPGRAM_THINK_MODEL = os.getenv("DEEPGRAM_THINK_MODEL", "gpt-4o-mini")
    DEEPGRAM_THINK_TEMPERATURE = float(os.getenv("DEEPGRAM_THINK_TEMPERATURE", "0.15"))
    DEEPGRAM_SPEAK_MODEL = os.getenv("DEEPGRAM_SPEAK_MODEL", "aura-2-harmonia-en")
    DEEPGRAM_AGENT_GREETING = os.getenv(
        "DEEPGRAM_AGENT_GREETING", "Hi, this is Ressy! Thanks for calling {RESTAURANT_NAME}. How can I help you today?"
    )
    RESTAURANT_TIMEZONE = os.getenv("RESTAURANT_TIMEZONE", "America/Vancouver")

    # Message played when an incoming call is for a Twilio number not registered to any restaurant
    UNREGISTERED_TWILIO_MESSAGE = os.getenv(
        "UNREGISTERED_TWILIO_MESSAGE",
        "We are unable to connect to the restaurant at the moment, "
        "requesting you to use any alternate number or try again later.",
    )

    # Maximum time window (in seconds) for allowing updates to orders/reservations via voice agent
    # Orders/reservations created more than this many seconds ago cannot be updated
    AGENT_UPDATE_WINDOW_SECONDS = int(os.getenv("AGENT_UPDATE_WINDOW_SECONDS", "300"))  # 5 minutes

    # Barge-in behavior
    # Minimum gap in seconds after last agent audio chunk before clearing Twilio buffer when user starts speaking
    BARGE_IN_CLEAR_SECONDS = float(os.getenv("BARGE_IN_CLEAR_SECONDS", "0.15"))

    # Telemetry / diagnostics
    # Enable verbose latency logging for call manager pipelines
    LATENCY_LOGS_ENABLED = os.getenv("LATENCY_LOGS_ENABLED", "false").lower() in {"1", "true", "yes", "on"}

    # Cost settings (USD)
    #
    # Defaults are intentionally set to the *highest* per-second costs discussed:
    # - Twilio Voice (Mobile/PSTN, US): ~$0.018 / minute -> 0.0003 / second
    # - Deepgram (Pay-as-you-go "basic services"): ~$0.08 / minute -> 0.0013333333 / second
    #
    # Multipliers allow applying markups/adjustments without code changes.
    TWILIO_COST_PER_SECOND = float(os.getenv("TWILIO_COST_PER_SECOND", "0.0003"))
    DEEPGRAM_COST_PER_SECOND = float(os.getenv("DEEPGRAM_COST_PER_SECOND", "0.0013333333"))
    TWILIO_MULTIPLIER = float(os.getenv("TWILIO_MULTIPLIER", "1.0"))
    DEEPGRAM_MULTIPLIER = float(os.getenv("DEEPGRAM_MULTIPLIER", "1.0"))
    RESSY_MULTIPLIER = float(os.getenv("RESSY_MULTIPLIER", "1.0"))

    # Twilio audio pipeline tuning
    TWILIO_INBOUND_BUFFER_SIZE = int(os.getenv("TWILIO_INBOUND_BUFFER_SIZE", str(3 * 160)))  # bytes
    TWILIO_INBOUND_FLUSH_INTERVAL = float(os.getenv("TWILIO_INBOUND_FLUSH_INTERVAL", "0.15"))  # seconds
    TWILIO_OUTBOUND_CHUNK_SIZE = int(os.getenv("TWILIO_OUTBOUND_CHUNK_SIZE", "160"))  # bytes
    TWILIO_OUTBOUND_QUEUE_MAXSIZE = int(os.getenv("TWILIO_OUTBOUND_QUEUE_MAXSIZE", "1000"))
    TWILIO_OUTBOUND_PACING_SECONDS = float(os.getenv("TWILIO_OUTBOUND_PACING_SECONDS", "0.04"))  # seconds per chunk

    # Call limits
    # Maximum duration (seconds) a live call should run before gracefully timing out
    AGENT_CALL_TIMEOUT_SECONDS = int(os.getenv("AGENT_CALL_TIMEOUT_SECONDS", "900"))  # 15 minutes
    AGENT_CALL_TIMEOUT_MESSAGE = os.getenv(
        "AGENT_CALL_TIMEOUT_MESSAGE",
        "I have to wrap up this call now. If you need anything else, please call back and I'll get you sorted.",
    )
    AGENT_IDLE_TIMEOUT_SECONDS = int(os.getenv("AGENT_IDLE_TIMEOUT_SECONDS", "60"))
    AGENT_IDLE_TIMEOUT_MESSAGE = os.getenv(
        "AGENT_IDLE_TIMEOUT_MESSAGE",
        "I'm still here, but I'll need to wrap up this call. If you need anything else, please call back.",
    )

    # Public base URL (reachable by Twilio) used for outbound-call testing webhooks.
    # Example: https://api.example.com
    PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "http://localhost:5001")
    OUTBOUND_CALL_STATUS_SECRET = os.getenv("OUTBOUND_CALL_STATUS_SECRET", "")

    # Database Connection Pool Configuration
    # These settings control the MySQL connection pool behavior
    DB_POOL_SIZE = int(os.getenv("DB_POOL_SIZE", 10))  # Max connections in pool
    DB_POOL_NAME = os.getenv("DB_POOL_NAME", "ressy_pool")  # Pool identifier
    DB_CONNECTION_TIMEOUT = int(os.getenv("DB_CONNECTION_TIMEOUT", 20))  # Connection timeout in seconds
    # Enable connection logging for debugging
    DB_POOL_LOG_CONNECTIONS = os.getenv("DB_POOL_LOG_CONNECTIONS", "false").lower() in (
        "true",
        "1",
        "yes",
    )

    # Twilio SMS Configuration
    TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID", "")
    TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "")
    NOTIFICATION_MAX_RETRIES = int(os.getenv("NOTIFICATION_MAX_RETRIES", "3"))

    # Database Tables
    RESTAURANTS_TABLE: str = "Restaurants"
    MENUS_TABLE: str = "Menus"
    SPECIALS_TABLE: str = "Specials"
    CALLS_TABLE: str = "Calls"
    ORDERS_TABLE: str = "Orders"
    ORDER_HISTORY_TABLE: str = "OrderHistory"
    RESERVATIONS_TABLE: str = "Reservations"
    TRANSCRIPTS_TABLE: str = "ConversationTranscripts"
    FAQS_TABLE: str = "FAQs"
    USERS_TABLE: str = "Users"
    OPENTABLE_API_LOGS_TABLE: str = "OpenTable_API_Logs"


settings = Settings()
