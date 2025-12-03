from app.repositories.mysql_transcript_repo import MySQLTranscriptRepository


class TranscriptService:
    def __init__(self):
        self.transcript_repo = MySQLTranscriptRepository()

    def delete_transcript(self, transcript_id: str) -> dict:
        """Delete a transcript."""
        self.transcript_repo.delete_transcript(int(transcript_id))
        return {"message": "Transcript deleted"}

    def create_transcript(self, user_id: int | None, order_id: int | None, call_log: dict) -> dict:
        transcript_id = self.transcript_repo.create_transcript(user_id, order_id, call_log)
        return {"transcript_id": transcript_id}
