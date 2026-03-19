"""
Activity History Service for order and reservation audit logging.
"""

from typing import Any, Dict, Optional

from app.repositories.mysql_activity_history_repo import MySQLActivityHistoryRepository


class BusinessActivityHistoryService:
    """Service for activity history operations."""

    def __init__(self):
        self.history_repo = MySQLActivityHistoryRepository()

    def _format_performed_by_suffix(self, performed_by: Optional[Dict[str, Any]] = None) -> str:
        """
        Format the 'performed by' suffix for change summary.

        Args:
            performed_by: Dict containing 'email' and 'user_type' from JWT claims.
                         If None, assumes action was performed by voice agent.

        Returns:
            Formatted suffix string like " by ressy admin - admin@ressy.ai"
            or empty string if performed_by is None (agent action).
        """
        if not performed_by:
            return ""

        email = performed_by.get("email", "unknown")
        user_type = performed_by.get("user_type", "").lower()

        if user_type == "admin":
            return f" by ressy admin - {email}"
        elif user_type == "business":
            return f" by business admin - {email}"
        else:
            return f" by {email}"

    def log_activity(
        self,
        activity_type: str,
        action: str,
        business_id: int,
        user_id: Optional[int] = None,
        order_id: Optional[int] = None,
        booking_id: Optional[int] = None,
        previous_value: Optional[Dict[str, Any]] = None,
        new_value: Optional[Dict[str, Any]] = None,
        change_summary: Optional[str] = None,
    ) -> int:
        """
        Log an activity entry.

        Args:
            activity_type: 'order' or 'reservation'
            action: Action type (created, updated, cancelled, status_changed)
            business_id: Restaurant ID for RBAC
            user_id: User ID (from Users table - the customer)
            order_id: Order ID (if applicable)
            booking_id: Reservation ID (if applicable)
            previous_value: Previous state
            new_value: New state
            change_summary: Human-readable summary

        Returns:
            Created history entry ID
        """
        return self.history_repo.create_history_entry(
            activity_type=activity_type,
            action=action,
            business_id=business_id,
            user_id=user_id,
            order_id=order_id,
            booking_id=booking_id,
            previous_value=previous_value,
            new_value=new_value,
            change_summary=change_summary,
        )

    def log_order_created(
        self,
        order_id: int,
        business_id: int,
        order_data: Dict[str, Any],
        user_id: Optional[int] = None,
        performed_by: Optional[Dict[str, Any]] = None,
    ) -> int:
        """
        Log order creation.

        Args:
            order_id: The created order ID
            business_id: Restaurant ID
            order_data: Order data including status, total_amount, etc.
            user_id: Customer user ID
            performed_by: Dict with 'email' and 'user_type' if created via dashboard

        Returns:
            Created history entry ID
        """
        suffix = self._format_performed_by_suffix(performed_by)
        base_summary = f"Order #{order_id} created with status: {order_data.get('status', 'pending')}"
        change_summary = f"{base_summary}{suffix}"

        return self.log_activity(
            activity_type="order",
            action="created",
            business_id=business_id,
            user_id=user_id,
            order_id=order_id,
            new_value=order_data,
            change_summary=change_summary[:500],
        )

    def log_order_updated(
        self,
        order_id: int,
        business_id: int,
        previous_data: Dict[str, Any],
        new_data: Dict[str, Any],
        user_id: Optional[int] = None,
        performed_by: Optional[Dict[str, Any]] = None,
    ) -> int:
        """
        Log order update.

        Args:
            order_id: The order ID
            business_id: Restaurant ID
            previous_data: Previous order state
            new_data: New order state
            user_id: Customer user ID
            performed_by: Dict with 'email' and 'user_type' if updated via dashboard

        Returns:
            Created history entry ID
        """
        # Build change summary
        changes = []
        for key in new_data:
            if key in previous_data and previous_data[key] != new_data[key]:
                changes.append(f"{key}: {previous_data[key]} → {new_data[key]}")

        base_summary = f"Order #{order_id} updated: " + ", ".join(changes) if changes else f"Order #{order_id} updated"
        suffix = self._format_performed_by_suffix(performed_by)
        change_summary = f"{base_summary}{suffix}"

        return self.log_activity(
            activity_type="order",
            action="updated",
            business_id=business_id,
            user_id=user_id,
            order_id=order_id,
            previous_value=previous_data,
            new_value=new_data,
            change_summary=change_summary[:500],
        )

    def log_order_status_changed(
        self,
        order_id: int,
        business_id: int,
        old_status: str,
        new_status: str,
        user_id: Optional[int] = None,
        performed_by: Optional[Dict[str, Any]] = None,
    ) -> int:
        """
        Log order status change.

        Args:
            order_id: The order ID
            business_id: Restaurant ID
            old_status: Previous status
            new_status: New status
            user_id: Customer user ID
            performed_by: Dict with 'email' and 'user_type' if changed via dashboard

        Returns:
            Created history entry ID
        """
        suffix = self._format_performed_by_suffix(performed_by)
        base_summary = f"Order #{order_id} status changed: {old_status} → {new_status}"
        change_summary = f"{base_summary}{suffix}"

        return self.log_activity(
            activity_type="order",
            action="status_changed",
            business_id=business_id,
            user_id=user_id,
            order_id=order_id,
            previous_value={"status": old_status},
            new_value={"status": new_status},
            change_summary=change_summary[:500],
        )

    def log_order_cancelled(
        self,
        order_id: int,
        business_id: int,
        previous_status: str,
        user_id: Optional[int] = None,
        performed_by: Optional[Dict[str, Any]] = None,
    ) -> int:
        """
        Log order cancellation.

        Args:
            order_id: The order ID
            business_id: Restaurant ID
            previous_status: Previous status before cancellation
            user_id: Customer user ID
            performed_by: Dict with 'email' and 'user_type' if cancelled via dashboard

        Returns:
            Created history entry ID
        """
        suffix = self._format_performed_by_suffix(performed_by)
        base_summary = f"Order #{order_id} cancelled (was: {previous_status})"
        change_summary = f"{base_summary}{suffix}"

        return self.log_activity(
            activity_type="order",
            action="cancelled",
            business_id=business_id,
            user_id=user_id,
            order_id=order_id,
            previous_value={"status": previous_status},
            new_value={"status": "cancelled"},
            change_summary=change_summary[:500],
        )

    def log_reservation_created(
        self,
        booking_id: int,
        business_id: int,
        reservation_data: Dict[str, Any],
        user_id: Optional[int] = None,
        performed_by: Optional[Dict[str, Any]] = None,
    ) -> int:
        """
        Log reservation creation.

        Args:
            booking_id: The created reservation ID
            business_id: Restaurant ID
            reservation_data: Reservation data including party_size, status, etc.
            user_id: Customer user ID
            performed_by: Dict with 'email' and 'user_type' if created via dashboard

        Returns:
            Created history entry ID
        """
        suffix = self._format_performed_by_suffix(performed_by)
        party_size = reservation_data.get("party_size", "?")
        base_summary = f"Reservation #{booking_id} created for {party_size} guests"
        change_summary = f"{base_summary}{suffix}"

        return self.log_activity(
            activity_type="reservation",
            action="created",
            business_id=business_id,
            user_id=user_id,
            booking_id=booking_id,
            new_value=reservation_data,
            change_summary=change_summary[:500],
        )

    def log_reservation_updated(
        self,
        booking_id: int,
        business_id: int,
        previous_data: Dict[str, Any],
        new_data: Dict[str, Any],
        user_id: Optional[int] = None,
        performed_by: Optional[Dict[str, Any]] = None,
    ) -> int:
        """
        Log reservation update.

        Args:
            booking_id: The reservation ID
            business_id: Restaurant ID
            previous_data: Previous reservation state
            new_data: New reservation state
            user_id: Customer user ID
            performed_by: Dict with 'email' and 'user_type' if updated via dashboard

        Returns:
            Created history entry ID
        """
        # Build change summary
        changes = []
        for key in new_data:
            if key in previous_data and previous_data[key] != new_data[key]:
                changes.append(f"{key}: {previous_data[key]} → {new_data[key]}")

        base_summary = (
            f"Reservation #{booking_id} updated: " + ", ".join(changes)
            if changes
            else f"Reservation #{booking_id} updated"
        )
        suffix = self._format_performed_by_suffix(performed_by)
        change_summary = f"{base_summary}{suffix}"

        return self.log_activity(
            activity_type="reservation",
            action="updated",
            business_id=business_id,
            user_id=user_id,
            booking_id=booking_id,
            previous_value=previous_data,
            new_value=new_data,
            change_summary=change_summary[:500],
        )

    def log_reservation_status_changed(
        self,
        booking_id: int,
        business_id: int,
        old_status: str,
        new_status: str,
        user_id: Optional[int] = None,
        performed_by: Optional[Dict[str, Any]] = None,
    ) -> int:
        """
        Log reservation status change.

        Args:
            booking_id: The reservation ID
            business_id: Restaurant ID
            old_status: Previous status
            new_status: New status
            user_id: Customer user ID
            performed_by: Dict with 'email' and 'user_type' if changed via dashboard

        Returns:
            Created history entry ID
        """
        suffix = self._format_performed_by_suffix(performed_by)
        base_summary = f"Reservation #{booking_id} status changed: {old_status} → {new_status}"
        change_summary = f"{base_summary}{suffix}"

        return self.log_activity(
            activity_type="reservation",
            action="status_changed",
            business_id=business_id,
            user_id=user_id,
            booking_id=booking_id,
            previous_value={"status": old_status},
            new_value={"status": new_status},
            change_summary=change_summary[:500],
        )

    def log_reservation_cancelled(
        self,
        booking_id: int,
        business_id: int,
        previous_status: str,
        user_id: Optional[int] = None,
        performed_by: Optional[Dict[str, Any]] = None,
    ) -> int:
        """
        Log reservation cancellation.

        Args:
            booking_id: The reservation ID
            business_id: Restaurant ID
            previous_status: Previous status before cancellation
            user_id: Customer user ID
            performed_by: Dict with 'email' and 'user_type' if cancelled via dashboard

        Returns:
            Created history entry ID
        """
        suffix = self._format_performed_by_suffix(performed_by)
        base_summary = f"Reservation #{booking_id} cancelled (was: {previous_status})"
        change_summary = f"{base_summary}{suffix}"

        return self.log_activity(
            activity_type="reservation",
            action="cancelled",
            business_id=business_id,
            user_id=user_id,
            booking_id=booking_id,
            previous_value={"status": previous_status},
            new_value={"status": "cancelled"},
            change_summary=change_summary[:500],
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
        # Check if order exists and get business_id
        business_id = self.history_repo.get_order_business_id(order_id)
        if business_id is None:
            raise ValueError(f"Order with ID {order_id} not found")

        entries = self.history_repo.get_history_by_order(order_id, limit, offset)
        total = self.history_repo.count_history_by_order(order_id)

        return {
            "order_id": order_id,
            "business_id": business_id,
            "entries": entries,
            "total": total,
            "limit": limit,
            "offset": offset,
        }

    def get_reservation_history(
        self,
        booking_id: int,
        limit: int = 100,
        offset: int = 0,
    ) -> Dict[str, Any]:
        """
        Get activity history for a reservation.

        Args:
            booking_id: Reservation ID
            limit: Maximum results
            offset: Pagination offset

        Returns:
            History entries with pagination info

        Raises:
            ValueError: If reservation not found
        """
        # Check if reservation exists and get business_id
        business_id = self.history_repo.get_reservation_business_id(booking_id)
        if business_id is None:
            raise ValueError(f"Reservation with ID {booking_id} not found")

        entries = self.history_repo.get_history_by_reservation(booking_id, limit, offset)
        total = self.history_repo.count_history_by_reservation(booking_id)

        return {
            "booking_id": booking_id,
            "business_id": business_id,
            "entries": entries,
            "total": total,
            "limit": limit,
            "offset": offset,
        }

    def get_order_business_id(self, order_id: int) -> Optional[int]:
        """Get business_id for an order (for RBAC checks)."""
        return self.history_repo.get_order_business_id(order_id)

    def get_reservation_business_id(self, booking_id: int) -> Optional[int]:
        """Get business_id for a reservation (for RBAC checks)."""
        return self.history_repo.get_reservation_business_id(booking_id)
