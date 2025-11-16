import asyncio
import base64
import json
import websockets
from datetime import datetime
from typing import List, Dict, Optional, Any
from fastapi import WebSocket, WebSocketDisconnect
from app.services.deepgram_service import DeepGramService
from app.services.data_extraction_service import DataExtractionService
from app.repositories.call_repo import CallRepository
from app.repositories.mysql_restaurant_repo import MySQLRestaurantRepository
from app.repositories.mysql_menu_repo import MySQLMenuRepository
from app.repositories.mysql_faq_repo import MySQLFAQRepository
from app.repositories.mysql_user_repo import MySQLUserRepository
from app.repositories.mysql_order_repo import MySQLOrderRepository
from app.repositories.mysql_transcript_repo import MySQLTranscriptRepository

class WebSocketService:
    def __init__(self):
        self.deepgram_service = DeepGramService()
        self.call_repo = CallRepository()
        self.data_extraction_service = DataExtractionService()
        self.restaurant_repo = MySQLRestaurantRepository()
        self.menu_repo = MySQLMenuRepository()
        self.faq_repo = MySQLFAQRepository()
        self.user_repo = MySQLUserRepository()
        self.order_repo = MySQLOrderRepository()
        self.transcript_repo = MySQLTranscriptRepository()
    
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
        user_id=None,
        conversation_history=None
    ):
        """Receive messages from Deepgram STS and forward to Twilio."""
        print("sts_receiver started")
        streamsid = await streamsid_queue.get()
        start_time = asyncio.get_event_loop().time()
        message_seq = 0

        BUFFER_SIZE = 3200  # 100ms of 16kHz mono PCM16
        audio_buffer = bytearray()
        last_agent_audio_time = None
        
        if conversation_history is None:
            conversation_history = []

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

                    # Save transcript and collect conversation history
                    if decoded.get("type") in ["ConversationText", "History"]:
                        role = decoded.get("role")
                        text = decoded.get("content")
                        if text:
                            # Store in DynamoDB (if call_id exists)
                            if call_id:
                                message_seq += 1
                                self.call_repo.store_transcript(
                                    call_id=call_id,
                                    message_sequence=message_seq,
                                    speaker=role,
                                    message=text,
                                    timestamp=datetime.utcnow().isoformat(),
                                )
                            
                            # Collect for conversation history
                            conversation_history.append({
                                "role": role,
                                "content": text,
                                "timestamp": datetime.utcnow().isoformat()
                            })

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

    async def twilio_receiver(self, twilio_ws, audio_queue, streamsid_queue, twilio_number_queue):
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
                    
                    # Extract Twilio phone number from start event customParameters
                    print("params: ", data.get("start", {}).get("customParameters", {}))
                    params = data.get("start", {}).get("customParameters", {})
                    to_number = params.get("toNumber")
                    from_number = params.get("fromNumber")
                    
                    print("📥 Twilio START event received")
                    print(f"To Number: {to_number}")
                    print(f"From Number: {from_number}")
                    
                    # Put toNumber into queue for restaurant lookup
                    if to_number:
                        await twilio_number_queue.put(to_number)
                        print(f"📞 Stream started: {streamsid}, Twilio Number: {to_number}")
                    else:
                        print(f"📞 Stream started: {streamsid} (no Twilio number found in customParameters)")
                        
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

    async def process_and_store_data(
        self,
        conversation_history: List[Dict[str, Any]],
        menu_items: List[Dict[str, Any]],
        restaurant_id: int
    ):
        """Extract and store structured data from conversation."""
        try:
            # Combine all conversation text
            conversation_text = " ".join([
                f"{msg['role']}: {msg['content']}" 
                for msg in conversation_history
            ])
            
            # Extract structured data
            extracted_data = self.data_extraction_service.extract_structured_data(
                conversation_text,
                conversation_history,
                menu_items
            )
            
            user_details = extracted_data.get("user_details")
            order_details = extracted_data.get("order_details")
            transcript_log = extracted_data.get("transcript_log")
            
            user_id = None
            order_id = None
            
            # Store user if details were extracted
            if user_details:
                try:
                    user_id = self.user_repo.create_or_update_user(user_details)
                    print(f"✅ User stored/updated: user_id={user_id}")
                except Exception as e:
                    print(f"❌ Error storing user: {e}")
            
            # Store order if details were extracted
            if order_details and user_id:
                try:
                    order_id = self.order_repo.create_order(user_id, {
                        "status": "pending",
                        "total_amount": order_details.get("total_amount", 0.0),
                        "order_details": order_details.get("items", []),
                        "customization": order_details.get("customization", {})
                    })
                    print(f"✅ Order created: order_id={order_id}")
                    
                    # Store order details
                    for item in order_details.get("items", []):
                        menu_item_id = item.get("menu_item_id")
                        if menu_item_id:
                            quantity = item.get("quantity", 1)
                            for _ in range(quantity):
                                self.order_repo.create_order_details(order_id, menu_item_id)
                    print(f"✅ Order details stored for order_id={order_id}")
                except Exception as e:
                    print(f"❌ Error storing order: {e}")
            
            # Store transcript
            try:
                transcript_id = self.transcript_repo.create_transcript(
                    user_id,
                    order_id,
                    transcript_log
                )
                print(f"✅ Transcript stored: transcript_id={transcript_id}")
            except Exception as e:
                print(f"❌ Error storing transcript: {e}")
                
        except Exception as e:
            print(f"❌ Error in process_and_store_data: {e}")

    async def twilio_websocket_handler(self, websocket: WebSocket, user_id: str = "demo-user"):
        """Main WebSocket handler for Twilio connections with multitenancy."""
        await websocket.accept()
        
        call_id = None
        audio_queue = asyncio.Queue()
        streamsid_queue = asyncio.Queue()
        twilio_number_queue = asyncio.Queue()
        conversation_history = []
        restaurant_id = None
        restaurant_name = None
        menu_items = []
        faqs = []

        try:
            print("Twilio connected!")
            
            # Start twilio_receiver task FIRST to process incoming messages
            receiver_task = asyncio.create_task(self.twilio_receiver(
                websocket, 
                audio_queue, 
                streamsid_queue,
                twilio_number_queue
            ))
            
            # Wait for Twilio number from start event (receiver is now running)
            try:
                twilio_number = await asyncio.wait_for(twilio_number_queue.get(), timeout=5.0)
                print(f"📱 Twilio number received: {twilio_number}")
                
                # Get restaurant by Twilio number
                restaurant = self.restaurant_repo.get_by_twilio_number(twilio_number)
                if restaurant:
                    restaurant_id = restaurant.get("id")
                    restaurant_name = restaurant.get("name", "Restaurant")
                    print(f"🏪 Restaurant found: {restaurant_name} (id={restaurant_id})")
                    
                    # Fetch menu items (only available)
                    menu_items = self.menu_repo.get_available_items_by_restaurant(restaurant_id)
                    print(f"📋 Fetched {len(menu_items)} available menu items")
                    
                    # Fetch FAQs
                    faqs = self.faq_repo.get_by_restaurant(restaurant_id)
                    print(f"❓ Fetched {len(faqs)} FAQs")
                else:
                    print(f"⚠️ No restaurant found for Twilio number: {twilio_number}")
            except asyncio.TimeoutError:
                print("⚠️ Twilio number not received within timeout, proceeding with default config")
            
            async with self.deepgram_service.sts_connect() as sts_ws:
                print("🔗 Connected to DeepGram STS")
                
                # Build dynamic config with restaurant context
                config_message = self.deepgram_service.load_config(
                    restaurant_name=restaurant_name,
                    menu_items=menu_items,
                    faqs=faqs
                )
                await sts_ws.send(json.dumps(config_message))
                print("📤 Sent dynamic config to DeepGram with restaurant context")

                try:
                    call_id = self.call_repo.create_call_session(
                        user_id, 
                        "twilio-demo", 
                        "deepgram-demo",
                        restaurant_id=str(restaurant_id) if restaurant_id else None
                    )
                    print(f"📞 Call session created: {call_id}")
                except Exception as e:
                    print(f"[DB] create_call_session error: {e}")

                await asyncio.gather(
                    asyncio.create_task(self.sts_sender(sts_ws, audio_queue)),
                    asyncio.create_task(self.sts_receiver(
                        sts_ws, 
                        websocket, 
                        streamsid_queue, 
                        call_id, 
                        user_id,
                        conversation_history
                    )),
                    receiver_task,  # Already started earlier
                )

        except WebSocketDisconnect:
            print("Client disconnected")
        except Exception as e:
            print(f"Error in twilio_websocket_handler: {e}")
        finally:
            # Process and store extracted data when call ends
            if conversation_history and menu_items:
                print("🔄 Processing and storing extracted data...")
                await self.process_and_store_data(conversation_history, menu_items, restaurant_id)
            
            # Close MySQL connections
            try:
                self.restaurant_repo.close()
                self.menu_repo.close()
                self.faq_repo.close()
                self.user_repo.close()
                self.order_repo.close()
                self.transcript_repo.close()
            except Exception as e:
                print(f"Error closing MySQL connections: {e}")
            
            await websocket.close()
            print("🔌 Twilio connection closed")

