import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    AWS_REGION = os.getenv('AWS_REGION', 'us-east-1')
    JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY', 'your-super-secret-jwt-key-change-in-production')
    JWT_ALGORITHM = 'HS256'
    JWT_EXPIRE_HOURS = 24
    DEEPGRAM_API_KEY = os.getenv('DEEPGRAM_API_KEY')
    
    # Database Tables
    USERS_TABLE = 'voice_agent_users'
    CALLS_TABLE = 'voice_agent_calls'
    TRANSCRIPTS_TABLE = 'voice_agent_transcripts'

settings = Settings()