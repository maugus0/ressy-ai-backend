from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class EscalationListItem(BaseModel):
    """Summary row for escalation listings."""

    id: int
    call_id: str = Field(..., description="Internal call ID associated with the escalation")
    user_id: str = Field(..., description="User identifier from the call context")
    restaurant_id: Optional[str] = Field(None, description="Restaurant identifier")
    restaurant_name: Optional[str] = Field(None, description="Restaurant name")
    call_sid: Optional[str] = Field(None, description="Twilio call SID")
    caller_phone: Optional[str] = Field(None, description="Caller phone number")
    escalation_phone_number: Optional[str] = Field(None, description="Forwarding phone number used at escalation time")
    urgency: Optional[str] = Field(None, description="Urgency provided by the agent")
    reason: Optional[str] = Field(None, description="Reason provided by the agent")
    status: str = Field(..., description="Escalation status")
    requested_at: Optional[str] = Field(None, description="Timestamp when escalation was raised")


class EscalationListPage(BaseModel):
    """Paginated escalation list wrapper."""

    items: List[EscalationListItem]
    total: int
    page: int
    limit: int


class EscalationDetailResponse(BaseModel):
    """Detailed escalation view."""

    id: int
    call_id: str = Field(..., description="Internal call ID associated with the escalation")
    user_id: str = Field(..., description="User identifier from the call context")
    restaurant_id: Optional[str] = Field(None, description="Restaurant identifier")
    restaurant_name: Optional[str] = Field(None, description="Restaurant name")
    call_sid: Optional[str] = Field(None, description="Twilio call SID")
    caller_phone: Optional[str] = Field(None, description="Caller phone number")
    escalation_phone_number: Optional[str] = Field(None, description="Forwarding phone number used at escalation time")
    urgency: Optional[str] = Field(None, description="Urgency provided by the agent")
    reason: Optional[str] = Field(None, description="Reason provided by the agent")
    status: str = Field(..., description="Escalation status")
    requested_at: Optional[str] = Field(None, description="Timestamp when escalation was raised")
    forwarded_at: Optional[str] = Field(None, description="Timestamp when escalation was forwarded")
    created_at: Optional[str] = Field(None, description="Record creation timestamp")
    updated_at: Optional[str] = Field(None, description="Record update timestamp")


class EscalationStatusUpdateRequest(BaseModel):
    """Request model for updating escalation status."""

    status: str = Field(..., description="New escalation status (raised, forwarded, failed, resolved)")
