from fastapi import WebSocket

from app.services.websocket_service import WebSocketService
from app.utils.logging_config import get_logger

logger = get_logger(__name__)

# Global reference for shutdown - will be set when a connection is active
_active_service: WebSocketService | None = None


def get_websocket_service() -> WebSocketService:
    """Create a fresh WebSocket service instance per connection."""
    return WebSocketService()


async def twilio_websocket_handler(websocket: WebSocket):
    """
    Handle Twilio WebSocket connections for voice calls.

    Creates a fresh WebSocketService instance per connection to ensure
    database connections are fresh and no stale data is returned.
    """
    global _active_service

    caller_number = websocket.query_params.get("fromNumber")
    restaurant_twilio_number = websocket.query_params.get("toNumber")

    # Create fresh service for this WebSocket connection
    websocket_service = get_websocket_service()
    _active_service = websocket_service

    try:
        await websocket_service.twilio_websocket_handler(
            websocket,
            restaurant_twilio_number=restaurant_twilio_number,
            caller_number=caller_number,
        )
    finally:
        _active_service = None


async def shutdown_websockets() -> None:
    """Shutdown any active WebSocket service."""
    if _active_service is not None:
        await _active_service.shutdown()
