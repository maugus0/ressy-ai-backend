"""
MySQL Restaurant Repository for multitenant operations.
"""
from app.repositories.mysql_base import MySQLBaseRepository
from typing import Dict, Optional

class MySQLRestaurantRepository(MySQLBaseRepository):
    """Repository for restaurant data access in MySQL."""
    
    def get_by_twilio_number(self, twilio_phone_number: str) -> Optional[Dict]:
        """
        Get restaurant by Twilio phone number.
        Used for multitenant call routing.
        """
        query = """
            SELECT 
                id,
                name,
                address,
                phone_number,
                twilio_phone_number,
                twilio_details,
                deepgram_details,
                open_table_details,
                forward_minutes,
                backward_minutes,
                is_credit_card_required_for_reservation,
                created_at,
                updated_at
            FROM Restaurants
            WHERE twilio_phone_number = %s
            LIMIT 1
        """
        results = self._execute_query(query, (twilio_phone_number,))
        print("twilio_phone_numberaaa: ", twilio_phone_number)
        return results[0] if results else None

