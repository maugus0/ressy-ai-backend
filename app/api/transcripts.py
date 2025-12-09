from fastapi import APIRouter, Depends

from app.middleware.auth_middleware import get_current_active_user, require_role
from app.services.transcript_service import TranscriptService

router = APIRouter()
transcript_service = TranscriptService()


@router.delete(
    "/{transcript_id}",
    dependencies=[Depends(require_role(["admin"]))],
    summary="Delete Transcript",
    description="Permanently delete a transcript segment from the system. Admin access only. This action cannot be undone.",
    response_description="Confirmation message or deleted transcript details.",
)
async def delete_transcript(transcript_id: str, current_user: dict = Depends(get_current_active_user)):
    """
    Delete a transcript segment from the system.
    
    **Authentication**: Required (admin role only)
    
    **Path Parameters**:
    - transcript_id: Unique identifier of the transcript to delete
    
    **Warning**: This action is permanent and cannot be undone.
    
    **Response**: Confirmation of deletion.
    """
    return transcript_service.delete_transcript(transcript_id)
