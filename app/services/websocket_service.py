import asyncio
import base64
import json
import websockets
from datetime import datetime
from fastapi import WebSocket, WebSocketDisconnect
from app.services.deepgram_service import DeepGramService
from app.repositories.call_repo import CallRepository

class WebSocketService:
    def __init__(self):
        self.deepgram_service = DeepGramService()
        self.call_repo = CallRepository()
    
    async def handle_barge_in(self, decoded, twilio_ws, streamsid, last_agent_audio_time):
        """Clear Twilio audio only if user starts speaking after a gap."""
        if decoded.get("type") == "UserStartedSpeaking":
            now = asyncio.get_event_loop().time()
            # Avoid clearing mid-sentence; only after 2s gap
            if not last_agent_audio_time or (now - last_agent_audio_time) > 2.0:
                clear_msg = {"event": "clear", "streamSid": streamsid}
                await twilio_ws.send_text(json.dumps(clear_msg))
                print(f"🧹 Cleared Twilio buffer after {now - (last_agent_audio_time or 0):.2f}s")

    async def handle_text_message(self, decoded, twilio_ws, sts_ws, streamsid, last_agent_audio_time):
        """Handle text messages and barge-in logic."""
        await self.handle_barge_in(decoded, twilio_ws, streamsid, last_agent_audio_time)

    async def sts_sender(self, sts_ws, audio_queue):
        """Send audio chunks to Deepgram STS."""
        print("sts_sender started")
        try:
            while True:
                chunk = await audio_queue.get()
                await sts_ws.send(chunk)
        except (asyncio.CancelledError, websockets.exceptions.ConnectionClosed):
            print("sts_sender stopped")

    async def sts_receiver(
        self,
        sts_ws,
        twilio_ws,
        streamsid_queue,
        call_id=None,
        user_id=None
    ):
        """Receive messages from Deepgram STS and forward to Twilio."""
        print("sts_receiver started")
        streamsid = await streamsid_queue.get()
        start_time = asyncio.get_event_loop().time()
        message_seq = 0

        BUFFER_SIZE = 3200  # 100ms of 16kHz mono PCM16
        audio_buffer = bytearray()
        last_agent_audio_time = None

        async def flush_audio():
            nonlocal audio_buffer, last_agent_audio_time
            if audio_buffer:
                payload = base64.b64encode(audio_buffer).decode("ascii")
                msg = {"event": "media", "streamSid": streamsid, "media": {"payload": payload}}
                try:
                    await twilio_ws.send_text(json.dumps(msg))
                    last_agent_audio_time = asyncio.get_event_loop().time()
                    print(f"✅ Flushed {len(audio_buffer)} bytes to Twilio")
                except Exception as e:
                    print(f"Error sending buffered audio to Twilio: {e}")
                audio_buffer.clear()

        try:
            async for message in sts_ws:
                if isinstance(message, str):
                    decoded = json.loads(message)
                    print(f"DeepGram Message: {decoded}")

                    # Handle Deepgram audio messages
                    if decoded.get("type") in ["ConversationAudio", "AgentAudioDone"]:
                        audio_payload = decoded.get("audio", "")
                        if audio_payload:
                            try:
                                audio_bytes = base64.b64decode(audio_payload)
                                audio_buffer.extend(audio_bytes)
                                while len(audio_buffer) >= BUFFER_SIZE:
                                    chunk = audio_buffer[:BUFFER_SIZE]
                                    del audio_buffer[:BUFFER_SIZE]
                                    payload = base64.b64encode(chunk).decode("ascii")
                                    msg = {"event": "media", "streamSid": streamsid, "media": {"payload": payload}}
                                    await twilio_ws.send_text(json.dumps(msg))
                                    last_agent_audio_time = asyncio.get_event_loop().time()
                                    print(f"✅ Sent ConversationAudio {len(chunk)} bytes to Twilio")
                            except Exception as e:
                                print(f"Error processing ConversationAudio: {e}")

                    await self.handle_text_message(decoded, twilio_ws, sts_ws, streamsid, last_agent_audio_time)

                    # Save transcript
                    if decoded.get("type") in ["ConversationText", "History"]:
                        role = decoded.get("role")
                        text = decoded.get("content")
                        if text and call_id:
                            message_seq += 1
                            self.call_repo.store_transcript(
                                call_id=call_id,
                                message_sequence=message_seq,
                                speaker=role,
                                message=text,
                                timestamp=datetime.utcnow().isoformat(),
                            )

                    # Flush remaining audio when done
                    if decoded.get("type") == "AgentAudioDone":
                        await flush_audio()
                    continue
                            
                audio_buffer.extend(message)
                while len(audio_buffer) >= BUFFER_SIZE:
                    chunk = audio_buffer[:BUFFER_SIZE]
                    del audio_buffer[:BUFFER_SIZE]
                    payload = base64.b64encode(chunk).decode("ascii")
                    msg = {"event": "media", "streamSid": streamsid, "media": {"payload": payload}}
                    await twilio_ws.send_text(json.dumps(msg))
                    last_agent_audio_time = asyncio.get_event_loop().time()                

            await flush_audio()
        except (websockets.exceptions.ConnectionClosed, websockets.exceptions.ConnectionClosedOK):
            print("sts_receiver: Deepgram connection closed")
        except asyncio.CancelledError:
            print("sts_receiver cancelled")
            raise
        finally:
            end_time = asyncio.get_event_loop().time()
            duration = int(end_time - start_time)
            if call_id and user_id:
                self.call_repo.update_call_cost(call_id, duration)

    async def twilio_receiver(self, twilio_ws, audio_queue, streamsid_queue):
        """Receive audio from Twilio and forward to Deepgram."""
        BUFFER_SIZE = 20 * 160  # 3200 bytes per 100ms
        inbuffer = bytearray()

        try:
            async for message in twilio_ws.iter_text():
                data = json.loads(message)
                event = data.get("event")

                if event == "start":
                    streamsid = data["start"]["streamSid"]
                    await streamsid_queue.put(streamsid)
                    print(f"📞 Stream started: {streamsid}")
                elif event == "media":
                    chunk = base64.b64decode(data["media"]["payload"])
                    if data["media"]["track"] == "inbound":
                        inbuffer.extend(chunk)
                elif event == "stop":
                    print("🛑 Twilio stop event received - closing gracefully")
                    break

                while len(inbuffer) >= BUFFER_SIZE:
                    await audio_queue.put(inbuffer[:BUFFER_SIZE])
                    del inbuffer[:BUFFER_SIZE]

        except (WebSocketDisconnect, ConnectionError):
            print("Twilio receiver disconnected")
        except asyncio.CancelledError:
            print("twilio_receiver cancelled")
            raise
        except Exception as e:
            print(f"Twilio receiver error: {e}")

    async def twilio_websocket_handler(self, websocket: WebSocket, user_id: str = "demo-user"):
        """Main WebSocket handler for Twilio connections."""
        await websocket.accept()
        
        call_id = None
        audio_queue = asyncio.Queue()
        streamsid_queue = asyncio.Queue()

        try:
            print("Twilio connected!")
            async with self.deepgram_service.sts_connect() as sts_ws:
                print("🔗 Connected to DeepGram STS")
                config_message = self.deepgram_service.load_config()
                await sts_ws.send(json.dumps(config_message))
                print("📤 Sent full config to DeepGram")

                try:
                    call_id = self.call_repo.create_call_session(user_id, "twilio-demo", "deepgram-demo")
                    print(f"📞 Call session created: {call_id}")
                except Exception as e:
                    print(f"[DB] create_call_session error: {e}")

                await asyncio.gather(
                    asyncio.create_task(self.sts_sender(sts_ws, audio_queue)),
                    asyncio.create_task(self.sts_receiver(sts_ws, websocket, streamsid_queue, call_id, user_id)),
                    asyncio.create_task(self.twilio_receiver(websocket, audio_queue, streamsid_queue)),
                )

        except WebSocketDisconnect:
            print("Client disconnected")
        except Exception as e:
            print(f"Error in twilio_websocket_handler: {e}")
        finally:
            await websocket.close()
            print("🔌 Twilio connection closed")

