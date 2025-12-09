from typing import List

from fastapi import APIRouter, Depends

from app.middleware.auth_middleware import get_current_active_user, require_role
from app.models.call_models import AnalyticsResponse, CallResponse, TranscriptResponse
from app.services.call_service import CallService

router = APIRouter()
call_service = CallService()


@router.get(
    "/history",
    response_model=List[CallResponse],
    dependencies=[Depends(require_role(["admin", "client"]))],
    summary="Get Call History",
    description="Retrieve call history with optional filtering by restaurant. Returns a list of call records with details such as duration, cost, status, and outcome.",
    response_description="List of call records with call details, timestamps, costs, and outcomes.",
)
async def get_call_history(
    restaurant_id: str | None = None,
    limit: int = 50,
    current_user: dict = Depends(require_role(["admin", "manager", "staff"])),
):
    """
    Get call history for the authenticated user.
    
    **Authentication**: Required (admin, manager, or staff role)
    
    **Query Parameters**:
    - restaurant_id: Optional restaurant ID to filter calls (restaurant users see only their restaurant's calls)
    - limit: Maximum number of calls to return (default: 50)
    
    **Response**: List of call records including:
    - call_id, user_id, start_time, end_time
    - duration_seconds, cost, status
    - twilio_stream_sid, from_number, outcome
    """
    user_id = current_user.get("sub")
    user_role = current_user.get("role")
    return call_service.get_call_history(user_id, user_role, restaurant_id, limit)


@router.get(
    "/{call_id}/transcripts",
    response_model=List[TranscriptResponse],
    summary="Get Call Transcripts",
    description="Retrieve all transcript segments for a specific call. Returns both interim and final transcripts in chronological order.",
    response_description="List of transcript segments with text, timestamps, and final status.",
)
async def get_call_transcripts(call_id: str):
    """
    Get all transcript segments for a specific call.
    
    **Authentication**: Public (no authentication required)
    
    **Path Parameters**:
    - call_id: Unique identifier of the call
    
    **Response**: List of transcript segments including:
    - transcript_id, call_id, text
    - timestamp, is_final (boolean indicating if transcript is final)
    """
    return call_service.get_call_transcripts(call_id)


@router.get(
    "/analytics/summary",
    response_model=AnalyticsResponse,
    dependencies=[Depends(require_role(["admin"]))],
    summary="Get Call Analytics Summary",
    description="Get aggregated analytics for all calls. Provides total calls, total cost, total duration, and average call duration. Admin access only.",
    response_description="Analytics summary with totals and averages for all calls.",
)
async def get_analytics_summary(current_user: dict = Depends(get_current_active_user)):
    """
    Get call analytics summary for the platform.
    
    **Authentication**: Required (admin role only)
    
    **Response**: Analytics summary including:
    - total_calls: Total number of calls
    - total_cost: Total cost in USD
    - total_duration_minutes: Total duration in minutes
    - average_call_duration: Average call duration in minutes
    """
    user_id = current_user.get("sub")
    return call_service.get_analytics_summary(user_id)
