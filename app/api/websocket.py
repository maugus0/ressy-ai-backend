from fastapi import WebSocket

from app.services.websocket_service import WebSocketService

websocket_service = WebSocketService()


async def twilio_websocket_handler(websocket: WebSocket):
    caller_number = websocket.query_params.get("fromNumber")
    restaurant_twilio_number = websocket.query_params.get("toNumber")
    print(
        f"[WS] Received incoming call for restaurant_twilio_number={restaurant_twilio_number}, caller_number={caller_number}"
    )
    await websocket_service.twilio_websocket_handler(
        websocket,
        user_id="demo-user",
        restaurant_twilio_number=restaurant_twilio_number,
        caller_number=caller_number,
    )


async def shutdown_websockets() -> None:
    await websocket_service.shutdown()
