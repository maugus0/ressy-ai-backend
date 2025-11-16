import websockets
import ssl
import certifi
import json
from app.config import settings
from typing import List, Dict, Any

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
    
    def build_menu_context(self, menu_items: List[Dict[str, Any]]) -> str:
        """Build menu context string for prompt."""
        if not menu_items:
            return "No menu items available."
        
        context = "Available Menu Items:\n"
        current_category = None
        current_subcategory = None
        
        for item in menu_items:
            category = item.get("category", "Other")
            subcategory = item.get("sub_category", "")
            item_name = item.get("item_name", "")
            price = item.get("price", 0)
            description = item.get("item_desc", "")
            prep_time = item.get("avg_prep_time")
            is_special = item.get("is_special", False)
            
            # Add category header if changed
            if category != current_category:
                context += f"\n{category}:\n"
                current_category = category
                current_subcategory = None
            
            # Add subcategory if exists and changed
            if subcategory and subcategory != current_subcategory:
                context += f"  {subcategory}:\n"
                current_subcategory = subcategory
            
            # Add item
            special_marker = " [SPECIAL]" if is_special else ""
            context += f"  - {item_name}{special_marker}: ${price:.2f}"
            if description:
                context += f" - {description}"
            if prep_time:
                context += f" (Prep time: {prep_time} min)"
            context += "\n"
        
        return context
    
    def build_faq_context(self, faqs: List[Dict[str, Any]]) -> str:
        """Build FAQ context string for prompt."""
        if not faqs:
            return ""
        
        context = "\n\nFrequently Asked Questions:\n"
        for faq in faqs:
            question = faq.get("question", "")
            answer = faq.get("answer", "")
            context += f"Q: {question}\nA: {answer}\n\n"
        
        return context
    
    def build_dynamic_prompt(
        self,
        restaurant_name: str,
        menu_items: List[Dict[str, Any]],
        faqs: List[Dict[str, Any]]
    ) -> str:
        """Build dynamic prompt with restaurant context."""
        base_prompt = f"""You are a professional restaurant assistant for {restaurant_name}. Your role is to:

1. **Collect User Information**: 
   - Get the customer's full name (ask them to spell it if unclear)
   - Get their phone number
   - Get their email address (if they provide it)
   - Get their delivery/pickup address (if applicable)

2. **Help with Menu and Orders**:
   - Answer questions about menu items using the available menu below
   - Help customers place orders
   - Confirm all order details before finalizing (customer name, items, quantities, total amount)
   - Be thorough and professional in collecting information

3. **Answer FAQs**: Use the FAQ section below to answer common questions accurately.

4. **Important Guidelines**:
   - Always ask users to spell out their full name clearly when placing orders
   - Confirm the complete order details before finalizing any transaction
   - If a user provides a name that's unclear, ask them to spell it out letter by letter
   - Be friendly, professional, and helpful
   - If you don't know something, say so politely

{self.build_menu_context(menu_items)}
{self.build_faq_context(faqs)}

Remember: Always confirm customer name, items ordered, quantities, and total amount before completing any order."""

        return base_prompt
    
    def load_config(
        self,
        restaurant_name: str = None,
        menu_items: List[Dict[str, Any]] = None,
        faqs: List[Dict[str, Any]] = None
    ):
        """Load Deepgram configuration with dynamic prompt based on restaurant context."""
        # Build dynamic prompt if restaurant context is provided
        if restaurant_name and menu_items is not None:
            prompt = self.build_dynamic_prompt(restaurant_name, menu_items or [], faqs or [])
        else:
            # Fallback to default prompt
            prompt = settings.DEEPGRAM_THINK_PROMPT
        
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
                    "prompt": prompt,
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