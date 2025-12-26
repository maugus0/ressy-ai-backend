import asyncio

from fastapi import WebSocket

from app.services.websocket_service import WebSocketService
from app.utils.logging_config import get_logger

logger = get_logger(__name__)

# Track all active WebSocket services to handle concurrent connections
# Using a set to allow multiple simultaneous connections
_active_services: set[WebSocketService] = set()
_services_lock = asyncio.Lock()


def get_websocket_service() -> WebSocketService:
    """Create a fresh WebSocket service instance per connection."""
    return WebSocketService()


async def twilio_websocket_handler(websocket: WebSocket):
    """
    Handle Twilio WebSocket connections for voice calls.

    Creates a fresh WebSocketService instance per connection to ensure
    database connections are fresh and no stale data is returned.
    """
    caller_number = websocket.query_params.get("fromNumber")
    restaurant_twilio_number = websocket.query_params.get("toNumber")

    # Create fresh service for this WebSocket connection
    websocket_service = get_websocket_service()

    # Register this service for shutdown tracking
    async with _services_lock:
        _active_services.add(websocket_service)

    try:
        await websocket_service.twilio_websocket_handler(
            websocket,
            restaurant_twilio_number=restaurant_twilio_number,
            caller_number=caller_number,
        )
    finally:
        # Unregister this service when connection closes
        async with _services_lock:
            _active_services.discard(websocket_service)


async def shutdown_websockets() -> None:
    """Shutdown all active WebSocket services."""
    async with _services_lock:
        services_to_shutdown = list(_active_services)
        _active_services.clear()

    # Shutdown all services in parallel
    if services_to_shutdown:
        shutdown_tasks = [service.shutdown() for service in services_to_shutdown]
        await asyncio.gather(*shutdown_tasks, return_exceptions=True)
        logger.info("Shutdown %d active WebSocket service(s)", len(services_to_shutdown))
