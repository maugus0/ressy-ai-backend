import asyncio
import base64
import json
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import websockets
from fastapi import WebSocket, WebSocketDisconnect

from app.agent_fc.config import get_settings as get_fc_settings
from app.agent_fc.functions import conversation, menu, orders, reservations
from app.agent_fc.models import AgentFrame
from app.agent_fc.registry import FunctionRegistry
from app.agent_fc.responses import AgentSideEffect
from app.agent_fc.router import FunctionCallRouter
from app.agent_fc.transport import Transport
from app.config import settings
from app.repositories.mysql_user_repo import MySQLUserRepository
from app.services.call_service import CallService
from app.services.callmanager.call_filler import FillerManager
from app.services.callmanager.call_latency import log_agent_audio_start_latency, log_assistant_text_latency
from app.services.callmanager.call_state import StreamState
from app.services.deepgram_service import DeepgramService
from app.services.faq_service import FAQService
from app.services.menu_service import MenuService
from app.services.restaurant_service import RestaurantService
from app.utils import prompt_loader


@dataclass
class CallResources:
    context_payload: Dict[str, Any]
    restaurant_id: Optional[str]
    restaurant_phone: Optional[str]
    restaurant_phone_fwd: Optional[str]
    restaurant_name: Optional[str]
    deepgram_key_terms: Optional[Any]
    think_prompt: str


class WebSocketService:
    def __init__(self):
        self.deepgram_service = DeepgramService()
        self.call_service = CallService()
        self.user_repo = MySQLUserRepository()
        self.restaurant_service = RestaurantService()
        self.menu_service = MenuService()
        self.faq_service = FAQService()
        self._active_twilio: set[WebSocket] = set()
        self._active_deepgram: set[Any] = set()
        self._connections_lock = asyncio.Lock()
        self._filler_manager = FillerManager()

    def _summarize_menu(self, items: list[dict[str, Any]]) -> Dict[str, Any]:
        """Return a compact menu summary for prompts."""
        highlights: list[dict[str, Any]] = []
        categories: list[str] = []
        for item in items:
            category = item.get("category")
            if category:
                categories.append(str(category))
            entry = {
                "item_id": item.get("id"),
                "name": item.get("item_name"),
                "price": item.get("price"),
                "description": item.get("item_desc"),
                "category": category,
            }
            if entry["name"]:
                highlights.append(entry)
            if len(highlights) >= 10:
                break
        # Preserve order while deduping categories
        deduped_categories = list(dict.fromkeys(categories))
        return {"categories": deduped_categories[:6], "highlights": highlights[:10]}

    def _summarize_specials(self, specials: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [
            {
                "item_id": special.get("id"),
                "name": special.get("item_name"),
                "description": special.get("item_desc"),
                "price": special.get("price"),
                "category": special.get("category"),
            }
            for special in specials[:5]
        ]

    def _summarize_faqs(self, faqs: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [
            {
                "question": faq.get("question"),
                "answer": faq.get("answer"),
            }
            for faq in faqs[:6]
        ]

    def _build_restaurant_context(
        self, caller_phone: Optional[str] = None, restaurant_record: Optional[Dict[str, Any]] = None
    ) -> tuple[Dict[str, Any], Optional[str], Optional[str], Optional[str]]:
        restaurant_phone_fwd = restaurant_record.get("phone_number") if restaurant_record else None
        restaurant_id = restaurant_record.get("id") if restaurant_record else None
        if isinstance(restaurant_id, str) and restaurant_id.isdigit():
            restaurant_id = int(restaurant_id)
        restaurant = restaurant_record or {}

        # TODO: Removing specials and menu highlights from the initial context for now.
        #  Not removing the code just yet as we may decide to add them back later.
        # menu_items = self.menu_service.get_available_items_by_restaurant(restaurant_id) if restaurant_id else []
        # specials: list[dict[str, Any]] = [item for item in menu_items if item.get("is_special")]
        # regular_menu_items = [item for item in menu_items if not item.get("is_special")]
        faqs = self.faq_service.list_faqs(restaurant_id) if restaurant_id else []

        restaurant_name = restaurant.get("name")
        hours = restaurant.get("hours") or restaurant.get("hours_of_operation") or []
        if isinstance(hours, dict):
            hours = [f"{day}: {span}" for day, span in hours.items()]

        service_options = restaurant.get("service_options") or {}
        if not isinstance(service_options, dict):
            service_options = {}

        context = {
            "restaurant_profile": {
                "id": restaurant_id,
                "name": restaurant_name,
                "cuisine": restaurant.get("cuisine_type"),
                "address": restaurant.get("full_address") or restaurant.get("address"),
                "phone": restaurant.get("phone_number"),
                "prep_time_minutes": restaurant.get("prep_time_minutes", 20),
            },
            "hours": hours,
            "service_options": {
                "dine_in": service_options.get("dine_in", True),
                "takeout": service_options.get("takeout", True),
                "delivery": service_options.get("delivery", False),
                "reservations": service_options.get("reservations", True),
            },
            # "menu": self._summarize_menu(regular_menu_items),
            # "specials": self._summarize_specials(specials),
            "faqs": self._summarize_faqs(faqs),
            "function_defaults": {
                "restaurant_id": restaurant_id,
                "restaurant_phone": restaurant_phone_fwd,
            },
        }
        restaurant_timezone_name = getattr(settings, "RESTAURANT_TIMEZONE", "America/Vancouver")
        try:
            restaurant_tz = ZoneInfo(restaurant_timezone_name)
            timezone_label = restaurant_timezone_name
        except ZoneInfoNotFoundError:
            restaurant_tz = datetime.now().astimezone().tzinfo or timezone.utc
            timezone_label = restaurant_tz.tzname(None) or "America/Vancouver"

        now_utc = datetime.now(timezone.utc)
        now_local = now_utc.astimezone(restaurant_tz)
        context["current_time"] = {
            "utc_iso": now_utc.isoformat(),
            "local_iso": now_local.isoformat(),
            "local_date": now_local.date().isoformat(),
            "timezone": timezone_label,
        }
        if caller_phone:
            context["caller_profile"] = {
                "caller_phone": caller_phone,
                "source": "inbound_call",
            }
            context["function_defaults"]["caller_phone"] = caller_phone
        return context, restaurant_id, restaurant_phone_fwd, restaurant_name

    async def shutdown(self) -> None:
        """Close any remaining Twilio or Deepgram connections during app shutdown."""
        async with self._connections_lock:
            closing_tasks = []
            for ws in list(self._active_twilio):
                closing_tasks.append(self._safe_close(ws.close))
                self._active_twilio.discard(ws)
            for conn in list(self._active_deepgram):
                closing_tasks.append(self._safe_close(conn.close))
                self._active_deepgram.discard(conn)
        if closing_tasks:
            await asyncio.gather(*closing_tasks, return_exceptions=True)

    async def _safe_close(self, closer) -> None:
        try:
            result = closer()
            if asyncio.iscoroutine(result):
                await result
        except Exception as exc:
            print(f"[Shutdown] connection close failed: {exc}")

    async def _handle_side_effects(
        self,
        side_effects: list[AgentSideEffect],
        sts_ws,
    ) -> dict[str, Optional[str] | bool]:
        """Send side effect messages (e.g., InjectAgentMessage) back to Deepgram."""

        if not side_effects:
            return {"close_requested": False, "farewell_message": None}

        close_requested = False
        last_inject_message: Optional[str] = None

        for effect in side_effects:
            try:
                if effect.delay_seconds > 0:
                    await asyncio.sleep(effect.delay_seconds)
                payload = effect.payload or {}
                effect_type = payload.get("type")
                if effect_type == "InjectAgentMessage":
                    await sts_ws.send(json.dumps(payload))
                    last_inject_message = payload.get("message") or last_inject_message
                    print(f"[FX] InjectAgentMessage sent: {payload}")
                elif effect_type == "close":
                    close_requested = True
                    print("[FX] Close request received from agent function")
                else:
                    await sts_ws.send(json.dumps(payload))
                    print(f"[FX] Side effect forwarded: {payload}")
            except Exception as exc:
                print(f"[FX] Failed to process side effect {effect.payload}: {exc}")

        if not close_requested:
            last_inject_message = None
        return {"close_requested": close_requested, "farewell_message": last_inject_message}

    async def _graceful_shutdown_call(
        self,
        twilio_ws,
        sts_ws,
        shutdown_event: Optional[asyncio.Event] = None,
        audio_queue: Optional[asyncio.Queue] = None,
    ) -> None:
        """Close Deepgram and Twilio sockets after the farewell finishes."""

        if shutdown_event and not shutdown_event.is_set():
            shutdown_event.set()
        if audio_queue is not None:
            try:
                audio_queue.put_nowait(None)
            except asyncio.QueueFull:
                pass
        print("🔚 Farewell finished, closing sockets")
        try:
            await twilio_ws.close()
        except Exception as exc:
            print(f"[Close] Failed to close Twilio websocket: {exc}")
        try:
            await sts_ws.close()
        except Exception as exc:
            print(f"[Close] Failed to close Deepgram websocket: {exc}")

    async def _handle_unregistered_twilio_call(
        self,
        twilio_ws,
        streamsid_queue: asyncio.Queue,
        shutdown_event: asyncio.Event,
        audio_queue: asyncio.Queue,
    ) -> None:
        """
        Handle calls to Twilio numbers not registered with any restaurant.
        Plays an error message to the caller before disconnecting.
        """
        error_message = settings.UNREGISTERED_TWILIO_MESSAGE
        print(f"[INFO] Playing unregistered number message: {error_message}")

        try:
            # Wait for streamSid from Twilio start event
            try:
                streamsid = await asyncio.wait_for(streamsid_queue.get(), timeout=5.0)
            except asyncio.TimeoutError:
                print("[WARN] Timeout waiting for Twilio streamSid, closing connection")
                return

            # Connect to Deepgram with default API key to play the message
            async with self.deepgram_service.sts_connect() as sts_ws:
                async with self._connections_lock:
                    self._active_deepgram.add(sts_ws)

                try:
                    # Build config with the error message as the greeting
                    # This ensures the error message is spoken immediately
                    config_message = {
                        "type": "Settings",
                        "audio": {
                            "input": {
                                "encoding": settings.DEEPGRAM_AUDIO_INPUT_ENCODING or "mulaw",
                                "sample_rate": settings.DEEPGRAM_AUDIO_INPUT_SAMPLE_RATE or 8000,
                            },
                            "output": {
                                "encoding": settings.DEEPGRAM_AUDIO_OUTPUT_ENCODING or "mulaw",
                                "sample_rate": settings.DEEPGRAM_AUDIO_OUTPUT_SAMPLE_RATE or 8000,
                                "container": settings.DEEPGRAM_AUDIO_OUTPUT_CONTAINER or "none",
                            },
                        },
                        "agent": {
                            "language": settings.DEEPGRAM_AGENT_LANGUAGE,
                            "listen": {
                                "provider": {
                                    "type": "deepgram",
                                    "model": settings.DEEPGRAM_LISTEN_MODEL,
                                }
                            },
                            "think": {
                                "provider": {
                                    "type": settings.DEEPGRAM_THINK_PROVIDER_TYPE,
                                    "model": settings.DEEPGRAM_THINK_MODEL,
                                },
                                "prompt": "You are an automated message system. Do not respond to any user input.",
                            },
                            "speak": {
                                "provider": {
                                    "type": "deepgram",
                                    "model": settings.DEEPGRAM_SPEAK_MODEL,
                                }
                            },
                            "greeting": error_message,
                        },
                    }
                    await sts_ws.send(json.dumps(config_message))
                    print("[INFO] Sent config with error message as greeting to Deepgram")

                    # Create a stream state for audio handling
                    state = self._create_stream_state()

                    # Listen for Deepgram responses and forward audio to Twilio
                    audio_done = False
                    start_time = asyncio.get_event_loop().time()
                    timeout_seconds = 15.0  # Max time to wait for message to play

                    async for message in sts_ws:
                        elapsed = asyncio.get_event_loop().time() - start_time
                        if elapsed > timeout_seconds:
                            print("[WARN] Timeout waiting for error message audio")
                            break

                        if isinstance(message, str):
                            decoded = json.loads(message)
                            msg_type = decoded.get("type")

                            if msg_type == "AgentAudioDone":
                                # Flush remaining audio and mark as done
                                await self._flush_audio_buffer(state, twilio_ws, streamsid)
                                audio_done = True
                                # Give time for audio to play
                                await asyncio.sleep(2.0)
                                break
                            elif msg_type == "ConversationAudio":
                                # Forward audio to Twilio
                                await self._handle_audio_payload(decoded, state, twilio_ws, streamsid)

                        elif isinstance(message, (bytes, bytearray, memoryview)):
                            await self._handle_binary_audio(message, state, twilio_ws, streamsid)

                    if not audio_done:
                        await self._flush_audio_buffer(state, twilio_ws, streamsid)

                finally:
                    async with self._connections_lock:
                        self._active_deepgram.discard(sts_ws)

        except Exception as exc:
            print(f"[ERROR] Failed to play unregistered number message: {exc}")

        finally:
            # Signal shutdown and close connections
            shutdown_event.set()
            try:
                audio_queue.put_nowait(None)
            except asyncio.QueueFull:
                pass
            print("[INFO] Closing connection for unregistered Twilio number")

    async def _prepare_call_resources(
        self,
        restaurant_phone: Optional[str],
        caller_phone: Optional[str],
        restaurant_record: Optional[Dict[str, Any]] = None,
        deepgram_key_terms: Optional[Any] = None,
    ) -> CallResources:
        context_payload, restaurant_id, restaurant_phone_fwd, restaurant_name = await asyncio.to_thread(
            self._build_restaurant_context,
            caller_phone,
            restaurant_record,
        )
        think_prompt = prompt_loader.load_think_prompt(context_payload)
        return CallResources(
            context_payload=context_payload,
            restaurant_id=restaurant_id,
            restaurant_phone=restaurant_phone,
            restaurant_phone_fwd=restaurant_phone_fwd,
            restaurant_name=restaurant_name,
            deepgram_key_terms=deepgram_key_terms,
            think_prompt=think_prompt,
        )

    def _resolve_user_id(self, caller_phone: Optional[str], provided_user_id: Optional[str]) -> str:
        """
        Resolve a concrete Users.id to store on Calls.
        Preference: existing user by caller phone, then create a placeholder user, then fallback to provided ID.
        """
        fallback_user_id = str(provided_user_id) if provided_user_id else None

        if caller_phone:
            try:
                existing_id = self.user_repo.get_user_id_by_phone_or_email(caller_phone, None)
                if existing_id:
                    return str(existing_id)
                created_id = self.user_repo.create_user(
                    {
                        "name": None,
                        "phone_number": caller_phone,
                        "email": None,
                        "address": None,
                        "is_spam": False,
                        "credit_card": None,
                    }
                )
                if created_id:
                    return str(created_id)
            except Exception as exc:
                print(f"[WARN] Failed to resolve/create user for phone {caller_phone}: {exc}")

        if fallback_user_id:
            return fallback_user_id

        # No phone or provided user – use a safe sentinel to avoid breaking FK/analytics
        print("[WARN] No caller phone or provided user_id; defaulting to user_id=0 for call logging")
        return "0"

    def _build_function_router(self, sts_ws) -> Transport:
        registry = FunctionRegistry()
        registry.register(
            name="create_order",
            handler=orders.create_order,
            arg_model=orders.CreateOrderArgs,
        )
        registry.register(
            name="lookup_order",
            handler=orders.lookup_order,
            arg_model=orders.LookupOrderArgs,
        )
        registry.register(
            name="update_order_details",
            handler=orders.update_order_details,
            arg_model=orders.UpdateOrderDetailsArgs,
        )
        registry.register(
            name="check_items_availability",
            handler=orders.check_items_availability,
            arg_model=orders.CheckItemsAvailabilityArgs,
        )
        registry.register(
            name="list_menu_items",
            handler=menu.list_menu_items,
            arg_model=menu.ListMenuArgs,
        )
        registry.register(
            name="get_menu_item_details",
            handler=menu.get_menu_item_details,
            arg_model=menu.GetMenuItemDetailsArgs,
        )
        registry.register(
            name="create_reservation",
            handler=reservations.create_reservation,
            arg_model=reservations.CreateReservationArgs,
        )
        registry.register(
            name="lookup_reservation",
            handler=reservations.lookup_reservation,
            arg_model=reservations.LookupReservationArgs,
        )
        registry.register(
            name="update_reservation",
            handler=reservations.update_reservation,
            arg_model=reservations.UpdateReservationArgs,
        )
        registry.register(
            name="check_reservation_availability",
            handler=reservations.check_reservation_availability,
            arg_model=reservations.CheckAvailabilityArgs,
        )
        registry.register(
            name="agent_filler",
            handler=conversation.agent_filler,
            arg_model=conversation.AgentFillerArgs,
        )
        registry.register(
            name="end_call",
            handler=conversation.end_call,
            arg_model=conversation.EndCallArgs,
        )
        registry.register(
            name="escalate_to_human",
            handler=conversation.escalate_to_human,
            arg_model=conversation.EscalateToHumanArgs,
        )

        transport = Transport(send_callable=sts_ws.send)
        router = FunctionCallRouter(
            registry=registry,
            transport=transport,
            settings=get_fc_settings(),
        )
        transport.on_message(router.handle_frame)
        print("Function calling router initialized")
        return transport

    def _create_call_session(
        self,
        user_id: str,
        restaurant_id: Optional[str],
        twilio_sid: Optional[str],
        deepgram_session_id: Optional[str],
    ) -> Optional[str]:
        try:
            call_id = self.call_service.create_call_session(
                user_id,
                twilio_sid,
                deepgram_session_id,
                restaurant_id,
            )
            print(f"📞 Call session created: {call_id}")
            return str(call_id)
        except Exception as exc:
            print(f"[DB] create_call_session error: {exc}")
            return None

    def _create_stream_state(self) -> StreamState:
        return StreamState()

    async def _flush_audio_buffer(self, state: StreamState, twilio_ws, streamsid) -> None:
        if not state.audio_buffer:
            return
        payload = base64.b64encode(state.audio_buffer).decode("ascii")
        msg = {"event": "media", "streamSid": streamsid, "media": {"payload": payload}}
        try:
            await twilio_ws.send_text(json.dumps(msg))
            state.last_agent_audio_time = asyncio.get_event_loop().time()
            print(f"✅ Flushed {len(state.audio_buffer)} bytes to Twilio")
        except Exception as exc:
            print(f"Error sending buffered audio to Twilio: {exc}")
        state.audio_buffer.clear()

    async def _wait_for_farewell_playback(self, state: StreamState) -> None:
        """Allow buffered farewell audio to play before closing sockets."""
        grace_seconds = float(getattr(settings, "FAREWELL_PLAYBACK_GRACE_SECONDS", 3.5))
        if grace_seconds <= 0:
            return

        last_audio_time = state.last_agent_audio_time
        if last_audio_time is None:
            await asyncio.sleep(grace_seconds)
            return

        elapsed = asyncio.get_event_loop().time() - last_audio_time
        remaining = grace_seconds - elapsed
        if remaining > 0:
            await asyncio.sleep(remaining)

    def _update_barge_in_state(self, decoded: dict[str, Any], state: StreamState) -> None:
        event_type = decoded.get("type")
        if event_type == "AgentStartedSpeaking":
            state.agent_speaking = True
        elif event_type == "AgentAudioDone":
            state.agent_speaking = False
            state.barge_in_active = False
        elif event_type == "UserStartedSpeaking":
            state.barge_in_active = True
            state.barge_in_start_time = time.perf_counter()
            state.barge_in_reported = False
            state.audio_buffer.clear()
        elif event_type == "UserStoppedSpeaking":
            state.barge_in_active = False

    async def _handle_audio_payload(self, decoded: dict[str, Any], state: StreamState, twilio_ws, streamsid) -> None:
        if decoded.get("type") not in {"ConversationAudio", "AgentAudioDone"}:
            return
        if state.barge_in_active:
            if not state.barge_in_reported and state.barge_in_start_time is not None:
                delta = time.perf_counter() - state.barge_in_start_time
                print(f"Barge-in suppression delay: {delta:.3f}s")
                state.barge_in_reported = True
            return

        audio_payload = decoded.get("audio", "")
        if not audio_payload:
            return
        try:
            now = time.perf_counter()
            audio_bytes = base64.b64decode(audio_payload)
            state.audio_buffer.extend(audio_bytes)
            buffer_size = 3200
            while len(state.audio_buffer) >= buffer_size:
                chunk = state.audio_buffer[:buffer_size]
                del state.audio_buffer[:buffer_size]
                payload = base64.b64encode(chunk).decode("ascii")
                msg = {"event": "media", "streamSid": streamsid, "media": {"payload": payload}}
                await twilio_ws.send_text(json.dumps(msg))
                state.last_agent_audio_time = asyncio.get_event_loop().time()
                log_agent_audio_start_latency(state, now)
                print(f"✅ Sent ConversationAudio {len(chunk)} bytes to Twilio")
        except Exception as exc:
            print(f"Error processing ConversationAudio: {exc}")

    def _track_conversation_turn(
        self, decoded: dict[str, Any], state: StreamState, now: Optional[float] = None
    ) -> None:
        if decoded.get("type") != "ConversationText":
            return
        current_time = now or time.perf_counter()
        role = decoded.get("role")
        if role == "user":
            state.last_user_text_time = current_time
            state.in_function_chain = False
        elif role == "assistant":
            state.in_function_chain = False
            state.last_assistant_text_time = current_time
            state.agent_audio_latency_logged = False
            state.last_assistant_audio_start_time = None

    def _store_transcript_entry(self, decoded: dict[str, Any], call_id: Optional[str], state: StreamState) -> None:
        # Record only live ConversationText events to avoid duplicate transcript entries from History payloads.
        if decoded.get("type") != "ConversationText":
            return
        text = decoded.get("content")
        if not text:
            return
        role = decoded.get("role")
        state.message_seq += 1
        entry = {
            "role": role,
            "content": text,
            "timestamp": datetime.utcnow().isoformat(),
            "sequence": state.message_seq,
        }
        state.conversation_history.append(entry)

    async def _route_function_calls(
        self,
        decoded: dict[str, Any],
        state: StreamState,
        transport: Optional[Transport],
        sts_ws,
    ) -> None:
        if transport is None:
            return
        try:
            frame = AgentFrame.parse(decoded)
        except Exception:
            frame = None
        if not frame or frame.function_call is None:
            return

        now = time.perf_counter()
        if state.in_function_chain and state.last_function_response_time:
            latency = now - state.last_function_response_time
            print(f"LLM Decision Latency (chain): {latency:.3f}s")
        elif state.last_user_text_time:
            latency = now - state.last_user_text_time
            print(f"LLM Decision Latency (initial): {latency:.3f}s")
            state.in_function_chain = True

        exec_start = time.perf_counter()
        router_result = await transport.emit(decoded)
        exec_ms = (time.perf_counter() - exec_start) * 1000.0
        print(f"Function Execution Latency: {exec_ms:.2f}ms")
        state.last_function_response_time = time.perf_counter()

        if not router_result or not router_result.get("side_effects"):
            return
        effects_meta = await self._handle_side_effects(
            router_result["side_effects"],
            sts_ws,
        )
        if effects_meta.get("close_requested"):
            state.closing_after_farewell = True
            state.farewell_expected_text = effects_meta.get("farewell_message")
            state.farewell_started = state.farewell_expected_text is None
            print("[Call] Farewell close scheduled")

    async def _maybe_finish_farewell(
        self,
        decoded: dict[str, Any],
        state: StreamState,
        twilio_ws,
        sts_ws,
        streamsid,
        shutdown_event: Optional[asyncio.Event],
        audio_queue: Optional[asyncio.Queue] = None,
    ) -> bool:
        if not state.closing_after_farewell:
            return False
        event_type = decoded.get("type")
        if event_type == "AgentStartedSpeaking":
            state.farewell_started = True
        elif (
            event_type == "ConversationText"
            and decoded.get("role") == "assistant"
            and state.farewell_expected_text
            and decoded.get("content") == state.farewell_expected_text
        ):
            state.farewell_started = True
        elif event_type == "AgentAudioDone" and state.farewell_started:
            await self._flush_audio_buffer(state, twilio_ws, streamsid)
            await self._wait_for_farewell_playback(state)
            await self._graceful_shutdown_call(twilio_ws, sts_ws, shutdown_event, audio_queue)
            state.farewell_shutdown_complete = True
            return True
        return False

    async def _handle_binary_audio(
        self, message: bytes | bytearray | memoryview, state: StreamState, twilio_ws, streamsid
    ) -> None:
        now = time.perf_counter()
        try:
            state.audio_buffer.extend(message)
        except Exception as exc:
            print(f"[WARN] Failed to buffer binary audio payload ({type(message)}): {exc}")
            return
        # Keep outbound chunks small to reduce playback latency
        buffer_size = 5 * 160  # 800 bytes per ~100ms
        while len(state.audio_buffer) >= buffer_size:
            chunk = state.audio_buffer[:buffer_size]
            del state.audio_buffer[:buffer_size]
            payload = base64.b64encode(chunk).decode("ascii")
            msg = {"event": "media", "streamSid": streamsid, "media": {"payload": payload}}
            await twilio_ws.send_text(json.dumps(msg))
            state.last_agent_audio_time = asyncio.get_event_loop().time()
            log_agent_audio_start_latency(state, now)

    async def handle_barge_in(self, decoded, twilio_ws, streamsid, last_agent_audio_time):
        """Clear Twilio audio only if user starts speaking after a gap."""
        if decoded.get("type") == "UserStartedSpeaking":
            now = asyncio.get_event_loop().time()
            threshold = float(getattr(settings, "BARGE_IN_CLEAR_SECONDS", 0.5))
            if not last_agent_audio_time or (now - last_agent_audio_time) > threshold:
                clear_msg = {"event": "clear", "streamSid": streamsid}
                await twilio_ws.send_text(json.dumps(clear_msg))
                print(f"🧹 Cleared Twilio buffer after {now - (last_agent_audio_time or 0):.2f}s")

    async def handle_text_message(self, decoded, twilio_ws, sts_ws, streamsid, last_agent_audio_time):
        """Handle text messages and barge-in logic."""
        await self.handle_barge_in(decoded, twilio_ws, streamsid, last_agent_audio_time)

    async def buffer_flusher(
        self,
        shared_buffer: bytearray,
        audio_queue: asyncio.Queue,
        shutdown_event: Optional[asyncio.Event] = None,
        buffer_lock: Optional[asyncio.Lock] = None,
    ) -> None:
        """Periodically flush partial inbound audio to keep Deepgram connection active."""
        flush_interval = 0.3
        try:
            while True:
                if shutdown_event and shutdown_event.is_set():
                    # Flush remaining buffered audio before exiting
                    if buffer_lock:
                        async with buffer_lock:
                            if shared_buffer:
                                await audio_queue.put(bytes(shared_buffer))
                                shared_buffer.clear()
                    elif shared_buffer:
                        await audio_queue.put(bytes(shared_buffer))
                        shared_buffer.clear()
                    break

                await asyncio.sleep(flush_interval)
                chunk = None
                if buffer_lock:
                    async with buffer_lock:
                        if not shared_buffer:
                            chunk = None
                        else:
                            chunk = bytes(shared_buffer)
                            shared_buffer.clear()
                else:
                    if not shared_buffer:
                        chunk = None
                    else:
                        chunk = bytes(shared_buffer)
                        shared_buffer.clear()
                if chunk:
                    await audio_queue.put(chunk)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            if not shutdown_event or not shutdown_event.is_set():
                print(f"buffer_flusher error: {exc}")

    async def sts_sender(self, sts_ws, audio_queue, shutdown_event: Optional[asyncio.Event] = None):
        """Send audio chunks to Deepgram STS."""
        print("sts_sender started")
        try:
            while True:
                if shutdown_event and shutdown_event.is_set():
                    break
                try:
                    chunk = await asyncio.wait_for(audio_queue.get(), timeout=0.5)
                except asyncio.TimeoutError:
                    continue
                if chunk is None:
                    break
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
        transport: Optional[Transport] = None,
        shutdown_event: Optional[asyncio.Event] = None,
        audio_queue: Optional[asyncio.Queue] = None,
        state: Optional[StreamState] = None,
    ):
        """Receive messages from Deepgram STS and forward to Twilio."""
        print("sts_receiver started")
        streamsid = await streamsid_queue.get()
        start_time = asyncio.get_event_loop().time()
        state = state or self._create_stream_state()

        try:
            async for message in sts_ws:
                if isinstance(message, str):
                    decoded = json.loads(message)
                    message_type = decoded.get("type")
                    now = time.perf_counter()
                    if message_type == "History":
                        pass  # Don't print history entries to reduce noise
                    elif message_type == "ConversationText":
                        role = decoded.get("role", "unknown")
                        content = decoded.get("content", "")
                        print(f"{role}: {content}")
                    else:
                        print(f"Deepgram Message: {decoded}")

                    if message_type == "UserStartedSpeaking":
                        state.last_user_started_speaking_time = now
                        self._filler_manager.cancel(state)
                    elif message_type == "ConversationText":
                        role = decoded.get("role")
                        self._track_conversation_turn(decoded, state, now)
                        if role == "user":
                            self._filler_manager.schedule(state, sts_ws)
                        elif role == "assistant":
                            self._filler_manager.cancel(state)
                            log_assistant_text_latency(state, now)
                    elif message_type in {"ConversationAudio", "AgentAudioDone", "AgentStartedSpeaking"}:
                        self._filler_manager.cancel(state)

                    farewell_finished = await self._maybe_finish_farewell(
                        decoded, state, twilio_ws, sts_ws, streamsid, shutdown_event, audio_queue
                    )
                    if farewell_finished:
                        break

                    self._update_barge_in_state(decoded, state)
                    await self._handle_audio_payload(decoded, state, twilio_ws, streamsid)
                    await self.handle_text_message(decoded, twilio_ws, sts_ws, streamsid, state.last_agent_audio_time)
                    await self._route_function_calls(decoded, state, transport, sts_ws)
                    self._store_transcript_entry(decoded, call_id, state)

                    if decoded.get("type") == "AgentAudioDone" and not state.closing_after_farewell:
                        await self._flush_audio_buffer(state, twilio_ws, streamsid)
                        continue

                elif isinstance(message, (bytes, bytearray, memoryview)):
                    await self._handle_binary_audio(message, state, twilio_ws, streamsid)
                else:
                    print(f"[WARN] Dropping unexpected Deepgram payload type: {type(message)}")
                    continue

            if not state.farewell_shutdown_complete:
                await self._flush_audio_buffer(state, twilio_ws, streamsid)
        except (websockets.exceptions.ConnectionClosed, websockets.exceptions.ConnectionClosedOK):
            print("sts_receiver: Deepgram connection closed")
        except asyncio.CancelledError:
            print("sts_receiver cancelled")
            raise
        finally:
            end_time = asyncio.get_event_loop().time()
            duration = int(end_time - start_time)
            self._filler_manager.cancel(state)
            try:
                if call_id:
                    self.call_service.update_call_cost(call_id, duration)
            except Exception as exc:
                print(f"[WARN] Error updating call cost: {exc}")

    async def twilio_receiver(
        self,
        twilio_ws,
        audio_queue,
        streamsid_queue,
        shutdown_event: Optional[asyncio.Event] = None,
        to_number_queue: Optional[asyncio.Queue] = None,
        from_number_queue: Optional[asyncio.Queue] = None,
        call_sid_queue: Optional[asyncio.Queue] = None,
        shared_buffer: Optional[bytearray] = None,
        buffer_lock: Optional[asyncio.Lock] = None,
    ):
        """Receive audio from Twilio and forward to Deepgram."""
        # Smaller buffer reduces turnaround latency (~0.1s chunks)
        buffer_size = 5 * 160  # 800 bytes per ~100ms
        inbuffer = shared_buffer if shared_buffer is not None else bytearray()

        try:
            async for message in twilio_ws.iter_text():
                if shutdown_event and shutdown_event.is_set():
                    break
                data = json.loads(message)
                event = data.get("event")

                if event == "start":
                    streamsid = data["start"]["streamSid"]
                    await streamsid_queue.put(streamsid)
                    params = data.get("start", {}).get("customParameters", {}) or {}
                    call_sid = data.get("start", {}).get("callSid")
                    to_number = params.get("toNumber")
                    from_number = params.get("fromNumber")
                    if to_number_queue and to_number:
                        await to_number_queue.put(to_number)
                    if from_number_queue and from_number:
                        await from_number_queue.put(from_number)
                    if call_sid_queue and call_sid:
                        await call_sid_queue.put(call_sid)
                    print(f"📞 Stream started: {streamsid}, to={to_number}, from={from_number}")
                elif event == "media":
                    chunk = base64.b64decode(data["media"]["payload"])
                    if data["media"]["track"] == "inbound":
                        if buffer_lock:
                            async with buffer_lock:
                                inbuffer.extend(chunk)
                        else:
                            inbuffer.extend(chunk)
                elif event == "stop":
                    print("🛑 Twilio stop event received - closing gracefully")
                    break

                while True:
                    if buffer_lock:
                        async with buffer_lock:
                            if len(inbuffer) < buffer_size:
                                break
                            chunk_to_send = inbuffer[:buffer_size]
                            del inbuffer[:buffer_size]
                    else:
                        if len(inbuffer) < buffer_size:
                            break
                        chunk_to_send = inbuffer[:buffer_size]
                        del inbuffer[:buffer_size]
                    await audio_queue.put(chunk_to_send)

        except (WebSocketDisconnect, ConnectionError) as exc:
            print(f"Twilio receiver disconnected: {exc}")
        except asyncio.CancelledError:
            print("twilio_receiver cancelled")
            raise
        except Exception as e:
            if shutdown_event and shutdown_event.is_set():
                print("Twilio receiver closed after shutdown")
            else:
                print(f"Twilio receiver error: {e}")
        finally:
            if buffer_lock:
                async with buffer_lock:
                    if inbuffer:
                        await audio_queue.put(bytes(inbuffer))
                        inbuffer.clear()
            elif inbuffer:
                await audio_queue.put(bytes(inbuffer))
                inbuffer.clear()
            if shutdown_event and not shutdown_event.is_set():
                shutdown_event.set()
            try:
                audio_queue.put_nowait(None)
            except asyncio.QueueFull:
                # Best-effort sentinel; queue is already saturated so receiver will exit shortly.
                print("[WARN] audio_queue full while sending shutdown sentinel")

    async def twilio_websocket_handler(
        self,
        twilio_ws: WebSocket,
        user_id: Optional[str] = None,
        restaurant_twilio_number: Optional[str] = None,
        caller_number: Optional[str] = None,
    ) -> None:
        """Main WebSocket handler for Twilio connections."""

        await twilio_ws.accept()
        async with self._connections_lock:
            self._active_twilio.add(twilio_ws)

        audio_queue: asyncio.Queue = asyncio.Queue()
        streamsid_queue: asyncio.Queue = asyncio.Queue()
        to_number_queue: asyncio.Queue = asyncio.Queue()
        from_number_queue: asyncio.Queue = asyncio.Queue()
        call_sid_queue: asyncio.Queue = asyncio.Queue()
        shutdown_event = asyncio.Event()
        shared_buffer = bytearray()
        buffer_lock = asyncio.Lock()
        state = self._create_stream_state()
        call_id = None
        call_sid: Optional[str] = None
        transport: Optional[Transport] = None
        restaurant_record: Optional[Dict[str, Any]] = None
        deepgram_api_key: Optional[str] = None
        deepgram_key_terms: Optional[Any] = None

        twilio_task = asyncio.create_task(
            self.twilio_receiver(
                twilio_ws,
                audio_queue,
                streamsid_queue,
                shutdown_event,
                to_number_queue,
                from_number_queue,
                call_sid_queue,
                shared_buffer,
                buffer_lock,
            )
        )
        flusher_task = asyncio.create_task(self.buffer_flusher(shared_buffer, audio_queue, shutdown_event, buffer_lock))

        try:
            # Use values provided by API first; fall back to Twilio start event if missing.
            if not restaurant_twilio_number:
                try:
                    restaurant_twilio_number = await asyncio.wait_for(to_number_queue.get(), timeout=0.5)
                except asyncio.TimeoutError:
                    restaurant_twilio_number = None
            if not caller_number:
                try:
                    caller_number = await asyncio.wait_for(from_number_queue.get(), timeout=0.5)
                except asyncio.TimeoutError:
                    caller_number = None
            if not call_sid:
                try:
                    call_sid = await asyncio.wait_for(call_sid_queue.get(), timeout=0.5)
                except asyncio.TimeoutError:
                    call_sid = None

            restaurant_record = self.restaurant_service.get_restaurant_by_twilio(restaurant_twilio_number)
            if not restaurant_record:
                print(f"[FATAL ERROR] No restaurant found with twilio number: {restaurant_twilio_number}")
                # Play an error message to the caller before disconnecting
                await self._handle_unregistered_twilio_call(twilio_ws, streamsid_queue, shutdown_event, audio_queue)
                return
            else:
                print(f"Serving call for restaurant: {restaurant_record.get('name')}")

            deepgram_details = restaurant_record.get("deepgram_details") if restaurant_record else None
            if isinstance(deepgram_details, str):
                try:
                    deepgram_details = json.loads(deepgram_details)
                except json.JSONDecodeError:
                    deepgram_details = None
            if isinstance(deepgram_details, dict):
                deepgram_api_key = deepgram_details.get("api_key") or deepgram_details.get("apiKey")
                deepgram_key_terms = deepgram_details.get("key_terms") or deepgram_details.get("keyTerms")
                if isinstance(deepgram_api_key, str):
                    deepgram_api_key = deepgram_api_key.strip() or None

            call_resources = await self._prepare_call_resources(
                restaurant_twilio_number, caller_number, restaurant_record, deepgram_key_terms
            )

            try:
                async with self.deepgram_service.sts_connect(api_key=deepgram_api_key) as sts_ws:
                    async with self._connections_lock:
                        self._active_deepgram.add(sts_ws)

                    try:
                        print("🔗 Connected to Deepgram STS")
                        config_message = self.deepgram_service.load_config(
                            think_prompt=call_resources.think_prompt,
                            key_terms=call_resources.deepgram_key_terms or None,
                            restaurant_name=call_resources.restaurant_name,
                        )
                        config_message_json = json.dumps(config_message)
                        print(f"Deepgram agent config: {config_message_json}")
                        await sts_ws.send(config_message_json)

                        transport = self._build_function_router(sts_ws)
                        resolved_user_id = self._resolve_user_id(caller_number, user_id)
                        call_id = self._create_call_session(
                            resolved_user_id, call_resources.restaurant_id, call_sid, None
                        )

                        tasks = [
                            twilio_task,
                            flusher_task,
                            asyncio.create_task(self.sts_sender(sts_ws, audio_queue, shutdown_event)),
                            asyncio.create_task(
                                self.sts_receiver(
                                    sts_ws,
                                    twilio_ws,
                                    streamsid_queue,
                                    call_id,
                                    user_id,
                                    transport,
                                    shutdown_event,
                                    audio_queue,
                                    state,
                                )
                            ),
                        ]
                        try:
                            done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
                            # Signal shutdown to remaining tasks and drain queues
                            shutdown_event.set()
                            try:
                                audio_queue.put_nowait(None)
                            except asyncio.QueueFull:
                                pass
                            for task in pending:
                                task.cancel()
                            await asyncio.gather(*tasks, return_exceptions=True)
                        finally:
                            for task in tasks:
                                if not task.done():
                                    task.cancel()
                            await asyncio.gather(*tasks, return_exceptions=True)
                    finally:
                        async with self._connections_lock:
                            self._active_deepgram.discard(sts_ws)
            except websockets.exceptions.InvalidStatusCode as exc:
                if exc.status_code == 401:
                    print(
                        "[Deepgram] Unauthorized (401). Check that DEEPGRAM_API_KEY is valid "
                        "for the restaurant or environment."
                    )
                raise
        except WebSocketDisconnect:
            print("Client disconnected")
        except Exception as e:
            print(f"Error in twilio_websocket_handler: {e}")
        finally:
            if shutdown_event and not shutdown_event.is_set():
                shutdown_event.set()
            try:
                audio_queue.put_nowait(None)
            except asyncio.QueueFull:
                pass

            # Ensure background tasks are stopped
            for task in (twilio_task, flusher_task):
                if task and not task.done():
                    task.cancel()
            await asyncio.gather(twilio_task, flusher_task, return_exceptions=True)

            async with self._connections_lock:
                self._active_twilio.discard(twilio_ws)
            try:
                await twilio_ws.close()
            except Exception:
                pass

            if state.conversation_history and call_id:
                try:
                    self.call_service.save_call_transcript(call_id, state.conversation_history)
                    print("[INFO] Transcript stored to Calls.call_transcript")
                except Exception as exc:
                    print(f"[WARN] Failed to store call transcript: {exc}")

            print("🔌 Twilio connection closed")
