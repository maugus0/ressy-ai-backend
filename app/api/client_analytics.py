"""
Client Analytics API for restaurant dashboard insights.

Provides analytics endpoints for restaurant clients to view insights about their
own restaurant's performance, including calls, reservations, orders, menu, and FAQs.

All endpoints are scoped to the authenticated restaurant user's restaurant.
"""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.middleware.auth_middleware import get_current_restaurant_user
from app.services.client_analytics_service import ClientAnalyticsService

# ---------- Response Models ----------


class RecentActivityItem(BaseModel):
    """Recent activity item (call, reservation, or order)."""

    id: int = Field(..., description="Activity ID")
    type: str = Field(..., description="Activity type: call, reservation, or order")
    description: str = Field(..., description="Brief description of the activity")
    status: Optional[str] = Field(None, description="Current status")
    timestamp: Optional[str] = Field(None, description="Activity timestamp")


class ScheduleItem(BaseModel):
    """Today's schedule item (reservation)."""

    id: int = Field(..., description="Reservation ID")
    time: str = Field(..., description="Reservation time (HH:MM)")
    party_size: int = Field(..., description="Number of guests")
    customer_name: str = Field(..., description="Customer name")
    status: Optional[str] = Field(None, description="Reservation status")
    special_request: Optional[str] = Field(None, description="Special requests")


class PendingOrderItem(BaseModel):
    """Pending order item."""

    id: int = Field(..., description="Order ID")
    order_number: str = Field(..., description="Order number (e.g., #1234)")
    customer_name: str = Field(..., description="Customer name")
    total: float = Field(..., description="Order total amount")
    status: Optional[str] = Field(None, description="Order status")
    timestamp: Optional[str] = Field(None, description="Order creation timestamp")


class RestaurantAnalyticsResponse(BaseModel):
    """Comprehensive restaurant analytics response."""

    # Call statistics
    total_calls: int = Field(..., description="Total number of calls")
    calls_today: int = Field(..., description="Number of calls today")
    average_call_duration: float = Field(..., description="Average call duration in seconds")

    # Reservation statistics
    total_reservations: int = Field(..., description="Total number of reservations")
    reservations_today: int = Field(..., description="Number of reservations for today")
    confirmed_reservations: int = Field(..., description="Number of confirmed reservations")
    pending_reservations: int = Field(..., description="Number of pending reservations")

    # Order statistics
    total_orders: int = Field(..., description="Total number of orders")
    orders_today: int = Field(..., description="Number of orders today")
    total_revenue: float = Field(..., description="Total revenue from completed orders")
    revenue_today: float = Field(..., description="Revenue from today's completed orders")
    pending_orders_count: int = Field(..., description="Number of pending orders")

    # Menu statistics
    total_menu_items: int = Field(..., description="Total number of menu items")
    available_menu_items: int = Field(..., description="Number of available menu items")
    special_items: int = Field(..., description="Number of special/featured items")
    menu_categories: List[str] = Field(..., description="List of menu categories")

    # FAQ statistics
    total_faqs: int = Field(..., description="Total number of FAQs")

    # Customer statistics
    total_customers: int = Field(..., description="Total number of customers")

    # Activity data
    recent_activity: List[RecentActivityItem] = Field(..., description="Recent activity (calls, reservations, orders)")
    todays_schedule: List[ScheduleItem] = Field(..., description="Today's reservation schedule")
    pending_orders: List[PendingOrderItem] = Field(..., description="Current pending orders")


class CallAnalyticsResponse(BaseModel):
    """Detailed call analytics response."""

    total_calls: int = Field(..., description="Total number of calls")
    calls_today: int = Field(..., description="Number of calls today")
    average_call_duration: float = Field(..., description="Average call duration in seconds")
    status_breakdown: Dict[str, int] = Field(..., description="Calls by status")
    time_of_day_distribution: List[Dict[str, Any]] = Field(..., description="Call distribution by hour of day")
    calls_by_day_of_week: List[Dict[str, Any]] = Field(..., description="Call distribution by day of week")


class ReservationAnalyticsResponse(BaseModel):
    """Detailed reservation analytics response."""

    total_reservations: int = Field(..., description="Total number of reservations")
    reservations_today: int = Field(..., description="Reservations for today")
    confirmed_reservations: int = Field(..., description="Confirmed reservations")
    pending_reservations: int = Field(..., description="Pending reservations")
    cancelled_reservations: int = Field(..., description="Cancelled reservations")
    completed_reservations: int = Field(..., description="Completed reservations")
    no_show_reservations: int = Field(..., description="No-show reservations")


class OrderAnalyticsResponse(BaseModel):
    """Detailed order analytics response."""

    total_orders: int = Field(..., description="Total number of orders")
    orders_today: int = Field(..., description="Orders today")
    total_revenue: float = Field(..., description="Total revenue")
    revenue_today: float = Field(..., description="Today's revenue")
    pending_orders: int = Field(..., description="Pending orders")
    confirmed_orders: int = Field(..., description="Confirmed orders")
    preparing_orders: int = Field(..., description="Orders being prepared")
    completed_orders: int = Field(..., description="Completed orders")
    cancelled_orders: int = Field(..., description="Cancelled orders")


class MenuAnalyticsResponse(BaseModel):
    """Detailed menu analytics response."""

    total_menu_items: int = Field(..., description="Total menu items")
    available_menu_items: int = Field(..., description="Available items")
    unavailable_menu_items: int = Field(..., description="Unavailable items")
    special_items: int = Field(..., description="Special/featured items")
    categories: List[str] = Field(..., description="Menu categories")
    category_count: int = Field(..., description="Number of categories")


# ---------- Router Setup ----------


def get_analytics_service() -> ClientAnalyticsService:
    """Dependency to get analytics service instance."""
    return ClientAnalyticsService()


router = APIRouter(
    prefix="/api/v1/client",
    tags=["Client Analytics"],
    dependencies=[Depends(get_current_restaurant_user)],
)


# ---------- Endpoints ----------


@router.get(
    "/analytics",
    summary="Get restaurant analytics (Client)",
    description="""
Get comprehensive analytics for the authenticated restaurant.

This endpoint provides a complete overview of the restaurant's performance,
including statistics for calls, reservations, orders, menu, FAQs, and recent activity.

**Authentication**: Required (restaurant user)

**Scope**: Automatically scoped to the authenticated user's restaurant.

**Response includes**:
- **Call statistics**: Total calls, calls today, average duration
- **Reservation statistics**: Total, today, by status
- **Order statistics**: Total, today, revenue, pending count
- **Menu statistics**: Total items, available, specials, categories
- **FAQ statistics**: Total FAQs
- **Customer statistics**: Total unique customers
- **Recent activity**: Last 10 activities (calls, reservations, orders)
- **Today's schedule**: Today's reservations sorted by time
- **Pending orders**: Current orders awaiting processing
""",
    response_model=RestaurantAnalyticsResponse,
    response_description="Comprehensive restaurant analytics",
    responses={
        200: {
            "description": "Analytics retrieved successfully",
            "content": {
                "application/json": {
                    "example": {
                        "total_calls": 150,
                        "calls_today": 12,
                        "average_call_duration": 45.5,
                        "total_reservations": 89,
                        "reservations_today": 5,
                        "confirmed_reservations": 60,
                        "pending_reservations": 10,
                        "total_orders": 234,
                        "orders_today": 8,
                        "total_revenue": 15678.50,
                        "revenue_today": 450.00,
                        "pending_orders_count": 3,
                        "total_menu_items": 45,
                        "available_menu_items": 40,
                        "special_items": 5,
                        "menu_categories": ["Appetizers", "Main Course", "Desserts"],
                        "total_faqs": 12,
                        "total_customers": 500,
                        "recent_activity": [
                            {
                                "id": 1,
                                "type": "call",
                                "description": "Call from +1234567890",
                                "status": "completed",
                                "timestamp": "2024-12-20T14:30:00Z",
                            }
                        ],
                        "todays_schedule": [
                            {
                                "id": 1,
                                "time": "18:00",
                                "party_size": 4,
                                "customer_name": "John Doe",
                                "status": "confirmed",
                                "special_request": "Window seat",
                            }
                        ],
                        "pending_orders": [
                            {
                                "id": 1,
                                "order_number": "#1234",
                                "customer_name": "Jane Smith",
                                "total": 45.99,
                                "status": "pending",
                                "timestamp": "2024-12-20T14:45:00Z",
                            }
                        ],
                    }
                }
            },
        },
    },
)
async def get_restaurant_analytics(
    service: ClientAnalyticsService = Depends(get_analytics_service),
    claims: dict = Depends(get_current_restaurant_user),
):
    """Get comprehensive restaurant analytics."""
    restaurant_id = int(claims["restaurant_id"])
    return service.get_restaurant_analytics(restaurant_id)


@router.get(
    "/analytics/calls",
    summary="Get call analytics (Client)",
    description="""
Get detailed call analytics for the authenticated restaurant.

Provides call statistics including total calls, today's calls, average duration,
status breakdown, and call distribution by time of day and day of week.

**Authentication**: Required (restaurant user)

**Scope**: Automatically scoped to the authenticated user's restaurant.
""",
    response_model=CallAnalyticsResponse,
    response_description="Call analytics details",
    responses={
        200: {
            "description": "Call analytics retrieved successfully",
            "content": {
                "application/json": {
                    "example": {
                        "total_calls": 150,
                        "calls_today": 12,
                        "average_call_duration": 45.5,
                        "status_breakdown": {"completed": 120, "in_progress": 5, "missed": 25},
                        "time_of_day_distribution": [
                            {"hour_bucket": 9, "count": 10},
                            {"hour_bucket": 12, "count": 25},
                        ],
                        "calls_by_day_of_week": [
                            {"day_of_week": 1, "count": 20},
                            {"day_of_week": 2, "count": 25},
                        ],
                    }
                }
            },
        },
    },
)
async def get_call_analytics(
    service: ClientAnalyticsService = Depends(get_analytics_service),
    claims: dict = Depends(get_current_restaurant_user),
):
    """Get detailed call analytics."""
    restaurant_id = int(claims["restaurant_id"])
    return service.get_call_analytics(restaurant_id)


@router.get(
    "/analytics/reservations",
    summary="Get reservation analytics (Client)",
    description="""
Get detailed reservation analytics for the authenticated restaurant.

Provides reservation statistics including total reservations, today's count,
and breakdown by status (confirmed, pending, cancelled, completed, no-show).

**Authentication**: Required (restaurant user)

**Scope**: Automatically scoped to the authenticated user's restaurant.
""",
    response_model=ReservationAnalyticsResponse,
    response_description="Reservation analytics details",
    responses={
        200: {
            "description": "Reservation analytics retrieved successfully",
            "content": {
                "application/json": {
                    "example": {
                        "total_reservations": 89,
                        "reservations_today": 5,
                        "confirmed_reservations": 60,
                        "pending_reservations": 10,
                        "cancelled_reservations": 15,
                        "completed_reservations": 3,
                        "no_show_reservations": 1,
                    }
                }
            },
        },
    },
)
async def get_reservation_analytics(
    service: ClientAnalyticsService = Depends(get_analytics_service),
    claims: dict = Depends(get_current_restaurant_user),
):
    """Get detailed reservation analytics."""
    restaurant_id = int(claims["restaurant_id"])
    return service.get_reservation_analytics(restaurant_id)


@router.get(
    "/analytics/orders",
    summary="Get order analytics (Client)",
    description="""
Get detailed order analytics for the authenticated restaurant.

Provides order statistics including total orders, today's count, revenue,
and breakdown by status (pending, confirmed, preparing, completed, cancelled).

**Authentication**: Required (restaurant user)

**Scope**: Automatically scoped to the authenticated user's restaurant.
""",
    response_model=OrderAnalyticsResponse,
    response_description="Order analytics details",
    responses={
        200: {
            "description": "Order analytics retrieved successfully",
            "content": {
                "application/json": {
                    "example": {
                        "total_orders": 234,
                        "orders_today": 8,
                        "total_revenue": 15678.50,
                        "revenue_today": 450.00,
                        "pending_orders": 3,
                        "confirmed_orders": 2,
                        "preparing_orders": 1,
                        "completed_orders": 225,
                        "cancelled_orders": 3,
                    }
                }
            },
        },
    },
)
async def get_order_analytics(
    service: ClientAnalyticsService = Depends(get_analytics_service),
    claims: dict = Depends(get_current_restaurant_user),
):
    """Get detailed order analytics."""
    restaurant_id = int(claims["restaurant_id"])
    return service.get_order_analytics(restaurant_id)


@router.get(
    "/analytics/menu",
    summary="Get menu analytics (Client)",
    description="""
Get detailed menu analytics for the authenticated restaurant.

Provides menu statistics including total items, available/unavailable items,
special items count, and list of categories.

**Authentication**: Required (restaurant user)

**Scope**: Automatically scoped to the authenticated user's restaurant.
""",
    response_model=MenuAnalyticsResponse,
    response_description="Menu analytics details",
    responses={
        200: {
            "description": "Menu analytics retrieved successfully",
            "content": {
                "application/json": {
                    "example": {
                        "total_menu_items": 45,
                        "available_menu_items": 40,
                        "unavailable_menu_items": 5,
                        "special_items": 5,
                        "categories": ["Appetizers", "Main Course", "Desserts", "Beverages"],
                        "category_count": 4,
                    }
                }
            },
        },
    },
)
async def get_menu_analytics(
    service: ClientAnalyticsService = Depends(get_analytics_service),
    claims: dict = Depends(get_current_restaurant_user),
):
    """Get detailed menu analytics."""
    restaurant_id = int(claims["restaurant_id"])
    return service.get_menu_analytics(restaurant_id)
