"""
Dashboard API routes for persistent notifications (restaurant-scoped).

TODO: Add API tests for notification endpoints (list, get, mark-read, mark-all-read, unread-count).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.security import HTTPBearer

from app.middleware.auth_middleware import require_role
from app.models.notification_models import (
    MarkAllReadResponse,
    NotificationListResponse,
    NotificationResponse,
    UnreadCountResponse,
)
from app.services.notification_persistence_service import NotificationPersistenceService
from app.utils.notification_utils import normalize_notification_row

security = HTTPBearer(scheme_name="HTTPBearer", description="JWT access token")


def get_notification_service() -> NotificationPersistenceService:
    """Dependency to get notification persistence service instance."""
    return NotificationPersistenceService()


router = APIRouter(
    prefix="/api/v1/dashboard",
    tags=["Dashboard - Notifications"],
    dependencies=[Depends(security)],
)


def _get_restaurant_id(current_user: dict) -> int:
    """Extract restaurant_id from current user; raise 403 if missing."""
    restaurant_id = current_user.get("restaurant_id")
    if restaurant_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Restaurant access required",
        )
    return int(restaurant_id)


@router.get(
    "/notifications",
    summary="List notifications (Dashboard)",
    description="List notifications for the authenticated user's restaurant with optional filters. Returns paginated list and unread count.",
    response_model=NotificationListResponse,
)
async def list_notifications(
    is_read: bool | None = Query(None, description="Filter by read status"),
    type: str | None = Query(None, description="Filter by type: order, reservation, escalation"),
    limit: int = Query(50, ge=1, le=100, description="Page size"),
    offset: int = Query(0, ge=0, description="Offset"),
    current_user: dict = Depends(require_role(["admin", "client"])),
    notification_service: NotificationPersistenceService = Depends(get_notification_service),
) -> NotificationListResponse:
    restaurant_id = _get_restaurant_id(current_user)
    rows, total = notification_service.get_notifications(
        restaurant_id=restaurant_id,
        is_read=is_read,
        type=type,
        limit=limit,
        offset=offset,
    )
    unread_count = notification_service.get_unread_count(restaurant_id)
    notifications = [NotificationResponse(**normalize_notification_row(r)) for r in rows]
    return NotificationListResponse(
        notifications=notifications,
        total=total,
        unread_count=unread_count,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/notifications/unread-count",
    summary="Get unread count (Dashboard)",
    description="Lightweight endpoint returning unread notification count for the restaurant (e.g. for badge).",
    response_model=UnreadCountResponse,
)
async def get_unread_count(
    current_user: dict = Depends(require_role(["admin", "client"])),
    notification_service: NotificationPersistenceService = Depends(get_notification_service),
) -> UnreadCountResponse:
    restaurant_id = _get_restaurant_id(current_user)
    count = notification_service.get_unread_count(restaurant_id)
    return UnreadCountResponse(unread_count=count)


@router.get(
    "/notifications/{notification_id}",
    summary="Get notification by ID (Dashboard)",
    description="Get a single notification. Returns 404 if it does not belong to the user's restaurant.",
    response_model=NotificationResponse,
)
async def get_notification(
    notification_id: int,
    current_user: dict = Depends(require_role(["admin", "client"])),
    notification_service: NotificationPersistenceService = Depends(get_notification_service),
) -> NotificationResponse:
    restaurant_id = _get_restaurant_id(current_user)
    row = notification_service.get_notification_by_id(notification_id)
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found")
    if int(row.get("restaurant_id")) != int(restaurant_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found")
    return NotificationResponse(**normalize_notification_row(row))


@router.patch(
    "/notifications/{notification_id}/read",
    summary="Mark notification as read (Dashboard)",
    description="Mark a single notification as read. Returns 404 if it does not belong to the user's restaurant.",
    response_model=NotificationResponse,
)
async def mark_notification_read(
    notification_id: int,
    current_user: dict = Depends(require_role(["admin", "client"])),
    notification_service: NotificationPersistenceService = Depends(get_notification_service),
) -> NotificationResponse:
    restaurant_id = _get_restaurant_id(current_user)
    row = notification_service.get_notification_by_id(notification_id)
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found")
    if int(row.get("restaurant_id")) != int(restaurant_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found")
    updated = notification_service.mark_as_read(notification_id)
    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found")
    return NotificationResponse(**normalize_notification_row(updated))


@router.patch(
    "/notifications/read-all",
    summary="Mark all as read (Dashboard)",
    description="Mark all notifications as read for the restaurant. Optional type query param to scope to order, reservation, or escalation.",
    response_model=MarkAllReadResponse,
)
async def mark_all_read(
    type: str | None = Query(None, description="Optional: scope to type (order, reservation, escalation)"),
    current_user: dict = Depends(require_role(["admin", "client"])),
    notification_service: NotificationPersistenceService = Depends(get_notification_service),
) -> MarkAllReadResponse:
    restaurant_id = _get_restaurant_id(current_user)
    count = notification_service.mark_all_as_read(restaurant_id, type=type)
    return MarkAllReadResponse(updated_count=count)
