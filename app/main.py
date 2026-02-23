import asyncio
import urllib.parse
from contextlib import asynccontextmanager
from typing import Any, Optional
from xml.sax.saxutils import escape

from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from starlette.requests import Request
from starlette.responses import Response

from app.api import (
    activity_history,
    admin_notifications,
    admin_users,
    auth,
    calls,
    client_analytics,
    client_calls,
    client_client_users,
    client_escalations,
    client_faqs,
    client_menu_options,
    client_menus,
    client_restaurant,
    client_users,
    dashboard_notifications,
    dashboard_orders,
    dashboard_reservations,
    dashboard_users,
    escalations,
    faqs,
    menu_options,
    menus,
    opentable,
    reservations,
    restaurants,
    sse,
    testing,
)
from app.api.websocket import twilio_websocket_handler
from app.repositories.db_pool import close_db_pool, get_db_pool
from app.services.call_service import CallService
from app.services.escalation_service import EscalationService
from app.services.notification_persistence_service import NotificationPersistenceService
from app.services.restaurant_service import RestaurantService
from app.services.sse_service import SSEService
from app.services.user_service import UserService
from app.utils.encoding import install_utc_jsonable_encoder
from app.utils.logging_config import get_logger, setup_logging
from app.utils.utc_json_response import UTCJSONResponse

load_dotenv()
setup_logging()
logger = get_logger(__name__)
install_utc_jsonable_encoder()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup and shutdown events."""
    # Startup: Initialize database connection pool
    try:
        db_pool = get_db_pool()
        if db_pool.is_available:
            stats = db_pool.get_pool_stats()
            print(f"[Startup] Database pool initialized: {stats}")
        else:
            print("[Startup] Database pool not available (may be in test mode)")
    except Exception as e:
        print(f"[Startup] Warning - Database pool initialization: {e}")

    yield

    # Shutdown: cleanup SSE connections and heartbeat task
    sse_service = SSEService()
    await sse_service.shutdown()

    # Shutdown: Close database connection pool
    try:
        close_db_pool()
        print("[Shutdown] Database pool closed")
    except Exception as e:
        print(f"[Shutdown] Warning - Database pool cleanup: {e}")


app = FastAPI(
    title="RessyAI Backend",
    version="1.0.0",
    description="FastAPI backend for a multitenant, function-calling voice agent. Manages restaurants, menus, orders, reservations, calls, and user authentication.",
    lifespan=lifespan,
    default_response_class=UTCJSONResponse,
    swagger_ui_parameters={
        "persistAuthorization": True,  # Keep auth token across page refreshes
        "displayRequestDuration": True,  # Show request duration
        "filter": True,  # Enable filtering by tag
        "docExpansion": "none",  # Collapse all by default
    },
    openapi_tags=[
        {
            "name": "Authentication",
            "description": "User authentication and authorization endpoints. Handle login, logout, and token refresh for both admin and restaurant users.",
        },
        {
            "name": "Calls",
            "description": "Voice call management endpoints. Track call history, transcripts, and analytics for restaurant voice interactions.",
        },
        {
            "name": "Escalations",
            "description": "Escalation management endpoints for Admin and Client dashboards. Admins can access all restaurants; client endpoints are scoped to the authenticated restaurant.",
        },
        {
            "name": "Dashboard - Notifications",
            "description": "Persistent notifications for the dashboard. List, read, and mark as read notifications for the authenticated restaurant.",
        },
        {
            "name": "Admin - Notifications",
            "description": "Admin notification management. List and view notifications across all restaurants.",
        },
        {
            "name": "Menus",
            "description": "Menu management endpoints for Admin and Client CRM. Full CRUD, categories, availability, specials, and bulk updates; client endpoints are auto-scoped to the token restaurant.",
        },
        {
            "name": "Restaurants",
            "description": "Restaurant management endpoints for Admin CRM; Client CRM can read/update its own restaurant only.",
        },
        {
            "name": "FAQs",
            "description": "Frequently Asked Questions management for Admin and Client CRM. Admin can manage any restaurant; client endpoints are scoped to the token restaurant.",
        },
        {
            "name": "OpenTable",
            "description": "OpenTable integration endpoints. Manage reservations through the OpenTable API integration.",
        },
        {
            "name": "Reservations",
            "description": "In-house reservation management endpoints. Handle table availability, slot locking, and reservation creation.",
        },
        {
            "name": "Dashboard Reservations",
            "description": "Dashboard reservation management with RBAC. Admins access all restaurants; managers access only their restaurant's reservations.",
        },
        {
            "name": "Dashboard Users",
            "description": "Dashboard-specific user management with RBAC. Create, view, update, and delete customer users. Includes user statistics (calls, orders, reservations). Admins can access all restaurants; restaurant managers can only access their own restaurant's users.",
        },
        {
            "name": "Admin Users",
            "description": "Ressy platform admin user management (Admin CRM). Create, update, list, reset passwords, and manage roles.",
        },
        {
            "name": "Client Users",
            "description": "Restaurant client CRM users (admins/staff). Admin CRM can manage all; Client CRM (manager role) manages its own restaurant. Self password reset supported.",
        },
        {
            "name": "Client Analytics",
            "description": "Restaurant analytics for client dashboards. Provides insights on calls, reservations, orders, menu items, FAQs, and customers. All endpoints are scoped to the authenticated restaurant user's restaurant.",
        },
        {
            "name": "Dashboard Orders",
            "description": "Dashboard-specific order management with RBAC. Create, view, update, cancel, and soft-delete orders. Admins can access all restaurants; restaurant managers can only access their own restaurant's orders.",
        },
        {
            "name": "Activity History",
            "description": "Activity history and audit logs for orders and reservations. Track all changes including creation, updates, status changes, and cancellations. Supports RBAC: admins can access all restaurants; managers can only access their own restaurant's history.",
        },
        {
            "name": "Server-Sent Events",
            "description": "Real-time event streaming via Server-Sent Events (SSE). Subscribe to live updates for orders, reservations, and escalations. Supports escalation events (user_requested, internal_server_error, suspected_spam, sms_redirect_failed, kill_switch_redirected), order events (new_order, order_updated, order_cancelled), and reservation events (new_reservation, reservation_updated, reservation_cancelled).",
        },
        {
            "name": "Voice Agent",
            "description": "Voice agent webhook endpoints for Twilio integration. Handles incoming calls and WebSocket streaming for the voice agent system.",
        },
        {
            "name": "Outbound Calls",
            "description": "Developer testing endpoints to initiate outbound calls (typically to a developer's own phone) to validate the end-to-end call flow without needing an external caller to dial in.",
        },
    ],
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api/v1/auth", tags=["Authentication"])
app.include_router(calls.router)
app.include_router(client_calls.router)
app.include_router(escalations.router)
app.include_router(client_escalations.router)
app.include_router(dashboard_notifications.router)
app.include_router(admin_notifications.router)
app.include_router(menus.router)
app.include_router(menu_options.router)
app.include_router(
    restaurants.router
    # Note: restaurants router declares its own prefix/tags to keep Admin CRM docs localized.
)
app.include_router(faqs.router)
app.include_router(opentable.router, prefix="/api/v1/opentable", tags=["OpenTable"])
app.include_router(reservations.router, prefix="/api/v1/reservations", tags=["Reservations"])
app.include_router(dashboard_reservations.router, prefix="/api/v1/dashboard", tags=["Dashboard Reservations"])
app.include_router(dashboard_orders.router, prefix="/api/v1/dashboard", tags=["Dashboard Orders"])
app.include_router(dashboard_users.router, prefix="/api/v1/dashboard", tags=["Dashboard Users"])
app.include_router(activity_history.router, prefix="/api/v1/dashboard", tags=["Activity History"])
app.include_router(sse.router, prefix="/api/v1/sse", tags=["Server-Sent Events"])
app.include_router(admin_users.router, tags=["Admin Users"])
app.include_router(client_users.router, tags=["Client Users"])
app.include_router(client_faqs.router)
app.include_router(client_menus.router)
app.include_router(client_menu_options.router)
app.include_router(client_restaurant.router)
app.include_router(client_client_users.router)
app.include_router(client_analytics.router, tags=["Client Analytics"])

# Testing routes (keep last)
app.include_router(testing.router)
app.include_router(testing.callback_router)


# WebSocket Endpoint
@app.websocket("/twilio")
async def twilio_websocket(websocket: WebSocket):
    """
    WebSocket endpoint for Twilio audio streaming.

    **Purpose**: Real-time bidirectional audio streaming between Twilio and Deepgram STS
    for voice agent call processing.

    **Query Parameters**:
    - fromNumber: Phone number of the caller
    - toNumber: Restaurant's Twilio phone number

    **Protocol**: WebSocket (not REST API)
    **Note**: This endpoint is used internally by the voice agent system and does not appear in OpenAPI/Swagger documentation.
    """
    await twilio_websocket_handler(websocket)


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    try:
        return bool(int(value))
    except (TypeError, ValueError):
        return str(value).strip().lower() in {"true", "yes", "on"}


async def _record_kill_switch_bypass(
    *,
    restaurant: dict,
    caller_phone: Optional[str],
    call_sid: Optional[str],
) -> None:
    """
    Persist side effects for a call bypassed by restaurant kill switch.
    Best-effort only: failures are logged and do not block TwiML response.
    """
    restaurant_id_raw = restaurant.get("id")
    restaurant_id_str = str(restaurant_id_raw) if restaurant_id_raw is not None else None
    try:
        restaurant_id_int = int(restaurant_id_raw) if restaurant_id_raw is not None else None
    except (TypeError, ValueError):
        restaurant_id_int = None

    reason = "Call redirected because restaurant kill switch is enabled"
    escalation_phone = str(restaurant.get("escalation_phone_number") or "").strip() or None

    user_id: Optional[int] = None
    call_id: Optional[int] = None
    escalation_id: Optional[int] = None

    try:
        user_payload = {"phone_number": caller_phone} if caller_phone else {}
        user_result = UserService().create_user(user_payload)
        user_id_value = user_result.get("user_id")
        user_id = int(user_id_value) if user_id_value is not None else None
    except Exception as exc:  # noqa: BLE001 - defensive
        logger.warning("Kill-switch bypass: failed to resolve/create user for caller=%s: %s", caller_phone, exc)

    if user_id is not None and restaurant_id_str is not None:
        try:
            call_id = int(CallService().create_call_session(str(user_id), call_sid, None, restaurant_id_str))
        except Exception as exc:  # noqa: BLE001 - defensive
            logger.warning("Kill-switch bypass: failed to create call session call_sid=%s: %s", call_sid, exc)

    if call_id is not None:
        try:
            CallService().finalize_call_with_status(call_id, "agent_bypassed", duration_seconds=0, cost=0.0)
        except Exception as exc:  # noqa: BLE001 - defensive
            logger.warning("Kill-switch bypass: failed to finalize call_id=%s: %s", call_id, exc)

    if call_id is not None and user_id is not None and restaurant_id_str is not None:
        try:
            escalation_id = int(
                EscalationService().create_escalation(
                    {
                        "call_id": call_id,
                        "user_id": str(user_id),
                        "restaurant_id": restaurant_id_str,
                        "twilio_call_sid": call_sid,
                        "caller_phone": caller_phone,
                        "escalation_phone_number": escalation_phone,
                        "urgency": "standard",
                        "reason": reason,
                        "status": "raised",
                    }
                )
            )
        except Exception as exc:  # noqa: BLE001 - defensive
            logger.warning("Kill-switch bypass: failed to create escalation call_sid=%s: %s", call_sid, exc)

    if escalation_id is not None:
        try:
            EscalationService().mark_forwarded(escalation_id)
        except Exception as exc:  # noqa: BLE001 - defensive
            logger.warning("Kill-switch bypass: failed to mark escalation forwarded id=%s: %s", escalation_id, exc)

    if restaurant_id_int is not None:
        try:
            await SSEService().emit_escalation_kill_switch_redirected(
                restaurant_id=restaurant_id_int,
                call_id=str(call_id) if call_id is not None else None,
                caller_phone=caller_phone,
                reason=reason,
                data={"twilio_call_sid": call_sid},
            )
        except Exception as exc:  # noqa: BLE001 - defensive
            logger.warning("Kill-switch bypass: failed to emit SSE event restaurant_id=%s: %s", restaurant_id_int, exc)

        try:
            NotificationPersistenceService().create_notification(
                restaurant_id=restaurant_id_int,
                type="escalation",
                subtype="kill_switch_redirected",
                data={
                    "caller_phone": caller_phone,
                    "reason": reason,
                    "urgency": "standard",
                    "twilio_call_sid": call_sid,
                    "escalation_phone_number": escalation_phone,
                    "escalation_id": escalation_id,
                },
                entity_id=escalation_id if escalation_id is not None else call_id,
            )
        except Exception as exc:  # noqa: BLE001 - defensive
            logger.warning(
                "Kill-switch bypass: failed to persist notification restaurant_id=%s: %s",
                restaurant_id_int,
                exc,
            )


async def _record_kill_switch_bypass_safe(
    *,
    restaurant: dict,
    caller_phone: Optional[str],
    call_sid: Optional[str],
) -> None:
    """Wrapper to ensure background kill-switch side effects never raise out of task."""
    try:
        await _record_kill_switch_bypass(
            restaurant=restaurant,
            caller_phone=caller_phone,
            call_sid=call_sid,
        )
    except Exception as exc:  # pragma: no cover - defensive
        logger.exception("Kill-switch bypass background task failed call_sid=%s: %s", call_sid, exc)


@app.post(
    "/voice",
    summary="Twilio Voice Webhook",
    description="Twilio webhook endpoint that receives incoming call requests and returns TwiML. "
    "By default, calls are connected to the WebSocket stream. If the restaurant kill switch is enabled and forwarding is configured, the call is immediately redirected to escalation_phone_number.",
    response_description="TwiML XML response instructing Twilio to either connect to the WebSocket stream or immediately dial escalation staff.",
    tags=["Voice Agent"],
    include_in_schema=True,
)
async def voice(request: Request):
    """
    Twilio voice webhook endpoint.

    **Purpose**: Receives incoming call webhooks from Twilio and sets up WebSocket streaming.

    **Request**: Form data from Twilio including:
    - From: Caller's phone number
    - To: Restaurant's Twilio phone number
    - CallSid: Twilio call session ID

    **Response**: TwiML XML that instructs Twilio to:
    - Connect the call to the WebSocket stream at /twilio for normal agent flow
    - OR immediately forward to staff when kill switch is enabled and forwarding is configured

    **Note**: This is a Twilio webhook endpoint, not a standard REST API endpoint.
    """
    try:
        form = await request.form()
        # Twilio provides these in POST form data.
        twilio_from = form.get("From")
        twilio_to = form.get("To")
        call_sid = form.get("CallSid")

        # For outbound calls, Twilio flips To/From (To becomes the destination phone).
        # Allow overriding toNumber/fromNumber via query params so we can keep websocket routing consistent:
        # - toNumber should be the restaurant's Twilio number
        # - fromNumber should be the end-caller phone (developer/user)
        qp = request.query_params
        from_number = qp.get("fromNumber") or twilio_from
        to_number = qp.get("toNumber") or twilio_to

        logger.info(
            "Incoming call call_sid=%s from=%s to=%s (ws from=%s to=%s)",
            call_sid,
            twilio_from,
            twilio_to,
            from_number,
            to_number,
        )

        restaurant = {}
        if to_number:
            try:
                restaurant = RestaurantService().get_restaurant_by_twilio(to_number) or {}
            except Exception as exc:  # noqa: BLE001 - defensive
                logger.warning("Kill-switch check failed for to=%s call_sid=%s: %s", to_number, call_sid, exc)
                restaurant = {}

        if restaurant and _as_bool(restaurant.get("kill_switch_enabled")):
            forward_escalations = _as_bool(restaurant.get("forward_escalations"))
            escalation_phone = str(restaurant.get("escalation_phone_number") or "").strip()
            if forward_escalations and escalation_phone:
                logger.warning(
                    "Kill switch active for restaurant_id=%s call_sid=%s. Redirecting call to escalation number.",
                    restaurant.get("id"),
                    call_sid,
                )
                asyncio.create_task(
                    _record_kill_switch_bypass_safe(
                        restaurant=restaurant,
                        caller_phone=from_number,
                        call_sid=call_sid,
                    )
                )
                dial_number = escape(escalation_phone)
                caller_id = escape(str(to_number))
                xml = f"""
                <Response>
                    <Dial callerId="{caller_id}" timeout="25">
                        <Number>{dial_number}</Number>
                    </Dial>
                </Response>
                """
                return Response(content=xml.strip(), media_type="application/xml")
            logger.warning(
                "Kill switch active but forwarding misconfigured for restaurant_id=%s call_sid=%s. "
                "Falling back to agent routing.",
                restaurant.get("id"),
                call_sid,
            )

        params = {
            "fromNumber": from_number,
            "toNumber": to_number,
        }
        filtered_params = {k: v for k, v in params.items() if v}
        query = urllib.parse.urlencode(filtered_params)
        url = request.url
        host = url.hostname
        stream_url = f"wss://{host}/twilio"
        if query:
            stream_url = f"{stream_url}?{query}"

        stream_url = escape(stream_url)
        redirect_url = f"https://{host}/redirect"
        # Escape user-controlled values before embedding into TwiML XML.
        from_number_xml = escape(from_number) if from_number is not None else ""
        to_number_xml = escape(to_number) if to_number is not None else ""
        xml = f"""
        <Response>
            <Say language="en">"This call may be monitored or recorded."</Say>
            <Connect>
                <Stream url="{stream_url}">
                    <Parameter name="fromNumber" value="{from_number_xml}"/>
                    <Parameter name="toNumber" value="{to_number_xml}"/>
                </Stream>
            </Connect>
            <Redirect method="POST">{redirect_url}</Redirect>
        </Response>
        """
        return Response(content=xml.strip(), media_type="application/xml")
    except Exception as exc:
        logger.exception("[ERROR] voice endpoint failed: %s", exc)
        error_xml = """
        <Response>
            <Say>We are experiencing technical difficulties. Please try again shortly.</Say>
        </Response>
        """
        return Response(content=error_xml.strip(), media_type="application/xml", status_code=500)


@app.post(
    "/redirect",
    summary="Twilio Call Redirection Endpoint",
    description="Twilio webhook endpoint that, if required, redirects twilio calls for escalations using TwiML. "
    "This endpoint is called by Twilio after the websocket stream from our /twilio endpoint has closed. ",
    response_description="TwiML XML response instructing Twilio to either forward an escalated call or do nothing.",
    tags=["Voice Agent"],
    include_in_schema=True,
)
async def redirect(request: Request):
    escalation_id = None
    try:
        form = await request.form()
        call_sid = form.get("CallSid")
        twilio_to = form.get("To")
        twilio_from = form.get("From")

        logger.info("Redirect webhook received call_sid=%s from=%s to=%s", call_sid, twilio_from, twilio_to)

        if not call_sid or not twilio_to:
            logger.warning("Redirect webhook missing CallSid or To; hanging up")
            return Response(content="<Response><Hangup/></Response>", media_type="application/xml")

        restaurant_service = RestaurantService()
        escalation_service = EscalationService()
        restaurant = restaurant_service.get_restaurant_by_twilio(twilio_to)
        if not restaurant:
            logger.warning("Redirect webhook no restaurant matched to=%s call_sid=%s", twilio_to, call_sid)
            return Response(content="<Response><Hangup/></Response>", media_type="application/xml")

        restaurant_id = str(restaurant.get("id"))
        escalation = escalation_service.get_latest_by_call_sid_and_restaurant(call_sid, restaurant_id)
        if not escalation:
            logger.info("No escalation found for call_sid=%s restaurant_id=%s", call_sid, restaurant_id)
            return Response(content="<Response><Hangup/></Response>", media_type="application/xml")
        escalation_id = escalation.get("id")

        forward_escalations = restaurant.get("forward_escalations")
        escalation_phone = restaurant.get("escalation_phone_number")
        if forward_escalations and escalation_phone:
            logger.info(
                "Call escalation requested and forwarding is enabled. Forwarding call to %s [call_sid: %s]",
                escalation_phone,
                call_sid,
            )
            escalation_service.mark_forwarded(escalation_id)
            dial_number = escape(str(escalation_phone))
            xml = f"""
            <Response>
                <Dial callerId="{twilio_to}" timeout="25">
                    <Number>{dial_number}</Number>
                </Dial>
            </Response>
            """
            return Response(content=xml.strip(), media_type="application/xml")

        return Response(content="<Response><Hangup/></Response>", media_type="application/xml")
    except Exception as exc:
        logger.exception("[ERROR] redirect endpoint failed: %s", exc)
        if escalation_id:
            try:
                EscalationService().mark_failed(escalation_id)
            except Exception as mark_exc:  # noqa: BLE001 - defensive
                logger.warning("[ERROR] failed to mark escalation failed id=%s: %s", escalation_id, mark_exc)
        error_xml = """
        <Response>
            <Hangup/>
        </Response>
        """
        return Response(content=error_xml.strip(), media_type="application/xml", status_code=500)


# Health Route
@app.get("/")
async def root():
    return {"message": "Voice Agent API running", "status": "healthy"}


@app.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": asyncio.get_event_loop().time()}


def custom_openapi():
    """Custom OpenAPI schema with Bearer token security scheme."""
    if app.openapi_schema:
        return app.openapi_schema

    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
        tags=app.openapi_tags,
    )

    # Ensure components exists
    if "components" not in openapi_schema:
        openapi_schema["components"] = {}

    # Get existing security schemes from routers
    existing_schemes = openapi_schema["components"].get("securitySchemes", {})

    # Remove BearerAuth if it exists (we'll use HTTPBearer instead)
    if "BearerAuth" in existing_schemes:
        del existing_schemes["BearerAuth"]

    # Ensure HTTPBearer exists with proper configuration
    existing_schemes["HTTPBearer"] = {
        "type": "http",
        "scheme": "bearer",
        "bearerFormat": "JWT",
        "description": "Enter your JWT access token obtained from login endpoints. Just paste the token without 'Bearer ' prefix.",
    }

    # Remove any other bearer token schemes to avoid duplicates
    schemes_to_remove = [
        key
        for key in existing_schemes.keys()
        if key != "HTTPBearer"
        and existing_schemes[key].get("type") == "http"
        and existing_schemes[key].get("scheme") == "bearer"
    ]
    for key in schemes_to_remove:
        del existing_schemes[key]

    openapi_schema["components"]["securitySchemes"] = existing_schemes

    app.openapi_schema = openapi_schema
    return app.openapi_schema


app.openapi = custom_openapi


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=5001, reload=True)
