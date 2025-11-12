import uuid
from app.repositories.order_repo import OrderRepository

class OrderService:
    def __init__(self):
        self.order_repo = OrderRepository()
    
    def create_order(self, restaurant_id: str, data: dict) -> dict:
        """Create a new order."""
        order_id = str(uuid.uuid4())
        self.order_repo.create(order_id, restaurant_id, data)
        return {"message": "Order created", "order_id": order_id}
    
    def list_orders(self, restaurant_id: str) -> list:
        """List all orders for a restaurant."""
        return self.order_repo.get_by_restaurant(restaurant_id)
    
    def get_order(self, order_id: str) -> dict:
        """Get a specific order by ID."""
        return self.order_repo.get_by_id(order_id)
    
    def update_order(self, order_id: str, data: dict) -> dict:
        """Update an existing order."""
        self.order_repo.update(order_id, data)
        return {"message": "Order updated"}
    
    def delete_order(self, order_id: str) -> dict:
        """Delete an order."""
        self.order_repo.delete(order_id)
        return {"message": "Order deleted"}
    
    def get_order_history(self, order_id: str) -> list:
        """Get order history for a specific order."""
        return self.order_repo.get_history(order_id)

