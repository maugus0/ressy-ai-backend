import asyncio
import base64
import json
import websockets
import os
import ssl
import certifi
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from app.utils.security import verify_cognito_token
from datetime import datetime
from app.routes import auth, calls, admin, users, menu, restaurants, specials, orders, order_history, transcripts, FAQs
from app.services.deepgram_service import DeepGramService 
from app.models.database import CallDatabase 
from pathlib import Path

env_path = Path(__file__).parent / ".env"
load_dotenv(dotenv_path=env_path)


app = FastAPI(title="Voice Agent API", version="1.0.0")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(calls.router, prefix="/api/v1/calls", tags=["calls"])
app.include_router(admin.router, prefix="/api/v1/admin", tags=["admin"])
app.include_router(users.router, prefix="/api/v1/users", tags=["users"])
app.include_router(menu.router, prefix="/api/v1/menu", tags=["menu"])
app.include_router(restaurants.router, prefix="/api/v1/restaurants", tags=["restaurants"])
app.include_router(specials.router, prefix="/api/v1/specials", tags=["specials"])
app.include_router(orders.router, prefix="/api/v1/orders", tags=["orders"])
app.include_router(order_history.router, prefix="/api/v1/order-history", tags=["order-history"])
app.include_router(transcripts.router, prefix="/api/v1/transcripts", tags=["transcripts"])
app.include_router(FAQs.router, prefix="/api/v1/faqs", tags=["faqs"])

deepgram_service = DeepGramService()
call_db = CallDatabase()


# DeepGram STS helpers
def sts_connect():
    api_key = os.getenv('DEEPGRAM_API_KEY')
    if not api_key:
        raise ValueError("DEEPGRAM_API_KEY environment variable is not set")

    ssl_context = ssl.create_default_context(cafile=certifi.where())

    return websockets.connect(
        "wss://agent.deepgram.com/v1/agent/converse",
        extra_headers={"Authorization": f"Token {api_key}"},
        ssl=ssl_context
    )


def load_config():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    cfg_path = os.path.join(base_dir, "config.json")
    with open(cfg_path, "r", encoding="utf-8") as f:
        return json.load(f)


async def handle_barge_in(decoded, twilio_ws, streamsid):
    if decoded.get("type") == "UserStartedSpeaking":
        clear_message = {"event": "clear", "streamsid": streamsid}
        await twilio_ws.send_json(clear_message)


async def handle_text_message(decoded, twilio_ws, sts_ws, streamsid):
    await handle_barge_in(decoded, twilio_ws, streamsid)


async def sts_sender(sts_ws, audio_queue):
    print("sts_sender started")
    while True:
        chunk = await audio_queue.get()
        await sts_ws.send(chunk)

async def sts_receiver(sts_ws, twilio_ws, streamsid_queue, call_id=None, user_id=None):
    print("sts_receiver started")
    streamsid = await streamsid_queue.get()
    start_time = asyncio.get_event_loop().time()
    message_seq = 0 

    async for message in sts_ws:
        if isinstance(message, str):
            decoded = json.loads(message)
            print(f"DeepGram Message: {decoded}")

            if decoded.get("type") in ["ConversationAudio", "AgentAudioDone"]:
                audio_payload = decoded.get("audio", "")
                if audio_payload:
                    media_message = {
                        "event": "media",
                        "streamSid": streamsid,
                        "media": {"payload": audio_payload}
                    }
                    await twilio_ws.send_json(media_message)

            await handle_text_message(decoded, twilio_ws, sts_ws, streamsid)

            if decoded.get("type") in ["ConversationText", "History"]:
                role = decoded.get("role")
                text = decoded.get("content")
                if text and call_id:
                    message_seq += 1
                    transcript_item = {
                        "call_id": call_id,
                        "message_sequence": message_seq,
                        "speaker": role,
                        "message": text,
                        "timestamp": datetime.utcnow().isoformat()
                    }
                    print(f"[DDB] put transcript: call_id={call_id} seq={message_seq} speaker={role}")
                    call_db._with_retries(call_db.db.transcripts_table.put_item, Item=transcript_item)
            continue

        media_message = {
            "event": "media",
            "streamSid": streamsid,
            "media": {"payload": base64.b64encode(message).decode("ascii")}
        }
        await twilio_ws.send_json(media_message)

    end_time = asyncio.get_event_loop().time()
    duration_seconds = int(end_time - start_time)
    if call_id and user_id:
        call_db.update_call_cost(call_id, duration_seconds)


async def twilio_receiver(twilio_ws, audio_queue, streamsid_queue):
    BUFFER_SIZE = 20 * 160
    inbuffer = bytearray()

    async for message in twilio_ws.iter_text():
        try:
            data = json.loads(message)
            event = data.get("event")

            if event == "start":
                streamsid = data["start"]["streamSid"]
                await streamsid_queue.put(streamsid)
            elif event == "media":
                chunk = base64.b64decode(data["media"]["payload"])
                if data["media"]["track"] == "inbound":
                    inbuffer.extend(chunk)
            elif event == "stop":
                break

            while len(inbuffer) >= BUFFER_SIZE:
                await audio_queue.put(inbuffer[:BUFFER_SIZE])
                inbuffer = inbuffer[BUFFER_SIZE:]

        except Exception as e:
            print(f"Twilio receiver error: {e}")
            break


# WebSocket Endpoint
@app.websocket("/twilio")
async def twilio_websocket(websocket: WebSocket):
    await websocket.accept()
    user_id = "demo-user"
    try:
        token = websocket.query_params.get("token")
        if token:
            payload = verify_cognito_token(token)
            user_id = payload.get("sub", user_id)
    except Exception as e:
        print(f"[WS] token verification failed, using fallback user_id. Error: {e}")
    call_id = None

    audio_queue = asyncio.Queue()
    streamsid_queue = asyncio.Queue()

    try:
        print("Twilio connected!")

        async with sts_connect() as sts_ws:
            print("🔗 Connected to DeepGram STS")
            config_message = load_config()
            await sts_ws.send(json.dumps(config_message))
            print("📤 Sent full config to DeepGram")

            try:
                call_id = call_db.create_call_session(user_id, "twilio-demo", "deepgram-demo")
                print(f"📞 Call session created: {call_id}")
            except Exception as e:
                print(f"[DB] create_call_session error: {e}")
                call_id = None

            await asyncio.gather(
                asyncio.create_task(sts_sender(sts_ws, audio_queue)),
                asyncio.create_task(sts_receiver(sts_ws, websocket, streamsid_queue, call_id, user_id)),
                asyncio.create_task(twilio_receiver(websocket, audio_queue, streamsid_queue)),
                return_exceptions=True
            )

    except WebSocketDisconnect:
        print("Client disconnected")
    except Exception as e:
        print(f"Error in twilio_websocket: {e}")
    finally:
        await websocket.close()
        print("🔌 Twilio connection closed")


# Health Route
@app.get("/")
async def root():
    return {"message": "Voice Agent API running", "status": "healthy"}


@app.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": asyncio.get_event_loop().time()}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5001, reload=True)