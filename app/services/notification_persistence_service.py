"""
Notification Persistence Service for the persistent notification system.
Builds human-readable title/message and delegates to MySQLNotificationRepository.
"""

from __future__ import annotations

import logging
from datetime import datetime as dt_type
from typing import Any, Dict, List, Optional, Tuple

from app.repositories.mysql_notification_repo import MySQLNotificationRepository
from app.services.sse_service import (
    EscalationEventSubtype,
    OrderEventSubtype,
    ReservationEventSubtype,
    SSEEventType,
    SystemEventSubtype,
)

logger = logging.getLogger(__name__)

VALID_TYPES = {
    SSEEventType.ORDER.value,
    SSEEventType.RESERVATION.value,
    SSEEventType.ESCALATION.value,
    SSEEventType.SYSTEM.value,
}
VALID_ORDER_SUBTYPES = {e.value for e in OrderEventSubtype}
VALID_RESERVATION_SUBTYPES = {e.value for e in ReservationEventSubtype}
VALID_ESCALATION_SUBTYPES = {e.value for e in EscalationEventSubtype}
VALID_SYSTEM_SUBTYPES = {e.value for e in SystemEventSubtype}


def _format_datetime(dt_str: Optional[str]) -> str:
    """Parse ISO datetime string and return human-readable format (e.g. Feb 11, 2026 at 4:00 AM).
    Handles UTC 'Z' suffix; timezone conversion for display is left to the frontend."""
    if not dt_str:
        return ""
    try:
        s = dt_str.replace("Z", "+00:00") if isinstance(dt_str, str) else str(dt_str)
        dt = dt_type.fromisoformat(s)
        hour12 = dt.hour % 12 or 12
        am_pm = "AM" if dt.hour < 12 else "PM"
        return dt.strftime("%b %d, %Y at ") + f"{hour12}:{dt.minute:02d} {am_pm}"
    except (ValueError, TypeError):
        return str(dt_str)


class NotificationPersistenceService:
    """Service layer for persistent notification create/read/update."""

    def __init__(self, repo: Optional[MySQLNotificationRepository] = None) -> None:
        self._repo = repo or MySQLNotificationRepository()

    @staticmethod
    def build_notification_title(type: str, subtype: str, data: Optional[Dict[str, Any]]) -> str:
        """Generate human-readable notification title from type/subtype/data."""
        data = data or {}
        if type == "order":
            order_id = data.get("order_id", "?")
            if subtype == "new_order":
                name = data.get("customer_name") or ""
                return f"New Order #{order_id} — {name}" if name else f"New Order #{order_id}"
            if subtype == "order_updated":
                status = (data.get("status") or "").strip().lower()
                if status == "confirmed":
                    return f"Order #{order_id} Confirmed"
                if status == "preparing":
                    return f"Order #{order_id} Being Prepared"
                if status == "ready":
                    return f"Order #{order_id} Ready for Pickup"
                if status == "completed":
                    return f"Order #{order_id} Completed"
                if status == "cancelled":
                    return f"Order #{order_id} Cancelled"
                return f"Order #{order_id} Updated — {data.get('status', 'updated')}"
            if subtype == "order_cancelled":
                return f"Order #{order_id} Cancelled"
        if type == "reservation":
            res_id = data.get("reservation_id", "?")
            name = data.get("name") or ""
            suffix = f" — {name}" if name else f" #{res_id}"
            if subtype == "new_reservation":
                party = data.get("party_size")
                if name and party is not None:
                    return f"New Reservation — {name}, Party of {party}"
                return f"New Reservation{suffix}"
            if subtype == "reservation_updated":
                status = (data.get("status") or "").strip().lower()
                if status == "confirmed":
                    return f"Reservation Confirmed{suffix}"
                if status == "cancelled":
                    return f"Reservation Cancelled{suffix}"
                if status == "no_show":
                    return f"Reservation No-Show{suffix}"
                if status == "completed":
                    return f"Reservation Completed{suffix}"
                return f"Reservation #{res_id} Updated"
            if subtype == "reservation_cancelled":
                return f"Reservation Cancelled{suffix}"
        if type == "escalation":
            if subtype == "user_requested":
                return "Escalation — Customer Requested Human"
            if subtype == "internal_server_error":
                return "⚠ Escalation — System Error During Call"
            if subtype == "suspected_spam":
                return "Escalation — Suspected Spam Call"
            if subtype == "sms_redirect_failed":
                return "Escalation — SMS Redirect Failed"
            if subtype == "kill_switch_redirected":
                return "Escalation — Kill Switch Redirected"
        if type == "system":
            if subtype == "kill_switch_toggled":
                enabled = bool(data.get("enabled"))
                return "System — Kill Switch Enabled" if enabled else "System — Kill Switch Disabled"
            if subtype == "kill_switch_bulk_updated":
                enabled = bool(data.get("enabled"))
                return "System — Kill Switch Bulk Enabled" if enabled else "System — Kill Switch Bulk Disabled"
        return f"{type}/{subtype}"

    @staticmethod
    def build_notification_message(type: str, subtype: str, data: Optional[Dict[str, Any]]) -> str:
        """Generate short contextual message from event data."""
        data = data or {}
        if type == "order":
            order_id = data.get("order_id", "?")
            if subtype == "new_order":
                name = data.get("customer_name")
                total = data.get("total_amount")
                status = data.get("status", "pending")
                if name is not None and total is not None:
                    try:
                        amount_str = f"${float(total):.2f}"
                    except (TypeError, ValueError):
                        amount_str = str(total)
                    return f"{name} placed a new order for {amount_str}. Status: {status}."
                return f"New order #{order_id} received. Status: {status}."
            if subtype == "order_updated":
                status = (data.get("status") or "").strip().lower()
                if status == "confirmed":
                    return f"Order #{order_id} has been confirmed and is queued for preparation."
                if status == "preparing":
                    return f"Order #{order_id} is now being prepared in the kitchen."
                if status == "ready":
                    return f"Order #{order_id} is ready for customer pickup."
                if status == "completed":
                    return f"Order #{order_id} has been completed and picked up."
                if status == "cancelled":
                    return f"Order #{order_id} has been cancelled."
                return f"Order #{order_id} status changed to {data.get('status', 'unknown')}."
            if subtype == "order_cancelled":
                return f"Order #{order_id} has been cancelled."
        if type == "reservation":
            res_id = data.get("reservation_id", "?")
            name = data.get("name") or ""
            party_size = data.get("party_size")
            date_time = data.get("date_time")
            formatted_date = _format_datetime(str(date_time) if date_time is not None else "")
            conf = data.get("confirmation_number", "")
            status = (data.get("status") or "").strip().lower()
            if subtype == "new_reservation":
                if name and party_size is not None and formatted_date and conf:
                    return f"{name} booked a table for {party_size} on {formatted_date}. Confirmation: {conf}."
                return f"New reservation #{res_id} received. Status: {data.get('status', 'pending')}."
            if subtype == "reservation_updated" or subtype == "reservation_cancelled":
                if status == "confirmed" and name and formatted_date:
                    return f"{name}'s reservation for {party_size} on {formatted_date} has been confirmed."
                if status == "cancelled" and name and formatted_date:
                    return f"{name}'s reservation for {party_size} on {formatted_date} has been cancelled."
                if status == "no_show" and name and formatted_date:
                    return f"{name} did not show up for their reservation for {party_size} on {formatted_date}."
                if status == "completed" and name and formatted_date:
                    return f"{name}'s reservation for {party_size} on {formatted_date} has been completed."
                return f"Reservation #{res_id} status changed to {data.get('status', 'unknown')}."
        if type == "escalation":
            reason = data.get("reason") or ""
            caller = data.get("caller_phone") or ""
            urgency = data.get("urgency") or "standard"
            if subtype == "user_requested":
                msg = f"{reason} Caller: {caller}. Urgency: {urgency}."
                return msg.strip() or "Customer requested human."
            if subtype == "internal_server_error":
                return f"A system error occurred during the call. {reason} Caller: {caller}.".strip()
            if subtype == "suspected_spam":
                return f"A call was flagged as suspected spam. {reason} Caller: {caller}.".strip()
            if subtype == "sms_redirect_failed":
                redirect_type = data.get("redirect_type") or "request"
                return f"Could not send SMS redirect for {redirect_type}. Caller: {caller}. {reason}".strip()
            if subtype == "kill_switch_redirected":
                return (
                    f"Call was redirected to staff because kill switch is enabled. Caller: {caller}. {reason}".strip()
                )
        if type == "system":
            if subtype == "kill_switch_toggled":
                state = "enabled" if bool(data.get("enabled")) else "disabled"
                actor_type = data.get("actor_type") or "system"
                actor_email = data.get("actor_email")
                actor_label = actor_email or actor_type
                return f"Kill switch was {state} by {actor_label}."
            if subtype == "kill_switch_bulk_updated":
                state = "enabled" if bool(data.get("enabled")) else "disabled"
                updated_count = int(data.get("updated_count") or 0)
                targeted_count = int(data.get("targeted_count") or 0)
                skipped_count = int(data.get("skipped_count") or 0)
                actor_type = data.get("actor_type") or "system"
                actor_email = data.get("actor_email")
                actor_label = actor_email or actor_type
                return (
                    f"Bulk kill switch {state} by {actor_label}. "
                    f"Updated {updated_count}/{targeted_count} restaurants; skipped {skipped_count}."
                )
        return ""

    def create_notification(
        self,
        restaurant_id: Optional[int],
        type: str,
        subtype: str,
        data: Optional[Dict[str, Any]] = None,
        entity_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Validate type/subtype, build title/message, and persist. Returns created row.
        Failures are logged; caller should not rely on success for critical path.
        """
        try:
            type_lower = (type or "").strip().lower()
            subtype_lower = (subtype or "").strip().lower()
            if type_lower not in VALID_TYPES:
                logger.warning("[Notification] Invalid type=%s, skipping persistence", type)
                return {}
            if restaurant_id is None and type_lower != SSEEventType.SYSTEM.value:
                logger.warning("[Notification] Null restaurant_id is only allowed for type=system; skipping")
                return {}
            if type_lower == SSEEventType.ORDER.value and subtype_lower not in VALID_ORDER_SUBTYPES:
                logger.warning("[Notification] Invalid order subtype=%s, skipping", subtype)
                return {}
            if type_lower == SSEEventType.RESERVATION.value and subtype_lower not in VALID_RESERVATION_SUBTYPES:
                logger.warning("[Notification] Invalid reservation subtype=%s, skipping", subtype)
                return {}
            if type_lower == SSEEventType.ESCALATION.value and subtype_lower not in VALID_ESCALATION_SUBTYPES:
                logger.warning("[Notification] Invalid escalation subtype=%s, skipping", subtype)
                return {}
            if type_lower == SSEEventType.SYSTEM.value and subtype_lower not in VALID_SYSTEM_SUBTYPES:
                logger.warning("[Notification] Invalid system subtype=%s, skipping", subtype)
                return {}

            title = self.build_notification_title(type_lower, subtype_lower, data)
            message = self.build_notification_message(type_lower, subtype_lower, data)
            row = self._repo.create_notification(
                restaurant_id=restaurant_id,
                type=type_lower,
                subtype=subtype_lower,
                title=title,
                message=message or None,
                data=data,
                entity_id=entity_id,
            )
            logger.info(
                "[Notification] Created notification id=%s restaurant_id=%s type=%s",
                row.get("id"),
                restaurant_id,
                type_lower,
            )
            return row
        except Exception as e:
            logger.exception("[Notification] create_notification failed: %s", e)
            return {}

    def create_system_kill_switch_toggled_bulk(self, events: List[Dict[str, Any]]) -> int:
        """
        Bulk create system/kill_switch_toggled notifications for restaurant-scoped dashboards.
        """
        try:
            rows: List[Dict[str, Any]] = []
            for event in events:
                restaurant_id = event.get("restaurant_id")
                if restaurant_id is None:
                    logger.warning("[Notification] Missing restaurant_id in bulk kill-switch event; skipping row")
                    continue
                data = event.get("data") or {}
                rows.append(
                    {
                        "restaurant_id": int(restaurant_id),
                        "type": SSEEventType.SYSTEM.value,
                        "subtype": SystemEventSubtype.KILL_SWITCH_TOGGLED.value,
                        "title": self.build_notification_title(
                            SSEEventType.SYSTEM.value,
                            SystemEventSubtype.KILL_SWITCH_TOGGLED.value,
                            data,
                        ),
                        "message": self.build_notification_message(
                            SSEEventType.SYSTEM.value,
                            SystemEventSubtype.KILL_SWITCH_TOGGLED.value,
                            data,
                        )
                        or None,
                        "data": data,
                        "entity_id": event.get("entity_id"),
                    }
                )

            if not rows:
                return 0
            return self._repo.create_notifications_bulk(rows)
        except Exception as e:
            logger.exception("[Notification] create_system_kill_switch_toggled_bulk failed: %s", e)
            return 0

    def get_notifications(
        self,
        restaurant_id: Optional[int] = None,
        is_read: Optional[bool] = None,
        type: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
        exclude_bulk_system_kill_switch_toggled: bool = False,
    ) -> Tuple[List[Dict[str, Any]], int]:
        """List notifications with optional filters. Returns (rows, total). restaurant_id=None for admin (all restaurants)."""
        try:
            return self._repo.get_notifications(
                restaurant_id=restaurant_id,
                is_read=is_read,
                type=type,
                limit=limit,
                offset=offset,
                exclude_bulk_system_kill_switch_toggled=exclude_bulk_system_kill_switch_toggled,
            )
        except Exception as e:
            logger.exception("[Notification] get_notifications failed: %s", e)
            return [], 0

    def get_notification_by_id(self, notification_id: int) -> Optional[Dict[str, Any]]:
        """Fetch a single notification by ID."""
        try:
            return self._repo.get_notification_by_id(notification_id)
        except Exception as e:
            logger.exception("[Notification] get_notification_by_id failed: %s", e)
            return None

    def mark_as_read(self, notification_id: int) -> Optional[Dict[str, Any]]:
        """Mark one notification as read. Returns updated row or None."""
        try:
            return self._repo.mark_as_read(notification_id)
        except Exception as e:
            logger.exception("[Notification] mark_as_read failed: %s", e)
            return None

    def mark_all_as_read(self, restaurant_id: int, type: Optional[str] = None) -> int:
        """Mark all (optionally filtered by type) as read. Returns count updated."""
        try:
            return self._repo.mark_all_as_read(restaurant_id, type=type)
        except Exception as e:
            logger.exception("[Notification] mark_all_as_read failed: %s", e)
            return 0

    def get_unread_count(self, restaurant_id: int) -> int:
        """Return unread count for the restaurant."""
        try:
            return self._repo.get_unread_count(restaurant_id)
        except Exception as e:
            logger.exception("[Notification] get_unread_count failed: %s", e)
            return 0
