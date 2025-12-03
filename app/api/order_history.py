from fastapi import APIRouter, Depends

from app.middleware.auth_middleware import get_current_active_user, require_role
from app.services.order_service import OrderService

router = APIRouter()
order_service = OrderService()


@router.get("/{order_id}/history", dependencies=[Depends(require_role(["admin", "client"]))])
async def get_order_history(order_id: str, current_user: dict = Depends(get_current_active_user)):
    return order_service.get_order_history(order_id)
