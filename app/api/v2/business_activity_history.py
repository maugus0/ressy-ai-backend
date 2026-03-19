"""
Activity History API routes for order and reservation audit logs.
Includes RBAC: admins can access all, managers can only access their business's history.
"""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.security import HTTPBearer
from pydantic import BaseModel, Field

from app.middleware.auth_middleware import require_role
from app.services.business_activity_history_service import BusinessActivityHistoryService

security = HTTPBearer(
    scheme_name="HTTPBearer",
    description="Enter your JWT access token obtained from login endpoints",
)

router = APIRouter(
    dependencies=[Depends(security)],
)


# ---------- Service dependencies ----------


def get_history_service() -> BusinessActivityHistoryService:
    """Dependency to get a fresh activity history service instance per request."""
    return BusinessActivityHistoryService()


# ---------- Pydantic Response Models ----------


class HistoryEntryResponse(BaseModel):
    """Response model for a history entry."""

    id: int = Field(..., description="History entry ID")
    user_id: Optional[int] = Field(None, description="User ID who performed the action")
    activity_type: str = Field(..., description="Type: 'order' or 'reservation'")
    order_id: Optional[int] = Field(None, description="Associated order ID")
    booking_id: Optional[int] = Field(None, description="Associated reservation ID")
    action: str = Field(..., description="Action performed (created, updated, cancelled, etc.)")
    previous_value: Optional[Dict[str, Any]] = Field(None, description="Previous state")
    new_value: Optional[Dict[str, Any]] = Field(None, description="New state")
    change_summary: Optional[str] = Field(None, description="Human-readable summary")
    business_id: int = Field(..., description="Restaurant ID")
    created_at: str = Field(..., description="Timestamp of the action")
    performed_by_name: Optional[str] = Field(None, description="Name of user who performed action")
    performed_by_email: Optional[str] = Field(None, description="Email of user who performed action")


class OrderHistoryResponse(BaseModel):
    """Response model for order history."""

    order_id: int = Field(..., description="Order ID")
    business_id: int = Field(..., description="Restaurant ID")
    entries: List[HistoryEntryResponse] = Field(..., description="History entries")
    total: int = Field(..., description="Total count of entries")
    limit: int = Field(..., description="Results limit")
    offset: int = Field(..., description="Pagination offset")


class ReservationHistoryResponse(BaseModel):
    """Response model for reservation history."""

    booking_id: int = Field(..., description="Reservation ID")
    business_id: int = Field(..., description="Restaurant ID")
    entries: List[HistoryEntryResponse] = Field(..., description="History entries")
    total: int = Field(..., description="Total count of entries")
    limit: int = Field(..., description="Results limit")
    offset: int = Field(..., description="Pagination offset")


# ---------- Helper functions for RBAC ----------


def _check_business_access(current_user: dict, business_id: int):
    """
    Check if the current user has access to the specified business.
    Admins have access to all businesss.
    Restaurant users (managers) can only access their own business.

    Args:
        current_user: JWT claims dict containing user_type, business_id
        business_id: The business ID to check access for

    Raises:
        HTTPException 403: If user doesn't have access to this business
    """
    user_type = current_user.get("user_type")

    if user_type == "admin":
        return

    if user_type == "business":
        user_business_id = current_user.get("business_id")

        if user_business_id is None:
            raise HTTPException(
                status_code=403,
                detail="Your account is not associated with any business",
            )

        if int(user_business_id) != int(business_id):
            raise HTTPException(
                status_code=403,
                detail=f"You can only access history for your own business (ID: {user_business_id})",
            )
        return

    raise HTTPException(status_code=403, detail="Access denied - unknown user type")


# ---------- GET ORDER HISTORY ----------
@router.get(
    "/orders/{order_id}/history",
    summary="Get order activity history",
    description="""
Retrieve the complete activity history for a specific order.

This endpoint returns all changes made to an order including:
- Creation
- Status changes
- Updates to items, amounts, or customization
- Cancellation

Each entry includes who made the change, when, and what was changed.

**Authentication**: Required (admin or business manager role)

**Authorization**:
- Admins can view history for any order
- Restaurant managers can only view history for their own business's orders

**Query Parameters**:
- `limit`: Maximum number of results (default: 100, max: 500)
- `offset`: Pagination offset (default: 0)
""",
    response_description="Order activity history with pagination",
    response_model=OrderHistoryResponse,
    responses={
        200: {
            "description": "History retrieved successfully",
            "content": {
                "application/json": {
                    "example": {
                        "order_id": 123,
                        "business_id": 1,
                        "entries": [
                            {
                                "id": 1,
                                "user_id": 5,
                                "activity_type": "order",
                                "order_id": 123,
                                "booking_id": None,
                                "action": "status_changed",
                                "previous_value": {"status": "pending"},
                                "new_value": {"status": "preparing"},
                                "change_summary": "Order #123 status changed: pending → preparing",
                                "business_id": 1,
                                "created_at": "2025-12-14T10:30:00Z",
                                "performed_by_name": "John Staff",
                                "performed_by_email": "john@business.com",
                            }
                        ],
                        "total": 1,
                        "limit": 100,
                        "offset": 0,
                    }
                }
            },
        },
        403: {"description": "Access denied - cannot access this order's history"},
        404: {"description": "Order not found"},
    },
)
async def get_order_history(
    order_id: int,
    limit: int = Query(100, ge=1, le=500, description="Maximum results"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    current_user: dict = Depends(require_role(["admin", "client"])),
    history_service: BusinessActivityHistoryService = Depends(get_history_service),
):
    """Get activity history for an order."""
    # Check if order exists and get business_id for RBAC
    business_id = history_service.get_order_business_id(order_id)
    if business_id is None:
        raise HTTPException(status_code=404, detail=f"Order with ID {order_id} not found")

    _check_business_access(current_user, business_id)

    try:
        result = history_service.get_order_history(
            order_id=order_id,
            limit=limit,
            offset=offset,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching order history: {str(e)}")


# ---------- GET RESERVATION HISTORY ----------
@router.get(
    "/reservations/{booking_id}/history",
    summary="Get reservation activity history",
    description="""
Retrieve the complete activity history for a specific reservation.

This endpoint returns all changes made to a reservation including:
- Creation
- Status changes (pending → confirmed, cancelled, etc.)
- Updates to party size, date/time, notes, etc.
- Cancellation

Each entry includes who made the change, when, and what was changed.

**Authentication**: Required (admin or business manager role)

**Authorization**:
- Admins can view history for any reservation
- Restaurant managers can only view history for their own business's reservations

**Query Parameters**:
- `limit`: Maximum number of results (default: 100, max: 500)
- `offset`: Pagination offset (default: 0)
""",
    response_description="Reservation activity history with pagination",
    response_model=ReservationHistoryResponse,
    responses={
        200: {
            "description": "History retrieved successfully",
            "content": {
                "application/json": {
                    "example": {
                        "booking_id": 456,
                        "business_id": 1,
                        "entries": [
                            {
                                "id": 2,
                                "user_id": 5,
                                "activity_type": "reservation",
                                "order_id": None,
                                "booking_id": 456,
                                "action": "status_changed",
                                "previous_value": {"status": "pending"},
                                "new_value": {"status": "confirmed"},
                                "change_summary": "Reservation #456 status changed: pending → confirmed",
                                "business_id": 1,
                                "created_at": "2025-12-14T11:00:00Z",
                                "performed_by_name": "Jane Manager",
                                "performed_by_email": "jane@business.com",
                            }
                        ],
                        "total": 1,
                        "limit": 100,
                        "offset": 0,
                    }
                }
            },
        },
        403: {"description": "Access denied - cannot access this reservation's history"},
        404: {"description": "Reservation not found"},
    },
)
async def get_reservation_history(
    booking_id: int,
    limit: int = Query(100, ge=1, le=500, description="Maximum results"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    current_user: dict = Depends(require_role(["admin", "client"])),
    history_service: BusinessActivityHistoryService = Depends(get_history_service),
):
    """Get activity history for a reservation."""
    # Check if reservation exists and get business_id for RBAC
    business_id = history_service.get_reservation_business_id(booking_id)
    if business_id is None:
        raise HTTPException(status_code=404, detail=f"Reservation with ID {booking_id} not found")

    _check_business_access(current_user, business_id)

    try:
        result = history_service.get_reservation_history(
            booking_id=booking_id,
            limit=limit,
            offset=offset,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching reservation history: {str(e)}")
