import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    AWS_REGION = os.getenv('AWS_REGION', 'ca-central-1')
    JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY', 'your-super-secret-jwt-key-change-in-production')
    JWT_ALGORITHM = 'HS256'
    JWT_EXPIRE_HOURS = 24
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
    DEEPGRAM_THINK_TEMPERATURE = float(os.getenv('DEEPGRAM_THINK_TEMPERATURE', '0.7'))
    DEEPGRAM_THINK_PROMPT = os.getenv('DEEPGRAM_THINK_PROMPT', 'You are a professional pharmacy assistant named Mahima. You can: 1) Get drug info with get_drug_info, 2) Place orders with place_order, 3) Look up orders with lookup_order. IMPORTANT: Always ask users to spell out their full name clearly when placing orders. Confirm all order details before processing - including customer name, drug name, and quantity. Be thorough and professional in collecting information. If a user provides a name that\'s unclear, ask them to spell it out letter by letter. Always confirm the complete order details before finalizing any transaction.')
    DEEPGRAM_SPEAK_MODEL = os.getenv('DEEPGRAM_SPEAK_MODEL', 'aura-2-thalia-en')
    DEEPGRAM_AGENT_GREETING = os.getenv('DEEPGRAM_AGENT_GREETING', 'Hello! I\'m your pharmacy assistant Mahima. I can help you with drug information, placing orders, and checking order status. When placing orders, I\'ll need your full name spelled out clearly and will confirm all details with you. How can I assist you today?')
    
    # Database Tables
    RESTAURANTS_TABLE: str = "Restaurants" 
    MENUS_TABLE: str = "Menus"
    SPECIALS_TABLE: str = "Spceials"
    CALLS_TABLE: str = "Calls"
    ORDERS_TABLE: str = "Orders"
    ORDER_HISTORY_TABLE: str = "OrderHistory"
    TRANSCRIPTS_TABLE: str = "ConversationTranscripts"
    FAQS_TABLE: str = "FAQs"
    USERS_TABLE: str = "Users"

settings = Settings()

