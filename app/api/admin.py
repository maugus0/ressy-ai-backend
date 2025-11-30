from fastapi import APIRouter, Depends

from app.middleware.auth_middleware import get_current_admin_user
from app.services.admin_service import AdminService

router = APIRouter()
admin_service = AdminService()


@router.get("/users")
async def get_all_users(current_user: dict = Depends(get_current_admin_user)):
    return admin_service.get_all_users()
