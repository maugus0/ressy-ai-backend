import json
import re
from typing import Dict, List, Optional, Any
from datetime import datetime

class DataExtractionService:
    """Service for extracting structured data from conversation transcripts."""
    
    def extract_user_details(self, conversation_text: str) -> Optional[Dict[str, Any]]:
        """
        Extract user details from conversation text.
        Looks for name, phone_number, email, address.
        """
        user_data = {}
        
        # Extract name patterns
        name_patterns = [
            r"name is ([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)",
            r"my name is ([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)",
            r"i'm ([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)",
            r"call me ([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)",
        ]
        for pattern in name_patterns:
            match = re.search(pattern, conversation_text, re.IGNORECASE)
            if match:
                user_data["name"] = match.group(1).strip()
                break
        
        # Extract phone number patterns
        phone_patterns = [
            r"phone.*?(\d{3}[-.\s]?\d{3}[-.\s]?\d{4})",
            r"number.*?(\d{3}[-.\s]?\d{3}[-.\s]?\d{4})",
            r"(\+?1?[-.\s]?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4})",
        ]
        for pattern in phone_patterns:
            match = re.search(pattern, conversation_text, re.IGNORECASE)
            if match:
                phone = re.sub(r'[-.\s()]', '', match.group(1))
                user_data["phone_number"] = phone
                break
        
        # Extract email patterns
        email_pattern = r"([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})"
        email_match = re.search(email_pattern, conversation_text, re.IGNORECASE)
        if email_match:
            user_data["email"] = email_match.group(1).strip()
        
        # Extract address patterns
        address_patterns = [
            r"address is (.+?)(?:\.|,|$)",
            r"live at (.+?)(?:\.|,|$)",
            r"address: (.+?)(?:\.|,|$)",
        ]
        for pattern in address_patterns:
            match = re.search(pattern, conversation_text, re.IGNORECASE)
            if match:
                address = match.group(1).strip()
                if len(address) > 10:  # Basic validation
                    user_data["address"] = address
                    break
        
        return user_data if user_data else None
    
    def extract_order_details(self, conversation_text: str, menu_items: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """
        Extract order details from conversation text.
        Matches mentioned items with menu items.
        """
        order_data = {
            "items": [],
            "total_amount": 0.0,
            "customization": {}
        }
        
        # Create a lookup map of menu items by name (case-insensitive)
        menu_lookup = {}
        for item in menu_items:
            item_name_lower = item.get("item_name", "").lower()
            menu_lookup[item_name_lower] = item
            # Also add variations
            words = item_name_lower.split()
            if len(words) > 1:
                menu_lookup[" ".join(words[:2])] = item  # First two words
        
        # Find order patterns
        order_patterns = [
            r"i want (.+?)(?:\.|,|$)",
            r"i'd like (.+?)(?:\.|,|$)",
            r"i'll have (.+?)(?:\.|,|$)",
            r"can i get (.+?)(?:\.|,|$)",
            r"order (.+?)(?:\.|,|$)",
            r"add (.+?)(?:\.|,|$)",
        ]
        
        found_items = set()
        for pattern in order_patterns:
            matches = re.finditer(pattern, conversation_text, re.IGNORECASE)
            for match in matches:
                item_phrase = match.group(1).strip().lower()
                
                # Try to match with menu items
                for menu_key, menu_item in menu_lookup.items():
                    if menu_key in item_phrase or item_phrase in menu_key:
                        item_id = menu_item.get("id")
                        if item_id and item_id not in found_items:
                            found_items.add(item_id)
                            order_data["items"].append({
                                "menu_item_id": item_id,
                                "item_name": menu_item.get("item_name"),
                                "price": float(menu_item.get("price", 0))
                            })
                            order_data["total_amount"] += float(menu_item.get("price", 0))
                            break
        
        # Extract quantity if mentioned
        quantity_pattern = r"(\d+)\s*(?:x|times|of)\s*([a-zA-Z\s]+)"
        quantity_matches = re.finditer(quantity_pattern, conversation_text, re.IGNORECASE)
        for match in quantity_matches:
            qty = int(match.group(1))
            item_name = match.group(2).strip().lower()
            # Try to match with existing items
            for item in order_data["items"]:
                if item_name in item["item_name"].lower():
                    item["quantity"] = qty
                    # Adjust total if quantity > 1
                    if qty > 1:
                        order_data["total_amount"] += item["price"] * (qty - 1)
        
        return order_data if order_data["items"] else None
    
    def build_transcript_log(self, conversation_history: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Build complete transcript log from conversation history.
        """
        return {
            "conversation": conversation_history,
            "extracted_at": datetime.utcnow().isoformat(),
            "total_messages": len(conversation_history)
        }
    
    def extract_structured_data(
        self,
        conversation_text: str,
        conversation_history: List[Dict[str, Any]],
        menu_items: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Extract all structured data from conversation.
        Returns user_details, order_details, and transcript_log.
        """
        user_details = self.extract_user_details(conversation_text)
        order_details = self.extract_order_details(conversation_text, menu_items)
        transcript_log = self.build_transcript_log(conversation_history)
        
        return {
            "user_details": user_details,
            "order_details": order_details,
            "transcript_log": transcript_log
        }

