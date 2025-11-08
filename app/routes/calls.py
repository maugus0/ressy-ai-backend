from fastapi import APIRouter, Depends
from app.utils.security import get_current_active_user, require_role
from app.models.database import CallDatabase
from app.models.call_models import CallResponse, TranscriptResponse, AnalyticsResponse
from typing import List
from boto3.dynamodb.conditions import Attr
from decimal import Decimal

router = APIRouter()
call_db = CallDatabase()


@router.get("/history", response_model=List[CallResponse], dependencies=[Depends(require_role(["admin", "client"]))])
async def get_call_history(
    restaurant_id: str | None = None,
    limit: int = 50,
    current_user: dict = Depends(require_role(["admin", "manager", "staff"])),
):
    # Use demo-user directly
    # user_id = "demo-user"
    # raw_calls = call_db.get_user_calls(user_id, limit)
    if restaurant_id:
        raw_calls = call_db.get_calls_by_restaurant(restaurant_id, limit)
    else:
        # Admins can see all, others limited to their own
        user_role = current_user.get("role")
        if user_role == "admin":
            raw_calls = call_db.get_all_calls(limit)
        else:
            user_id = current_user.get("sub")
            raw_calls = call_db.get_user_calls(user_id, limit)

    normalized: List[CallResponse] = []
    for c in raw_calls:
        normalized.append({
            "call_id": c.get("call_id", ""),
            "user_id": c.get("user_id", ""),
            "start_time": c.get("started_at", ""),
            "end_time": c.get("ended_at") or None,
            "duration_seconds": int(c.get("call_duration", 0)),
            "cost": float(c.get("cost", 0)),
            "status": c.get("call_status", "unknown"),
            "twilio_stream_sid": c.get("twilio_call_sid", ""),
        })
    return normalized

@router.get(
    "/{call_id}/transcripts",
    response_model=List[TranscriptResponse],
    # dependencies=[Depends(require_role(["admin", "client"]))]
)
async def get_call_transcripts(call_id: str):
    items = call_db.get_call_transcripts(call_id)
    items.sort(key=lambda x: x.get("timestamp", ""))

    # Normalize for Pydantic
    items_normalized = []
    for i, item in enumerate(items):
        items_normalized.append({
            "transcript_id": str(item.get("message_sequence", f"t-{i}")),  # cast to string
            "call_id": item.get("call_id"),
            "text": item.get("message"),
            "speaker": item.get("speaker"),
            "timestamp": item.get("timestamp"),
            "message_sequence": int(item.get("message_sequence", 0)),
            "is_final": True
        })

    return items_normalized


@router.get("/analytics/summary", response_model=AnalyticsResponse, dependencies=[Depends(require_role(["admin"]))])
async def get_analytics_summary(current_user: dict = Depends(get_current_active_user)):
    user_id = current_user.get("sub")
    calls = call_db.get_user_calls(user_id, limit=1000)
    
    total_calls = len(calls)
    total_cost = sum(float(call.get('cost', 0)) for call in calls)
    total_duration = sum(call.get('duration_seconds', 0) for call in calls)
    
    return AnalyticsResponse(
        total_calls=total_calls,
        total_cost=round(total_cost, 2),
        total_duration_minutes=round(total_duration / 60, 2),
        average_call_duration=round(total_duration / max(total_calls, 1), 2)
    )