"""
Server-Sent Events (SSE) Service for real-time event broadcasting.

Supports the following event types:
- Escalation: user_requested, internal_server_error, suspected_spam
- Order: new_order, order_updated, order_cancelled
- Reservation: new_reservation, reservation_updated, reservation_cancelled
"""

import asyncio
import json
import logging
import uuid
from datetime import date, datetime, time, timezone
from decimal import Decimal
from enum import Enum
from typing import Any, AsyncGenerator, Dict, List, Optional, Set

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class SSEJSONEncoder(json.JSONEncoder):
    """
    Custom JSON encoder for SSE events.

    Handles serialization of non-JSON-native types:
    - datetime objects -> ISO format string
    - date objects -> ISO format string
    - time objects -> ISO format string
    - Decimal objects -> float
    - Enum objects -> value
    """

    def default(self, obj: Any) -> Any:
        if isinstance(obj, datetime):
            return obj.isoformat()
        if isinstance(obj, date):
            return obj.isoformat()
        if isinstance(obj, time):
            return obj.isoformat()
        if isinstance(obj, Decimal):
            return float(obj)
        if isinstance(obj, Enum):
            return obj.value
        return super().default(obj)


class SSEEventType(str, Enum):
    """Main SSE event types."""

    ESCALATION = "escalation"
    ORDER = "order"
    RESERVATION = "reservation"
    HEARTBEAT = "heartbeat"


class EscalationEventSubtype(str, Enum):
    """Subtypes for escalation events."""

    USER_REQUESTED = "user_requested"
    INTERNAL_SERVER_ERROR = "internal_server_error"
    SUSPECTED_SPAM = "suspected_spam"


class OrderEventSubtype(str, Enum):
    """Subtypes for order events."""

    NEW_ORDER = "new_order"
    ORDER_UPDATED = "order_updated"
    ORDER_CANCELLED = "order_cancelled"


class ReservationEventSubtype(str, Enum):
    """Subtypes for reservation events."""

    NEW_RESERVATION = "new_reservation"
    RESERVATION_UPDATED = "reservation_updated"
    RESERVATION_CANCELLED = "reservation_cancelled"


class SSEEvent(BaseModel):
    """SSE Event model."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    event_type: SSEEventType
    subtype: Optional[str] = None
    restaurant_id: Optional[int] = None
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"))
    data: Dict[str, Any] = Field(default_factory=dict)

    def to_sse_format(self) -> str:
        """
        Convert event to SSE format string.

        Uses SSEJSONEncoder to handle non-JSON-native types like datetime,
        date, time, Decimal, and Enum objects.
        """
        event_data = {
            "id": self.id,
            "event_type": self.event_type.value,
            "subtype": self.subtype,
            "restaurant_id": self.restaurant_id,
            "timestamp": self.timestamp,
            "data": self.data,
        }
        return f"id: {self.id}\nevent: {self.event_type.value}\ndata: {json.dumps(event_data, cls=SSEJSONEncoder)}\n\n"


class SSEConnection:
    """Represents a single SSE connection."""

    def __init__(
        self,
        connection_id: str,
        restaurant_id: Optional[int] = None,
        user_id: Optional[str] = None,
        is_admin: bool = False,
    ):
        self.connection_id = connection_id
        self.restaurant_id = restaurant_id
        self.user_id = user_id
        self.is_admin = is_admin
        self.queue: asyncio.Queue = asyncio.Queue(maxsize=100)
        self.connected = True
        self.created_at = datetime.now(timezone.utc)

    async def send(self, event: SSEEvent):
        """Add event to connection queue. Disconnect if queue is full."""
        if self.connected:
            try:
                self.queue.put_nowait(event)
            except asyncio.QueueFull:
                logger.warning(f"[SSE] Queue full for connection {self.connection_id}, disconnecting slow client")
                await self.disconnect()

    async def disconnect(self):
        """Mark connection as disconnected."""
        self.connected = False


class SSEService:
    """
    Service for managing Server-Sent Events.

    Features:
    - Connection management per restaurant
    - Admin connections can receive events from all restaurants
    - Event broadcasting with filtering
    - Heartbeat mechanism for connection keep-alive
    """

    _instance = None
    _lock: Optional[asyncio.Lock] = None

    def __new__(cls):
        """Singleton pattern for SSE service."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        # Initialize lock at runtime when event loop is available
        if SSEService._lock is None:
            SSEService._lock = asyncio.Lock()
        self.connections: Dict[str, SSEConnection] = {}
        self.restaurant_connections: Dict[int, Set[str]] = {}
        self.admin_connections: Set[str] = set()
        self._heartbeat_interval = 30  # seconds
        self._heartbeat_task: Optional[asyncio.Task] = None

    async def start_heartbeat(self):
        """Start the heartbeat task."""
        if self._heartbeat_task is None or self._heartbeat_task.done():
            self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())

    async def _heartbeat_loop(self):
        """Send periodic heartbeat events to all connections."""
        while True:
            try:
                await asyncio.sleep(self._heartbeat_interval)
                heartbeat = SSEEvent(
                    event_type=SSEEventType.HEARTBEAT,
                    data={"message": "ping"},
                )
                await self._broadcast_to_all(heartbeat)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.warning("[SSE] Heartbeat error: %s", e)

    async def connect(
        self,
        restaurant_id: Optional[int] = None,
        user_id: Optional[str] = None,
        is_admin: bool = False,
    ) -> SSEConnection:
        """
        Create a new SSE connection.

        Args:
            restaurant_id: Restaurant ID for filtering (None for admin global access)
            user_id: User identifier
            is_admin: Whether the connection is from an admin

        Returns:
            SSEConnection instance
        """
        connection_id = str(uuid.uuid4())
        connection = SSEConnection(
            connection_id=connection_id,
            restaurant_id=restaurant_id,
            user_id=user_id,
            is_admin=is_admin,
        )

        async with self._lock:
            self.connections[connection_id] = connection

            if is_admin:
                self.admin_connections.add(connection_id)
            elif restaurant_id is not None:
                if restaurant_id not in self.restaurant_connections:
                    self.restaurant_connections[restaurant_id] = set()
                self.restaurant_connections[restaurant_id].add(connection_id)

        # Start heartbeat if not running
        await self.start_heartbeat()

        logger.info("[SSE] New connection: %s (restaurant_id=%s, is_admin=%s)", connection_id, restaurant_id, is_admin)
        return connection

    async def disconnect(self, connection_id: str):
        """Disconnect and remove a connection."""
        async with self._lock:
            if connection_id in self.connections:
                connection = self.connections[connection_id]
                await connection.disconnect()

                # Remove from admin set
                self.admin_connections.discard(connection_id)

                # Remove from restaurant set
                if connection.restaurant_id is not None:
                    if connection.restaurant_id in self.restaurant_connections:
                        self.restaurant_connections[connection.restaurant_id].discard(connection_id)
                        if not self.restaurant_connections[connection.restaurant_id]:
                            del self.restaurant_connections[connection.restaurant_id]

                del self.connections[connection_id]
                logger.info("[SSE] Disconnected: %s", connection_id)

    async def _broadcast_to_all(self, event: SSEEvent):
        """Broadcast event to all connections."""
        async with self._lock:
            connections = list(self.connections.values())
        for connection in connections:
            if connection.connected:
                await connection.send(event)

    async def _broadcast_to_restaurant(self, restaurant_id: int, event: SSEEvent):
        """Broadcast event to connections for a specific restaurant."""
        # Get a consistent snapshot of connection IDs under the lock
        async with self._lock:
            connection_ids: Set[str] = set()
            if restaurant_id in self.restaurant_connections:
                connection_ids.update(self.restaurant_connections[restaurant_id])
            connection_ids.update(self.admin_connections)
        # Now iterate and send events outside the lock
        for connection_id in connection_ids:
            connection = self.connections.get(connection_id)
            if connection and connection.connected:
                await connection.send(event)

    async def emit_event(
        self,
        event_type: SSEEventType,
        subtype: Optional[str] = None,
        restaurant_id: Optional[int] = None,
        data: Optional[Dict[str, Any]] = None,
    ) -> SSEEvent:
        """
        Emit an SSE event.

        Args:
            event_type: Type of event
            subtype: Event subtype
            restaurant_id: Target restaurant ID (None for global broadcast)
            data: Event data payload

        Returns:
            The emitted SSEEvent
        """
        event = SSEEvent(
            event_type=event_type,
            subtype=subtype,
            restaurant_id=restaurant_id,
            data=data or {},
        )

        if restaurant_id is not None:
            await self._broadcast_to_restaurant(restaurant_id, event)
        else:
            await self._broadcast_to_all(event)

        logger.info("[SSE] Event emitted: %s/%s to restaurant_id=%s", event_type.value, subtype, restaurant_id)
        return event

    # ---------- Escalation Event Methods ----------

    async def emit_escalation_user_requested(
        self,
        restaurant_id: int,
        call_id: Optional[str] = None,
        caller_phone: Optional[str] = None,
        reason: Optional[str] = None,
        data: Optional[Dict[str, Any]] = None,
    ) -> SSEEvent:
        """
        Emit an escalation event when user requests human assistance.

        Args:
            restaurant_id: Restaurant ID
            call_id: Call identifier
            caller_phone: Caller's phone number
            reason: Reason for escalation
            data: Additional data

        Returns:
            The emitted SSEEvent
        """
        event_data = {
            "call_id": call_id,
            "caller_phone": caller_phone,
            "reason": reason or "User requested human assistance",
            **(data or {}),
        }
        return await self.emit_event(
            event_type=SSEEventType.ESCALATION,
            subtype=EscalationEventSubtype.USER_REQUESTED.value,
            restaurant_id=restaurant_id,
            data=event_data,
        )

    async def emit_escalation_server_error(
        self,
        restaurant_id: int,
        call_id: Optional[str] = None,
        error_message: Optional[str] = None,
        error_code: Optional[str] = None,
        data: Optional[Dict[str, Any]] = None,
    ) -> SSEEvent:
        """
        Emit an escalation event for internal server errors.

        Args:
            restaurant_id: Restaurant ID
            call_id: Call identifier
            error_message: Error description
            error_code: Error code
            data: Additional data

        Returns:
            The emitted SSEEvent
        """
        event_data = {
            "call_id": call_id,
            "error_message": error_message or "Internal server error occurred",
            "error_code": error_code,
            **(data or {}),
        }
        return await self.emit_event(
            event_type=SSEEventType.ESCALATION,
            subtype=EscalationEventSubtype.INTERNAL_SERVER_ERROR.value,
            restaurant_id=restaurant_id,
            data=event_data,
        )

    async def emit_escalation_suspected_spam(
        self,
        restaurant_id: int,
        call_id: Optional[str] = None,
        caller_phone: Optional[str] = None,
        spam_score: Optional[float] = None,
        indicators: Optional[List[str]] = None,
        data: Optional[Dict[str, Any]] = None,
    ) -> SSEEvent:
        """
        Emit an escalation event for suspected spam calls.

        Args:
            restaurant_id: Restaurant ID
            call_id: Call identifier
            caller_phone: Caller's phone number
            spam_score: Spam probability score
            indicators: List of spam indicators
            data: Additional data

        Returns:
            The emitted SSEEvent
        """
        event_data = {
            "call_id": call_id,
            "caller_phone": caller_phone,
            "spam_score": spam_score,
            "indicators": indicators or [],
            **(data or {}),
        }
        return await self.emit_event(
            event_type=SSEEventType.ESCALATION,
            subtype=EscalationEventSubtype.SUSPECTED_SPAM.value,
            restaurant_id=restaurant_id,
            data=event_data,
        )

    # ---------- Order Event Methods ----------

    async def emit_order_event(
        self,
        restaurant_id: int,
        order_id: int,
        subtype: OrderEventSubtype,
        data: Optional[Dict[str, Any]] = None,
    ) -> SSEEvent:
        """
        Emit an order-related event.

        Args:
            restaurant_id: Restaurant ID
            order_id: Order ID
            subtype: Order event subtype
            data: Additional event data

        Returns:
            The emitted SSEEvent
        """
        event_data = {
            "order_id": order_id,
            **(data or {}),
        }
        return await self.emit_event(
            event_type=SSEEventType.ORDER,
            subtype=subtype.value,
            restaurant_id=restaurant_id,
            data=event_data,
        )

    # ---------- Reservation Event Methods ----------

    async def emit_reservation_event(
        self,
        restaurant_id: int,
        reservation_id: int,
        subtype: ReservationEventSubtype,
        data: Optional[Dict[str, Any]] = None,
    ) -> SSEEvent:
        """
        Emit a reservation-related event.

        Args:
            restaurant_id: Restaurant ID
            reservation_id: Reservation ID
            subtype: Reservation event subtype
            data: Additional event data

        Returns:
            The emitted SSEEvent
        """
        event_data = {
            "reservation_id": reservation_id,
            **(data or {}),
        }
        return await self.emit_event(
            event_type=SSEEventType.RESERVATION,
            subtype=subtype.value,
            restaurant_id=restaurant_id,
            data=event_data,
        )

    # ---------- Event Stream Generator ----------

    async def event_stream(self, connection: SSEConnection) -> AsyncGenerator[str, None]:
        """
        Generate SSE events for a connection.

        Args:
            connection: SSE connection

        Yields:
            SSE formatted event strings
        """
        try:
            while connection.connected:
                try:
                    # Wait for event with timeout for heartbeat
                    event = await asyncio.wait_for(connection.queue.get(), timeout=self._heartbeat_interval)
                    yield event.to_sse_format()
                except asyncio.TimeoutError:
                    # Send heartbeat if no events
                    heartbeat = SSEEvent(
                        event_type=SSEEventType.HEARTBEAT,
                        data={"message": "ping"},
                    )
                    yield heartbeat.to_sse_format()
        except asyncio.CancelledError:
            pass
        finally:
            await self.disconnect(connection.connection_id)

    def get_connection_stats(self) -> Dict[str, Any]:
        """Get connection statistics."""
        return {
            "total_connections": len(self.connections),
            "admin_connections": len(self.admin_connections),
            "restaurants_with_connections": len(self.restaurant_connections),
            "connections_per_restaurant": {str(rid): len(cids) for rid, cids in self.restaurant_connections.items()},
        }

    async def shutdown(self):
        """Shutdown SSE service and disconnect all connections."""
        logger.info("[SSE] Shutting down...")

        # Cancel heartbeat task
        if self._heartbeat_task and not self._heartbeat_task.done():
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass

        # Disconnect all connections
        for connection_id in list(self.connections.keys()):
            await self.disconnect(connection_id)

        logger.info("[SSE] Shutdown complete")
