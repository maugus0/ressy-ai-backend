import json
from datetime import datetime
from typing import List, Optional

from app.config import settings
from app.models.call_models import (
    AdminCallDetailResponse,
    AnalyticsResponse,
    CallAnalyticsV2,
    CallDetailResponse,
    CallListItem,
    CallListPage,
    CallResponse,
    ConversationEntry,
    TranscriptResponse,
)
from app.repositories.mysql_business_call_repo import MySQLBusinessCallRepository
from app.utils.timezone import isoformat_z


class BusinessCallService:
    """
    Service for managing call sessions and analytics.
    """

    def __init__(self):
        # Lazily initialized repository instance; reused to avoid unnecessary allocations.
        self._business_call_repo: Optional[MySQLBusinessCallRepository] = None

    def _get_business_call_repo(self) -> MySQLBusinessCallRepository:
        """Get the call repository instance, creating it on first use."""
        if self._business_call_repo is None:
            self._business_call_repo = MySQLBusinessCallRepository()
        return self._business_call_repo

    @staticmethod
    def calculate_call_costs(duration_seconds: int) -> dict:
        """
        Calculate call costs using current settings.

        This is the single source of truth for cost calculations.
        All cost calculations should use this method to ensure consistency.

        Args:
            duration_seconds: Call duration in seconds

        Returns:
            Dictionary with 'twilio_cost', 'deepgram_cost', and 'ressy_cost'
        """
        twilio_cost = duration_seconds * settings.TWILIO_COST_PER_SECOND * settings.TWILIO_MULTIPLIER
        deepgram_cost = duration_seconds * settings.DEEPGRAM_COST_PER_SECOND * settings.DEEPGRAM_MULTIPLIER
        ressy_cost = (twilio_cost + deepgram_cost) * settings.RESSY_MULTIPLIER

        return {
            "twilio_cost": float(twilio_cost),
            "deepgram_cost": float(deepgram_cost),
            "ressy_cost": float(ressy_cost),
        }

    def create_call_session(
        self,
        user_id: str,
        twilio_sid: str | None,
        deepgram_session_id: str | None,
        business_id: str | None = None,
    ) -> int:
        business_call_repo = self._get_business_call_repo()
        return business_call_repo.create_call_session(user_id, twilio_sid, deepgram_session_id, business_id)

    def update_call_cost(self, call_id: int, duration_seconds: int) -> None:
        normalized_id = self._safe_int(call_id)
        if normalized_id is None:
            return

        # Calculate cost using centralized method to ensure consistency
        costs = self.calculate_call_costs(duration_seconds)
        ressy_cost = costs["ressy_cost"]

        business_call_repo = self._get_business_call_repo()
        business_call_repo.update_call_cost(normalized_id, duration_seconds, ressy_cost)

    def update_call_status(self, call_id: str | int, status: str) -> bool:
        normalized_id = self._safe_int(call_id)
        if normalized_id is None:
            return False
        if not status:
            return False
        business_call_repo = self._get_business_call_repo()
        return business_call_repo.update_call_status(normalized_id, status)

    def mark_escalated(self, call_id: str | int) -> bool:
        return self.update_call_status(call_id, "escalated")

    def finalize_call_with_status(
        self,
        call_id: str | int,
        status: str,
        duration_seconds: int = 0,
        cost: float = 0.0,
    ) -> bool:
        """Set final call fields and terminal status explicitly."""
        normalized_id = self._safe_int(call_id)
        if normalized_id is None:
            return False
        if not status:
            return False
        business_call_repo = self._get_business_call_repo()
        return business_call_repo.finalize_call_with_status(
            normalized_id,
            status,
            duration_seconds=duration_seconds,
            cost=cost,
        )

    def store_transcript_message(
        self, call_id: int, message_sequence: int, speaker: str, message: str, timestamp: str
    ) -> None:
        business_call_repo = self._get_business_call_repo()
        business_call_repo.store_transcript_message(call_id, message_sequence, speaker, message, timestamp)

    def update_deepgram_request_id(self, call_id: str | int, deepgram_request_id: str) -> None:
        """Persist Deepgram request ID for a call once it is available."""
        normalized_id = self._safe_int(call_id)
        if normalized_id is None:
            return
        if not deepgram_request_id:
            return
        business_call_repo = self._get_business_call_repo()
        business_call_repo.update_deepgram_request_id(normalized_id, deepgram_request_id)

    def get_call_history(
        self, user_id: str, user_role: str, business_id: str | None = None, limit: int = 50
    ) -> List[CallResponse]:
        """Get call history based on user role and filters."""
        business_call_repo = self._get_business_call_repo()
        if business_id:
            raw_calls = business_call_repo.get_calls_by_business(business_id, limit)
        else:
            # Admins can see all, others limited to their own
            if user_role == "admin":
                raw_calls = business_call_repo.get_all_calls(limit)
            else:
                raw_calls = business_call_repo.get_user_calls(user_id, limit)

        normalized: List[CallResponse] = []
        for c in raw_calls:
            started_at = c.get("started_at")
            ended_at = c.get("ended_at")
            if isinstance(started_at, datetime):
                started_at_str = isoformat_z(started_at)
            else:
                started_at_str = str(started_at or "")
            if isinstance(ended_at, datetime):
                ended_at_str = isoformat_z(ended_at)
            else:
                ended_at_str = ended_at or None
            normalized.append(
                CallResponse(
                    call_id=str(c.get("id") or c.get("call_id") or ""),
                    user_id=str(c.get("user_id", "")),
                    start_time=started_at_str,
                    end_time=ended_at_str,
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

        business_call_repo = self._get_business_call_repo()
        call_row = business_call_repo.get_call_by_id(normalized_id)
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
        business_call_repo = self._get_business_call_repo()
        calls = business_call_repo.get_user_calls(user_id, limit=1000)

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
        """Persist full transcript JSON to Business_Calls table."""
        normalized_id = self._safe_int(call_id)
        if normalized_id is None:
            return
        business_call_repo = self._get_business_call_repo()
        business_call_repo.update_call_transcript(normalized_id, conversation)

    def list_calls(
        self,
        business_id: Optional[str] = None,
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
        business_call_repo = self._get_business_call_repo()
        rows, total = business_call_repo.list_calls(
            business_id=business_id,
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
            if isinstance(started_at, datetime):
                started_at_str = isoformat_z(started_at)
            else:
                started_at_str = str(started_at) if started_at is not None else None
            items.append(
                CallListItem(
                    call_id=str(row.get("id")),
                    business_id=str(row.get("business_id")) if row.get("business_id") is not None else None,
                    business_name=row.get("business_name"),
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
        self, call_id: str, business_scope: Optional[str] = None
    ) -> tuple[Optional[CallDetailResponse], bool]:
        normalized_id = self._safe_int(call_id)
        if normalized_id is None:
            return None, False

        business_call_repo = self._get_business_call_repo()
        call_row = business_call_repo.get_call_by_id(normalized_id)
        if not call_row:
            return None, False
        if business_scope and str(call_row.get("business_id")) != str(business_scope):
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
        duration_seconds = int(call_row.get("call_duration") or 0)

        # Calculate ressy_cost dynamically using centralized method
        # This ensures clients see the correct Ressy cost (not raw Twilio/Deepgram costs)
        # and costs are always calculated from current settings, not stored values
        costs = self.calculate_call_costs(duration_seconds)

        if isinstance(started_at, datetime):
            started_at_str = isoformat_z(started_at)
        else:
            started_at_str = str(started_at) if started_at is not None else None
        if isinstance(ended_at, datetime):
            ended_at_str = isoformat_z(ended_at)
        else:
            ended_at_str = str(ended_at) if ended_at else None

        return (
            CallDetailResponse(
                call_id=str(call_row.get("id")),
                business_id=str(call_row.get("business_id")) if call_row.get("business_id") is not None else None,
                business_name=call_row.get("business_name"),
                caller_phone=call_row.get("caller_phone"),
                status=call_row.get("call_status", "unknown"),
                started_at=started_at_str,
                ended_at=ended_at_str,
                duration_seconds=duration_seconds,
                cost=costs["ressy_cost"],  # Return calculated ressy_cost, not stored cost
                call_direction=call_row.get("call_direction"),
                has_transcript=bool(transcript_entries),
                transcript=transcript_entries or None,
                summary=call_row.get("outcome"),
                order_id=call_row.get("order_id"),
                reservation_id=call_row.get("reservation_id"),
            ),
            False,
        )

    def get_admin_call_detail(self, call_id: str) -> Optional[AdminCallDetailResponse]:
        """
        Admin-only call detail with cost breakdown computed from duration.

        Note: This does NOT rely on the stored `Business_Calls.cost` column; it computes:
        - twilio_cost = duration_seconds * TWILIO_COST_PER_SECOND * TWILIO_MULTIPLIER
        - deepgram_cost = duration_seconds * DEEPGRAM_COST_PER_SECOND * DEEPGRAM_MULTIPLIER
        - ressy_cost = (twilio_cost + deepgram_cost) * RESSY_MULTIPLIER

        RESSY_MULTIPLIER is a *total multiplier* (e.g. 1.2 means 20% markup on top of Twilio+Deepgram).
        """
        normalized_id = self._safe_int(call_id)
        if normalized_id is None:
            return None

        business_call_repo = self._get_business_call_repo()
        call_row = business_call_repo.get_call_by_id(normalized_id)
        if not call_row:
            return None

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

        duration_seconds = int(call_row.get("call_duration") or 0)

        # Calculate costs dynamically using centralized method
        # This ensures costs are always calculated from current settings, not stored values
        costs = self.calculate_call_costs(duration_seconds)

        started_at = call_row.get("started_at")
        ended_at = call_row.get("ended_at")
        if isinstance(started_at, datetime):
            started_at_str = isoformat_z(started_at)
        else:
            started_at_str = str(started_at) if started_at is not None else None
        if isinstance(ended_at, datetime):
            ended_at_str = isoformat_z(ended_at)
        else:
            ended_at_str = str(ended_at) if ended_at else None

        return AdminCallDetailResponse(
            call_id=str(call_row.get("id")),
            business_id=str(call_row.get("business_id")) if call_row.get("business_id") is not None else None,
            business_name=call_row.get("business_name"),
            caller_phone=call_row.get("caller_phone"),
            status=call_row.get("call_status", "unknown"),
            started_at=started_at_str,
            ended_at=ended_at_str,
            duration_seconds=duration_seconds,
            twilio_cost=costs["twilio_cost"],
            deepgram_cost=costs["deepgram_cost"],
            ressy_cost=costs["ressy_cost"],
            call_direction=call_row.get("call_direction"),
            has_transcript=bool(transcript_entries),
            transcript=transcript_entries or None,
            summary=call_row.get("outcome"),
            order_id=call_row.get("order_id"),
            reservation_id=call_row.get("reservation_id"),
        )

    def delete_call(self, call_id: str) -> bool:
        normalized_id = self._safe_int(call_id)
        if normalized_id is None:
            return False
        business_call_repo = self._get_business_call_repo()
        deleted = business_call_repo.delete_call(normalized_id)
        return deleted > 0

    def delete_call_transcript(self, call_id: str) -> bool:
        normalized_id = self._safe_int(call_id)
        if normalized_id is None:
            return False
        business_call_repo = self._get_business_call_repo()
        updated = business_call_repo.delete_call_transcript(normalized_id)
        return updated > 0

    def get_dashboard_analytics(
        self, business_id: Optional[str] = None, date_from: Optional[str] = None, date_to: Optional[str] = None
    ) -> CallAnalyticsV2:
        business_call_repo = self._get_business_call_repo()
        analytics = business_call_repo.get_call_analytics(
            business_id=business_id,
            date_from=date_from,
            date_to=date_to,
        )
        # Ensure we return consistent data structure even if analytics is empty
        conversion_rates = analytics.get("conversion_rates", {})
        return CallAnalyticsV2(
            total_calls=analytics.get("total_calls", 0) or 0,
            average_call_duration=analytics.get("average_call_duration", 0.0) or 0.0,
            status_breakdown=analytics.get("status_breakdown", {}) or {},
            time_of_day_distribution=analytics.get("time_of_day_distribution", []) or [],
            top_businesss=analytics.get("top_businesss") or [],
            calls_by_day_of_week=analytics.get("calls_by_day_of_week", []) or [],
            conversion_rates={
                "orders": conversion_rates.get("orders", 0),
                "reservations": conversion_rates.get("reservations", 0),
                "rate": conversion_rates.get("rate", 0.0),
            },
        )

    def export_calls(
        self,
        business_id: Optional[str],
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
            business_id=business_id,
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
