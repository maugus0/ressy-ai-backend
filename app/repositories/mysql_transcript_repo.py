"""
MySQL Transcript Repository for storing call transcripts.
"""
from app.repositories.mysql_base import MySQLBaseRepository
from typing import Dict, Optional
import json

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

