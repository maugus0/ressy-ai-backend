from fastapi import APIRouter, Depends, HTTPException
from app.utils.security import get_current_active_user, require_role
from app.models.database import DynamoDBManager

router = APIRouter()
db = DynamoDBManager()

@router.delete("/{transcript_id}", dependencies=[Depends(require_role(["admin"]))])
async def delete_transcript(transcript_id: str, current_user: dict = Depends(get_current_active_user)):
    db.transcripts_table.delete_item(Key={"transcript_id": transcript_id})
    return {"message": "Transcript deleted"}
