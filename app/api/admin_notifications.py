"""
Admin API routes for persistent notifications (system-wide).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.middleware.auth_middleware import get_current_admin_user
from app.models.notification_models import NotificationListResponse, NotificationResponse
from app.services.notification_persistence_service import NotificationPersistenceService
from app.utils.notification_utils import normalize_notification_row


def get_notification_service() -> NotificationPersistenceService:
    """Dependency to get notification persistence service instance."""
    return NotificationPersistenceService()


router = APIRouter(
    prefix="/api/v1/admin",
    tags=["Admin - Notifications"],
    dependencies=[Depends(get_current_admin_user)],
)


@router.get(
    "/notifications",
    summary="List all notifications (Admin)",
    description="List notifications across all restaurants with optional filters. Use restaurant_id to scope to one restaurant.",
    response_model=NotificationListResponse,
)
async def list_admin_notifications(
    restaurant_id: int | None = Query(None, description="Filter by restaurant ID"),
    is_read: bool | None = Query(None, description="Filter by read status"),
    type: str | None = Query(None, description="Filter by type: order, reservation, escalation"),
    limit: int = Query(50, ge=1, le=100, description="Page size"),
    offset: int = Query(0, ge=0, description="Offset"),
    notification_service: NotificationPersistenceService = Depends(get_notification_service),
) -> NotificationListResponse:
    rows, total = notification_service.get_notifications(
        restaurant_id=restaurant_id,
        is_read=is_read,
        type=type,
        limit=limit,
        offset=offset,
    )
    unread_count = notification_service.get_unread_count(restaurant_id) if restaurant_id else 0
    notifications = [NotificationResponse(**normalize_notification_row(r)) for r in rows]
    return NotificationListResponse(
        notifications=notifications,
        total=total,
        unread_count=unread_count,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/notifications/{notification_id}",
    summary="Get notification by ID (Admin)",
    description="Get any notification by ID (no restaurant scoping).",
    response_model=NotificationResponse,
)
async def get_admin_notification(
    notification_id: int,
    notification_service: NotificationPersistenceService = Depends(get_notification_service),
) -> NotificationResponse:
    row = notification_service.get_notification_by_id(notification_id)
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found")
    return NotificationResponse(**normalize_notification_row(row))
