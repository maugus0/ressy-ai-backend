"""
Spam Management API endpoints.

Allows restaurant admins to mark/unmark users as spam and check spam status.
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.security import HTTPBearer
from pydantic import BaseModel

from app.config import settings
from app.middleware.auth_middleware import require_role
from app.repositories.mysql_user_repo import MySQLUserRepository
from app.repositories.mysql_user_restaurant_metadata_repo import (
    MySQLUserRestaurantMetadataRepository,
)

logger = logging.getLogger(__name__)

security = HTTPBearer(
    scheme_name="HTTPBearer",
    description="Enter your JWT access token obtained from login endpoints",
)

router = APIRouter(
    prefix="/api/v1/spam",
    tags=["Spam Management"],
    dependencies=[Depends(security)],
)


# ---------- Request/Response Models ----------


class MarkSpamRequest(BaseModel):
    user_id: int
    restaurant_id: int
    reason: Optional[str] = None
    ai_summary: Optional[str] = None


class UnmarkSpamRequest(BaseModel):
    user_id: int
    restaurant_id: int


class SpamStatusResponse(BaseModel):
    user_id: int
    restaurant_id: int
    is_global_spam: bool
    is_restaurant_spam: bool
    spam_restaurant_count: int


class MarkSpamResponse(BaseModel):
    message: str
    user_id: int
    restaurant_id: int
    is_global_spam: bool
    spam_restaurant_count: int


# ---------- Service dependencies ----------


def get_user_repo() -> MySQLUserRepository:
    """Dependency to get user repository."""
    return MySQLUserRepository()


def get_metadata_repo() -> MySQLUserRestaurantMetadataRepository:
    """Dependency to get metadata repository."""
    return MySQLUserRestaurantMetadataRepository()


# ---------- API Endpoints ----------


@router.post(
    "/mark",
    summary="Mark User as Spam",
    description="Mark a user as spam for a specific restaurant. If 5+ restaurants mark the user, they are automatically marked as global spam.",
    response_model=MarkSpamResponse,
)
async def mark_user_as_spam(
    request: MarkSpamRequest,
    current_user: dict = Depends(require_role(["admin", "client"])),
    metadata_repo: MySQLUserRestaurantMetadataRepository = Depends(get_metadata_repo),
    user_repo: MySQLUserRepository = Depends(get_user_repo),
):
    """
    Mark a user as spam for a restaurant.

    Requires restaurant admin role. If the user is marked as spam by 5+ restaurants
    (configurable via SPAM_GLOBAL_THRESHOLD), they are automatically marked as global spam.
    """
    # Verify user exists
    user = user_repo.get_user_by_id(request.user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Check restaurant access (for client role)
    if current_user.get("user_type") == "restaurant":
        token_restaurant_id = current_user.get("restaurant_id")
        if token_restaurant_id and str(token_restaurant_id) != str(request.restaurant_id):
            raise HTTPException(status_code=403, detail="Cannot mark spam for other restaurants")

    # Mark user as spam for this restaurant
    metadata_repo.mark_as_spam(
        user_id=request.user_id,
        restaurant_id=request.restaurant_id,
        reason=request.reason,
        ai_summary=request.ai_summary,
    )

    # Check if threshold reached for global spam
    spam_count = metadata_repo.get_spam_count_by_user(request.user_id)
    is_global_spam = bool(user.get("is_spam", False))

    if spam_count >= settings.SPAM_GLOBAL_THRESHOLD and not is_global_spam:
        # Mark as global spam
        user_repo.mark_user_global_spam(
            request.user_id,
            reason=f"Marked as spam by {spam_count} restaurants (threshold: {settings.SPAM_GLOBAL_THRESHOLD})",
        )
        is_global_spam = True
        logger.info(
            "User %s automatically marked as global spam (marked by %d restaurants)",
            request.user_id,
            spam_count,
        )

    # Create notification (if notification service is available)
    try:
        from app.services.notification_persistence_service import (
            NotificationPersistenceService,
        )

        notification_service = NotificationPersistenceService()
        notification_service.create_notification(
            restaurant_id=request.restaurant_id,
            type="spam",
            subtype="marked",
            data={
                "user_id": request.user_id,
                "phone_number": user.get("phone_number"),
                "reason": request.reason,
                "ai_summary": request.ai_summary,
            },
            entity_id=request.user_id,
        )
    except Exception as e:
        logger.warning("Failed to create spam notification: %s", e)

    return MarkSpamResponse(
        message="User marked as spam successfully",
        user_id=request.user_id,
        restaurant_id=request.restaurant_id,
        is_global_spam=is_global_spam,
        spam_restaurant_count=spam_count,
    )


@router.post(
    "/unmark",
    summary="Unmark User as Spam",
    description="Remove spam marking for a user from a specific restaurant.",
    response_model=dict,
)
async def unmark_user_as_spam(
    request: UnmarkSpamRequest,
    current_user: dict = Depends(require_role(["admin", "client"])),
    metadata_repo: MySQLUserRestaurantMetadataRepository = Depends(get_metadata_repo),
):
    """Unmark a user as spam for a restaurant."""
    # Check restaurant access (for client role)
    if current_user.get("user_type") == "restaurant":
        token_restaurant_id = current_user.get("restaurant_id")
        if token_restaurant_id and str(token_restaurant_id) != str(request.restaurant_id):
            raise HTTPException(status_code=403, detail="Cannot unmark spam for other restaurants")

    # Unmark spam
    affected = metadata_repo.unmark_as_spam(request.user_id, request.restaurant_id)

    if affected == 0:
        raise HTTPException(status_code=404, detail="User was not marked as spam for this restaurant")

    return {
        "message": "User unmarked as spam successfully",
        "user_id": request.user_id,
        "restaurant_id": request.restaurant_id,
    }


@router.get(
    "/status/{user_id}",
    summary="Get Spam Status",
    description="Get spam status for a user (restaurant-specific and global).",
    response_model=SpamStatusResponse,
)
async def get_spam_status(
    user_id: int,
    restaurant_id: Optional[int] = Query(None, description="Restaurant ID (optional for restaurant users)"),
    current_user: dict = Depends(require_role(["admin", "client"])),
    user_repo: MySQLUserRepository = Depends(get_user_repo),
):
    """Get spam status for a user."""
    # For restaurant users, use their restaurant_id if not provided
    if current_user.get("user_type") == "restaurant":
        token_restaurant_id = current_user.get("restaurant_id")
        if not restaurant_id:
            restaurant_id = token_restaurant_id
        elif token_restaurant_id and str(token_restaurant_id) != str(restaurant_id):
            raise HTTPException(status_code=403, detail="Access denied")

    if not restaurant_id:
        raise HTTPException(status_code=400, detail="restaurant_id is required")

    status = user_repo.get_user_spam_status(user_id, restaurant_id)
    if "error" in status:
        raise HTTPException(status_code=404, detail=status["error"])

    return SpamStatusResponse(**status)
