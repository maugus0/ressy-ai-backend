import asyncio
import traceback
import urllib.parse
from xml.sax.saxutils import escape

from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.api import (
    admin,
    auth,
    calls,
    dashboard_reservations,
    faqs,
    menus,
    opentable,
    order_history,
    orders,
    reservations,
    restaurants,
    specials,
    transcripts,
    users,
)
from app.api.websocket import twilio_websocket_handler

app = FastAPI(title="RessyAI Backend", version="1.0.0")

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
app.include_router(menus.router, prefix="/api/v1/menu", tags=["menu"])
app.include_router(restaurants.router, prefix="/api/v1/restaurants", tags=["restaurants"])
app.include_router(specials.router, prefix="/api/v1/specials", tags=["specials"])
app.include_router(orders.router, prefix="/api/v1/orders", tags=["orders"])
app.include_router(order_history.router, prefix="/api/v1/order-history", tags=["order-history"])
app.include_router(transcripts.router, prefix="/api/v1/transcripts", tags=["transcripts"])
app.include_router(faqs.router)
app.include_router(opentable.router, prefix="/api/v1/opentable", tags=["opentable"])
app.include_router(reservations.router, prefix="/api/v1/reservations", tags=["reservations"])
app.include_router(dashboard_reservations.router, prefix="/api/v1/dashboard", tags=["dashboard-reservations"])


# WebSocket Endpoint
@app.websocket("/twilio")
async def twilio_websocket(websocket: WebSocket):
    await twilio_websocket_handler(websocket)


@app.post("/voice")
async def voice(request: Request):
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


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=5001, reload=True)
