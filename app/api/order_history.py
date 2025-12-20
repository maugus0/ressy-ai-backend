"""
Legacy Order History API endpoint.

⚠️ DEPRECATED: This endpoint is deprecated and will be removed in a future version.
Please use the Activity History API endpoints at /api/v1/dashboard/orders/{order_id}/history instead.
"""

from fastapi import APIRouter, Depends

from app.middleware.auth_middleware import get_current_active_user, require_role
from app.services.order_service import OrderService

router = APIRouter()
order_service = OrderService()


@router.get(
    "/{order_id}/history",
    dependencies=[Depends(require_role(["admin", "client"]))],
    summary="[DEPRECATED] Get Order History",
    description="""
⚠️ **DEPRECATED**: This endpoint is deprecated. Please use `/api/v1/dashboard/orders/{order_id}/history` instead.

Retrieve the complete history and status changes for a specific order.
Includes all state transitions and updates.

**Note**: The new endpoint provides more detailed history with user information and change summaries.
""",
    response_description="Order history with all status changes and updates in chronological order.",
    deprecated=True,
)
async def get_order_history(order_id: str, current_user: dict = Depends(get_current_active_user)):
    """
    [DEPRECATED] Get the complete history for a specific order.

    ⚠️ Please use GET /api/v1/dashboard/orders/{order_id}/history instead.

    **Authentication**: Required (admin or restaurant client role)

    **Path Parameters**:
    - order_id: Unique identifier of the order

    **Response**: Order history with all status changes, updates, and timestamps.
    """
    return order_service.get_order_history(order_id)
