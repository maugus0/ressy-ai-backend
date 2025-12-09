from fastapi import APIRouter, Depends

from app.middleware.auth_middleware import get_current_admin_user
from app.services.admin_service import AdminService

router = APIRouter()
admin_service = AdminService()


@router.get(
    "/users",
    summary="Get All Users",
    description="Retrieve all users in the system including admin and restaurant users. Admin access only. Returns complete user information with roles and permissions.",
    response_description="List of all users with their details, roles, and permissions.",
)
async def get_all_users(current_user: dict = Depends(get_current_admin_user)):
    """
    Get all users in the system.
    
    **Authentication**: Required (admin role only)
    
    **Response**: List of all users including:
    - User IDs, emails, roles
    - Permissions and restaurant associations
    - Account status and creation dates
    """
    return admin_service.get_all_users()
