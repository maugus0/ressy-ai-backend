"""
MySQL Menu Repository for fetching available menu items.
"""
from app.repositories.mysql_base import MySQLBaseRepository
from typing import List, Dict

class MySQLMenuRepository(MySQLBaseRepository):
    """Repository for menu data access in MySQL."""
    
    def get_available_items_by_restaurant(self, restaurant_id: int) -> List[Dict]:
        """
        Get all available menu items for a restaurant.
        Only returns items where is_available = TRUE.
        """
        query = """
            SELECT 
                id,
                restaurant_id,
                category,
                sub_category,
                item_name,
                item_desc,
                price,
                avg_prep_time,
                suggested_items,
                is_available,
                is_special,
                created_at,
                updated_at
            FROM Menus
            WHERE restaurant_id = %s 
              AND is_available = TRUE
            ORDER BY category, sub_category, item_name
        """
        return self._execute_query(query, (restaurant_id,))
    
    def get_item_by_name(self, restaurant_id: int, item_name: str) -> Dict:
        """
        Get menu item by name (for order details).
        """
        query = """
            SELECT id, restaurant_id, item_name, price
            FROM Menus
            WHERE restaurant_id = %s
              AND LOWER(item_name) LIKE LOWER(%s)
              AND is_available = TRUE
            LIMIT 1
        """
        results = self._execute_query(query, (restaurant_id, f"%{item_name}%"))
        return results[0] if results else None

