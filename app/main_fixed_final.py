
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import asyncio
import base64
import json
import websockets
import os
import ssl
import certifi
from dotenv import load_dotenv

# ✅ FIXED: Use absolute imports without dots
from app.routes import auth, calls, admin
from app.utils.security import get_current_active_user
from app.services.deepgram_service import DeepGramService
from app.models.database import CallDatabase

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

# Global services
deepgram_service = DeepGramService()
call_db = CallDatabase()

# ✅ YOUR ORIGINAL CODE - STARTS HERE
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
    return {
        "type": "SettingsConfiguration",
        "audio": {
            "input": {
                "encoding": "mulaw",
                "sample_rate": 8000
            },
            "output": {
                "encoding": "mulaw", 
                "sample_rate": 8000,
                "container": "none"
            }
        }
    }

async def handle_barge_in(decoded, twilio_ws, streamsid):
    if decoded["type"] == "UserStartedSpeaking":
        clear_message = {
            "event": "clear",
            "streamsid": streamsid
        }
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
    
    async for message in sts_ws:
        if isinstance(message, str):
            print(f"DeepGram Message: {message}")
            decoded = json.loads(message)
            
            # ✅ Store transcripts in database
            if decoded.get("type") == "Results" and decoded.get("results"):
                transcript = decoded["results"].get("transcript", "")
                if transcript and call_id:
                    call_db.store_transcript(call_id, transcript, decoded.get("is_final", False))
            
            await handle_text_message(decoded, twilio_ws, sts_ws, streamsid)
            continue

        # Audio data to Twilio
        raw_mulaw = message
        media_message = {
            "event": "media",
            "streamSid": streamsid,
            "media": {"payload": base64.b64encode(raw_mulaw).decode("ascii")}
        }
        await twilio_ws.send_json(media_message)
    
    # Calculate call duration and cost when connection ends
    end_time = asyncio.get_event_loop().time()
    duration_seconds = int(end_time - start_time)
    if call_id and user_id:
        total_cost = call_db.update_call_cost(call_id, duration_seconds)

async def twilio_receiver(twilio_ws, audio_queue, streamsid_queue):
    BUFFER_SIZE = 20 * 160
    inbuffer = bytearray(b"")

    async for message in twilio_ws.iter_text():
        try:
            data = json.loads(message)
            event = data["event"]

            if event == "start":
                print("get our streamsid")
                start = data["start"]
                streamsid = start["streamSid"]
                await streamsid_queue.put(streamsid)
            elif event == "connected":
                continue
            elif event == "media":
                media = data["media"]
                chunk = base64.b64decode(media["payload"])
                if media["track"] == "inbound":
                    inbuffer.extend(chunk)
            elif event == "stop":
                break

            while len(inbuffer) >= BUFFER_SIZE:
                chunk = inbuffer[:BUFFER_SIZE]
                await audio_queue.put(bytes(chunk))
                inbuffer = inbuffer[BUFFER_SIZE:]
        except Exception as e:
            print(f"Twilio receiver error: {e}")
            break

@app.websocket("/twilio")
async def twilio_websocket(websocket: WebSocket):
    await websocket.accept()
    
    # For demo - in production, you'd get user_id from JWT
    user_id = "demo-user"
    call_id = None
    
    try:
        print("Twilio connected!")
        audio_queue = asyncio.Queue()
        streamsid_queue = asyncio.Queue()

        async with sts_connect() as sts_ws:
            print("🔗 Connected to Deepgram STS")
            config_message = load_config()
            await sts_ws.send(json.dumps(config_message))
            print("📤 Sent config to Deepgram")

            # Create call session
            call_id = call_db.create_call_session(user_id, "twilio-demo", "deepgram-demo")
            print(f"📞 Call session created: {call_id}")

            await asyncio.gather(
                asyncio.create_task(sts_sender(sts_ws, audio_queue)),
                asyncio.create_task(sts_receiver(sts_ws, websocket, streamsid_queue, call_id, user_id)),
                asyncio.create_task(twilio_receiver(websocket, audio_queue, streamsid_queue)),
                return_exceptions=True
            )

    except WebSocketDisconnect:
        print("Client disconnected")
    except Exception as e:
        print(f"Error in twilio_handler: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await websocket.close()
        print("🔌 Twilio connection closed")

@app.get("/")
async def root():
    return {"message": "Voice Agent API is running", "status": "healthy"}

@app.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": asyncio.get_event_loop().time()}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5001, reload=True)
