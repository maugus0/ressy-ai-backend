from fastapi import APIRouter, Depends
from app.middleware.auth_middleware import get_current_active_user, require_role
from app.services.order_service import OrderService

router = APIRouter()
order_service = OrderService()


# CREATE
@router.post("/{restaurant_id}", dependencies=[Depends(require_role(["admin", "client"]))])
async def create_order(restaurant_id: str, data: dict, current_user: dict = Depends(get_current_active_user)):
    return order_service.create_order(restaurant_id, data)

# READ ALL
@router.get("/{restaurant_id}", dependencies=[Depends(require_role(["admin", "client"]))])
async def list_orders(restaurant_id: str, current_user: dict = Depends(get_current_active_user)):
    return order_service.list_orders(restaurant_id)

# READ ONE
@router.get("/details/{order_id}", dependencies=[Depends(require_role(["admin", "client"]))] )
async def get_order(order_id: str, current_user: dict = Depends(get_current_active_user)):
    return order_service.get_order(order_id)

# UPDATE
@router.put("/{order_id}", dependencies=[Depends(require_role(["admin", "client"]))])
async def update_order(order_id: str, data: dict, current_user: dict = Depends(get_current_active_user)):
    return order_service.update_order(order_id, data)

# DELETE
@router.delete("/{order_id}", dependencies=[Depends(require_role(["admin"]))])
async def delete_order(order_id: str, current_user: dict = Depends(get_current_active_user)):
    return order_service.delete_order(order_id)

