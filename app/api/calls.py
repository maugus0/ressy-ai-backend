from typing import List

from fastapi import APIRouter, Depends

from app.middleware.auth_middleware import get_current_active_user, require_role
from app.models.call_models import CallResponse, TranscriptResponse, AnalyticsResponse
from app.services.call_service import CallService

router = APIRouter()
call_service = CallService()


@router.get("/history", response_model=List[CallResponse], dependencies=[Depends(require_role(["admin", "client"]))])
async def get_call_history(
        restaurant_id: str | None = None,
        limit: int = 50,
        current_user: dict = Depends(require_role(["admin", "manager", "staff"])),
):
    user_id = current_user.get("sub")
    user_role = current_user.get("role")
    return call_service.get_call_history(user_id, user_role, restaurant_id, limit)


@router.get(
    "/{call_id}/transcripts",
    response_model=List[TranscriptResponse],
)
async def get_call_transcripts(call_id: str):
    return call_service.get_call_transcripts(call_id)


@router.get("/analytics/summary", response_model=AnalyticsResponse, dependencies=[Depends(require_role(["admin"]))])
async def get_analytics_summary(current_user: dict = Depends(get_current_active_user)):
    user_id = current_user.get("sub")
    return call_service.get_analytics_summary(user_id)
