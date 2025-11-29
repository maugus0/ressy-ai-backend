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
        # Try to get restaurant with opening/closing times, fallback to basic query if columns don't exist
        try:
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
                    opening_time,
                    closing_time,
                    created_at,
                    updated_at
                FROM Restaurants
                WHERE twilio_phone_number = %s
                LIMIT 1
            """
            results = self._execute_query(query, (twilio_phone_number,))
            if results:
                result = results[0]
                # Set defaults if columns don't exist
                if 'opening_time' not in result or result.get('opening_time') is None:
                    result['opening_time'] = '09:00:00'
                if 'closing_time' not in result or result.get('closing_time') is None:
                    result['closing_time'] = '22:00:00'
                return result
            return None
        except Exception as e:
            # If columns don't exist, use basic query with defaults
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
            if results:
                result = results[0]
                result['opening_time'] = '09:00:00'
                result['closing_time'] = '22:00:00'
                return result
            return None
    
    def get_by_id(self, restaurant_id: int) -> Optional[Dict]:
        """
        Get restaurant by ID.
        """
        # Try to get restaurant with opening/closing times, fallback to basic query if columns don't exist
        try:
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
                    opening_time,
                    closing_time,
                    created_at,
                    updated_at
                FROM Restaurants
                WHERE id = %s
                LIMIT 1
            """
            results = self._execute_query(query, (restaurant_id,))
            if results:
                result = results[0]
                # Set defaults if columns don't exist
                if 'opening_time' not in result or result.get('opening_time') is None:
                    result['opening_time'] = '09:00:00'
                if 'closing_time' not in result or result.get('closing_time') is None:
                    result['closing_time'] = '22:00:00'
                return result
            return None
        except Exception as e:
            # If columns don't exist, use basic query with defaults
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
                WHERE id = %s
                LIMIT 1
            """
            results = self._execute_query(query, (restaurant_id,))
            if results:
                result = results[0]
                result['opening_time'] = '09:00:00'
                result['closing_time'] = '22:00:00'
                return result
            return None

