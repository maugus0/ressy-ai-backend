from pydantic import BaseModel
from typing import List, Optional
from decimal import Decimal

class CallResponse(BaseModel):
    call_id: str
    user_id: str
    start_time: str
    end_time: Optional[str] = None
    duration_seconds: int
    cost: float
    status: str
    twilio_stream_sid: str
    from_number: Optional[str] = None
    outcome: Optional[str] = None

class TranscriptResponse(BaseModel):
    transcript_id: str
    call_id: str
    text: str
    timestamp: str
    is_final: bool

class AnalyticsResponse(BaseModel):
    total_calls: int
    total_cost: float
    total_duration_minutes: float
    average_call_duration: float

class CallHistoryPage(BaseModel):
    items: List[CallResponse]
    total: int