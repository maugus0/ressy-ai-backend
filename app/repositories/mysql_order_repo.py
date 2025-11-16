"""
MySQL Order Repository for order operations.
"""
from app.repositories.mysql_base import MySQLBaseRepository
from typing import Dict, List
import json

class MySQLOrderRepository(MySQLBaseRepository):
    """Repository for order data access in MySQL."""
    
    def create_order(self, user_id: int, order_data: Dict) -> int:
        """
        Create a new order and return order ID.
        """
        query = """
            INSERT INTO Orders (user_id, status, total_amount, order_details, customization, created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s, NOW(), NOW())
        """
        order_id = self._execute_insert(query, (
            user_id,
            order_data.get("status", "pending"),
            order_data.get("total_amount", 0.0),
            json.dumps(order_data.get("order_details", {})),
            json.dumps(order_data.get("customization", {}))
        ))
        return order_id
    
    def create_order_details(self, order_id: int, menu_item_id: int) -> int:
        """
        Create order detail entry.
        """
        query = """
            INSERT INTO Order_Details (order_id, menu_item_id, created_at, updated_at)
            VALUES (%s, %s, NOW(), NOW())
        """
        return self._execute_insert(query, (order_id, menu_item_id))

