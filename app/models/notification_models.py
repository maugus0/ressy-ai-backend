"""
Pydantic models for persistent notification API responses.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class NotificationResponse(BaseModel):
    """Single notification response."""

    id: int = Field(..., description="Notification ID")
    restaurant_id: int = Field(..., description="Restaurant this notification belongs to")
    type: str = Field(..., description="Event type: order, reservation, escalation")
    subtype: str = Field(..., description="Event subtype")
    title: str = Field(..., description="Human-readable title")
    message: Optional[str] = Field(None, description="Human-readable message body")
    data: Optional[Dict[str, Any]] = Field(None, description="Full event payload for frontend")
    entity_id: Optional[int] = Field(None, description="Related entity ID (order_id, reservation_id, call_id)")
    is_read: bool = Field(False, description="Whether the notification has been read")
    read_at: Optional[str] = Field(None, description="When the notification was marked as read (ISO)")
    created_at: str = Field(..., description="Creation timestamp (ISO)")
    updated_at: str = Field(..., description="Last update timestamp (ISO)")


class NotificationListResponse(BaseModel):
    """Paginated notification list with unread count."""

    notifications: List[NotificationResponse] = Field(..., description="List of notifications")
    total: int = Field(..., description="Total count matching filters")
    unread_count: int = Field(..., description="Unread count for the restaurant")
    limit: int = Field(..., description="Page size")
    offset: int = Field(..., description="Offset used")


class UnreadCountResponse(BaseModel):
    """Unread count for badge display."""

    unread_count: int = Field(..., description="Number of unread notifications")


class MarkAllReadResponse(BaseModel):
    """Response for mark-all-as-read."""

    updated_count: int = Field(..., description="Number of notifications marked as read")
