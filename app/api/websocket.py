from fastapi import WebSocket
from app.middleware.auth_middleware import verify_cognito_token
from app.services.websocket_service import WebSocketService

websocket_service = WebSocketService()


async def twilio_websocket_handler(websocket: WebSocket):
    user_id = "demo-user"
    try:
        token = websocket.query_params.get("token")
        if token:
            payload = verify_cognito_token(token)
            user_id = payload.get("sub", user_id)
    except Exception as e:
        print(f"[WS] token verification failed, fallback user_id. Error: {e}")

    await websocket_service.twilio_websocket_handler(websocket, user_id)
