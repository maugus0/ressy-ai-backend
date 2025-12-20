"""
Activity History API routes for order and reservation audit logs.
Includes RBAC: admins can access all, managers can only access their restaurant's history.
"""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.security import HTTPBearer
from pydantic import BaseModel, Field

from app.middleware.auth_middleware import require_role
from app.services.activity_history_service import ActivityHistoryService

security = HTTPBearer(
    scheme_name="HTTPBearer",
    description="Enter your JWT access token obtained from login endpoints",
)

router = APIRouter(
    dependencies=[Depends(security)],
)
history_service = ActivityHistoryService()


# ---------- Pydantic Response Models ----------


class HistoryEntryResponse(BaseModel):
    """Response model for a history entry."""

    id: int = Field(..., description="History entry ID")
    user_id: Optional[int] = Field(None, description="User ID who performed the action")
    activity_type: str = Field(..., description="Type: 'order' or 'reservation'")
    order_id: Optional[int] = Field(None, description="Associated order ID")
    reservation_id: Optional[int] = Field(None, description="Associated reservation ID")
    action: str = Field(..., description="Action performed (created, updated, cancelled, etc.)")
    previous_value: Optional[Dict[str, Any]] = Field(None, description="Previous state")
    new_value: Optional[Dict[str, Any]] = Field(None, description="New state")
    change_summary: Optional[str] = Field(None, description="Human-readable summary")
    restaurant_id: int = Field(..., description="Restaurant ID")
    ip_address: Optional[str] = Field(None, description="Client IP address")
    user_agent: Optional[str] = Field(None, description="Client user agent")
    created_at: str = Field(..., description="Timestamp of the action")
    performed_by_name: Optional[str] = Field(None, description="Name of user who performed action")
    performed_by_email: Optional[str] = Field(None, description="Email of user who performed action")


class OrderHistoryResponse(BaseModel):
    """Response model for order history."""

    order_id: int = Field(..., description="Order ID")
    restaurant_id: int = Field(..., description="Restaurant ID")
    entries: List[HistoryEntryResponse] = Field(..., description="History entries")
    total: int = Field(..., description="Total count of entries")
    limit: int = Field(..., description="Results limit")
    offset: int = Field(..., description="Pagination offset")


class ReservationHistoryResponse(BaseModel):
    """Response model for reservation history."""

    reservation_id: int = Field(..., description="Reservation ID")
    restaurant_id: int = Field(..., description="Restaurant ID")
    entries: List[HistoryEntryResponse] = Field(..., description="History entries")
    total: int = Field(..., description="Total count of entries")
    limit: int = Field(..., description="Results limit")
    offset: int = Field(..., description="Pagination offset")


class RestaurantHistoryResponse(BaseModel):
    """Response model for restaurant activity history."""

    restaurant_id: int = Field(..., description="Restaurant ID")
    activity_type: Optional[str] = Field(None, description="Filtered activity type")
    entries: List[HistoryEntryResponse] = Field(..., description="History entries")
    total: int = Field(..., description="Total count of entries")
    limit: int = Field(..., description="Results limit")
    offset: int = Field(..., description="Pagination offset")


# ---------- Helper functions for RBAC ----------


def _check_restaurant_access(current_user: dict, restaurant_id: int):
    """
    Check if the current user has access to the specified restaurant.
    Admins have access to all restaurants.
    Restaurant users (managers) can only access their own restaurant.

    Args:
        current_user: JWT claims dict containing user_type, restaurant_id
        restaurant_id: The restaurant ID to check access for

    Raises:
        HTTPException 403: If user doesn't have access to this restaurant
    """
    user_type = current_user.get("user_type")

    if user_type == "admin":
        return

    if user_type == "restaurant":
        user_restaurant_id = current_user.get("restaurant_id")

        if user_restaurant_id is None:
            raise HTTPException(
                status_code=403,
                detail="Your account is not associated with any restaurant",
            )

        if int(user_restaurant_id) != int(restaurant_id):
            raise HTTPException(
                status_code=403,
                detail=f"You can only access history for your own restaurant (ID: {user_restaurant_id})",
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

**Authentication**: Required (admin or restaurant manager role)

**Authorization**:
- Admins can view history for any order
- Restaurant managers can only view history for their own restaurant's orders

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
                        "restaurant_id": 1,
                        "entries": [
                            {
                                "id": 1,
                                "user_id": 5,
                                "activity_type": "order",
                                "order_id": 123,
                                "reservation_id": None,
                                "action": "status_changed",
                                "previous_value": {"status": "pending"},
                                "new_value": {"status": "preparing"},
                                "change_summary": "Order #123 status changed: pending → preparing",
                                "restaurant_id": 1,
                                "ip_address": "192.168.1.1",
                                "user_agent": "Mozilla/5.0...",
                                "created_at": "2025-12-14T10:30:00",
                                "performed_by_name": "John Staff",
                                "performed_by_email": "john@restaurant.com",
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
):
    """Get activity history for an order."""
    # Check if order exists and get restaurant_id for RBAC
    restaurant_id = history_service.get_order_restaurant_id(order_id)
    if restaurant_id is None:
        raise HTTPException(status_code=404, detail=f"Order with ID {order_id} not found")

    _check_restaurant_access(current_user, restaurant_id)

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
    "/reservations/{reservation_id}/history",
    summary="Get reservation activity history",
    description="""
Retrieve the complete activity history for a specific reservation.

This endpoint returns all changes made to a reservation including:
- Creation
- Status changes (pending → confirmed, cancelled, etc.)
- Updates to party size, date/time, notes, etc.
- Cancellation

Each entry includes who made the change, when, and what was changed.

**Authentication**: Required (admin or restaurant manager role)

**Authorization**:
- Admins can view history for any reservation
- Restaurant managers can only view history for their own restaurant's reservations

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
                        "reservation_id": 456,
                        "restaurant_id": 1,
                        "entries": [
                            {
                                "id": 2,
                                "user_id": 5,
                                "activity_type": "reservation",
                                "order_id": None,
                                "reservation_id": 456,
                                "action": "status_changed",
                                "previous_value": {"status": "pending"},
                                "new_value": {"status": "confirmed"},
                                "change_summary": "Reservation #456 status changed: pending → confirmed",
                                "restaurant_id": 1,
                                "ip_address": "192.168.1.1",
                                "user_agent": "Mozilla/5.0...",
                                "created_at": "2025-12-14T11:00:00",
                                "performed_by_name": "Jane Manager",
                                "performed_by_email": "jane@restaurant.com",
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
    reservation_id: int,
    limit: int = Query(100, ge=1, le=500, description="Maximum results"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    current_user: dict = Depends(require_role(["admin", "client"])),
):
    """Get activity history for a reservation."""
    # Check if reservation exists and get restaurant_id for RBAC
    restaurant_id = history_service.get_reservation_restaurant_id(reservation_id)
    if restaurant_id is None:
        raise HTTPException(status_code=404, detail=f"Reservation with ID {reservation_id} not found")

    _check_restaurant_access(current_user, restaurant_id)

    try:
        result = history_service.get_reservation_history(
            reservation_id=reservation_id,
            limit=limit,
            offset=offset,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching reservation history: {str(e)}")


# ---------- GET RESTAURANT HISTORY ----------
@router.get(
    "/restaurants/{restaurant_id}/history",
    summary="Get restaurant activity history",
    description="""
Retrieve all activity history for a restaurant.

This endpoint returns all order and reservation changes for the restaurant.
Use the `activity_type` filter to show only orders or reservations.

**Authentication**: Required (admin or restaurant manager role)

**Authorization**:
- Admins can view history for any restaurant
- Restaurant managers can only view history for their own restaurant

**Query Parameters**:
- `activity_type`: Filter by 'order' or 'reservation' (optional)
- `start_date`: Filter from this date (ISO format, optional)
- `end_date`: Filter until this date (ISO format, optional)
- `limit`: Maximum results (default: 100, max: 500)
- `offset`: Pagination offset (default: 0)
""",
    response_description="Restaurant activity history with pagination",
    response_model=RestaurantHistoryResponse,
    responses={
        200: {
            "description": "History retrieved successfully",
            "content": {
                "application/json": {
                    "example": {
                        "restaurant_id": 1,
                        "activity_type": None,
                        "entries": [
                            {
                                "id": 1,
                                "user_id": 5,
                                "activity_type": "order",
                                "order_id": 123,
                                "reservation_id": None,
                                "action": "created",
                                "previous_value": None,
                                "new_value": {"status": "pending", "total_amount": 45.99},
                                "change_summary": "Order #123 created with status: pending",
                                "restaurant_id": 1,
                                "ip_address": "192.168.1.1",
                                "user_agent": "Mozilla/5.0...",
                                "created_at": "2025-12-14T10:00:00",
                                "performed_by_name": "System",
                                "performed_by_email": None,
                            }
                        ],
                        "total": 1,
                        "limit": 100,
                        "offset": 0,
                    }
                }
            },
        },
        400: {"description": "Invalid filter parameters"},
        403: {"description": "Access denied - cannot access this restaurant's history"},
    },
)
async def get_restaurant_history(
    restaurant_id: int,
    activity_type: Optional[str] = Query(
        None,
        description="Filter by activity type ('order' or 'reservation')",
        json_schema_extra={"example": "order"},
    ),
    start_date: Optional[str] = Query(
        None,
        description="Filter from this date (ISO format)",
        json_schema_extra={"example": "2025-12-01T00:00:00"},
    ),
    end_date: Optional[str] = Query(
        None,
        description="Filter until this date (ISO format)",
        json_schema_extra={"example": "2025-12-31T23:59:59"},
    ),
    limit: int = Query(100, ge=1, le=500, description="Maximum results"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    current_user: dict = Depends(require_role(["admin", "client"])),
):
    """Get activity history for a restaurant."""
    _check_restaurant_access(current_user, restaurant_id)

    try:
        result = history_service.get_restaurant_history(
            restaurant_id=restaurant_id,
            activity_type=activity_type,
            start_date=start_date,
            end_date=end_date,
            limit=limit,
            offset=offset,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching restaurant history: {str(e)}")
