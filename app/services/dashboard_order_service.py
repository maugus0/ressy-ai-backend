"""
Dashboard Order Service for managing orders with RBAC support.
"""

import json
from datetime import datetime
from typing import Any, Dict, List, Optional

from app.repositories.mysql_menu_repo import MySQLMenuRepository
from app.repositories.mysql_order_item_repo import MySQLOrderItemRepository
from app.repositories.mysql_order_repo import MySQLOrderRepository
from app.repositories.mysql_restaurant_repo import MySQLRestaurantRepository
from app.repositories.mysql_user_repo import MySQLUserRepository
from app.repositories.mysql_user_restaurant_metadata_repo import (
    MySQLUserRestaurantMetadataRepository,
)
from app.services.order_customization_service import OrderCustomizationService
from app.services.pos_service import POSService
from app.utils.logging_config import get_logger
from app.utils.timezone import isoformat_z, parse_datetime

logger = get_logger(__name__)


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
            result[field] = isoformat_z(result[field])

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
        self.metadata_repo = MySQLUserRestaurantMetadataRepository()
        self.menu_repo = MySQLMenuRepository()
        self.order_item_repo = MySQLOrderItemRepository()
        self.customization_service = OrderCustomizationService(self.menu_repo)
        self.pos_service = POSService()

    def _attach_order_item_snapshots(self, order: Dict[str, Any]) -> Dict[str, Any]:
        if not order or not order.get("id"):
            return order
        order_id = int(order["id"])
        items = self.order_item_repo.list_order_items(order_id)
        if not items:
            order["order_items"] = []
            return order
        options = self.order_item_repo.list_order_item_options(order_id)
        options_by_item: Dict[int, List[Dict[str, Any]]] = {}
        for opt in options:
            order_item_id = opt.get("order_item_id")
            if order_item_id is None:
                continue
            options_by_item.setdefault(int(order_item_id), []).append(opt)
        for item in items:
            item_id = item.get("id")
            item["options"] = options_by_item.get(int(item_id), []) if item_id is not None else []
        order["order_items"] = items
        return order

    def _validate_and_price_order_details(
        self, order_details: List[Dict[str, Any]]
    ) -> tuple[list[Dict[str, Any]], float]:
        priced_items: List[Dict[str, Any]] = []
        total = 0.0
        for item in order_details:
            item_id = item.get("item_id")
            options = item.get("options")
            price = float(item.get("price") or 0)
            quantity = max(int(item.get("quantity") or 1), 1)
            if options and not item_id:
                raise ValueError("Customizations require a valid item_id.")
            if not item_id:
                line_total = round(price * quantity, 2)
                priced_items.append(
                    {
                        "menu_item_id": None,
                        "item_name_snapshot": item.get("name"),
                        "base_price_snapshot": price,
                        "quantity": quantity,
                        "instructions": item.get("instructions"),
                        "final_unit_price_snapshot": price,
                        "option_total_snapshot": 0.0,
                        "total_price_snapshot": line_total,
                        "option_snapshots": [],
                    }
                )
                total += line_total
                continue
            validation = self.customization_service.validate_item_options(item_id, options)
            if not validation.is_valid:
                raise ValueError("Invalid customizations provided for one or more items.")
            priced = self.customization_service.price_item(item_id, price, quantity, validation.normalized_options)
            priced_items.append(
                {
                    "menu_item_id": item_id,
                    "item_name_snapshot": item.get("name"),
                    "base_price_snapshot": price,
                    "quantity": quantity,
                    "instructions": item.get("instructions"),
                    "final_unit_price_snapshot": priced.final_unit_price,
                    "option_total_snapshot": priced.option_total,
                    "total_price_snapshot": priced.total_price,
                    "option_snapshots": priced.option_snapshots,
                }
            )
            total += priced.total_price
        return priced_items, round(total, 2)

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
        # Ensure item_ids are integers for consistent comparison (defensive conversion)
        raw_item_ids = [item.get("item_id") for item in order_details if item.get("item_id") is not None]

        # Convert item_ids to integers with error handling
        item_ids: List[int] = []
        invalid_item_ids: List[str] = []
        for iid in raw_item_ids:
            try:
                item_ids.append(int(iid))
            except (TypeError, ValueError):
                invalid_item_ids.append(str(iid))

        if invalid_item_ids:
            raise ValueError(
                f"Order contains invalid item_id values: {', '.join(invalid_item_ids)}. " "Item IDs must be integers."
            )

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

            # Create user-restaurant metadata mapping (for dashboard user visibility)
            try:
                self.metadata_repo.create_mapping(
                    user_id=user_id,
                    restaurant_id=restaurant_id,
                    source="order",
                    notes="Created via dashboard order",
                )
            except Exception as meta_err:
                # Log but don't fail order creation if metadata mapping fails
                logger.warning("Failed to create user-restaurant metadata: %s", meta_err)

        priced_items, computed_total = self._validate_and_price_order_details(order_details)
        priced_items = self.pos_service.attach_external_snapshot_ids(restaurant_id, priced_items)
        if computed_total > 0:
            total_amount = computed_total

        # Create order
        order_data = {
            "restaurant_id": restaurant_id,
            "status": status,
            "total_amount": total_amount,
            "order_details": order_details,
            "customization": customization or {},
        }

        order_id = self.order_repo.create_order(user_id, order_data)
        for item in priced_items:
            order_item_id = self.order_item_repo.create_order_item(
                order_id,
                {
                    "menu_item_id": item.get("menu_item_id"),
                    "external_item_id_snapshot": item.get("external_item_id_snapshot"),
                    "item_name_snapshot": item.get("item_name_snapshot"),
                    "base_price_snapshot": item.get("base_price_snapshot"),
                    "quantity": item.get("quantity"),
                    "instructions": item.get("instructions"),
                    "final_unit_price_snapshot": item.get("final_unit_price_snapshot"),
                    "option_total_snapshot": item.get("option_total_snapshot"),
                    "total_price_snapshot": item.get("total_price_snapshot"),
                },
            )
            self.order_item_repo.create_order_item_options(order_item_id, item.get("option_snapshots", []))

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

        order = _transform_order(order)
        return self._attach_order_item_snapshots(order)

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

        return self._attach_order_item_snapshots(order)

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
                start_dt = parse_datetime(start_date).replace(tzinfo=None)
            except ValueError:
                raise ValueError(f"Invalid start_date format: {start_date}")

        if end_date:
            try:
                end_dt = parse_datetime(end_date).replace(tzinfo=None)
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
        transformed_orders = []
        for order in orders:
            transformed = _transform_order(order)
            transformed_orders.append(self._attach_order_item_snapshots(transformed))

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

        if order_details is not None:
            priced_items, computed_total = self._validate_and_price_order_details(order_details)
            priced_items = self.pos_service.attach_external_snapshot_ids(order.get("restaurant_id"), priced_items)
            if computed_total > 0:
                total_amount = computed_total

        previous_state = self.pos_service.capture_order_state(order_id)

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

        if order_details is not None:
            self.order_item_repo.replace_order_item_snapshots(order_id, priced_items)

        if status == "cancelled":
            if previous_state and self.pos_service.has_confirmed_sync(order_id):
                pos_result = self.pos_service.cancel_order_in_pos(
                    order_id,
                    int(order.get("restaurant_id")),
                    reason="Dashboard cancelled order",
                )
                if not pos_result.get("success"):
                    self.pos_service.restore_order_state(order_id, previous_state)
                    raise ValueError(
                        pos_result.get("error") or "Failed to cancel the order with the restaurant system."
                    )
        elif order_details is not None and previous_state and self.pos_service.has_confirmed_sync(order_id):
            pos_result = self.pos_service.replace_order_after_internal_update(
                order_id,
                int(order.get("restaurant_id")),
                previous_state=previous_state,
                reason="Dashboard updated order",
            )
            if not pos_result.get("success"):
                raise ValueError(
                    pos_result.get("error") or "Failed to confirm the updated order with the restaurant system."
                )

        # Return updated order (transformed)
        updated = _transform_order(self.order_repo.get_order_with_user(order_id))
        return self._attach_order_item_snapshots(updated)

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

        if status == "cancelled":
            cancelled = self.cancel_order(order_id)
            return {
                "order_id": order_id,
                "status": "cancelled",
                "message": cancelled.get("message", "Order cancelled successfully"),
            }

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

        previous_state = self.pos_service.capture_order_state(order_id)

        # Update status to cancelled
        success = self.order_repo.update_order_status(order_id, "cancelled")

        if not success:
            raise ValueError("Failed to cancel order")

        if previous_state and self.pos_service.has_confirmed_sync(order_id):
            pos_result = self.pos_service.cancel_order_in_pos(
                order_id,
                int(order.get("restaurant_id")),
                reason="Dashboard cancelled order",
            )
            if not pos_result.get("success"):
                self.pos_service.restore_order_state(order_id, previous_state)
                raise ValueError(pos_result.get("error") or "Failed to cancel the order with the restaurant system.")

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
