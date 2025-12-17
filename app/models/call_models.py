from typing import List, Optional

from pydantic import BaseModel, Field


class CallResponse(BaseModel):
    """Response model for call information."""

    call_id: str = Field(..., description="Unique identifier for the call")
    user_id: str = Field(..., description="ID of the user who made/received the call")
    start_time: str = Field(..., description="Call start time in ISO format")
    end_time: Optional[str] = Field(None, description="Call end time in ISO format (null if call is ongoing)")
    duration_seconds: int = Field(..., description="Call duration in seconds")
    cost: float = Field(..., description="Cost of the call in USD")
    status: str = Field(..., description="Call status (e.g., 'completed', 'in-progress', 'failed')")
    twilio_stream_sid: str = Field(..., description="Twilio stream session ID")
    from_number: Optional[str] = Field(None, description="Phone number the call originated from")
    outcome: Optional[str] = Field(
        None, description="Call outcome (e.g., 'reservation_created', 'order_placed', 'no_action')"
    )


class TranscriptResponse(BaseModel):
    """Response model for call transcript segments."""

    transcript_id: str = Field(..., description="Unique identifier for the transcript segment")
    call_id: str = Field(..., description="ID of the call this transcript belongs to")
    text: str = Field(..., description="Transcribed text content")
    timestamp: str = Field(..., description="Timestamp when this transcript segment was created (ISO format)")
    is_final: bool = Field(..., description="Whether this is a final transcript (true) or interim (false)")


class AnalyticsResponse(BaseModel):
    """Response model for call analytics summary."""

    total_calls: int = Field(..., description="Total number of calls")
    total_cost: float = Field(..., description="Total cost of all calls in USD")
    total_duration_minutes: float = Field(..., description="Total duration of all calls in minutes")
    average_call_duration: float = Field(..., description="Average call duration in minutes")


class CallHistoryPage(BaseModel):
    """Response model for paginated call history."""

    items: List[CallResponse] = Field(..., description="List of call records")
    total: int = Field(..., description="Total number of calls matching the query")


class ConversationEntry(BaseModel):
    """Single message in a call transcript conversation."""

    sequence: int = Field(..., description="Order of the message in the conversation")
    role: str = Field(..., description="Speaker role (user/assistant)")
    content: str = Field(..., description="Transcript content")
    timestamp: Optional[str] = Field(None, description="Timestamp when the message was recorded")


class CallListItem(BaseModel):
    """Summary row for admin/client call listings."""

    call_id: str
    restaurant_id: Optional[str] = None
    restaurant_name: Optional[str] = None
    caller_phone: Optional[str] = None
    duration_seconds: int
    status: str
    started_at: Optional[str] = None
    has_transcript: bool = False
    summary: Optional[str] = None


class CallListPage(BaseModel):
    """Paginated call list wrapper."""

    items: List[CallListItem]
    total: int
    page: int
    limit: int


class CallDetailResponse(BaseModel):
    """Detailed call view including transcript."""

    call_id: str
    restaurant_id: Optional[str] = None
    restaurant_name: Optional[str] = None
    caller_phone: Optional[str] = None
    status: str
    started_at: Optional[str] = None
    ended_at: Optional[str] = None
    duration_seconds: int
    cost: float
    call_direction: Optional[str] = None
    has_transcript: bool = False
    transcript: Optional[List[ConversationEntry]] = None
    order_id: Optional[str] = None
    reservation_id: Optional[str] = None
    summary: Optional[str] = None


class AdminCallDetailResponse(BaseModel):
    """Admin-only detailed call view including cost breakdown."""

    call_id: str
    restaurant_id: Optional[str] = None
    restaurant_name: Optional[str] = None
    caller_phone: Optional[str] = None
    status: str
    started_at: Optional[str] = None
    ended_at: Optional[str] = None
    duration_seconds: int

    # Admin cost breakdown (computed from duration + env-configured rates/multipliers)
    twilio_cost: float = Field(..., description="Computed Twilio cost in USD")
    deepgram_cost: float = Field(..., description="Computed Deepgram cost in USD")
    ressy_cost: float = Field(..., description="Computed Ressy cost in USD (based on Twilio+Deepgram and multiplier)")

    call_direction: Optional[str] = None
    has_transcript: bool = False
    transcript: Optional[List[ConversationEntry]] = None
    order_id: Optional[str] = None
    reservation_id: Optional[str] = None
    summary: Optional[str] = None


class CallAnalyticsV2(BaseModel):
    """Extended analytics payload for admin/client dashboards."""

    total_calls: int
    average_call_duration: float
    status_breakdown: dict
    time_of_day_distribution: List[dict]
    top_restaurants: Optional[List[dict]] = None
    calls_by_day_of_week: Optional[List[dict]] = None
    conversion_rates: Optional[dict] = None
