from typing import List, Dict, Any
from app.repositories.call_repo import CallRepository
from app.models.call_models import CallResponse, TranscriptResponse, AnalyticsResponse

class CallService:
    def __init__(self):
        self.call_repo = CallRepository()
    
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
                call_id=c.get("call_id", ""),
                user_id=c.get("user_id", ""),
                start_time=c.get("started_at", ""),
                end_time=c.get("ended_at") or None,
                duration_seconds=int(c.get("call_duration", 0)),
                cost=float(c.get("cost", 0)),
                status=c.get("call_status", "unknown"),
                twilio_stream_sid=c.get("twilio_call_sid", ""),
            ))
        return normalized
    
    def get_call_transcripts(self, call_id: str) -> List[TranscriptResponse]:
        """Get transcripts for a specific call."""
        items = self.call_repo.get_call_transcripts(call_id)
        items.sort(key=lambda x: x.get("timestamp", ""))

        # Normalize for Pydantic
        items_normalized = []
        for i, item in enumerate(items):
            items_normalized.append(TranscriptResponse(
                transcript_id=str(item.get("message_sequence", f"t-{i}")),  # cast to string
                call_id=item.get("call_id"),
                text=item.get("message"),
                timestamp=item.get("timestamp"),
                is_final=True
            ))

        return items_normalized
    
    def get_analytics_summary(self, user_id: str) -> AnalyticsResponse:
        """Get analytics summary for a user."""
        calls = self.call_repo.get_user_calls(user_id, limit=1000)
        
        total_calls = len(calls)
        total_cost = sum(float(call.get('cost', 0)) for call in calls)
        total_duration = sum(call.get('duration_seconds', 0) for call in calls)
        
        return AnalyticsResponse(
            total_calls=total_calls,
            total_cost=round(total_cost, 2),
            total_duration_minutes=round(total_duration / 60, 2),
            average_call_duration=round(total_duration / max(total_calls, 1), 2)
        )

