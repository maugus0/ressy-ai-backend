"""
Dashboard API routes for order management.
Includes RBAC: admins can access all, managers can only access their restaurant's orders.
"""

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.security import HTTPBearer
from pydantic import BaseModel, Field

from app.middleware.auth_middleware import require_role
from app.services.dashboard_order_service import DashboardOrderService
from app.services.sse_service import OrderEventSubtype, SSEService

logger = logging.getLogger(__name__)

security = HTTPBearer(
    scheme_name="BearerAuth",
    description="Enter your JWT access token obtained from login endpoints",
)

router = APIRouter(
    dependencies=[Depends(security)],
)
order_service = DashboardOrderService()
sse_service = SSEService()


# ---------- Pydantic models for request validation ----------


class OrderItemRequest(BaseModel):
    """Individual order item."""

    item_id: Optional[int] = Field(
        None,
        description="Menu item ID (optional, for linking to menu)",
        json_schema_extra={"example": 123},
    )
    name: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description="Item name",
        json_schema_extra={"example": "Margherita Pizza"},
    )
    quantity: int = Field(
        1,
        gt=0,
        le=100,
        description="Quantity ordered",
        json_schema_extra={"example": 2},
    )
    price: Optional[float] = Field(
        None,
        ge=0,
        description="Unit price of the item",
        json_schema_extra={"example": 12.99},
    )
    instructions: Optional[str] = Field(
        None,
        max_length=500,
        description="Special instructions for this item",
        json_schema_extra={"example": "Extra cheese, no onions"},
    )


class CreateOrderRequest(BaseModel):
    """Request model for creating an order from the dashboard."""

    order_details: List[OrderItemRequest] = Field(
        ...,
        min_length=1,
        description="List of order items (at least one required)",
        json_schema_extra={
            "example": [
                {"item_id": 101, "name": "Margherita Pizza", "quantity": 2, "price": 12.99},
                {
                    "item_id": 102,
                    "name": "Caesar Salad",
                    "quantity": 1,
                    "price": 8.99,
                    "instructions": "Dressing on side",
                },
            ]
        },
    )
    total_amount: float = Field(
        ...,
        ge=0,
        description="Total order amount including tax and fees",
        json_schema_extra={"example": 34.97},
    )
    customer_name: Optional[str] = Field(
        None,
        max_length=200,
        description="Customer's full name",
        json_schema_extra={"example": "John Smith"},
    )
    customer_phone: Optional[str] = Field(
        None,
        max_length=20,
        description="Customer's phone number",
        json_schema_extra={"example": "+1234567890"},
    )
    customer_email: Optional[str] = Field(
        None,
        max_length=255,
        description="Customer's email address",
        json_schema_extra={"example": "john.smith@example.com"},
    )
    customization: Optional[Dict[str, Any]] = Field(
        None,
        description="Additional customization options (delivery info, notes, etc.)",
        json_schema_extra={"example": {"delivery": True, "notes": "Ring doorbell twice", "table_number": 5}},
    )
    status: Optional[str] = Field(
        "pending",
        description="Initial order status (pending, confirmed, preparing, ready, completed, cancelled)",
        json_schema_extra={"example": "pending"},
    )


class UpdateOrderRequest(BaseModel):
    """Request model for updating an order."""

    status: Optional[str] = Field(
        None,
        description="Order status (pending, confirmed, preparing, ready, completed, cancelled)",
        json_schema_extra={"example": "preparing"},
    )
    total_amount: Optional[float] = Field(
        None,
        ge=0,
        description="Updated total order amount",
        json_schema_extra={"example": 55.99},
    )
    order_details: Optional[List[OrderItemRequest]] = Field(
        None,
        description="Updated list of order items",
    )
    customization: Optional[Dict[str, Any]] = Field(
        None,
        description="Updated customization options",
        json_schema_extra={"example": {"delivery": False, "notes": "Customer will pick up"}},
    )


class UpdateOrderStatusRequest(BaseModel):
    """Request model for updating order status only."""

    status: str = Field(
        ...,
        description="New order status (pending, confirmed, preparing, ready, completed, cancelled)",
        json_schema_extra={"example": "preparing"},
    )


# ---------- Response models for documentation ----------


class OrderItemResponse(BaseModel):
    """Response model for order item."""

    item_id: Optional[int] = Field(None, description="Menu item ID")
    name: str = Field(..., description="Item name")
    quantity: int = Field(..., description="Quantity ordered")
    price: Optional[float] = Field(None, description="Unit price")
    instructions: Optional[str] = Field(None, description="Special instructions")


class OrderResponse(BaseModel):
    """Response model for a single order."""

    id: int = Field(..., description="Order ID")
    user_id: Optional[int] = Field(None, description="Associated user ID")
    restaurant_id: int = Field(..., description="Restaurant ID")
    status: str = Field(..., description="Order status")
    total_amount: float = Field(..., description="Total order amount")
    order_details: List[Dict[str, Any]] = Field(..., description="Order items")
    customization: Optional[Dict[str, Any]] = Field(None, description="Customization options")
    customer_name: Optional[str] = Field(None, description="Customer name")
    customer_phone: Optional[str] = Field(None, description="Customer phone")
    customer_email: Optional[str] = Field(None, description="Customer email")
    created_at: str = Field(..., description="Creation timestamp")
    updated_at: str = Field(..., description="Last update timestamp")
    deleted_at: Optional[str] = Field(None, description="Soft delete timestamp")


class CreateOrderResponse(BaseModel):
    """Response model for order creation."""

    order_id: int = Field(..., description="Created order ID")
    restaurant_id: int = Field(..., description="Restaurant ID")
    user_id: Optional[int] = Field(None, description="Associated user ID")
    status: str = Field(..., description="Order status")
    total_amount: float = Field(..., description="Total amount")
    order_details: List[Dict[str, Any]] = Field(..., description="Order items")
    customization: Optional[Dict[str, Any]] = Field(None, description="Customization")
    customer_name: Optional[str] = Field(None, description="Customer name")
    customer_phone: Optional[str] = Field(None, description="Customer phone")
    customer_email: Optional[str] = Field(None, description="Customer email")
    message: str = Field(..., description="Success message")


class OrderListResponse(BaseModel):
    """Response model for order list."""

    restaurant_id: int = Field(..., description="Restaurant ID")
    orders: List[OrderResponse] = Field(..., description="List of orders")
    total: int = Field(..., description="Total count of orders matching filters")
    limit: int = Field(..., description="Results limit")
    offset: int = Field(..., description="Pagination offset")


class OrderStatusResponse(BaseModel):
    """Response model for status update."""

    order_id: int = Field(..., description="Order ID")
    status: str = Field(..., description="New status")
    message: str = Field(..., description="Success message")


class OrderCancelResponse(BaseModel):
    """Response model for order cancellation."""

    order_id: int = Field(..., description="Order ID")
    status: str = Field(..., description="Cancelled status")
    previous_status: str = Field(..., description="Previous order status")
    message: str = Field(..., description="Success message")


class OrderDeleteResponse(BaseModel):
    """Response model for order deletion."""

    order_id: int = Field(..., description="Order ID")
    message: str = Field(..., description="Success message")


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
                detail=f"You can only access orders for your own restaurant (ID: {user_restaurant_id})",
            )
        return

    raise HTTPException(status_code=403, detail="Access denied - unknown user type")


def _check_order_access(current_user: dict, order_id: int):
    """
    Check if the current user has access to the specified order.
    Fetches the order and validates restaurant access.

    Args:
        current_user: JWT claims dict
        order_id: The order ID to check access for

    Returns:
        The order dict if access is granted

    Raises:
        HTTPException 404: If order not found
        HTTPException 403: If user doesn't have access
    """
    try:
        order = order_service.get_order_with_restaurant_check(order_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    restaurant_id = order.get("restaurant_id")

    if restaurant_id is None:
        raise HTTPException(
            status_code=500,
            detail="Order has no associated restaurant",
        )

    _check_restaurant_access(current_user, restaurant_id)
    return order


# ---------- CREATE ORDER ----------
@router.post(
    "/restaurants/{restaurant_id}/orders",
    summary="Create a new order (Dashboard)",
    description="""
Create a new order directly from the dashboard.

This endpoint is designed for staff to manually enter orders for walk-in customers,
phone orders, or to create orders on behalf of customers.

**Authentication**: Required (admin or restaurant manager role)

**Authorization**:
- Admins can create orders for any restaurant
- Restaurant managers can only create orders for their own restaurant

**Request Body**:
- `order_details`: List of order items with name, quantity, price, and optional instructions
- `total_amount`: Total order amount (should match sum of items plus tax/fees)
- `customer_name`: Customer's name (optional but recommended)
- `customer_phone`: Customer's phone number (optional)
- `customer_email`: Customer's email (optional)
- `customization`: Additional options like delivery info, table number, notes
- `status`: Initial status (defaults to 'pending')

**Valid Statuses**: pending, confirmed, preparing, ready, completed, cancelled

**SSE Event**: Emits `order.new_order` event on successful creation
""",
    response_description="Created order with all details",
    response_model=CreateOrderResponse,
    responses={
        200: {
            "description": "Order created successfully",
            "content": {
                "application/json": {
                    "example": {
                        "order_id": 456,
                        "restaurant_id": 1,
                        "user_id": 789,
                        "status": "pending",
                        "total_amount": 34.97,
                        "order_details": [
                            {"item_id": 101, "name": "Margherita Pizza", "quantity": 2, "price": 12.99},
                            {"item_id": 102, "name": "Caesar Salad", "quantity": 1, "price": 8.99},
                        ],
                        "customization": {"delivery": True, "notes": "Ring doorbell"},
                        "customer_name": "John Smith",
                        "customer_phone": "+1234567890",
                        "customer_email": "john@example.com",
                        "message": "Order created successfully",
                    }
                }
            },
        },
        400: {
            "description": "Invalid request data",
            "content": {
                "application/json": {
                    "example": {"detail": "Invalid status 'unknown'. Must be one of: pending, confirmed, ..."}
                }
            },
        },
        403: {
            "description": "Access denied",
            "content": {
                "application/json": {
                    "example": {"detail": "You can only access orders for your own restaurant (ID: 1)"}
                }
            },
        },
        404: {
            "description": "Restaurant not found",
            "content": {"application/json": {"example": {"detail": "Restaurant with ID 999 not found"}}},
        },
    },
)
async def create_order(
    restaurant_id: int,
    request: CreateOrderRequest,
    current_user: dict = Depends(require_role(["admin", "client"])),
):
    """Create a new order from the dashboard."""
    _check_restaurant_access(current_user, restaurant_id)

    try:
        # Convert order items to dict
        order_details = [item.model_dump() for item in request.order_details]

        result = order_service.create_order(
            restaurant_id=restaurant_id,
            order_details=order_details,
            total_amount=request.total_amount,
            customer_name=request.customer_name,
            customer_phone=request.customer_phone,
            customer_email=request.customer_email,
            customization=request.customization,
            status=request.status or "pending",
        )

        # Emit SSE event for new order (non-blocking, log errors)
        try:
            await sse_service.emit_order_event(
                restaurant_id=restaurant_id,
                order_id=result["order_id"],
                subtype=OrderEventSubtype.NEW_ORDER,
                data={
                    "order_id": result["order_id"],
                    "status": result["status"],
                    "total_amount": result["total_amount"],
                    "customer_name": result.get("customer_name"),
                },
            )
        except Exception as sse_error:
            logger.error(f"Failed to emit SSE event for new order {result['order_id']}: {sse_error}")

        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creating order: {str(e)}")


# ---------- GET ORDERS BY RESTAURANT ----------
@router.get(
    "/restaurants/{restaurant_id}/orders",
    summary="Get orders for a restaurant (Dashboard)",
    description="""
Retrieve all orders for a specific restaurant with optional filters.

This endpoint supports pagination and filtering by status, date range,
and includes the option to show soft-deleted orders.

**Authentication**: Required (admin or restaurant manager role)

**Authorization**:
- Admins can view orders for any restaurant
- Restaurant managers can only view orders for their own restaurant

**Query Parameters**:
- `status`: Filter by order status (pending, confirmed, preparing, ready, completed, cancelled)
- `start_date`: Filter orders created on or after this date (ISO format)
- `end_date`: Filter orders created on or before this date (ISO format)
- `include_deleted`: Include soft-deleted orders (default: false)
- `limit`: Maximum number of results (1-1000, default: 100)
- `offset`: Pagination offset (default: 0)

**Response**: Paginated list of orders with customer details
""",
    response_description="List of orders with pagination info",
    response_model=OrderListResponse,
    responses={
        200: {
            "description": "Orders retrieved successfully",
            "content": {
                "application/json": {
                    "example": {
                        "restaurant_id": 1,
                        "orders": [
                            {
                                "id": 456,
                                "user_id": 789,
                                "restaurant_id": 1,
                                "status": "preparing",
                                "total_amount": 34.97,
                                "order_details": [
                                    {"item_id": 101, "name": "Margherita Pizza", "quantity": 2, "price": 12.99}
                                ],
                                "customization": {"delivery": True},
                                "customer_name": "John Smith",
                                "customer_phone": "+1234567890",
                                "customer_email": "john@example.com",
                                "created_at": "2025-12-14T10:30:00",
                                "updated_at": "2025-12-14T10:35:00",
                                "deleted_at": None,
                            }
                        ],
                        "total": 1,
                        "limit": 100,
                        "offset": 0,
                    }
                }
            },
        },
        400: {
            "description": "Invalid filter parameters",
            "content": {"application/json": {"example": {"detail": "Invalid start_date format: not-a-date"}}},
        },
        403: {
            "description": "Access denied",
            "content": {
                "application/json": {
                    "example": {"detail": "You can only access orders for your own restaurant (ID: 1)"}
                }
            },
        },
    },
)
async def get_restaurant_orders(
    restaurant_id: int,
    status: Optional[str] = Query(
        None,
        description="Filter by order status (pending, confirmed, preparing, ready, completed, cancelled)",
        json_schema_extra={"example": "pending"},
    ),
    start_date: Optional[str] = Query(
        None,
        description="Filter orders from this date (ISO format)",
        json_schema_extra={"example": "2025-12-01T00:00:00"},
    ),
    end_date: Optional[str] = Query(
        None,
        description="Filter orders until this date (ISO format)",
        json_schema_extra={"example": "2025-12-31T23:59:59"},
    ),
    include_deleted: bool = Query(
        False,
        description="Include soft-deleted orders in results",
    ),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of results to return"),
    offset: int = Query(0, ge=0, description="Number of results to skip for pagination"),
    current_user: dict = Depends(require_role(["admin", "client"])),
):
    """Get orders for a restaurant with optional filters."""
    _check_restaurant_access(current_user, restaurant_id)

    try:
        result = order_service.get_orders_by_restaurant(
            restaurant_id=restaurant_id,
            status=status,
            start_date=start_date,
            end_date=end_date,
            limit=limit,
            offset=offset,
            include_deleted=include_deleted,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching orders: {str(e)}")


# ---------- GET ORDER BY ID ----------
@router.get(
    "/orders/{order_id}",
    summary="Get an order by ID (Dashboard)",
    description="""
Retrieve detailed information about a specific order.

Returns the complete order with all items, customer information,
and metadata including timestamps.

**Authentication**: Required (admin or restaurant manager role)

**Authorization**:
- Admins can view any order
- Restaurant managers can only view orders for their own restaurant
""",
    response_description="Complete order details with customer information",
    response_model=OrderResponse,
    responses={
        200: {
            "description": "Order retrieved successfully",
            "content": {
                "application/json": {
                    "example": {
                        "id": 456,
                        "user_id": 789,
                        "restaurant_id": 1,
                        "status": "preparing",
                        "total_amount": 34.97,
                        "order_details": [
                            {"item_id": 101, "name": "Margherita Pizza", "quantity": 2, "price": 12.99},
                            {"item_id": 102, "name": "Caesar Salad", "quantity": 1, "price": 8.99},
                        ],
                        "customization": {"delivery": True, "notes": "Ring doorbell"},
                        "customer_name": "John Smith",
                        "customer_phone": "+1234567890",
                        "customer_email": "john@example.com",
                        "created_at": "2025-12-14T10:30:00",
                        "updated_at": "2025-12-14T10:35:00",
                        "deleted_at": None,
                    }
                }
            },
        },
        403: {
            "description": "Access denied",
            "content": {
                "application/json": {
                    "example": {"detail": "You can only access orders for your own restaurant (ID: 1)"}
                }
            },
        },
        404: {
            "description": "Order not found",
            "content": {"application/json": {"example": {"detail": "Order with ID 999 not found"}}},
        },
    },
)
async def get_order(
    order_id: int,
    current_user: dict = Depends(require_role(["admin", "client"])),
):
    """Get an order by ID with authorization check."""
    order = _check_order_access(current_user, order_id)
    return order


# ---------- UPDATE ORDER ----------
@router.put(
    "/orders/{order_id}",
    summary="Update an order (Dashboard)",
    description="""
Update order details including status, items, amount, and customization.

This endpoint allows partial updates - only provided fields will be modified.
Cancelled orders cannot be updated (except by restoring them first).

**Authentication**: Required (admin or restaurant manager role)

**Authorization**:
- Admins can update any order
- Restaurant managers can only update orders for their own restaurant

**Updatable Fields**:
- `status`: Order status (pending, confirmed, preparing, ready, completed, cancelled)
- `total_amount`: Updated total amount
- `order_details`: Full replacement of order items
- `customization`: Full replacement of customization options

**SSE Event**: Emits `order.order_updated` event on successful update
""",
    response_description="Updated order with all details",
    response_model=OrderResponse,
    responses={
        200: {
            "description": "Order updated successfully",
            "content": {
                "application/json": {
                    "example": {
                        "id": 456,
                        "user_id": 789,
                        "restaurant_id": 1,
                        "status": "ready",
                        "total_amount": 34.97,
                        "order_details": [{"item_id": 101, "name": "Margherita Pizza", "quantity": 2, "price": 12.99}],
                        "customization": {"delivery": True},
                        "customer_name": "John Smith",
                        "customer_phone": "+1234567890",
                        "customer_email": "john@example.com",
                        "created_at": "2025-12-14T10:30:00",
                        "updated_at": "2025-12-14T11:00:00",
                        "deleted_at": None,
                    }
                }
            },
        },
        400: {
            "description": "Invalid request data or order cannot be updated",
            "content": {"application/json": {"example": {"detail": "Cannot update a cancelled order"}}},
        },
        403: {
            "description": "Access denied",
            "content": {
                "application/json": {
                    "example": {"detail": "You can only access orders for your own restaurant (ID: 1)"}
                }
            },
        },
        404: {
            "description": "Order not found",
            "content": {"application/json": {"example": {"detail": "Order with ID 999 not found"}}},
        },
    },
)
async def update_order(
    order_id: int,
    request: UpdateOrderRequest,
    current_user: dict = Depends(require_role(["admin", "client"])),
):
    """Update order details."""
    order = _check_order_access(current_user, order_id)
    restaurant_id = order.get("restaurant_id")

    try:
        # Convert order items to dict if provided
        order_details = None
        if request.order_details:
            order_details = [item.model_dump() for item in request.order_details]

        result = order_service.update_order(
            order_id=order_id,
            status=request.status,
            total_amount=request.total_amount,
            order_details=order_details,
            customization=request.customization,
        )

        # Emit SSE event for order update (non-blocking, log errors)
        if restaurant_id:
            try:
                await sse_service.emit_order_event(
                    restaurant_id=restaurant_id,
                    order_id=order_id,
                    subtype=OrderEventSubtype.ORDER_UPDATED,
                    data={
                        "order_id": order_id,
                        "status": result.get("status"),
                        "total_amount": result.get("total_amount"),
                    },
                )
            except Exception as sse_error:
                logger.error(f"Failed to emit SSE event for order update {order_id}: {sse_error}")

        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error updating order: {str(e)}")


# ---------- UPDATE ORDER STATUS ----------
@router.put(
    "/orders/{order_id}/status",
    summary="Update order status (Dashboard)",
    description="""
Update only the order status without modifying other fields.

This is a convenience endpoint for quick status updates during order processing.

**Authentication**: Required (admin or restaurant manager role)

**Authorization**:
- Admins can update any order
- Restaurant managers can only update orders for their own restaurant

**Valid Statuses**:
- `pending`: Order received, awaiting confirmation
- `confirmed`: Order confirmed by restaurant
- `preparing`: Order is being prepared
- `ready`: Order is ready for pickup/delivery
- `completed`: Order has been fulfilled
- `cancelled`: Order has been cancelled

**SSE Event**: Emits `order.order_updated` event on successful update
""",
    response_description="Status update confirmation",
    response_model=OrderStatusResponse,
    responses={
        200: {
            "description": "Status updated successfully",
            "content": {
                "application/json": {
                    "example": {
                        "order_id": 456,
                        "status": "preparing",
                        "message": "Order status updated to 'preparing'",
                    }
                }
            },
        },
        400: {
            "description": "Invalid status value",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Invalid status 'unknown'. Must be one of: pending, confirmed, preparing, ready, completed, cancelled"
                    }
                }
            },
        },
        403: {
            "description": "Access denied",
            "content": {
                "application/json": {
                    "example": {"detail": "You can only access orders for your own restaurant (ID: 1)"}
                }
            },
        },
        404: {
            "description": "Order not found",
            "content": {"application/json": {"example": {"detail": "Order with ID 999 not found"}}},
        },
    },
)
async def update_order_status(
    order_id: int,
    request: UpdateOrderStatusRequest,
    current_user: dict = Depends(require_role(["admin", "client"])),
):
    """Update order status."""
    order = _check_order_access(current_user, order_id)
    restaurant_id = order.get("restaurant_id")

    try:
        result = order_service.update_order_status(order_id=order_id, status=request.status)

        # Emit SSE event for order update (non-blocking, log errors)
        if restaurant_id:
            try:
                await sse_service.emit_order_event(
                    restaurant_id=restaurant_id,
                    order_id=order_id,
                    subtype=OrderEventSubtype.ORDER_UPDATED,
                    data={
                        "order_id": order_id,
                        "status": request.status,
                    },
                )
            except Exception as sse_error:
                logger.error(f"Failed to emit SSE event for order status update {order_id}: {sse_error}")

        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error updating order status: {str(e)}")


# ---------- CANCEL ORDER ----------
@router.put(
    "/orders/{order_id}/cancel",
    summary="Cancel an order (Dashboard)",
    description="""
Cancel an order by changing its status to 'cancelled'.

This action cannot be performed on already cancelled or completed orders.
To undo a cancellation, you would need to update the status back to a valid state.

**Authentication**: Required (admin or restaurant manager role)

**Authorization**:
- Admins can cancel any order
- Restaurant managers can only cancel orders for their own restaurant

**Restrictions**:
- Cannot cancel already cancelled orders
- Cannot cancel completed orders

**SSE Event**: Emits `order.order_cancelled` event on successful cancellation
""",
    response_description="Cancellation confirmation with previous status",
    response_model=OrderCancelResponse,
    responses={
        200: {
            "description": "Order cancelled successfully",
            "content": {
                "application/json": {
                    "example": {
                        "order_id": 456,
                        "status": "cancelled",
                        "previous_status": "preparing",
                        "message": "Order cancelled successfully",
                    }
                }
            },
        },
        400: {
            "description": "Cannot cancel order",
            "content": {
                "application/json": {
                    "examples": {
                        "already_cancelled": {"value": {"detail": "Order is already cancelled"}},
                        "already_completed": {"value": {"detail": "Cannot cancel a completed order"}},
                    }
                }
            },
        },
        403: {
            "description": "Access denied",
            "content": {
                "application/json": {
                    "example": {"detail": "You can only access orders for your own restaurant (ID: 1)"}
                }
            },
        },
        404: {
            "description": "Order not found",
            "content": {"application/json": {"example": {"detail": "Order with ID 999 not found"}}},
        },
    },
)
async def cancel_order(
    order_id: int,
    current_user: dict = Depends(require_role(["admin", "client"])),
):
    """Cancel an order."""
    order = _check_order_access(current_user, order_id)
    restaurant_id = order.get("restaurant_id")

    try:
        result = order_service.cancel_order(order_id=order_id)

        # Emit SSE event for order cancellation (non-blocking, log errors)
        if restaurant_id:
            try:
                await sse_service.emit_order_event(
                    restaurant_id=restaurant_id,
                    order_id=order_id,
                    subtype=OrderEventSubtype.ORDER_CANCELLED,
                    data={
                        "order_id": order_id,
                        "status": "cancelled",
                    },
                )
            except Exception as sse_error:
                logger.error(f"Failed to emit SSE event for order cancellation {order_id}: {sse_error}")

        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error cancelling order: {str(e)}")


# ---------- SOFT DELETE ORDER ----------
@router.delete(
    "/orders/{order_id}",
    summary="Delete an order (Dashboard)",
    description="""
Soft delete an order by setting the deleted_at timestamp.

The order is not permanently removed from the database but is hidden from
normal queries. Use the `include_deleted` filter when listing orders to see
deleted orders.

Deleted orders can be restored using the restore endpoint.

**Authentication**: Required (admin or restaurant manager role)

**Authorization**:
- Admins can delete any order
- Restaurant managers can only delete orders for their own restaurant

**Note**: This is a soft delete. The order data is preserved for audit purposes.
""",
    response_description="Deletion confirmation",
    response_model=OrderDeleteResponse,
    responses={
        200: {
            "description": "Order deleted successfully",
            "content": {
                "application/json": {
                    "example": {
                        "order_id": 456,
                        "message": "Order deleted successfully",
                    }
                }
            },
        },
        400: {
            "description": "Cannot delete order",
            "content": {"application/json": {"example": {"detail": "Order is already deleted"}}},
        },
        403: {
            "description": "Access denied",
            "content": {
                "application/json": {
                    "example": {"detail": "You can only access orders for your own restaurant (ID: 1)"}
                }
            },
        },
        404: {
            "description": "Order not found",
            "content": {"application/json": {"example": {"detail": "Order with ID 999 not found"}}},
        },
    },
)
async def delete_order(
    order_id: int,
    current_user: dict = Depends(require_role(["admin", "client"])),
):
    """Soft delete an order."""
    _check_order_access(current_user, order_id)

    try:
        result = order_service.soft_delete_order(order_id=order_id)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error deleting order: {str(e)}")


# ---------- RESTORE ORDER ----------
@router.put(
    "/orders/{order_id}/restore",
    summary="Restore a deleted order (Dashboard)",
    description="""
Restore a soft-deleted order by clearing the deleted_at timestamp.

The order will become visible again in normal queries and can be
updated or cancelled as normal.

**Authentication**: Required (admin or restaurant manager role)

**Authorization**:
- Admins can restore any order
- Restaurant managers can only restore orders for their own restaurant

**Note**: Can only restore orders that have been soft-deleted.
""",
    response_description="Restoration confirmation",
    response_model=OrderDeleteResponse,
    responses={
        200: {
            "description": "Order restored successfully",
            "content": {
                "application/json": {
                    "example": {
                        "order_id": 456,
                        "message": "Order restored successfully",
                    }
                }
            },
        },
        400: {
            "description": "Cannot restore order",
            "content": {"application/json": {"example": {"detail": "Order is not deleted"}}},
        },
        403: {
            "description": "Access denied",
            "content": {
                "application/json": {
                    "example": {"detail": "You can only access orders for your own restaurant (ID: 1)"}
                }
            },
        },
        404: {
            "description": "Order not found",
            "content": {"application/json": {"example": {"detail": "Order with ID 999 not found"}}},
        },
    },
)
async def restore_order(
    order_id: int,
    current_user: dict = Depends(require_role(["admin", "client"])),
):
    """Restore a soft-deleted order."""
    try:
        # Get restaurant_id for the order (even if deleted)
        restaurant_id = order_service.get_order_restaurant_id(order_id)
        if restaurant_id is None:
            raise HTTPException(status_code=404, detail=f"Order with ID {order_id} not found")

        _check_restaurant_access(current_user, restaurant_id)

        result = order_service.restore_order(order_id=order_id)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error restoring order: {str(e)}")
