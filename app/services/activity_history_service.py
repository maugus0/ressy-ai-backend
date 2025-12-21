"""
Activity History Service for order and reservation audit logging.
"""

from typing import Any, Dict, Optional

from app.repositories.mysql_activity_history_repo import MySQLActivityHistoryRepository


class ActivityHistoryService:
    """Service for activity history operations."""

    def __init__(self):
        self.history_repo = MySQLActivityHistoryRepository()

    def log_activity(
        self,
        activity_type: str,
        action: str,
        restaurant_id: int,
        user_id: Optional[int] = None,
        order_id: Optional[int] = None,
        reservation_id: Optional[int] = None,
        previous_value: Optional[Dict[str, Any]] = None,
        new_value: Optional[Dict[str, Any]] = None,
        change_summary: Optional[str] = None,
    ) -> int:
        """
        Log an activity entry.

        Args:
            activity_type: 'order' or 'reservation'
            action: Action type (created, updated, cancelled, status_changed)
            restaurant_id: Restaurant ID for RBAC
            user_id: User ID (from Users table)
            order_id: Order ID (if applicable)
            reservation_id: Reservation ID (if applicable)
            previous_value: Previous state
            new_value: New state
            change_summary: Human-readable summary

        Returns:
            Created history entry ID
        """
        return self.history_repo.create_history_entry(
            activity_type=activity_type,
            action=action,
            restaurant_id=restaurant_id,
            user_id=user_id,
            order_id=order_id,
            reservation_id=reservation_id,
            previous_value=previous_value,
            new_value=new_value,
            change_summary=change_summary,
        )

    def log_order_created(
        self,
        order_id: int,
        restaurant_id: int,
        order_data: Dict[str, Any],
        user_id: Optional[int] = None,
    ) -> int:
        """Log order creation."""
        return self.log_activity(
            activity_type="order",
            action="created",
            restaurant_id=restaurant_id,
            user_id=user_id,
            order_id=order_id,
            new_value=order_data,
            change_summary=f"Order #{order_id} created with status: {order_data.get('status', 'pending')}",
        )

    def log_order_updated(
        self,
        order_id: int,
        restaurant_id: int,
        previous_data: Dict[str, Any],
        new_data: Dict[str, Any],
        user_id: Optional[int] = None,
    ) -> int:
        """Log order update."""
        # Build change summary
        changes = []
        for key in new_data:
            if key in previous_data and previous_data[key] != new_data[key]:
                changes.append(f"{key}: {previous_data[key]} → {new_data[key]}")

        change_summary = (
            f"Order #{order_id} updated: " + ", ".join(changes) if changes else f"Order #{order_id} updated"
        )

        return self.log_activity(
            activity_type="order",
            action="updated",
            restaurant_id=restaurant_id,
            user_id=user_id,
            order_id=order_id,
            previous_value=previous_data,
            new_value=new_data,
            change_summary=change_summary[:500],
        )

    def log_order_status_changed(
        self,
        order_id: int,
        restaurant_id: int,
        old_status: str,
        new_status: str,
        user_id: Optional[int] = None,
    ) -> int:
        """Log order status change."""
        return self.log_activity(
            activity_type="order",
            action="status_changed",
            restaurant_id=restaurant_id,
            user_id=user_id,
            order_id=order_id,
            previous_value={"status": old_status},
            new_value={"status": new_status},
            change_summary=f"Order #{order_id} status changed: {old_status} → {new_status}",
        )

    def log_order_cancelled(
        self,
        order_id: int,
        restaurant_id: int,
        previous_status: str,
        user_id: Optional[int] = None,
    ) -> int:
        """Log order cancellation."""
        return self.log_activity(
            activity_type="order",
            action="cancelled",
            restaurant_id=restaurant_id,
            user_id=user_id,
            order_id=order_id,
            previous_value={"status": previous_status},
            new_value={"status": "cancelled"},
            change_summary=f"Order #{order_id} cancelled (was: {previous_status})",
        )

    def log_reservation_created(
        self,
        reservation_id: int,
        restaurant_id: int,
        reservation_data: Dict[str, Any],
        user_id: Optional[int] = None,
    ) -> int:
        """Log reservation creation."""
        return self.log_activity(
            activity_type="reservation",
            action="created",
            restaurant_id=restaurant_id,
            user_id=user_id,
            reservation_id=reservation_id,
            new_value=reservation_data,
            change_summary=f"Reservation #{reservation_id} created for {reservation_data.get('party_size', '?')} guests",
        )

    def log_reservation_updated(
        self,
        reservation_id: int,
        restaurant_id: int,
        previous_data: Dict[str, Any],
        new_data: Dict[str, Any],
        user_id: Optional[int] = None,
    ) -> int:
        """Log reservation update."""
        # Build change summary
        changes = []
        for key in new_data:
            if key in previous_data and previous_data[key] != new_data[key]:
                changes.append(f"{key}: {previous_data[key]} → {new_data[key]}")

        change_summary = (
            f"Reservation #{reservation_id} updated: " + ", ".join(changes)
            if changes
            else f"Reservation #{reservation_id} updated"
        )

        return self.log_activity(
            activity_type="reservation",
            action="updated",
            restaurant_id=restaurant_id,
            user_id=user_id,
            reservation_id=reservation_id,
            previous_value=previous_data,
            new_value=new_data,
            change_summary=change_summary[:500],
        )

    def log_reservation_status_changed(
        self,
        reservation_id: int,
        restaurant_id: int,
        old_status: str,
        new_status: str,
        user_id: Optional[int] = None,
    ) -> int:
        """Log reservation status change."""
        return self.log_activity(
            activity_type="reservation",
            action="status_changed",
            restaurant_id=restaurant_id,
            user_id=user_id,
            reservation_id=reservation_id,
            previous_value={"status": old_status},
            new_value={"status": new_status},
            change_summary=f"Reservation #{reservation_id} status changed: {old_status} → {new_status}",
        )

    def log_reservation_cancelled(
        self,
        reservation_id: int,
        restaurant_id: int,
        previous_status: str,
        user_id: Optional[int] = None,
    ) -> int:
        """Log reservation cancellation."""
        return self.log_activity(
            activity_type="reservation",
            action="cancelled",
            restaurant_id=restaurant_id,
            user_id=user_id,
            reservation_id=reservation_id,
            previous_value={"status": previous_status},
            new_value={"status": "cancelled"},
            change_summary=f"Reservation #{reservation_id} cancelled (was: {previous_status})",
        )

    def get_order_history(
        self,
        order_id: int,
        limit: int = 100,
        offset: int = 0,
    ) -> Dict[str, Any]:
        """
        Get activity history for an order.

        Args:
            order_id: Order ID
            limit: Maximum results
            offset: Pagination offset

        Returns:
            History entries with pagination info

        Raises:
            ValueError: If order not found
        """
        # Check if order exists and get restaurant_id
        restaurant_id = self.history_repo.get_order_restaurant_id(order_id)
        if restaurant_id is None:
            raise ValueError(f"Order with ID {order_id} not found")

        entries = self.history_repo.get_history_by_order(order_id, limit, offset)
        total = self.history_repo.count_history_by_order(order_id)

        return {
            "order_id": order_id,
            "restaurant_id": restaurant_id,
            "entries": entries,
            "total": total,
            "limit": limit,
            "offset": offset,
        }

    def get_reservation_history(
        self,
        reservation_id: int,
        limit: int = 100,
        offset: int = 0,
    ) -> Dict[str, Any]:
        """
        Get activity history for a reservation.

        Args:
            reservation_id: Reservation ID
            limit: Maximum results
            offset: Pagination offset

        Returns:
            History entries with pagination info

        Raises:
            ValueError: If reservation not found
        """
        # Check if reservation exists and get restaurant_id
        restaurant_id = self.history_repo.get_reservation_restaurant_id(reservation_id)
        if restaurant_id is None:
            raise ValueError(f"Reservation with ID {reservation_id} not found")

        entries = self.history_repo.get_history_by_reservation(reservation_id, limit, offset)
        total = self.history_repo.count_history_by_reservation(reservation_id)

        return {
            "reservation_id": reservation_id,
            "restaurant_id": restaurant_id,
            "entries": entries,
            "total": total,
            "limit": limit,
            "offset": offset,
        }

    def get_order_restaurant_id(self, order_id: int) -> Optional[int]:
        """Get restaurant_id for an order (for RBAC checks)."""
        return self.history_repo.get_order_restaurant_id(order_id)

    def get_reservation_restaurant_id(self, reservation_id: int) -> Optional[int]:
        """Get restaurant_id for a reservation (for RBAC checks)."""
        return self.history_repo.get_reservation_restaurant_id(reservation_id)
