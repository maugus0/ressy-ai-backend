from fastapi import APIRouter, Depends

from app.middleware.auth_middleware import get_current_active_user, require_role
from app.services.order_service import OrderService

router = APIRouter()
order_service = OrderService()


# CREATE
@router.post(
    "/{restaurant_id}",
    dependencies=[Depends(require_role(["admin", "client"]))],
    summary="Create Order",
    description="Create a new order for a restaurant. Can be used by admin or restaurant staff. Typically created through the voice agent when customers place orders.",
    response_description="Returns the created order with assigned order ID and details.",
)
async def create_order(restaurant_id: str, data: dict, current_user: dict = Depends(get_current_active_user)):
    """
    Create a new order for a restaurant.
    
    **Authentication**: Required (admin or restaurant client role)
    
    **Path Parameters**:
    - restaurant_id: ID of the restaurant the order belongs to
    
    **Request Body**: Order data including:
    - items: List of menu items with quantities
    - customer information
    - special instructions
    - Other order details
    
    **Response**: Created order object with order ID and all details.
    """
    return order_service.create_order(restaurant_id, data)


# READ ALL
@router.get(
    "/{restaurant_id}",
    dependencies=[Depends(require_role(["admin", "client"]))],
    summary="List Orders",
    description="Retrieve all orders for a specific restaurant. Restaurant users can only see orders for their restaurant.",
    response_description="List of orders with order details, items, and status.",
)
async def list_orders(restaurant_id: str, current_user: dict = Depends(get_current_active_user)):
    """
    Get all orders for a restaurant.
    
    **Authentication**: Required (admin or restaurant client role)
    
    **Path Parameters**:
    - restaurant_id: ID of the restaurant
    
    **Response**: List of all orders for the restaurant.
    """
    return order_service.list_orders(restaurant_id)


# READ ONE
@router.get(
    "/details/{order_id}",
    dependencies=[Depends(require_role(["admin", "client"]))],
    summary="Get Order Details",
    description="Retrieve detailed information for a specific order by ID. Includes order items, customer information, and status.",
    response_description="Complete order object with all details including items and status.",
)
async def get_order(order_id: str, current_user: dict = Depends(get_current_active_user)):
    """
    Get detailed information for a specific order.
    
    **Authentication**: Required (admin or restaurant client role)
    
    **Path Parameters**:
    - order_id: Unique identifier of the order
    
    **Response**: Complete order object with items, customer info, and status.
    """
    return order_service.get_order(order_id)


# UPDATE
@router.put(
    "/{order_id}",
    dependencies=[Depends(require_role(["admin", "client"]))],
    summary="Update Order",
    description="Update order information such as status, items, or customer details. Partial updates are supported.",
    response_description="Updated order object with modified fields.",
)
async def update_order(order_id: str, data: dict, current_user: dict = Depends(get_current_active_user)):
    """
    Update order information.
    
    **Authentication**: Required (admin or restaurant client role)
    
    **Path Parameters**:
    - order_id: Unique identifier of the order to update
    
    **Request Body**: Dictionary with fields to update (e.g., status, items, special instructions)
    
    **Response**: Updated order object.
    """
    return order_service.update_order(order_id, data)


# DELETE
@router.delete(
    "/{order_id}",
    dependencies=[Depends(require_role(["admin"]))],
    summary="Delete Order",
    description="Permanently delete an order from the system. Admin access only. This action cannot be undone.",
    response_description="Confirmation message or deleted order details.",
)
async def delete_order(order_id: str, current_user: dict = Depends(get_current_active_user)):
    """
    Delete an order from the system.
    
    **Authentication**: Required (admin role only)
    
    **Path Parameters**:
    - order_id: Unique identifier of the order to delete
    
    **Warning**: This action is permanent and cannot be undone.
    
    **Response**: Confirmation of deletion.
    """
    return order_service.delete_order(order_id)
