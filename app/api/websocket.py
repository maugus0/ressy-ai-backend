from fastapi import WebSocket

from app.services.websocket_service import WebSocketService
from app.utils.logging_config import get_logger

websocket_service = WebSocketService()
logger = get_logger(__name__)


async def twilio_websocket_handler(websocket: WebSocket):
    caller_number = websocket.query_params.get("fromNumber")
    restaurant_twilio_number = websocket.query_params.get("toNumber")
    await websocket_service.twilio_websocket_handler(
        websocket,
        restaurant_twilio_number=restaurant_twilio_number,
        caller_number=caller_number,
    )


async def shutdown_websockets() -> None:
    await websocket_service.shutdown()
