"""
Server-Sent Events API endpoints for real-time event streaming.

Provides real-time notifications for:
- Escalation events (user requests, errors, spam detection)
- Order events (new, updated, cancelled)
- Reservation events (new, updated, cancelled)
"""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field

from app.middleware.auth_middleware import require_role
from app.services.sse_service import (
    EscalationEventSubtype,
    SSEService,
)
from app.utils.jwt_util import JWTUtil

security = HTTPBearer(
    scheme_name="HTTPBearer",
    description="Enter your JWT access token obtained from login endpoints. Just paste the token without 'Bearer ' prefix.",
)

# Separate security scheme for SSE stream endpoint that allows optional header auth
# This enables query param authentication for browser EventSource API which cannot send headers
security_optional = HTTPBearer(
    scheme_name="HTTPBearerSSE",
    description="JWT access token via header (optional - can also use 'token' query parameter)",
    auto_error=False,  # Don't raise 403 when header is missing - allows query param fallback
)

router = APIRouter()
sse_service = SSEService()
jwt_util = JWTUtil()


# ---------- Pydantic models ----------


class EscalationEventRequest(BaseModel):
    """Request model for triggering escalation events."""

    subtype: str = Field(
        ...,
        description="Escalation subtype: user_requested, internal_server_error, suspected_spam",
        json_schema_extra={"example": "user_requested"},
    )
    call_id: Optional[str] = Field(
        None,
        description="Unique call identifier from Twilio/voice system",
        json_schema_extra={"example": "CA1234567890abcdef"},
    )
    caller_phone: Optional[str] = Field(
        None,
        description="Phone number of the caller",
        json_schema_extra={"example": "+1234567890"},
    )
    reason: Optional[str] = Field(
        None,
        description="Reason for escalation (for user_requested subtype)",
        json_schema_extra={"example": "Customer requested to speak with manager about billing issue"},
    )
    error_message: Optional[str] = Field(
        None,
        description="Error description (for internal_server_error subtype)",
        json_schema_extra={"example": "Database connection timeout during order processing"},
    )
    error_code: Optional[str] = Field(
        None,
        description="Error code (for internal_server_error subtype)",
        json_schema_extra={"example": "DB_TIMEOUT_001"},
    )
    spam_score: Optional[float] = Field(
        None,
        ge=0,
        le=1,
        description="Spam probability score from 0.0 to 1.0 (for suspected_spam subtype)",
        json_schema_extra={"example": 0.85},
    )
    indicators: Optional[List[str]] = Field(
        None,
        description="List of spam indicators detected (for suspected_spam subtype)",
        json_schema_extra={"example": ["rapid_hangup", "known_spam_number", "automated_voice"]},
    )


class EscalationEventResponse(BaseModel):
    """Response model for escalation event trigger."""

    event_id: str = Field(..., description="Unique event identifier (UUID)")
    event_type: str = Field(..., description="Event type (escalation)")
    subtype: str = Field(..., description="Escalation subtype")
    restaurant_id: int = Field(..., description="Restaurant ID the event was triggered for")
    timestamp: str = Field(..., description="ISO format timestamp of the event")
    message: str = Field(..., description="Success message")


class SSEStatsResponse(BaseModel):
    """Response model for SSE connection statistics."""

    total_connections: int = Field(..., description="Total number of active SSE connections")
    admin_connections: int = Field(..., description="Number of admin connections (receive all events)")
    restaurants_with_connections: int = Field(..., description="Number of restaurants with active connections")
    connections_per_restaurant: Dict[str, int] = Field(..., description="Map of restaurant_id to connection count")


class SSEEventPayload(BaseModel):
    """Model describing the SSE event payload structure."""

    id: str = Field(..., description="Unique event identifier (UUID)")
    event_type: str = Field(..., description="Event type: escalation, order, reservation, heartbeat")
    subtype: Optional[str] = Field(None, description="Event subtype (e.g., new_order, user_requested)")
    restaurant_id: Optional[int] = Field(None, description="Associated restaurant ID")
    timestamp: str = Field(..., description="ISO format timestamp")
    data: Dict[str, Any] = Field(..., description="Event-specific data payload")


# ---------- Helper functions ----------


def _check_restaurant_access(current_user: dict, restaurant_id: int):
    """
    Check if the current user has access to the specified restaurant.
    Admins have access to all restaurants.
    Restaurant users (managers) can only access their own restaurant.

    Args:
        current_user: JWT claims dict containing user_type, restaurant_id
        restaurant_id: The restaurant ID to check access for

    Raises:
        HTTPException 403: If user doesn't have access to this restaurant
    """
    user_type = current_user.get("user_type")

    if user_type == "admin":
        return

    if user_type == "restaurant":
        user_restaurant_id = current_user.get("restaurant_id")

        if user_restaurant_id is None:
            raise HTTPException(
                status_code=403,
                detail="Your account is not associated with any restaurant",
            )

        if int(user_restaurant_id) != int(restaurant_id):
            raise HTTPException(
                status_code=403,
                detail=f"You can only access events for your own restaurant (ID: {user_restaurant_id})",
            )
        return

    raise HTTPException(status_code=403, detail="Access denied - unknown user type")


# ---------- SSE Stream Endpoints ----------


@router.get(
    "/events/stream",
    summary="Subscribe to SSE event stream",
    description="""
Subscribe to real-time Server-Sent Events (SSE) stream for live updates.

This endpoint establishes a persistent connection that receives events as they happen.
The connection stays open until the client disconnects.

**Authentication**: Required (admin or restaurant manager role)

You can authenticate in two ways:
1. **Authorization Header**: Standard Bearer token in header
2. **Query Parameter**: Pass `token` query parameter (useful for browser EventSource API)

**Authorization**:
- **Admins**: Receive events from ALL restaurants
- **Restaurant managers**: Only receive events for their own restaurant

**Event Types**:

| Type | Subtype | Description |
|------|---------|-------------|
| `escalation` | `user_requested` | User asked to speak with a human |
| `escalation` | `internal_server_error` | System error occurred during call |
| `escalation` | `suspected_spam` | Call flagged as potential spam |
| `order` | `new_order` | New order created |
| `order` | `order_updated` | Order status or details changed |
| `order` | `order_cancelled` | Order was cancelled |
| `reservation` | `new_reservation` | New reservation created |
| `reservation` | `reservation_updated` | Reservation details changed |
| `reservation` | `reservation_cancelled` | Reservation was cancelled |
| `heartbeat` | - | Keep-alive ping (every 30 seconds) |

**Event Format** (JSON):
```json
{
  "id": "uuid-string",
  "event_type": "order",
  "subtype": "new_order",
  "restaurant_id": 1,
  "timestamp": "2025-12-14T10:30:00.000Z",
  "data": {
    "order_id": 456,
    "status": "pending",
    "total_amount": 34.97,
    "customer_name": "John Smith"
  }
}
```

**JavaScript Usage Example**:
```javascript
const token = 'your-jwt-token';
const eventSource = new EventSource(`/api/v1/sse/events/stream?token=${token}`);

eventSource.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log('Received event:', data);

  switch(data.event_type) {
    case 'order':
      handleOrderEvent(data);
      break;
    case 'escalation':
      handleEscalationEvent(data);
      break;
    case 'reservation':
      handleReservationEvent(data);
      break;
  }
};

eventSource.onerror = (error) => {
  console.error('SSE error:', error);
  eventSource.close();
};
```

**Note**: The connection will automatically send heartbeat events every 30 seconds
to keep the connection alive and detect disconnections.
""",
    response_class=StreamingResponse,
    responses={
        200: {
            "description": "SSE event stream established successfully",
            "content": {
                "text/event-stream": {
                    "example": 'id: 550e8400-e29b-41d4-a716-446655440000\nevent: order\ndata: {"id":"550e8400-e29b-41d4-a716-446655440000","event_type":"order","subtype":"new_order","restaurant_id":1,"timestamp":"2025-12-14T10:30:00.000Z","data":{"order_id":456}}\n\n'
                }
            },
        },
        401: {
            "description": "Not authenticated",
            "content": {
                "application/json": {
                    "examples": {
                        "no_token": {"value": {"detail": "Authentication required"}},
                        "invalid_token": {"value": {"detail": "Invalid token"}},
                        "wrong_token_type": {"value": {"detail": "Access token required"}},
                    }
                }
            },
        },
        403: {
            "description": "Access denied",
            "content": {
                "application/json": {
                    "examples": {
                        "no_restaurant": {"value": {"detail": "Your account is not associated with any restaurant"}},
                        "wrong_restaurant": {
                            "value": {"detail": "You can only subscribe to events for your own restaurant (ID: 1)"}
                        },
                    }
                }
            },
        },
    },
)
async def subscribe_to_events(
    restaurant_id: Optional[int] = Query(
        None,
        description="Restaurant ID to filter events (optional for admins, auto-set for restaurant users)",
        json_schema_extra={"example": 1},
    ),
    token: Optional[str] = Query(
        None,
        description="JWT access token (alternative to Authorization header for browser EventSource)",
    ),
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_optional),
):
    """
    Subscribe to SSE event stream.

    Establishes a persistent connection for receiving real-time events.
    The stream includes heartbeat events to maintain the connection.
    """
    # Get token from query param or header
    auth_token = token or (credentials.credentials if credentials else None)

    if not auth_token:
        raise HTTPException(status_code=401, detail="Authentication required")

    # Validate token
    try:
        claims = jwt_util.validate_token(auth_token, jwt_util.admin_audience)
    except Exception:
        try:
            claims = jwt_util.validate_token(auth_token, jwt_util.client_audience)
        except Exception:
            raise HTTPException(status_code=401, detail="Invalid token")

    if claims.get("token_type") != "access":
        raise HTTPException(status_code=401, detail="Access token required")

    user_type = claims.get("user_type")
    is_admin = user_type == "admin"
    user_id = claims.get("sub") or claims.get("user_id")

    # Determine restaurant_id for filtering
    effective_restaurant_id = restaurant_id

    if not is_admin:
        # Non-admin users must connect to their own restaurant
        user_restaurant_id = claims.get("restaurant_id")

        if user_restaurant_id is None:
            raise HTTPException(
                status_code=403,
                detail="Your account is not associated with any restaurant",
            )

        if restaurant_id is not None and int(restaurant_id) != int(user_restaurant_id):
            raise HTTPException(
                status_code=403,
                detail=f"You can only subscribe to events for your own restaurant (ID: {user_restaurant_id})",
            )

        effective_restaurant_id = int(user_restaurant_id)

    # Create connection
    connection = await sse_service.connect(
        restaurant_id=effective_restaurant_id,
        user_id=str(user_id) if user_id else None,
        is_admin=is_admin,
    )

    return StreamingResponse(
        sse_service.event_stream(connection),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ---------- Escalation Event Endpoints ----------


@router.post(
    "/events/escalation/{restaurant_id}",
    summary="Trigger an escalation event",
    description="""
Trigger an escalation event for a restaurant.

Escalation events are used to notify dashboard users when immediate attention
is needed, such as when a caller requests human assistance or when system
errors occur during a call.

**Authentication**: Required (admin or restaurant manager role)

**Authorization**:
- Admins can trigger escalations for any restaurant
- Restaurant managers can only trigger escalations for their own restaurant

**Subtypes**:

| Subtype | Description | Required Fields |
|---------|-------------|-----------------|
| `user_requested` | User asked to speak with a human | `reason` (recommended), `caller_phone` |
| `internal_server_error` | System error during call processing | `error_message`, `error_code` |
| `suspected_spam` | Call flagged as potential spam | `spam_score`, `indicators` |

**Use Cases**:
- Voice agent detects user frustration or explicit request for human
- API error occurs during order/reservation processing
- Spam detection system flags a suspicious call

**Example Payloads by Subtype**:

*User Requested Escalation:*
```json
{
  "subtype": "user_requested",
  "call_id": "CA1234567890",
  "caller_phone": "+1234567890",
  "reason": "Customer wants to discuss catering options with manager"
}
```

*Server Error Escalation:*
```json
{
  "subtype": "internal_server_error",
  "call_id": "CA1234567890",
  "error_message": "Payment processing failed",
  "error_code": "PAY_001"
}
```

*Spam Detection Escalation:*
```json
{
  "subtype": "suspected_spam",
  "call_id": "CA1234567890",
  "caller_phone": "+1234567890",
  "spam_score": 0.92,
  "indicators": ["robocall_pattern", "blocked_number_list"]
}
```
""",
    response_model=EscalationEventResponse,
    responses={
        200: {
            "description": "Escalation event triggered successfully",
            "content": {
                "application/json": {
                    "example": {
                        "event_id": "550e8400-e29b-41d4-a716-446655440000",
                        "event_type": "escalation",
                        "subtype": "user_requested",
                        "restaurant_id": 1,
                        "timestamp": "2025-12-14T10:30:00.000Z",
                        "message": "Escalation event triggered successfully",
                    }
                }
            },
        },
        400: {
            "description": "Invalid request",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Invalid subtype 'unknown'. Must be one of: user_requested, internal_server_error, suspected_spam"
                    }
                }
            },
        },
        403: {
            "description": "Access denied",
            "content": {
                "application/json": {
                    "example": {"detail": "You can only access events for your own restaurant (ID: 1)"}
                }
            },
        },
    },
)
async def trigger_escalation(
    restaurant_id: int,
    request: EscalationEventRequest,
    current_user: dict = Depends(require_role(["admin", "client"])),
):
    """
    Trigger an escalation event.

    Broadcasts the escalation to all connected SSE clients for the restaurant.
    """
    _check_restaurant_access(current_user, restaurant_id)

    # Validate subtype
    valid_subtypes = [e.value for e in EscalationEventSubtype]
    if request.subtype not in valid_subtypes:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid subtype '{request.subtype}'. Must be one of: {', '.join(valid_subtypes)}",
        )

    # Emit appropriate escalation event
    if request.subtype == EscalationEventSubtype.USER_REQUESTED.value:
        event = await sse_service.emit_escalation_user_requested(
            restaurant_id=restaurant_id,
            call_id=request.call_id,
            caller_phone=request.caller_phone,
            reason=request.reason,
        )
    elif request.subtype == EscalationEventSubtype.INTERNAL_SERVER_ERROR.value:
        event = await sse_service.emit_escalation_server_error(
            restaurant_id=restaurant_id,
            call_id=request.call_id,
            error_message=request.error_message,
            error_code=request.error_code,
        )
    elif request.subtype == EscalationEventSubtype.SUSPECTED_SPAM.value:
        event = await sse_service.emit_escalation_suspected_spam(
            restaurant_id=restaurant_id,
            call_id=request.call_id,
            caller_phone=request.caller_phone,
            spam_score=request.spam_score,
            indicators=request.indicators,
        )
    else:
        raise HTTPException(status_code=400, detail="Unknown escalation subtype")

    return EscalationEventResponse(
        event_id=event.id,
        event_type=event.event_type.value,
        subtype=event.subtype,
        restaurant_id=restaurant_id,
        timestamp=event.timestamp,
        message="Escalation event triggered successfully",
    )


# ---------- Stats Endpoint ----------


@router.get(
    "/events/stats",
    summary="Get SSE connection statistics",
    description="""
Get current Server-Sent Events connection statistics.

This endpoint provides insights into the active SSE connections across the platform.
Useful for monitoring and debugging real-time event delivery.

**Authentication**: Required (admin role only)

**Response Fields**:
- `total_connections`: Total number of active SSE connections
- `admin_connections`: Number of admin connections (these receive ALL events)
- `restaurants_with_connections`: Count of unique restaurants with connected clients
- `connections_per_restaurant`: Breakdown of connections by restaurant ID
""",
    response_model=SSEStatsResponse,
    responses={
        200: {
            "description": "Connection statistics retrieved successfully",
            "content": {
                "application/json": {
                    "example": {
                        "total_connections": 15,
                        "admin_connections": 3,
                        "restaurants_with_connections": 8,
                        "connections_per_restaurant": {
                            "1": 3,
                            "2": 2,
                            "5": 4,
                            "8": 1,
                            "12": 2,
                        },
                    }
                }
            },
        },
        403: {
            "description": "Admin access required",
            "content": {"application/json": {"example": {"detail": "Not authorized"}}},
        },
    },
)
async def get_sse_stats(
    current_user: dict = Depends(require_role(["admin"])),
):
    """
    Get SSE connection statistics.

    Returns current connection counts and distribution across restaurants.
    """
    stats = sse_service.get_connection_stats()
    return SSEStatsResponse(**stats)
