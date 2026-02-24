"""
Spam Management API endpoints.

Allows restaurant admins to mark/unmark users as spam and check spam status.
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.security import HTTPBearer
from pydantic import BaseModel, Field

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
    """Request model for marking a user as spam."""

    user_id: int = Field(..., description="ID of the user to mark as spam", example=123)
    restaurant_id: int = Field(..., description="ID of the restaurant marking the user", example=1)
    reason: Optional[str] = Field(
        None, description="Reason for marking the user as spam", example="User repeatedly asked unrelated questions"
    )
    ai_summary: Optional[str] = Field(
        None,
        description="AI-generated summary of the call if spam was detected by AI",
        example="Caller asked about credit card services multiple times after being redirected",
    )


class UnmarkSpamRequest(BaseModel):
    """Request model for unmarking a user as spam."""

    user_id: int = Field(..., description="ID of the user to unmark", example=123)
    restaurant_id: int = Field(..., description="ID of the restaurant unmarking the user", example=1)


class SpamStatusResponse(BaseModel):
    """Response model for spam status."""

    user_id: int = Field(..., description="User ID", example=123)
    restaurant_id: int = Field(..., description="Restaurant ID", example=1)
    is_global_spam: bool = Field(..., description="Whether the user is marked as global spam", example=False)
    is_restaurant_spam: bool = Field(
        ..., description="Whether the user is marked as spam for this specific restaurant", example=True
    )
    spam_restaurant_count: int = Field(
        ..., description="Number of restaurants that have marked this user as spam", example=2
    )


class MarkSpamResponse(BaseModel):
    """Response model for marking a user as spam."""

    message: str = Field(..., description="Success message", example="User marked as spam successfully")
    user_id: int = Field(..., description="User ID", example=123)
    restaurant_id: int = Field(..., description="Restaurant ID", example=1)
    is_global_spam: bool = Field(
        ...,
        description="Whether the user is now marked as global spam (after threshold check)",
        example=False,
    )
    spam_restaurant_count: int = Field(
        ..., description="Total number of restaurants that have marked this user as spam", example=2
    )


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
    description="Mark a user as spam for a specific restaurant. If the number of restaurants marking the user reaches the global threshold (configurable via SPAM_GLOBAL_THRESHOLD, default: 5), the user is automatically marked as global spam. Global spam users are blocked from all restaurants.",
    response_model=MarkSpamResponse,
    responses={
        200: {
            "description": "User marked as spam successfully",
            "content": {
                "application/json": {
                    "example": {
                        "message": "User marked as spam successfully",
                        "user_id": 123,
                        "restaurant_id": 1,
                        "is_global_spam": False,
                        "spam_restaurant_count": 2,
                    }
                }
            },
        },
        403: {"description": "Access denied - cannot mark spam for other restaurants"},
        404: {"description": "User not found"},
    },
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
    # Use atomic check-and-update to prevent race conditions
    spam_count = metadata_repo.get_spam_count_by_user(request.user_id)
    is_global_spam = bool(user.get("is_spam", False))

    if spam_count >= settings.SPAM_GLOBAL_THRESHOLD and not is_global_spam:
        # Mark as global spam atomically (only updates if not already marked)
        affected = user_repo.mark_user_global_spam(
            request.user_id,
            reason=f"Marked as spam by {spam_count} restaurants (threshold: {settings.SPAM_GLOBAL_THRESHOLD})",
        )
        if affected > 0:
            is_global_spam = True
            logger.info(
                "User %s automatically marked as global spam (marked by %d restaurants)",
                request.user_id,
                spam_count,
            )
        else:
            # Another request already marked this user as global spam
            is_global_spam = True

    # Create notification (if notification service is available)
    try:
        from app.services.notification_persistence_service import (
            NotificationPersistenceService,
        )

        notification_service = NotificationPersistenceService()
        notification_service.create_notification(
            restaurant_id=request.restaurant_id,
            type="escalation",
            subtype="suspected_spam",
            data={
                "user_id": request.user_id,
                "phone_number": user.get("phone_number"),
                "caller_phone": user.get("phone_number"),
                "reason": f"User marked as spam. Reason: {request.reason}" if request.reason else "User marked as spam",
                "indicators": ["manual_mark"],
                "spam_score": 1.0,
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
    description="Remove spam marking for a user from a specific restaurant. This only affects the restaurant-specific spam status, not global spam status.",
    response_model=dict,
    responses={
        200: {
            "description": "User unmarked as spam successfully",
            "content": {
                "application/json": {
                    "example": {
                        "message": "User unmarked as spam successfully",
                        "user_id": 123,
                        "restaurant_id": 1,
                    }
                }
            },
        },
        403: {"description": "Access denied - cannot unmark spam for other restaurants"},
        404: {"description": "User was not marked as spam for this restaurant"},
    },
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
    description="Get spam status for a user including both restaurant-specific and global spam status. For restaurant users, restaurant_id is optional and will default to their restaurant. For admin users, restaurant_id is required.",
    response_model=SpamStatusResponse,
    responses={
        200: {
            "description": "Spam status retrieved successfully",
            "content": {
                "application/json": {
                    "example": {
                        "user_id": 123,
                        "restaurant_id": 1,
                        "is_global_spam": False,
                        "is_restaurant_spam": True,
                        "spam_restaurant_count": 2,
                    }
                }
            },
        },
        400: {"description": "restaurant_id is required"},
        403: {"description": "Access denied"},
        404: {"description": "User not found"},
    },
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
