"""
Admin Middleware for JWT authentication and permission checking.
"""

from fastapi import HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Dict
from app.services.admin_auth_service import AdminAuthService

security = HTTPBearer()
auth_service = AdminAuthService()


def get_current_admin(credentials: HTTPAuthorizationCredentials = Depends(security)) -> Dict:
    """
    Get current admin from JWT token.
    Validates token and returns admin data.
    """
    token = credentials.credentials
    admin_data = auth_service.verify_token(token)
    return admin_data


def require_admin_role(roles: list[str]):
    """
    Require specific role(s) for access.
    """

    def role_checker(admin_data: Dict = Depends(get_current_admin)):
        if not admin_data or admin_data.get("type") != "admin":
            raise HTTPException(status_code=401, detail="Not authenticated as admin")

        admin_role = admin_data.get("role")
        if admin_role not in roles:
            raise HTTPException(status_code=403, detail="Not authorized - insufficient role")

        return admin_data

    return role_checker


def require_admin_permission(route: str):
    """
    Require specific route permission.
    """

    def permission_checker(admin_data: Dict = Depends(get_current_admin)):
        if not admin_data or admin_data.get("type") != "admin":
            raise HTTPException(status_code=401, detail="Not authenticated as admin")

        has_permission = auth_service.check_permission(admin_data, route)
        if not has_permission:
            raise HTTPException(status_code=403, detail="Not authorized - insufficient permissions")

        return admin_data

    return permission_checker
