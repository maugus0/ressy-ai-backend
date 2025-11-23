"""
MySQL Call Repository for call session operations.
"""

from typing import Dict, List, Optional

from app.repositories.mysql_base import MySQLBaseRepository


class MySQLCallRepository(MySQLBaseRepository):
    """Repository for call data access in MySQL."""

    def create_call_session(
        self, user_id: str, twilio_sid: str, deepgram_session_id: str, restaurant_id: Optional[str] = None
    ) -> int:
        """
        Create a new call session and return call ID.
        """
        query = """
            INSERT INTO Calls (
                user_id, restaurant_id, twilio_call_sid, deepgram_request_id,
                call_status, call_direction, call_duration, cost, started_at, created_at, updated_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW(), NOW())
        """
        call_id = self._execute_insert(
            query, (user_id, restaurant_id, twilio_sid, deepgram_session_id, "in_progress", "inbound", 0, 0.000000)
        )
        print(f"[MySQL] Created call session: call_id={call_id}, user_id={user_id}, restaurant_id={restaurant_id}")
        return call_id

    def update_call_cost(self, call_id: int, duration_seconds: int) -> None:
        """
        Update call cost and duration, mark as completed.
        """
        cost_per_second = 0.00009833
        total_cost = duration_seconds * cost_per_second

        query = """
            UPDATE Calls
            SET call_duration = %s,
                cost = %s,
                call_status = 'completed',
                ended_at = NOW(),
                updated_at = NOW()
            WHERE id = %s
        """
        self._execute_update(query, (duration_seconds, total_cost, call_id))
        print(f"[MySQL] Updated call: call_id={call_id}, duration={duration_seconds}s, cost=${total_cost:.6f}")

    def get_user_calls(self, user_id: str, limit: int = 50) -> List[Dict]:
        query = """
            SELECT * FROM Calls
            WHERE user_id = %s
            ORDER BY started_at DESC
            LIMIT %s
        """
        return self._execute_query(query, (user_id, limit))

    def get_calls_by_restaurant(self, restaurant_id: str, limit: int = 50) -> List[Dict]:
        query = """
            SELECT * FROM Calls
            WHERE restaurant_id = %s
            ORDER BY started_at DESC
            LIMIT %s
        """
        return self._execute_query(query, (restaurant_id, limit))

    def get_all_calls(self, limit: int = 50) -> List[Dict]:
        query = """
            SELECT * FROM Calls
            ORDER BY started_at DESC
            LIMIT %s
        """
        return self._execute_query(query, (limit,))

    def store_transcript_message(
        self, call_id: int, message_sequence: int, speaker: str, message: str, timestamp: str
    ) -> None:
        """
        Store individual transcript messages.
        Note: This stores to the conversation_history in the Transcripts table via process_and_store_data.
        Individual messages are not stored separately - they're aggregated in the transcript.
        """
        # Individual messages are stored in conversation_history, not separately
        # This method is kept for compatibility but does nothing
        # The actual transcript is saved via MySQLTranscriptRepository.create_transcript
        pass
