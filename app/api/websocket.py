from fastapi import WebSocket

from app.middleware.auth_middleware import verify_cognito_token
from app.services.websocket_service import WebSocketService

websocket_service = WebSocketService()


async def twilio_websocket_handler(websocket: WebSocket):
    user_id = "demo-user"
    caller_number = websocket.query_params.get("fromNumber")
    restaurant_twilio_number = websocket.query_params.get("toNumber")
    try:
        token = websocket.query_params.get("token")
        if token:
            payload = verify_cognito_token(token)
            user_id = payload.get("sub", user_id)
    except Exception as e:
        print(f"[WS] token verification failed, fallback user_id. Error: {e}")
    print(
        f"[WS] Received incoming call for restaurant_twilio_number={restaurant_twilio_number}, user={user_id}, caller_number={caller_number}"
    )
    await websocket_service.twilio_websocket_handler(
        websocket,
        user_id,
        restaurant_twilio_number=restaurant_twilio_number,
        caller_number=caller_number,
    )


async def shutdown_websockets() -> None:
    await websocket_service.shutdown()
