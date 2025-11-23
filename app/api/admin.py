from fastapi import APIRouter, Depends, HTTPException

from app.middleware.auth_middleware import get_current_active_user
from app.services.admin_service import AdminService

router = APIRouter()
admin_service = AdminService()


@router.get("/users")
async def get_all_users(current_user: dict = Depends(get_current_active_user)):
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Not authorized")

    return admin_service.get_all_users()
