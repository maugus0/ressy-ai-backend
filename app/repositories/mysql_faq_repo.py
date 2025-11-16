"""
MySQL FAQ Repository for fetching restaurant FAQs.
"""
from app.repositories.mysql_base import MySQLBaseRepository
from typing import List, Dict

class MySQLFAQRepository(MySQLBaseRepository):
    """Repository for FAQ data access in MySQL."""
    
    def get_by_restaurant(self, restaurant_id: int) -> List[Dict]:
        """
        Get all FAQs for a restaurant.
        """
        query = """
            SELECT 
                id,
                restaurant_id,
                question,
                answer,
                created_at,
                updated_at
            FROM FAQs
            WHERE restaurant_id = %s
            ORDER BY id
        """
        return self._execute_query(query, (restaurant_id,))

