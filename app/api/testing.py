from __future__ import annotations

import re
from typing import Any, Optional
from urllib.parse import quote, urlencode
from xml.sax.saxutils import escape

import requests
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.config import settings
from app.middleware.auth_middleware import get_current_admin_user
from app.services.restaurant_service import RestaurantService


class OutboundCallRequest(BaseModel):
    restaurant_id: int = Field(..., description="Restaurant ID whose Twilio settings to use")
    to_number: str = Field(..., description="Your phone number to call (E.164)")

    @field_validator("to_number")
    @classmethod
    def validate_e164(cls, value: str) -> str:
        v = str(value or "").strip()
        if not re.fullmatch(r"^\+[1-9]\d{7,14}$", v):
            raise ValueError("to_number must be a valid E.164 phone number (e.g. +14155551234)")
        return v


class OutboundCallResponse(BaseModel):
    message: str
    twilio_call_sid: Optional[str] = None
    to: Optional[str] = None
    from_number: Optional[str] = Field(None, alias="from")
    status: Optional[str] = None
    stream_url: str
    model_config = ConfigDict(populate_by_name=True)


def get_restaurant_service() -> RestaurantService:
    # Avoid FastAPI trying to introspect RestaurantService.__init__ params as dependencies.
    return RestaurantService()


router = APIRouter(
    prefix="/api/v1/testing",
    tags=["Outbound Calls"],
    dependencies=[Depends(get_current_admin_user)],
)

# Public callback router (Twilio cannot send Authorization header)
callback_router = APIRouter(prefix="/api/v1/testing", tags=["Outbound Calls"])


@callback_router.post(
    "/twilio-status",
    summary="Twilio status callback (Developer Testing)",
    description="Receives Twilio status callbacks for outbound test calls. Protected by OUTBOUND_CALL_STATUS_SECRET.",
    include_in_schema=False,
)
async def twilio_status_callback(request: Request, secret: str | None = Query(None)):
    if settings.OUTBOUND_CALL_STATUS_SECRET and secret != settings.OUTBOUND_CALL_STATUS_SECRET:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid status callback secret")
    # Twilio sends StatusCallback as application/x-www-form-urlencoded.
    form = await request.form()
    payload = dict(form)
    # Log the callback for debugging (contains CallStatus, CallSid, ErrorCode, etc.)
    print(f"[Twilio StatusCallback] {payload}")
    return {"ok": True}


@router.post(
    "/outbound-call",
    summary="Place an outbound call",
    description="Testing-only endpoint to place an outbound call to any number using a restaurant's Twilio settings. "
    "The call is configured to connect to this backend's `/voice` webhook for streaming to Deepgram.",
    response_model=OutboundCallResponse,
    response_model_by_alias=True,
    openapi_extra={
        "requestBody": {
            "content": {
                "application/json": {
                    "example": {
                        "restaurant_id": 1,
                        "to_number": "+14155551234",
                    }
                }
            }
        }
    },
)
def place_outbound_call(
    payload: OutboundCallRequest,
    restaurant_service: RestaurantService = Depends(get_restaurant_service),
) -> dict[str, Any]:
    restaurant = restaurant_service.get_restaurant(int(payload.restaurant_id))

    twilio_details = restaurant.get("twilio_details") or {}
    account_sid = twilio_details.get("account_sid") or twilio_details.get("TWILIO_ACCOUNT_SID")
    auth_token = twilio_details.get("auth_token") or twilio_details.get("TWILIO_AUTH_TOKEN")
    if not account_sid or not auth_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Restaurant is missing Twilio credentials in twilio_details (account_sid/auth_token).",
        )

    # Always call "from" the restaurant's Twilio number.
    effective_from = (restaurant.get("twilio_phone_number") or "").strip()
    if not effective_from:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Restaurant twilio_phone_number is missing; cannot place outbound call.",
        )

    # Recreate inbound flow by generating the same TwiML that /voice would return,
    # but send it directly to Twilio (avoids webhook/method/ngrok issues that can cause "Application error").
    ws_base = str(settings.PUBLIC_BASE_URL).rstrip("/")
    if ws_base.startswith("https://"):
        ws_base = "wss://" + ws_base[len("https://") :]
    elif ws_base.startswith("http://"):
        ws_base = "ws://" + ws_base[len("http://") :]
    else:
        # If scheme is missing, default to wss
        ws_base = "wss://" + ws_base.lstrip("/")

    stream_query = urlencode(
        {
            # Force websocket routing to use restaurant Twilio number (outbound calls flip Twilio's To/From).
            "toNumber": restaurant.get("twilio_phone_number"),
            # Preserve the "caller number" as the developer's phone for transcript/user mapping.
            "fromNumber": payload.to_number,
        }
    )
    stream_url = f"{ws_base}/twilio?{stream_query}"
    stream_url_xml = escape(stream_url)
    from_number_xml = escape(payload.to_number)
    to_number_xml = escape(effective_from)

    twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Connect>
    <Stream url="{stream_url_xml}">
      <Parameter name="fromNumber" value="{from_number_xml}"/>
      <Parameter name="toNumber" value="{to_number_xml}"/>
    </Stream>
  </Connect>
</Response>"""

    url = f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Calls.json"
    status_cb = f"{str(settings.PUBLIC_BASE_URL).rstrip('/')}/api/v1/testing/twilio-status"
    if settings.OUTBOUND_CALL_STATUS_SECRET:
        status_cb = f"{status_cb}?secret={quote(settings.OUTBOUND_CALL_STATUS_SECRET, safe='')}"
    data = {
        "To": payload.to_number,
        "From": effective_from,
        "Twiml": twiml,
        "StatusCallback": status_cb,
        # Pass parameters into the /voice webhook so it can embed them into the websocket stream URL.
        # We intentionally set toNumber to the restaurant's Twilio number so websocket routing finds the restaurant.
        "StatusCallbackEvent": "initiated ringing answered completed",
        "StatusCallbackMethod": "POST",
    }

    try:
        resp = requests.post(url, data=data, auth=(account_sid, auth_token), timeout=20)
    except requests.RequestException as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Twilio request failed: {exc}") from exc

    if resp.status_code >= 400:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Twilio API error ({resp.status_code}): {resp.text}",
        )

    response_data = resp.json()
    return {
        "message": "Outbound call initiated",
        "twilio_call_sid": response_data.get("sid"),
        "to": response_data.get("to"),
        "from": response_data.get("from"),
        "status": response_data.get("status"),
        "stream_url": stream_url,
    }
