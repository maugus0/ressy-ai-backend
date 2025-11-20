import asyncio
import base64
import json
import re
import websockets
from datetime import datetime
from typing import List, Dict, Optional, Any
from fastapi import WebSocket, WebSocketDisconnect
from app.services.deepgram_service import DeepGramService
from app.services.data_extraction_service import DataExtractionService
from app.repositories.mysql_call_repo import MySQLCallRepository
from app.repositories.mysql_restaurant_repo import MySQLRestaurantRepository
from app.repositories.mysql_menu_repo import MySQLMenuRepository
from app.repositories.mysql_faq_repo import MySQLFAQRepository
from app.repositories.mysql_user_repo import MySQLUserRepository
from app.repositories.mysql_order_repo import MySQLOrderRepository
from app.repositories.mysql_transcript_repo import MySQLTranscriptRepository

class WebSocketService:
    def __init__(self):
        self.deepgram_service = DeepGramService()
        self.call_repo = MySQLCallRepository()
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
    
    def parse_order_ready(self, text: str, menu_items: List[Dict[str, Any]], restaurant_id: int) -> Optional[Dict[str, Any]]:
        """
        Parse ORDER_READY format: "ORDER_READY: [customer name], [item1] x[quantity], [item2] x[quantity], Total: $[amount]"
        Returns order data if successfully parsed, None otherwise.
        """
        if "ORDER_READY:" not in text.upper():
            return None
        
        try:
            # Extract the order part after ORDER_READY:
            order_match = re.search(r'ORDER_READY:\s*(.+)', text, re.IGNORECASE)
            if not order_match:
                return None
            
            order_text = order_match.group(1).strip()
            
            # Extract customer name (before first comma)
            parts = order_text.split(',')
            if len(parts) < 2:
                return None
            
            customer_name = parts[0].strip()
            
            # Extract total amount
            total_match = re.search(r'Total:\s*\$?([\d.]+)', order_text, re.IGNORECASE)
            total_amount = float(total_match.group(1)) if total_match else 0.0
            
            # Extract items and quantities
            # Pattern: "item name xquantity" or "item name" (default quantity 1)
            items = []
            menu_lookup = {}
            for item in menu_items:
                item_name_lower = item.get("item_name", "").lower()
                menu_lookup[item_name_lower] = item
                # Also add variations
                words = item_name_lower.split()
                if len(words) > 1:
                    menu_lookup[" ".join(words[:2])] = item
            
            # Find all item patterns
            item_patterns = [
                r'([^,]+?)\s+x(\d+)',  # "item x2"
                r'([^,]+?)\s+(\d+)\s*x',  # "item 2x"
                r'([^,]+?)(?:\s*,\s*|$)',  # "item" (default quantity 1)
            ]
            
            found_items = []
            remaining_text = ','.join(parts[1:])  # Everything after customer name
            
            # Remove total from remaining text
            remaining_text = re.sub(r',\s*Total:.*$', '', remaining_text, flags=re.IGNORECASE)
            
            # Try to match items
            for pattern in item_patterns:
                matches = re.finditer(pattern, remaining_text, re.IGNORECASE)
                for match in matches:
                    item_phrase = match.group(1).strip()
                    quantity = int(match.group(2)) if len(match.groups()) > 1 and match.group(2).isdigit() else 1
                    
                    # Try to match with menu items
                    item_phrase_lower = item_phrase.lower()
                    for menu_key, menu_item in menu_lookup.items():
                        if menu_key in item_phrase_lower or item_phrase_lower in menu_key:
                            item_id = menu_item.get("id")
                            if item_id:
                                found_items.append({
                                    "menu_item_id": item_id,
                                    "item_name": menu_item.get("item_name"),
                                    "price": float(menu_item.get("price", 0)),
                                    "quantity": quantity
                                })
                                break
            
            if not found_items:
                return None
            
            return {
                "customer_name": customer_name,
                "items": found_items,
                "total_amount": total_amount
            }
        except Exception as e:
            print(f"[ERROR] Error parsing ORDER_READY: {e}")
            return None
    
    async def save_order_from_text(
        self,
        text: str,
        menu_items: List[Dict[str, Any]],
        restaurant_id: int,
        conversation_history: List[Dict[str, Any]]
    ):
        """
        Parse ORDER_READY text and save order to database.
        """
        order_data = self.parse_order_ready(text, menu_items, restaurant_id)
        if not order_data:
            return None
        
        try:
            # Extract user info from conversation history
            user_data = {}
            for msg in conversation_history:
                if msg.get("role") == "user":
                    content = msg.get("content", "").lower()
                    # Try to extract phone number
                    phone_match = re.search(r'(\+?1?[-.\s]?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4})', msg.get("content", ""))
                    if phone_match:
                        phone = re.sub(r'[-.\s()]', '', phone_match.group(1))
                        user_data["phone_number"] = phone
            
            # Get or create user
            user_id = None
            if user_data.get("phone_number"):
                user_id = self.user_repo.get_user_id_by_phone_or_email(
                    user_data.get("phone_number"),
                    user_data.get("email")
                )
            
            if not user_id:
                # Create user with name from order
                user_data["name"] = order_data["customer_name"]
                user_id = self.user_repo.create_or_update_user(user_data)
            
            # Create order
            order_id = self.order_repo.create_order(user_id, {
                "status": "pending",
                "total_amount": order_data["total_amount"],
                "order_details": order_data["items"],
                "customization": {}
            })
            print(f"[SUCCESS] Order saved immediately: order_id={order_id}, customer={order_data['customer_name']}, total=${order_data['total_amount']:.2f}")
            
            # Create order details
            for item in order_data["items"]:
                menu_item_id = item.get("menu_item_id")
                quantity = item.get("quantity", 1)
                if menu_item_id:
                    for _ in range(quantity):
                        self.order_repo.create_order_details(order_id, menu_item_id)
            
            return order_id
        except Exception as e:
            print(f"[ERROR] Error saving order from ORDER_READY: {e}")
            return None

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
        conversation_history=None,
        menu_items=None,
        restaurant_id=None
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
                try:
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
                                # Note: Individual messages are collected in conversation_history
                                # and saved to MySQL via process_and_store_data at call end
                                # No need to store each message individually
                                
                                # Collect for conversation history
                                conversation_history.append({
                                    "role": role,
                                    "content": text,
                                    "timestamp": datetime.utcnow().isoformat()
                                })
                                
                                # Check for ORDER_READY and save order immediately
                                if role == "agent" and menu_items and restaurant_id:
                                    if "ORDER_READY:" in text.upper():
                                        print(f"[INFO] Detected ORDER_READY in conversation, saving order...")
                                        await self.save_order_from_text(
                                            text,
                                            menu_items,
                                            restaurant_id,
                                            conversation_history
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
                except asyncio.CancelledError:
                    print("[INFO] sts_receiver: Cancellation detected in message loop")
                    raise
                except Exception as e:
                    print(f"[ERROR] Error processing message in sts_receiver: {e}")

            await flush_audio()
        except (websockets.exceptions.ConnectionClosed, websockets.exceptions.ConnectionClosedOK):
            print("[INFO] sts_receiver: Deepgram connection closed")
        except asyncio.CancelledError:
            print("[INFO] sts_receiver cancelled")
            await flush_audio()  # Flush before exiting
            raise
        except Exception as e:
            print(f"[ERROR] sts_receiver error: {e}")
            import traceback
            traceback.print_exc()
        finally:
            end_time = asyncio.get_event_loop().time()
            duration = int(end_time - start_time)
            if call_id and user_id:
                try:
                    self.call_repo.update_call_cost(call_id, duration)
                    print(f"[INFO] Updated call cost for call_id={call_id}, duration={duration}s")
                except Exception as e:
                    print(f"[ERROR] Error updating call cost: {e}")
                    import traceback
                    traceback.print_exc()

    async def twilio_receiver(self, twilio_ws, audio_queue, streamsid_queue, twilio_number_queue, disconnect_event=None):
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
                    print("[INFO] Twilio stop event received - call ending")
                    # Flush any remaining audio
                    if inbuffer:
                        await audio_queue.put(inbuffer[:])
                        inbuffer.clear()
                    # Signal disconnection
                    if disconnect_event:
                        disconnect_event.set()
                    break

                while len(inbuffer) >= BUFFER_SIZE:
                    await audio_queue.put(inbuffer[:BUFFER_SIZE])
                    del inbuffer[:BUFFER_SIZE]
            
            # Flush any remaining audio before exiting
            if inbuffer:
                await audio_queue.put(inbuffer[:])
                inbuffer.clear()

        except (WebSocketDisconnect, ConnectionError) as e:
            print(f"[INFO] Twilio receiver disconnected: {e}")
            if disconnect_event:
                disconnect_event.set()
        except asyncio.CancelledError:
            print("[INFO] twilio_receiver cancelled")
            if disconnect_event:
                disconnect_event.set()
            raise
        except Exception as e:
            print(f"[ERROR] Twilio receiver error: {e}")
            if disconnect_event:
                disconnect_event.set()

    async def process_and_store_data(
        self,
        conversation_history: List[Dict[str, Any]],
        menu_items: List[Dict[str, Any]],
        restaurant_id: int
    ):
        """Extract and store structured data from conversation."""
        try:
            if not conversation_history:
                print("[WARNING] No conversation history to process")
                return
            
            # Combine all conversation text
            conversation_text = " ".join([
                f"{msg['role']}: {msg['content']}" 
                for msg in conversation_history
            ])
            
            # Check if order was already saved via ORDER_READY
            order_already_saved = False
            for msg in conversation_history:
                if msg.get("role") == "agent" and "ORDER_READY:" in msg.get("content", "").upper():
                    order_already_saved = True
                    print("[INFO] Order was already saved via ORDER_READY, skipping duplicate order extraction")
                    break
            
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
                    print(f"[SUCCESS] User stored/updated: user_id={user_id}")
                except Exception as e:
                    print(f"[ERROR] Error storing user: {e}")
                    import traceback
                    traceback.print_exc()
            
            # Store order if details were extracted AND order wasn't already saved
            if order_details and user_id and not order_already_saved:
                try:
                    order_id = self.order_repo.create_order(user_id, {
                        "status": "pending",
                        "total_amount": order_details.get("total_amount", 0.0),
                        "order_details": order_details.get("items", []),
                        "customization": order_details.get("customization", {})
                    })
                    print(f"[SUCCESS] Order created: order_id={order_id}")
                    
                    # Store order details
                    for item in order_details.get("items", []):
                        menu_item_id = item.get("menu_item_id")
                        if menu_item_id:
                            quantity = item.get("quantity", 1)
                            for _ in range(quantity):
                                self.order_repo.create_order_details(order_id, menu_item_id)
                    print(f"[SUCCESS] Order details stored for order_id={order_id}")
                except Exception as e:
                    print(f"[ERROR] Error storing order: {e}")
                    import traceback
                    traceback.print_exc()
            elif order_already_saved:
                print("[INFO] Skipping order creation - already saved via ORDER_READY")
            
            # Store transcript (always save transcript, even if no user/order)
            try:
                transcript_id = self.transcript_repo.create_transcript(
                    user_id,
                    order_id,
                    transcript_log
                )
                print(f"[SUCCESS] Transcript stored: transcript_id={transcript_id}")
            except Exception as e:
                print(f"[ERROR] Error storing transcript: {e}")
                import traceback
                traceback.print_exc()
                
        except Exception as e:
            print(f"[ERROR] Error in process_and_store_data: {e}")
            import traceback
            traceback.print_exc()

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
        disconnect_event = asyncio.Event()  # Signal for disconnection
        # Track tasks for cleanup
        receiver_task = None
        sts_sender_task = None
        sts_receiver_task = None

        try:
            print("Twilio connected!")
            
            # Start twilio_receiver task FIRST to process incoming messages
            receiver_task = asyncio.create_task(self.twilio_receiver(
                websocket, 
                audio_queue, 
                streamsid_queue,
                twilio_number_queue,
                disconnect_event
            ))
            # Store in outer scope for finally block access
            
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
            
            # Use async with to ensure Deepgram connection is properly closed
            try:
                async with self.deepgram_service.sts_connect() as sts_ws:
                    print("[INFO] Connected to DeepGram STS")
                    
                    # Build dynamic config with restaurant context
                    config_message = self.deepgram_service.load_config(
                        restaurant_name=restaurant_name,
                        menu_items=menu_items,
                        faqs=faqs
                    )
                    await sts_ws.send(json.dumps(config_message))
                    print("[INFO] Sent dynamic config to DeepGram with restaurant context")

                    try:
                        call_id = self.call_repo.create_call_session(
                            user_id, 
                            "twilio-demo", 
                            "deepgram-demo",
                            restaurant_id=str(restaurant_id) if restaurant_id else None
                        )
                        print(f"[INFO] Call session created: call_id={call_id}")
                    except Exception as e:
                        print(f"[ERROR] create_call_session error: {e}")
                        import traceback
                        traceback.print_exc()
                        call_id = None

                    # Create tasks for Deepgram operations
                    sts_sender_task = asyncio.create_task(self.sts_sender(sts_ws, audio_queue))
                    sts_receiver_task = asyncio.create_task(self.sts_receiver(
                        sts_ws, 
                        websocket, 
                        streamsid_queue, 
                        call_id, 
                        user_id,
                        conversation_history,
                        menu_items,
                        restaurant_id
                    ))
                    # Tasks are already in outer scope

                    # Wait for disconnection event or any task to complete
                    try:
                        # Wait for either disconnection event or first task completion
                        done, pending = await asyncio.wait(
                            [
                                asyncio.create_task(disconnect_event.wait()),
                                sts_sender_task,
                                sts_receiver_task,
                                receiver_task
                            ],
                            return_when=asyncio.FIRST_COMPLETED
                        )
                        print(f"[INFO] Disconnection detected. Done: {len(done)}, Pending: {len(pending)}")
                        
                        # Cancel remaining tasks
                        for task in pending:
                            if not task.done():
                                task.cancel()
                        
                        # Wait for cancellation with timeout
                        if pending:
                            try:
                                await asyncio.wait_for(
                                    asyncio.gather(*pending, return_exceptions=True),
                                    timeout=1.0
                                )
                            except asyncio.TimeoutError:
                                print("[WARNING] Timeout waiting for tasks to cancel")
                    except Exception as e:
                        print(f"[ERROR] Error in wait: {e}")
                        import traceback
                        traceback.print_exc()
                    
                    print("[INFO] Exiting Deepgram connection context - connection will close automatically")
            except Exception as e:
                print(f"[ERROR] Error in Deepgram connection: {e}")
                import traceback
                traceback.print_exc()

        except WebSocketDisconnect:
            print("[INFO] Twilio WebSocket disconnected")
        except Exception as e:
            print(f"[ERROR] Error in twilio_websocket_handler: {e}")
            import traceback
            traceback.print_exc()
        finally:
            print("\n" + "="*70)
            print("[INFO] ========== CALL END - STARTING CLEANUP ==========")
            print("="*70)
            print(f"[INFO] Conversation history length: {len(conversation_history)}")
            print(f"[INFO] Menu items available: {len(menu_items) if menu_items else 0}")
            print(f"[INFO] Restaurant ID: {restaurant_id}")
            print(f"[INFO] Call ID: {call_id}")
            
            # Process and store extracted data FIRST (before cancelling tasks)
            # This is critical - must happen even if other errors occur
            print("\n[INFO] Step 1: Processing and storing extracted data...")
            try:
                if conversation_history:
                    print(f"[INFO] Found {len(conversation_history)} conversation messages")
                    print(f"[INFO] Sample messages:")
                    for i, msg in enumerate(conversation_history[:3]):
                        print(f"  {i+1}. {msg.get('role', 'unknown')}: {msg.get('content', '')[:50]}...")
                    
                    try:
                        await self.process_and_store_data(conversation_history, menu_items or [], restaurant_id)
                        print("[SUCCESS] Data saved successfully to MySQL")
                    except Exception as e:
                        print(f"[ERROR] Error saving data: {e}")
                        import traceback
                        traceback.print_exc()
                        # Try to at least save the transcript
                        try:
                            print("[INFO] Attempting to save transcript as fallback...")
                            transcript_log = {
                                "conversation": conversation_history,
                                "timestamp": datetime.utcnow().isoformat()
                            }
                            transcript_id = self.transcript_repo.create_transcript(None, None, transcript_log)
                            print(f"[SUCCESS] Transcript saved as fallback: transcript_id={transcript_id}")
                        except Exception as fallback_error:
                            print(f"[ERROR] Fallback transcript save also failed: {fallback_error}")
                else:
                    print("[WARNING] No conversation history to save - this might indicate a problem")
            except Exception as e:
                print(f"[CRITICAL ERROR] Failed to save data in finally block: {e}")
                import traceback
                traceback.print_exc()
            
            # Cancel only our specific tasks (not all system tasks)
            print("\n[INFO] Step 2: Cancelling call-specific tasks...")
            try:
                # Only cancel tasks that are related to this call
                # Don't cancel all tasks as that includes system tasks
                tasks_to_cancel = []
                if receiver_task and not receiver_task.done():
                    tasks_to_cancel.append(receiver_task)
                if sts_sender_task and not sts_sender_task.done():
                    tasks_to_cancel.append(sts_sender_task)
                if sts_receiver_task and not sts_receiver_task.done():
                    tasks_to_cancel.append(sts_receiver_task)
                
                if tasks_to_cancel:
                    print(f"[INFO] Cancelling {len(tasks_to_cancel)} call-specific tasks")
                    for task in tasks_to_cancel:
                        task.cancel()
                    # Wait for tasks to be cancelled with timeout
                    try:
                        await asyncio.wait_for(
                            asyncio.gather(*tasks_to_cancel, return_exceptions=True),
                            timeout=1.0
                        )
                        print(f"[INFO] Cancelled {len(tasks_to_cancel)} tasks")
                    except asyncio.TimeoutError:
                        print(f"[WARNING] Timeout waiting for tasks to cancel")
                    except Exception as e:
                        print(f"[WARNING] Error during task cancellation: {e}")
                else:
                    print("[INFO] No call-specific tasks to cancel")
            except Exception as e:
                print(f"[ERROR] Error cancelling tasks: {e}")
                import traceback
                traceback.print_exc()
            
            # Close MySQL connections
            print("\n[INFO] Step 3: Closing MySQL connections...")
            try:
                self.call_repo.close()
                self.restaurant_repo.close()
                self.menu_repo.close()
                self.faq_repo.close()
                self.user_repo.close()
                self.order_repo.close()
                self.transcript_repo.close()
                print("[INFO] All MySQL connections closed")
            except Exception as e:
                print(f"[ERROR] Error closing MySQL connections: {e}")
                import traceback
                traceback.print_exc()
            
            # Close WebSocket if still open
            print("\n[INFO] Step 4: Closing WebSocket...")
            try:
                if hasattr(websocket, 'client_state') and websocket.client_state.name != "DISCONNECTED":
                    await websocket.close()
                print("[INFO] Twilio WebSocket closed")
            except Exception as e:
                print(f"[ERROR] Error closing WebSocket: {e}")
            
            print("\n" + "="*70)
            print("[INFO] ========== CALL CLEANUP COMPLETED ==========")
            print("="*70 + "\n")

