"""
MySQL Transcript Repository for storing call transcripts.
"""
import json
from typing import Dict, Optional

from app.repositories.mysql_base import MySQLBaseRepository


class MySQLTranscriptRepository(MySQLBaseRepository):
    """Repository for transcript data access in MySQL."""

    def create_transcript(
            self,
            user_id: Optional[int],
            order_id: Optional[int],
            call_log: Dict
    ) -> int:
        """
        Create a transcript entry.
        """
        query = """
            INSERT INTO Transcripts (user_id, order_id, call_log, created_at, updated_at)
            VALUES (%s, %s, %s, NOW(), NOW())
        """
        return self._execute_insert(query, (
            user_id,
            order_id,
            json.dumps(call_log)
        ))

    def delete_transcript(self, transcript_id: int) -> int:
        """Delete transcript by id."""
        return self._execute_update("DELETE FROM Transcripts WHERE id = %s", (transcript_id,))
