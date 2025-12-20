"""
Dashboard Order Service for managing orders with RBAC support.
"""

import json
from datetime import datetime
from typing import Any, Dict, List, Optional

from app.repositories.mysql_menu_repo import MySQLMenuRepository
from app.repositories.mysql_order_repo import MySQLOrderRepository
from app.repositories.mysql_restaurant_repo import MySQLRestaurantRepository
from app.repositories.mysql_user_repo import MySQLUserRepository


def _transform_order(order: Dict[str, Any]) -> Dict[str, Any]:
    """
    Transform order data from MySQL format to API response format.

    - Parses JSON string fields (order_details, customization)
    - Converts datetime objects to ISO strings
    """
    if not order:
        return order

    result = dict(order)

    # Parse JSON fields if they are strings
    if isinstance(result.get("order_details"), str):
        try:
            result["order_details"] = json.loads(result["order_details"])
        except (json.JSONDecodeError, TypeError):
            result["order_details"] = []

    if isinstance(result.get("customization"), str):
        try:
            result["customization"] = json.loads(result["customization"])
        except (json.JSONDecodeError, TypeError):
            result["customization"] = {}

    # Convert datetime objects to ISO strings
    for field in ["created_at", "updated_at", "deleted_at"]:
        if isinstance(result.get(field), datetime):
            result[field] = result[field].isoformat()

    return result


class DashboardOrderService:
    """Service for dashboard order operations with RBAC."""

    # Valid order statuses
    VALID_STATUSES = [
        "pending",
        "confirmed",
        "preparing",
        "ready",
        "completed",
        "cancelled",
    ]

    def __init__(self):
        self.order_repo = MySQLOrderRepository()
        self.restaurant_repo = MySQLRestaurantRepository()
        self.user_repo = MySQLUserRepository()
        self.menu_repo = MySQLMenuRepository()

    def create_order(
        self,
        restaurant_id: int,
        order_details: List[Dict[str, Any]],
        total_amount: float,
        customer_name: Optional[str] = None,
        customer_phone: Optional[str] = None,
        customer_email: Optional[str] = None,
        customization: Optional[Dict[str, Any]] = None,
        status: str = "pending",
    ) -> Dict[str, Any]:
        """
        Create a new order from the dashboard.

        Args:
            restaurant_id: Restaurant ID
            order_details: List of order items
            total_amount: Total order amount
            customer_name: Customer name (optional)
            customer_phone: Customer phone number (optional)
            customer_email: Customer email (optional)
            customization: Order customization options (optional)
            status: Initial order status (default: pending)

        Returns:
            Created order details

        Raises:
            ValueError: If restaurant not found or invalid data
        """
        # Validate restaurant exists
        restaurant = self.restaurant_repo.get_by_id(restaurant_id)
        if not restaurant:
            raise ValueError(f"Restaurant with ID {restaurant_id} not found")

        # Validate status
        if status not in self.VALID_STATUSES:
            raise ValueError(f"Invalid status '{status}'. " f"Must be one of: {', '.join(self.VALID_STATUSES)}")

        # Validate order items belong to the restaurant's menu (single batch query)
        item_ids = [item.get("item_id") for item in order_details if item.get("item_id") is not None]
        if item_ids:
            # Fetch all menu items in a single query to avoid N+1 pattern
            menu_items_by_id = self.menu_repo.get_by_ids(item_ids)

            # Check for invalid items (missing or wrong restaurant)
            invalid_items = []
            for item_id in item_ids:
                menu_item = menu_items_by_id.get(item_id)
                if not menu_item:
                    invalid_items.append(f"item_id {item_id} (not found)")
                elif menu_item.get("restaurant_id") != restaurant_id:
                    item_restaurant_id = menu_item.get("restaurant_id")
                    item_name = menu_item.get("item_name", "Unknown")
                    invalid_items.append(
                        f"'{item_name}' (item_id {item_id}) belongs to restaurant {item_restaurant_id}"
                    )

            if invalid_items:
                raise ValueError(
                    f"Order contains items that don't belong to restaurant {restaurant_id}: "
                    f"{', '.join(invalid_items)}"
                )

        # Create or get user
        user_id = None
        if customer_phone or customer_email:
            user_data = {"name": customer_name}
            if customer_phone:
                user_data["phone_number"] = customer_phone
            if customer_email:
                user_data["email"] = customer_email
            user_id = self.user_repo.create_or_update_user(user_data)

        # Create order
        order_data = {
            "restaurant_id": restaurant_id,
            "status": status,
            "total_amount": total_amount,
            "order_details": order_details,
            "customization": customization or {},
        }

        order_id = self.order_repo.create_order(user_id, order_data)

        return {
            "order_id": order_id,
            "restaurant_id": restaurant_id,
            "user_id": user_id,
            "status": status,
            "total_amount": total_amount,
            "order_details": order_details,
            "customization": customization or {},
            "customer_name": customer_name,
            "customer_phone": customer_phone,
            "customer_email": customer_email,
            "message": "Order created successfully",
        }

    def get_order(self, order_id: int) -> Dict[str, Any]:
        """
        Get order by ID with customer details.

        Args:
            order_id: Order ID

        Returns:
            Order details with customer info

        Raises:
            ValueError: If order not found
        """
        order = self.order_repo.get_order_with_user(order_id)

        if not order:
            raise ValueError(f"Order with ID {order_id} not found")

        return _transform_order(order)

    def get_order_with_restaurant_check(self, order_id: int) -> Dict[str, Any]:
        """
        Get order by ID for RBAC checks.
        Ensures restaurant_id is returned for access validation.

        Args:
            order_id: Order ID

        Returns:
            Order details including restaurant_id

        Raises:
            ValueError: If order not found
        """
        order = self.order_repo.get_order_with_user(order_id)

        if not order:
            raise ValueError(f"Order with ID {order_id} not found")

        # Transform the order data
        order = _transform_order(order)

        # Ensure restaurant_id is properly typed for authorization checks
        restaurant_id = order.get("restaurant_id")
        if restaurant_id is not None:
            order["restaurant_id"] = int(restaurant_id)

        return order

    def get_orders_by_restaurant(
        self,
        restaurant_id: int,
        status: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
        include_deleted: bool = False,
    ) -> Dict[str, Any]:
        """
        Get orders for a restaurant with optional filters.

        Args:
            restaurant_id: Restaurant ID
            status: Filter by status
            start_date: Filter by start date (ISO format)
            end_date: Filter by end date (ISO format)
            limit: Maximum results
            offset: Pagination offset
            include_deleted: Include soft-deleted orders

        Returns:
            List of orders with pagination info
        """
        # Validate status if provided
        if status and status not in self.VALID_STATUSES:
            raise ValueError(f"Invalid status '{status}'. " f"Must be one of: {', '.join(self.VALID_STATUSES)}")

        # Parse dates
        start_dt = None
        end_dt = None

        if start_date:
            try:
                start_dt = datetime.fromisoformat(start_date.replace("Z", "+00:00"))
                if start_dt.tzinfo:
                    start_dt = start_dt.replace(tzinfo=None)
            except ValueError:
                raise ValueError(f"Invalid start_date format: {start_date}")

        if end_date:
            try:
                end_dt = datetime.fromisoformat(end_date.replace("Z", "+00:00"))
                if end_dt.tzinfo:
                    end_dt = end_dt.replace(tzinfo=None)
            except ValueError:
                raise ValueError(f"Invalid end_date format: {end_date}")

        # Get orders
        orders = self.order_repo.get_orders_by_restaurant(
            restaurant_id=restaurant_id,
            status=status,
            start_date=start_dt,
            end_date=end_dt,
            limit=limit,
            offset=offset,
            include_deleted=include_deleted,
        )

        # Transform each order
        transformed_orders = [_transform_order(order) for order in orders]

        # Get total count
        total = self.order_repo.count_orders_by_restaurant(
            restaurant_id=restaurant_id,
            status=status,
            start_date=start_dt,
            end_date=end_dt,
            include_deleted=include_deleted,
        )

        return {
            "restaurant_id": restaurant_id,
            "orders": transformed_orders,
            "total": total,
            "limit": limit,
            "offset": offset,
        }

    def update_order(
        self,
        order_id: int,
        status: Optional[str] = None,
        total_amount: Optional[float] = None,
        order_details: Optional[List[Dict[str, Any]]] = None,
        customization: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Update order details.

        Args:
            order_id: Order ID
            status: New status (optional)
            total_amount: New total amount (optional)
            order_details: New order details (optional)
            customization: New customization (optional)

        Returns:
            Updated order details

        Raises:
            ValueError: If order not found or invalid data
        """
        # Check order exists
        order = self.order_repo.get_order_with_user(order_id)
        if not order:
            raise ValueError(f"Order with ID {order_id} not found")

        # Validate status if provided
        if status and status not in self.VALID_STATUSES:
            raise ValueError(f"Invalid status '{status}'. " f"Must be one of: {', '.join(self.VALID_STATUSES)}")

        # Prevent updates to cancelled orders (except to uncancelled them)
        if order.get("status") == "cancelled" and status != "pending":
            raise ValueError("Cannot update a cancelled order")

        # Update order
        success = self.order_repo.update_order(
            order_id=order_id,
            status=status,
            total_amount=total_amount,
            order_details=order_details,
            customization=customization,
        )

        if not success:
            raise ValueError("Failed to update order")

        # Return updated order (transformed)
        return _transform_order(self.order_repo.get_order_with_user(order_id))

    def update_order_status(self, order_id: int, status: str) -> Dict[str, Any]:
        """
        Update only the order status.

        Args:
            order_id: Order ID
            status: New status

        Returns:
            Updated order details

        Raises:
            ValueError: If order not found or invalid status
        """
        # Check order exists
        order = self.order_repo.get_order_with_user(order_id)
        if not order:
            raise ValueError(f"Order with ID {order_id} not found")

        # Validate status
        if status not in self.VALID_STATUSES:
            raise ValueError(f"Invalid status '{status}'. " f"Must be one of: {', '.join(self.VALID_STATUSES)}")

        # Update status
        success = self.order_repo.update_order_status(order_id, status)

        if not success:
            raise ValueError("Failed to update order status")

        return {
            "order_id": order_id,
            "status": status,
            "message": f"Order status updated to '{status}'",
        }

    def cancel_order(self, order_id: int) -> Dict[str, Any]:
        """
        Cancel an order by setting status to 'cancelled'.

        Args:
            order_id: Order ID

        Returns:
            Cancellation confirmation

        Raises:
            ValueError: If order not found or already completed
        """
        # Check order exists
        order = self.order_repo.get_order_with_user(order_id)
        if not order:
            raise ValueError(f"Order with ID {order_id} not found")

        current_status = order.get("status")

        # Check if order can be cancelled
        if current_status == "cancelled":
            raise ValueError("Order is already cancelled")

        if current_status == "completed":
            raise ValueError("Cannot cancel a completed order")

        # Update status to cancelled
        success = self.order_repo.update_order_status(order_id, "cancelled")

        if not success:
            raise ValueError("Failed to cancel order")

        return {
            "order_id": order_id,
            "status": "cancelled",
            "previous_status": current_status,
            "message": "Order cancelled successfully",
        }

    def soft_delete_order(self, order_id: int) -> Dict[str, Any]:
        """
        Soft delete an order.

        Args:
            order_id: Order ID

        Returns:
            Deletion confirmation

        Raises:
            ValueError: If order not found or already deleted
        """
        # Check order exists
        order = self.order_repo.get_order_by_id(order_id)
        if not order:
            raise ValueError(f"Order with ID {order_id} not found")

        if order.get("deleted_at"):
            raise ValueError("Order is already deleted")

        # Soft delete
        success = self.order_repo.soft_delete_order(order_id)

        if not success:
            raise ValueError("Failed to delete order")

        return {
            "order_id": order_id,
            "message": "Order deleted successfully",
        }

    def restore_order(self, order_id: int) -> Dict[str, Any]:
        """
        Restore a soft-deleted order.

        Args:
            order_id: Order ID

        Returns:
            Restoration confirmation

        Raises:
            ValueError: If order not found or not deleted
        """
        # Check order exists
        order = self.order_repo.get_order_by_id(order_id)
        if not order:
            raise ValueError(f"Order with ID {order_id} not found")

        if not order.get("deleted_at"):
            raise ValueError("Order is not deleted")

        # Restore
        success = self.order_repo.restore_order(order_id)

        if not success:
            raise ValueError("Failed to restore order")

        return {
            "order_id": order_id,
            "message": "Order restored successfully",
        }

    def get_order_restaurant_id(self, order_id: int) -> Optional[int]:
        """
        Get the restaurant_id for an order (for RBAC checks).

        Args:
            order_id: Order ID

        Returns:
            restaurant_id if found, None otherwise
        """
        return self.order_repo.get_order_restaurant_id(order_id)
