from fastapi import APIRouter, Depends

from app.middleware.auth_middleware import get_current_active_user, require_role
from app.services.transcript_service import TranscriptService

router = APIRouter()
transcript_service = TranscriptService()


@router.delete("/{transcript_id}", dependencies=[Depends(require_role(["admin"]))])
async def delete_transcript(transcript_id: str, current_user: dict = Depends(get_current_active_user)):
    return transcript_service.delete_transcript(transcript_id)
