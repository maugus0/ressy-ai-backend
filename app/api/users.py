from fastapi import APIRouter, Depends

from app.middleware.auth_middleware import get_current_active_user, require_role
from app.services.user_service import UserService

router = APIRouter()
user_service = UserService()


# CREATE
@router.post("/", dependencies=[Depends(require_role(["admin"]))])
async def create_user(data: dict, current_user: dict = Depends(get_current_active_user)):
    return user_service.create_user(data)


# READ ALL
@router.get("/{restaurant_id}", dependencies=[Depends(require_role(["admin"]))])
async def list_users(restaurant_id: str, current_user: dict = Depends(get_current_active_user)):
    return user_service.list_users()


# UPDATE
@router.put("/{user_id}", dependencies=[Depends(require_role(["admin"]))])
async def update_user(user_id: str, data: dict, current_user: dict = Depends(get_current_active_user)):
    return user_service.update_user(user_id, data)


# DELETE
@router.delete("/{user_id}", dependencies=[Depends(require_role(["admin"]))])
async def delete_user(user_id: str, current_user: dict = Depends(get_current_active_user)):
    return user_service.delete_user(user_id)
