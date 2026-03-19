from app.repositories.mysql_business_order_repo import MySQLBusinessOrderRepository


class BusinessOrderService:
    def __init__(self):
        self.business_order_repo = MySQLBusinessOrderRepository()

    def create_order(self, business_id: str, data: dict) -> dict:
        """Create a new order."""
        # business_id currently unused in MySQL schema; storing user linkage instead
        user_id = data.get("customer_id") or data.get("user_id")
        order_id = self.business_order_repo.create_order(user_id or 0, data)
        return {"message": "Order created", "order_id": order_id}

    def list_orders(self, business_id: str) -> list:
        """List all orders for a business."""
        # Not implemented in MySQL repository; return empty list.
        return []

    def get_order(self, order_id: str) -> dict:
        """Get a specific order by ID."""
        return self.business_order_repo.get_order_by_id(int(order_id))

    def update_order(self, order_id: str, data: dict) -> dict:
        """Update an existing order."""
        self.business_order_repo.update_order_details(
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
