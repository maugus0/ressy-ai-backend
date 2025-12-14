import json
from typing import List, Optional

from app.models.call_models import (
    AnalyticsResponse,
    CallAnalyticsV2,
    CallDetailResponse,
    CallListItem,
    CallListPage,
    CallResponse,
    ConversationEntry,
    TranscriptResponse,
)
from app.repositories.mysql_call_repo import MySQLCallRepository


class CallService:
    def __init__(self):
        self.call_repo = MySQLCallRepository()

    def create_call_session(
        self,
        user_id: str,
        twilio_sid: str | None,
        deepgram_session_id: str | None,
        restaurant_id: str | None = None,
    ) -> int:
        return self.call_repo.create_call_session(user_id, twilio_sid, deepgram_session_id, restaurant_id)

    def update_call_cost(self, call_id: int, duration_seconds: int) -> None:
        normalized_id = self._safe_int(call_id)
        if normalized_id is None:
            return
        self.call_repo.update_call_cost(normalized_id, duration_seconds)

    def store_transcript_message(
        self, call_id: int, message_sequence: int, speaker: str, message: str, timestamp: str
    ) -> None:
        self.call_repo.store_transcript_message(call_id, message_sequence, speaker, message, timestamp)

    def get_call_history(
        self, user_id: str, user_role: str, restaurant_id: str | None = None, limit: int = 50
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
            normalized.append(
                CallResponse(
                    call_id=str(c.get("id") or c.get("call_id") or ""),
                    user_id=str(c.get("user_id", "")),
                    start_time=str(c.get("started_at", "")),
                    end_time=c.get("ended_at") or None,
                    duration_seconds=int(c.get("call_duration", 0)),
                    cost=float(c.get("cost", 0)),
                    status=c.get("call_status", "unknown"),
                    twilio_stream_sid=c.get("twilio_call_sid", ""),
                    from_number=c.get("caller_phone"),
                    outcome=c.get("outcome"),
                )
            )
        return normalized

    def get_call_transcripts(self, call_id: str) -> List[TranscriptResponse]:
        """Get transcripts for a specific call."""
        normalized_id = self._safe_int(call_id)
        if normalized_id is None:
            return []

        call_row = self.call_repo.get_call_by_id(normalized_id)
        if not call_row:
            return []

        raw_transcript = call_row.get("call_transcript")
        try:
            transcript_payload = json.loads(raw_transcript) if raw_transcript else {}
        except (TypeError, json.JSONDecodeError):
            transcript_payload = {}

        conversation = transcript_payload.get("conversation") or []
        responses: List[TranscriptResponse] = []
        for idx, entry in enumerate(conversation, start=1):
            text = entry.get("content") or entry.get("text") or ""
            timestamp = entry.get("timestamp") or entry.get("time") or ""
            responses.append(
                TranscriptResponse(
                    transcript_id=str(entry.get("sequence") or idx),
                    call_id=str(call_id),
                    text=text,
                    timestamp=timestamp,
                    is_final=True,
                )
            )
        return responses

    def get_analytics_summary(self, user_id: str) -> AnalyticsResponse:
        """Get analytics summary for a user."""
        calls = self.call_repo.get_user_calls(user_id, limit=1000)

        total_calls = len(calls)
        total_cost = sum(float(call.get("cost", 0)) for call in calls)
        total_duration = sum(call.get("call_duration", 0) or call.get("duration_seconds", 0) for call in calls)

        return AnalyticsResponse(
            total_calls=total_calls,
            total_cost=round(total_cost, 2),
            total_duration_minutes=round(total_duration / 60, 2),
            average_call_duration=round(total_duration / max(total_calls, 1), 2),
        )

    def save_call_transcript(self, call_id: str | int, conversation: List[dict]) -> None:
        """Persist full transcript JSON to Calls table."""
        normalized_id = self._safe_int(call_id)
        if normalized_id is None:
            return
        self.call_repo.update_call_transcript(normalized_id, conversation)

    def list_calls(
        self,
        restaurant_id: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        status: Optional[str] = None,
        duration_min: Optional[int] = None,
        duration_max: Optional[int] = None,
        caller_phone: Optional[str] = None,
        page: int = 1,
        limit: int = 20,
        sort_by: str = "created_at",
        sort_order: str = "desc",
        search_term: Optional[str] = None,
    ) -> CallListPage:
        rows, total = self.call_repo.list_calls(
            restaurant_id=restaurant_id,
            date_from=date_from,
            date_to=date_to,
            status=status,
            duration_min=duration_min,
            duration_max=duration_max,
            caller_phone=caller_phone,
            page=page,
            limit=limit,
            sort_by=sort_by,
            sort_order=sort_order,
            search_term=search_term,
        )

        items: List[CallListItem] = []
        for row in rows:
            started_at = row.get("started_at")
            started_at_str = str(started_at) if started_at is not None else None
            items.append(
                CallListItem(
                    call_id=str(row.get("id")),
                    restaurant_id=str(row.get("restaurant_id")) if row.get("restaurant_id") is not None else None,
                    restaurant_name=row.get("restaurant_name"),
                    caller_phone=row.get("caller_phone"),
                    duration_seconds=int(row.get("call_duration") or 0),
                    status=row.get("call_status", "unknown"),
                    started_at=started_at_str,
                    has_transcript=bool(row.get("has_transcript")),
                    summary=row.get("outcome") or row.get("call_status"),  # TODO: Implementation pending.
                )
            )

        return CallListPage(items=items, total=total, page=page, limit=limit)

    def get_call_detail(
        self, call_id: str, restaurant_scope: Optional[str] = None
    ) -> tuple[Optional[CallDetailResponse], bool]:
        normalized_id = self._safe_int(call_id)
        if normalized_id is None:
            return None, False

        call_row = self.call_repo.get_call_by_id(normalized_id)
        if not call_row:
            return None, False
        if restaurant_scope and str(call_row.get("restaurant_id")) != str(restaurant_scope):
            return None, True

        transcript_entries: List[ConversationEntry] = []
        raw_transcript = call_row.get("call_transcript")
        if raw_transcript:
            try:
                payload = json.loads(raw_transcript)
                conversation = payload.get("conversation") if isinstance(payload, dict) else []
            except (json.JSONDecodeError, TypeError):
                conversation = []
            for entry in conversation or []:
                transcript_entries.append(
                    ConversationEntry(
                        sequence=int(entry.get("sequence") or len(transcript_entries) + 1),
                        role=str(entry.get("role") or "assistant"),
                        content=str(entry.get("content") or entry.get("text") or ""),
                        timestamp=entry.get("timestamp"),
                    )
                )

        started_at = call_row.get("started_at")
        ended_at = call_row.get("ended_at")

        return (
            CallDetailResponse(
                call_id=str(call_row.get("id")),
                restaurant_id=str(call_row.get("restaurant_id")) if call_row.get("restaurant_id") is not None else None,
                restaurant_name=call_row.get("restaurant_name"),
                caller_phone=call_row.get("caller_phone"),
                status=call_row.get("call_status", "unknown"),
                started_at=str(started_at) if started_at is not None else None,
                ended_at=str(ended_at) if ended_at else None,
                duration_seconds=int(call_row.get("call_duration") or 0),
                cost=float(call_row.get("cost") or 0.0),
                call_direction=call_row.get("call_direction"),
                has_transcript=bool(transcript_entries),
                transcript=transcript_entries or None,
                summary=call_row.get("outcome"),
                order_id=call_row.get("order_id"),
                reservation_id=call_row.get("reservation_id"),
            ),
            False,
        )

    def delete_call(self, call_id: str) -> bool:
        normalized_id = self._safe_int(call_id)
        if normalized_id is None:
            return False
        deleted = self.call_repo.delete_call(normalized_id)
        return deleted > 0

    def delete_call_transcript(self, call_id: str) -> bool:
        normalized_id = self._safe_int(call_id)
        if normalized_id is None:
            return False
        updated = self.call_repo.delete_call_transcript(normalized_id)
        return updated > 0

    def get_dashboard_analytics(
        self, restaurant_id: Optional[str] = None, date_from: Optional[str] = None, date_to: Optional[str] = None
    ) -> CallAnalyticsV2:
        analytics = self.call_repo.get_call_analytics(
            restaurant_id=restaurant_id,
            date_from=date_from,
            date_to=date_to,
        )
        return CallAnalyticsV2(
            total_calls=analytics.get("total_calls", 0),
            average_call_duration=analytics.get("average_call_duration", 0.0),
            status_breakdown=analytics.get("status_breakdown", {}),
            time_of_day_distribution=analytics.get("time_of_day_distribution", []),
            top_restaurants=analytics.get("top_restaurants"),
            calls_by_day_of_week=analytics.get("calls_by_day_of_week"),
            conversion_rates={"orders": 0, "reservations": 0, "rate": 0},  # TODO: Implementation pending.
        )

    def export_calls(
        self,
        restaurant_id: Optional[str],
        date_from: Optional[str],
        date_to: Optional[str],
        status: Optional[str],
        duration_min: Optional[int],
        duration_max: Optional[int],
        caller_phone: Optional[str],
        sort_by: str,
        sort_order: str,
        page: int = 1,
        limit: int = 500,
    ) -> List[CallListItem]:
        page_data = self.list_calls(
            restaurant_id=restaurant_id,
            date_from=date_from,
            date_to=date_to,
            status=status,
            duration_min=duration_min,
            duration_max=duration_max,
            caller_phone=caller_phone,
            page=page,
            limit=limit,
            sort_by=sort_by,
            sort_order=sort_order,
        )
        return page_data.items

    @staticmethod
    def _safe_int(value: Optional[str | int]) -> Optional[int]:
        if value is None:
            return None
        if isinstance(value, int):
            return value
        try:
            return int(str(value))
        except (TypeError, ValueError):
            return None
