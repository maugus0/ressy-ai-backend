from fastapi import APIRouter, Depends

from app.middleware.auth_middleware import get_current_active_user, require_role
from app.services.order_service import OrderService

router = APIRouter()
order_service = OrderService()


@router.get(
    "/{order_id}/history",
    dependencies=[Depends(require_role(["admin", "client"]))],
    summary="Get Order History",
    description="Retrieve the complete history and status changes for a specific order. Includes all state transitions and updates.",
    response_description="Order history with all status changes and updates in chronological order.",
)
async def get_order_history(order_id: str, current_user: dict = Depends(get_current_active_user)):
    """
    Get the complete history for a specific order.
    
    **Authentication**: Required (admin or restaurant client role)
    
    **Path Parameters**:
    - order_id: Unique identifier of the order
    
    **Response**: Order history with all status changes, updates, and timestamps.
    """
    return order_service.get_order_history(order_id)
