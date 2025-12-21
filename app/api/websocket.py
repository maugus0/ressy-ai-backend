from fastapi import WebSocket

from app.services.websocket_service import WebSocketService

websocket_service = WebSocketService()


async def twilio_websocket_handler(websocket: WebSocket):
    caller_number = websocket.query_params.get("fromNumber")
    restaurant_twilio_number = websocket.query_params.get("toNumber")
    call_direction = websocket.query_params.get("callDirection", "inbound")
    print(
        f"[WS] Received {call_direction} call for restaurant_twilio_number={restaurant_twilio_number}, caller_number={caller_number}"
    )
    await websocket_service.twilio_websocket_handler(
        websocket,
        restaurant_twilio_number=restaurant_twilio_number,
        caller_number=caller_number,
        call_direction=call_direction,
    )


async def shutdown_websockets() -> None:
    await websocket_service.shutdown()
