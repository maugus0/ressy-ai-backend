from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import asyncio
import base64
import json
import websockets
import os
import ssl
import certifi
from dotenv import load_dotenv

from app.routes import auth, calls, admin
from app.utils.security import JWTManager
from app.services.deepgram_service import DeepGramService  # ADD THIS
from app.models.database import CallDatabase  # ADD THIS

load_dotenv()

app = FastAPI(title="Voice Agent API", version="1.0.0")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth.router, prefix="/api/auth", tags=["authentication"])
app.include_router(calls.router, prefix="/api/calls", tags=["calls"])
app.include_router(admin.router, prefix="/api/admin", tags=["admin"])

# ADD THIS: Global services
deepgram_service = DeepGramService()
call_db = CallDatabase()

# ---------------- DeepGram STS helpers ----------------
def sts_connect():
    api_key = os.getenv('DEEPGRAM_API_KEY')
    if not api_key:
        raise ValueError("DEEPGRAM_API_KEY environment variable is not set")

    ssl_context = ssl.create_default_context(cafile=certifi.where())

    return websockets.connect(
        "wss://agent.deepgram.com/v1/agent/converse",
        subprotocols=["token", api_key],
        ssl=ssl_context
    )


def load_config():
    # Resolve config.json next to this file
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
    start_time = asyncio.get_event_loop().time()  # ADDED
    
    async for message in sts_ws:
        if isinstance(message, str):
            decoded = json.loads(message)
            print(f"DeepGram Message: {decoded}")
            
            # ADDED: Store transcripts in database
            if decoded.get("type") == "Results" and decoded.get("results"):
                transcript = decoded["results"].get("transcript", "")
                if transcript and call_id:
                    call_db.store_transcript(call_id, transcript, decoded.get("is_final", False))
            
            await handle_text_message(decoded, twilio_ws, sts_ws, streamsid)
            continue

        # Audio → Twilio
        media_message = {
            "event": "media",
            "streamSid": streamsid,
            "media": {"payload": base64.b64encode(message).decode("ascii")}
        }
        await twilio_ws.send_json(media_message)
    
    # ADDED: Calculate call duration and cost
    end_time = asyncio.get_event_loop().time()
    duration_seconds = int(end_time - start_time)
    if call_id and user_id:
        total_cost = call_db.update_call_cost(call_id, duration_seconds)


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


# ---------------- WebSocket Endpoint ----------------
@app.websocket("/twilio")
async def twilio_websocket(websocket: WebSocket):
    await websocket.accept()
    user_id = "demo-user"
    # Optional JWT token support: /twilio?token=<jwt>
    try:
        token = websocket.query_params.get("token")
        if token:
            payload = JWTManager().verify_token(token)
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

            # ADDED: Create call session
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


# ---------------- Health Routes ----------------
@app.get("/")
async def root():
    return {"message": "Voice Agent API running", "status": "healthy"}


@app.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": asyncio.get_event_loop().time()}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5001, reload=True)