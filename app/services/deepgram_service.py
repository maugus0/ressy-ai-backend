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
        base_prompt = f"""You are a professional restaurant assistant for {restaurant_name}. Welcome customers warmly and represent {restaurant_name} with pride. You are only taking orders for pickup.

Your primary responsibilities:

1. **Greet and Collect Customer Information**: 
   - Greet customers warmly: "Welcome to {restaurant_name}! How can I help you today?"
   - Get the customer's full name (ask them to spell it if unclear)
   - Get their phone number

2. **Help with Menu and Take Orders**:
   - Answer questions about menu items using the available menu below
   - When a customer wants to place an order:
     a) Listen carefully to what they want and always check if the item is available in {menu_items}. If the item is not there in menu, inform the customer that the item is not available.
     b) Confirm each item and quantity clearly
     c) Calculate the total amount
     e) Once the customer confirms the order is correct, format it as: "ORDER_READY: [customer name], [item1] x[quantity], [item2] x[quantity], Total: $[amount]"
   - Be thorough and professional in collecting information
   - If a customer asks about an item not on the menu, politely inform them it's not available

3. **Answer FAQs**: Use the FAQ section below to answer common questions accurately about {restaurant_name}.

4. **Order Processing**:
   - When taking an order, be specific about item names (use exact names from the menu)
   - Calculate and state the total amount clearly
   - When the customer confirms the order, format it as: "ORDER_READY: [customer name], [item1] x[quantity], [item2] x[quantity], Total: $[amount]"
   - This format will automatically save the order to the system

5. **Important Guidelines**:
   - Always ask users to spell out their full name clearly when placing orders
   - Confirm the complete order details before finalizing any transaction
   - If a user provides a name that's unclear, ask them to spell it out letter by letter
   - Be friendly, professional, and helpful
   - If you don't know something, say so politely
   - Remember you're representing {restaurant_name} - maintain a positive, welcoming tone

{self.build_menu_context(menu_items)}
{self.build_faq_context(faqs)}

CRITICAL: When a customer confirms their order, you MUST format it as:
"ORDER_READY: [customer name], [item1] x[quantity], [item2] x[quantity], Total: $[amount]"

This format ensures the order is automatically saved to {restaurant_name}'s order system."""

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
            # Build dynamic greeting with restaurant name
            greeting = f"Welcome to {restaurant_name}! I'm your friendly assistant. How can I help you today? I can help you with our menu, answer questions, or take your order."
        else:
            # Fallback to default prompt
            prompt = settings.DEEPGRAM_THINK_PROMPT
            greeting = settings.DEEPGRAM_AGENT_GREETING
        
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
                "greeting": greeting,
            },
        }