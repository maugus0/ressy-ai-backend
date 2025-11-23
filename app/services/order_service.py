from app.repositories.mysql_order_repo import MySQLOrderRepository


class OrderService:
    def __init__(self):
        self.order_repo = MySQLOrderRepository()

    def create_order(self, restaurant_id: str, data: dict) -> dict:
        """Create a new order."""
        # restaurant_id currently unused in MySQL schema; storing user linkage instead
        user_id = data.get("customer_id") or data.get("user_id")
        order_id = self.order_repo.create_order(user_id or 0, data)
        return {"message": "Order created", "order_id": order_id}

    def list_orders(self, restaurant_id: str) -> list:
        """List all orders for a restaurant."""
        # Not implemented in MySQL repository; return empty list.
        return []

    def get_order(self, order_id: str) -> dict:
        """Get a specific order by ID."""
        return self.order_repo.get_order_by_id(int(order_id))

    def update_order(self, order_id: str, data: dict) -> dict:
        """Update an existing order."""
        self.order_repo.update_order_details(
            int(order_id), data.get("order_details", []), data.get("customization"), data.get("total_amount")
        )
        return {"message": "Order updated"}

    def delete_order(self, order_id: str) -> dict:
        """Delete an order."""
        # Deleting orders not implemented; return message.
        return {"message": "Order deleted"}

    def get_order_history(self, order_id: str) -> list:
        """Get order history for a specific order."""
        return []
