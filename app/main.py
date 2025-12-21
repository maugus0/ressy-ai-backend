import asyncio
import traceback
import urllib.parse
from contextlib import asynccontextmanager
from xml.sax.saxutils import escape

from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from starlette.requests import Request
from starlette.responses import Response

from app.api import (
    activity_history,
    admin_users,
    auth,
    calls,
    client_analytics,
    client_calls,
    client_client_users,
    client_faqs,
    client_menus,
    client_restaurant,
    client_users,
    dashboard_orders,
    dashboard_reservations,
    dashboard_users,
    faqs,
    menus,
    opentable,
    reservations,
    restaurants,
    sse,
    testing,
)
from app.api.websocket import twilio_websocket_handler
from app.services.sse_service import SSEService


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup and shutdown events."""
    # Startup
    yield
    # Shutdown: cleanup SSE connections and heartbeat task
    sse_service = SSEService()
    await sse_service.shutdown()


app = FastAPI(
    title="RessyAI Backend",
    version="1.0.0",
    description="FastAPI backend for a multitenant, function-calling voice agent. Manages restaurants, menus, orders, reservations, calls, and user authentication.",
    lifespan=lifespan,
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
            "description": "Real-time event streaming via Server-Sent Events (SSE). Subscribe to live updates for orders, reservations, and escalations. Supports escalation events (user_requested, internal_server_error, suspected_spam), order events (new_order, order_updated, order_cancelled), and reservation events (new_reservation, reservation_updated, reservation_cancelled).",
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
app.include_router(menus.router)
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


@app.post(
    "/voice",
    summary="Twilio Voice Webhook",
    description="Twilio webhook endpoint that receives incoming call requests and returns TwiML to connect the call to the WebSocket stream. "
    "This endpoint is called by Twilio when a call is received. It generates the WebSocket connection URL and returns TwiML instructions.",
    response_description="TwiML XML response instructing Twilio to connect the call to the WebSocket stream.",
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
    - Connect the call to the WebSocket stream at /twilio
    - Stream audio bidirectionally for voice agent processing

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

        print(
            f"Incoming call call_sid={call_sid} from={twilio_from} to={twilio_to} (ws from={from_number} to={to_number})"
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
        # Escape user-controlled values before embedding into TwiML XML.
        from_number_xml = escape(from_number) if from_number is not None else ""
        to_number_xml = escape(to_number) if to_number is not None else ""
        print(f"Final websocket stream URL: {stream_url}")
        xml = f"""
        <Response>
            <Connect>
                <Stream url="{stream_url}">
                    <Parameter name="fromNumber" value="{from_number_xml}"/>
                    <Parameter name="toNumber" value="{to_number_xml}"/>
                </Stream>
            </Connect>
        </Response>
        """
        return Response(content=xml.strip(), media_type="application/xml")
    except Exception as exc:
        print(f"[ERROR] voice endpoint failed: {exc}")
        print(traceback.format_exc())
        error_xml = """
        <Response>
            <Say>We are experiencing technical difficulties. Please try again shortly.</Say>
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
