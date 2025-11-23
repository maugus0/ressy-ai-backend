from typing import List

from app.models.call_models import CallResponse, TranscriptResponse, AnalyticsResponse
from app.repositories.mysql_call_repo import MySQLCallRepository
from app.repositories.mysql_transcript_repo import MySQLTranscriptRepository


class CallService:
    def __init__(self):
        self.call_repo = MySQLCallRepository()
        self.transcript_repo = MySQLTranscriptRepository()

    def create_call_session(self, user_id: str, twilio_sid: str, deepgram_session_id: str,
                            restaurant_id: str | None = None) -> int:
        return self.call_repo.create_call_session(user_id, twilio_sid, deepgram_session_id, restaurant_id)

    def update_call_cost(self, call_id: int, duration_seconds: int) -> None:
        self.call_repo.update_call_cost(call_id, duration_seconds)

    def store_transcript_message(self, call_id: int, message_sequence: int, speaker: str, message: str,
                                 timestamp: str) -> None:
        self.call_repo.store_transcript_message(call_id, message_sequence, speaker, message, timestamp)

    def get_call_history(
            self,
            user_id: str,
            user_role: str,
            restaurant_id: str | None = None,
            limit: int = 50
    ) -> List[CallResponse]:
        """Get call history based on user role and filters."""
        if restaurant_id:
            raw_calls = self.call_repo.get_calls_by_restaurant(restaurant_id, limit)
        else:
            # Admins can see all, others limited to their own
            if user_role == "admin":
                raw_calls = self.call_repo.get_all_calls(limit)
            else:
                raw_calls = self.call_repo.get_user_calls(user_id, limit)

        normalized: List[CallResponse] = []
        for c in raw_calls:
            normalized.append(CallResponse(
                call_id=str(c.get("id") or c.get("call_id") or ""),
                user_id=str(c.get("user_id", "")),
                start_time=str(c.get("started_at", "")),
                end_time=c.get("ended_at") or None,
                duration_seconds=int(c.get("call_duration", 0)),
                cost=float(c.get("cost", 0)),
                status=c.get("call_status", "unknown"),
                twilio_stream_sid=c.get("twilio_call_sid", ""),
            ))
        return normalized

    def get_call_transcripts(self, call_id: str) -> List[TranscriptResponse]:
        """Get transcripts for a specific call."""
        # MySQL transcripts are stored as full call_log JSON; fetch latest by user/order if needed.
        # Since schema lacks call_id, return empty list for now.
        return []

    def get_analytics_summary(self, user_id: str) -> AnalyticsResponse:
        """Get analytics summary for a user."""
        calls = self.call_repo.get_user_calls(user_id, limit=1000)

        total_calls = len(calls)
        total_cost = sum(float(call.get('cost', 0)) for call in calls)
        total_duration = sum(call.get('call_duration', 0) or call.get('duration_seconds', 0) for call in calls)

        return AnalyticsResponse(
            total_calls=total_calls,
            total_cost=round(total_cost, 2),
            total_duration_minutes=round(total_duration / 60, 2),
            average_call_duration=round(total_duration / max(total_calls, 1), 2)
        )
