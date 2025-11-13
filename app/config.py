import os

from dotenv import load_dotenv

load_dotenv()


class Settings:
    AWS_REGION = os.getenv('AWS_REGION', 'ca-central-1')
    JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY', 'your-super-secret-jwt-key-change-in-production')
    JWT_ALGORITHM = 'HS256'
    JWT_EXPIRE_HOURS = 24
    USE_MOCK_DATA = os.getenv('USE_MOCK_DATA', 'true').lower() in {'1', 'true', 'yes', 'on'}
    DEEPGRAM_API_KEY = os.getenv('DEEPGRAM_API_KEY')

    # Deepgram Audio Configuration
    DEEPGRAM_AUDIO_INPUT_ENCODING = os.getenv('DEEPGRAM_AUDIO_INPUT_ENCODING', 'mulaw')
    DEEPGRAM_AUDIO_INPUT_SAMPLE_RATE = int(os.getenv('DEEPGRAM_AUDIO_INPUT_SAMPLE_RATE', '8000'))
    DEEPGRAM_AUDIO_OUTPUT_ENCODING = os.getenv('DEEPGRAM_AUDIO_OUTPUT_ENCODING', 'mulaw')
    DEEPGRAM_AUDIO_OUTPUT_SAMPLE_RATE = int(os.getenv('DEEPGRAM_AUDIO_OUTPUT_SAMPLE_RATE', '8000'))
    DEEPGRAM_AUDIO_OUTPUT_CONTAINER = os.getenv('DEEPGRAM_AUDIO_OUTPUT_CONTAINER', 'none')

    # Deepgram Agent Configuration
    DEEPGRAM_AGENT_LANGUAGE = os.getenv('DEEPGRAM_AGENT_LANGUAGE', 'en')
    DEEPGRAM_LISTEN_MODEL = os.getenv('DEEPGRAM_LISTEN_MODEL', 'nova-3')
    DEEPGRAM_LISTEN_KEYTERMS = os.getenv('DEEPGRAM_LISTEN_KEYTERMS', 'hello,goodbye').split(',')
    DEEPGRAM_THINK_PROVIDER_TYPE = os.getenv('DEEPGRAM_THINK_PROVIDER_TYPE', 'open_ai')
    DEEPGRAM_THINK_MODEL = os.getenv('DEEPGRAM_THINK_MODEL', 'gpt-4o-mini')
    DEEPGRAM_THINK_TEMPERATURE = float(os.getenv('DEEPGRAM_THINK_TEMPERATURE', '0.25'))
    DEEPGRAM_SPEAK_MODEL = os.getenv('DEEPGRAM_SPEAK_MODEL', 'aura-2-amalthea-en')
    DEEPGRAM_AGENT_GREETING = os.getenv('DEEPGRAM_AGENT_GREETING', 'Hi! Thank you for calling {RESTAURANT_NAME}. How may I help you today?')

    # Barge-in behavior
    # Minimum gap in seconds after last agent audio chunk before clearing Twilio buffer when user starts speaking
    BARGE_IN_CLEAR_SECONDS = float(os.getenv('BARGE_IN_CLEAR_SECONDS', '0.5'))

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


settings = Settings()
