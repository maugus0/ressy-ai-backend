from app.repositories.call_repo import CallRepository

class TranscriptService:
    def __init__(self):
        self.call_repo = CallRepository()
    
    def delete_transcript(self, transcript_id: str) -> dict:
        """Delete a transcript."""
        self.call_repo.delete_transcript(transcript_id)
        return {"message": "Transcript deleted"}

