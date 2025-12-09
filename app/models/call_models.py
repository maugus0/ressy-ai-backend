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
    outcome: Optional[str] = Field(None, description="Call outcome (e.g., 'reservation_created', 'order_placed', 'no_action')")


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
