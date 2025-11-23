from fastapi import APIRouter, Depends

from app.middleware.auth_middleware import get_current_active_user, require_role
from app.services.restaurant_service import RestaurantService

router = APIRouter()
restaurant_service = RestaurantService()


# ---------- CREATE ----------
@router.post("/", dependencies=[Depends(require_role(["admin"]))], summary="Create a new restaurant (Admin only)")
async def create_restaurant(data: dict, current_user: dict = Depends(get_current_active_user)):
    return restaurant_service.create_restaurant(data)


# ---------- READ ALL ----------
@router.get("/", dependencies=[Depends(require_role(["admin"]))], summary="List all restaurants (Admin only)")
async def list_restaurants(current_user: dict = Depends(get_current_active_user)):
    return restaurant_service.list_restaurants()


# ---------- READ ONE ----------
@router.get(
    "/{restaurant_id}", dependencies=[Depends(require_role(["admin"]))], summary="Get restaurant details (Admin only)"
)
async def get_restaurant(restaurant_id: str, current_user: dict = Depends(get_current_active_user)):
    return restaurant_service.get_restaurant(restaurant_id)


# ---------- UPDATE ----------
@router.put(
    "/{restaurant_id}", dependencies=[Depends(require_role(["admin"]))], summary="Update restaurant info (Admin only)"
)
async def update_restaurant(restaurant_id: str, data: dict, current_user: dict = Depends(get_current_active_user)):
    return restaurant_service.update_restaurant(restaurant_id, data)


# ---------- DELETE ----------
@router.delete(
    "/{restaurant_id}", dependencies=[Depends(require_role(["admin"]))], summary="Delete restaurant (Admin only)"
)
async def delete_restaurant(restaurant_id: str, current_user: dict = Depends(get_current_active_user)):
    return restaurant_service.delete_restaurant(restaurant_id)
