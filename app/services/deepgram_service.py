import websockets
import ssl
import certifi
import os
from app.config.settings import settings

class DeepGramService:
    def __init__(self):
        self.api_key = settings.DEEPGRAM_API_KEY
    
    def connect(self):
        if not self.api_key:
            raise ValueError("DEEPGRAM_API_KEY environment variable is not set")
        
        ssl_context = ssl.create_default_context(cafile=certifi.where())
        return websockets.connect(
            "wss://agent.deepgram.com/v1/agent/converse",
            subprotocols=["token", self.api_key], #type: ignore
            ssl=ssl_context
        )
    
    def get_config(self):
        return {
            "type": "SettingsConfiguration",
            "audio": {
                "input": {
                    "encoding": "mulaw",
                    "sample_rate": 8000
                },
                "output": {
                    "encoding": "mulaw", 
                    "sample_rate": 8000,
                    "container": "none"
                }
            }
        }