import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    AWS_REGION = os.getenv('AWS_REGION', 'ca-central-1')
    JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY', 'your-super-secret-jwt-key-change-in-production')
    JWT_ALGORITHM = 'HS256'
    JWT_EXPIRE_HOURS = 24
    DEEPGRAM_API_KEY = os.getenv('DEEPGRAM_API_KEY')
    
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