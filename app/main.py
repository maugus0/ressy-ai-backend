import asyncio
import traceback
import urllib.parse
from xml.sax.saxutils import escape

from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from starlette.requests import Request
from starlette.responses import Response

from app.api import (
    admin_users,
    auth,
    calls,
    client_users,
    dashboard_reservations,
    faqs,
    menus,
    opentable,
    order_history,
    orders,
    reservations,
    restaurants,
    transcripts,
    users,
)
from app.api.websocket import twilio_websocket_handler

app = FastAPI(
    title="RessyAI Backend",
    version="1.0.0",
    description="""
FastAPI backend for a multitenant, function-calling voice agent. 
Manages restaurants, menus, orders, reservations, calls, and user authentication.

## Authentication

This API uses **Bearer Token** authentication (JWT). To authenticate:

1. **Login** using one of the login endpoints:
   - `/api/v1/auth/admin/login` - For Ressy platform admins
   - `/api/v1/auth/client/login` - For restaurant managers/staff

2. **Copy the `access_token`** from the login response

3. **Click "Authorize" button** (top right) and enter: `Bearer <your_access_token>`

4. All subsequent requests will include the authentication header

### Token Refresh
Access tokens expire. Use `/api/v1/auth/refresh` with your `refresh_token` to get new tokens.
""",
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
            "name": "Users",
            "description": "User management endpoints. Create, read, update, and delete user accounts for restaurants.",
        },
        {
            "name": "Menus",
            "description": "Menu management endpoints. Full CRUD operations for menu items including categories, availability, specials, and bulk operations. Admin access only.",
        },
        {
            "name": "Restaurants",
            "description": "Restaurant management endpoints. Create, update, and manage restaurant information and settings.",
        },
        {
            "name": "Orders",
            "description": "Order management endpoints. Create, track, and manage customer orders placed through the voice agent.",
        },
        {
            "name": "Order History",
            "description": "Order history and tracking endpoints. Retrieve detailed order history and status information.",
        },
        {
            "name": "Transcripts",
            "description": "Call transcript management endpoints. Access and manage transcripts from voice interactions.",
        },
        {
            "name": "FAQs",
            "description": "Frequently Asked Questions management. Create and manage FAQs for restaurants to help the voice agent answer customer questions.",
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
            "description": "Dashboard-specific reservation management with RBAC. Create, finalize, view, update notes, and manage reservations. Admins can access all restaurants; restaurant managers can only access their own restaurant's reservations.",
        },
        {
            "name": "Admin Users",
            "description": "Ressy platform admin user management (Admin CRM). Create, update, list, reset passwords, and manage roles.",
        },
        {
            "name": "Client Users",
            "description": "Restaurant client CRM users (admins/staff) managed by Ressy admins. Includes CRUD, role assignment, and password resets.",
        },
        {
            "name": "Voice Agent",
            "description": "Voice agent webhook endpoints for Twilio integration. Handles incoming calls and WebSocket streaming for the voice agent system.",
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
app.include_router(calls.router, prefix="/api/v1/calls", tags=["Calls"])
app.include_router(users.router, prefix="/api/v1/users", tags=["Users"])
app.include_router(menus.router)
app.include_router(
    restaurants.router
    # Note: restaurants router declares its own prefix/tags to keep Admin CRM docs localized.
)
app.include_router(orders.router, prefix="/api/v1/orders", tags=["Orders"])
app.include_router(order_history.router, prefix="/api/v1/order-history", tags=["Order History"])
app.include_router(transcripts.router, prefix="/api/v1/transcripts", tags=["Transcripts"])
app.include_router(faqs.router)
app.include_router(opentable.router, prefix="/api/v1/opentable", tags=["OpenTable"])
app.include_router(reservations.router, prefix="/api/v1/reservations", tags=["Reservations"])
app.include_router(dashboard_reservations.router, prefix="/api/v1/dashboard", tags=["Dashboard Reservations"])
app.include_router(admin_users.router, tags=["Admin Users"])
app.include_router(client_users.router, tags=["Client Users"])


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
        from_number = form.get("From")
        to_number = form.get("To")
        call_sid = form.get("CallSid")

        print(f"Incoming call call_sid={call_sid} from={from_number} to={to_number}")
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
        print(f"Final websocket stream URL: {stream_url}")
        xml = f"""
        <Response>
            <Connect>
                <Stream url="{stream_url}">
                    <Parameter name="fromNumber" value="{from_number}"/>
                    <Parameter name="toNumber" value="{to_number}"/>
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

    # Merge security schemes (keep existing ones from routers, add/update BearerAuth)
    existing_schemes = openapi_schema["components"].get("securitySchemes", {})
    existing_schemes["BearerAuth"] = {
        "type": "http",
        "scheme": "bearer",
        "bearerFormat": "JWT",
        "description": "Enter your JWT access token obtained from login endpoints. Just paste the token without 'Bearer ' prefix.",
    }
    openapi_schema["components"]["securitySchemes"] = existing_schemes

    app.openapi_schema = openapi_schema
    return app.openapi_schema


app.openapi = custom_openapi


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=5001, reload=True)
