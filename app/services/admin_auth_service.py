"""
Admin Authentication Service for Ressy Administrators.
"""

from datetime import datetime, timedelta
from typing import Dict, Optional

import bcrypt
import jwt
from fastapi import HTTPException

from app.config import settings
from app.repositories.mysql_admin_repo import MySQLAdminRepository


class AdminAuthService:
    """Service for admin authentication operations."""

    def __init__(self):
        self.admin_repo = MySQLAdminRepository()

    def authenticate_admin(self, email: str, password: str) -> Optional[Dict]:
        """
        Authenticate admin user with email and password.
        Returns admin data if authentication succeeds, None otherwise.
        """
        admin = self.admin_repo.get_by_email(email)
        if not admin:
            return None

        # Verify password
        try:
            password_match = bcrypt.checkpw(password.encode("utf-8"), admin["password"].encode("utf-8"))
            if not password_match:
                return None
        except Exception as e:
            print(f"[AdminAuth] Password verification error: {e}")
            return None

        # Return admin data without password
        admin_data = {
            "uuid": admin["uuid"],
            "email": admin["email"],
            "role_id": admin["role_id"],
            "role": admin["role"],
            "permission_id": admin["permission_id"],
            "routes": admin.get("routes", []),
        }
        return admin_data

    def generate_token(self, admin_data: Dict) -> str:
        """
        Generate JWT token for admin user.
        """
        now = datetime.utcnow()
        payload = {
            "sub": admin_data["uuid"],
            "email": admin_data["email"],
            "role": admin_data["role"],
            "role_id": admin_data["role_id"],
            "permission_id": admin_data["permission_id"],
            "routes": admin_data.get("routes", []),
            "type": "admin",
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(hours=settings.JWT_EXPIRE_HOURS)).timestamp()),
        }

        token = jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
        # Ensure token is a string (PyJWT may return bytes in some versions)
        if isinstance(token, bytes):
            return token.decode("utf-8")
        return token

    def verify_token(self, token: str) -> Dict:
        """
        Verify JWT token and return payload.
        """
        try:
            payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])

            # Verify token type
            if payload.get("type") != "admin":
                raise HTTPException(status_code=401, detail="Invalid token type")

            # Verify admin still exists
            admin = self.admin_repo.get_by_uuid(payload.get("sub"))
            if not admin:
                raise HTTPException(status_code=401, detail="Admin not found")

            # Return updated payload with current admin data
            return {
                "uuid": admin["uuid"],
                "email": admin["email"],
                "role": admin["role"],
                "role_id": admin["role_id"],
                "permission_id": admin["permission_id"],
                "routes": admin.get("routes", []),
                "type": "admin",
            }
        except jwt.ExpiredSignatureError:
            raise HTTPException(status_code=401, detail="Token expired")
        except jwt.InvalidTokenError as e:
            raise HTTPException(status_code=401, detail=f"Invalid token: {str(e)}")

    def check_permission(self, admin_data: Dict, route: str) -> bool:
        """
        Check if admin has permission to access a route.
        """
        import re

        routes = admin_data.get("routes", [])
        if not routes:
            return False

        # Check if route matches any permission route
        # Support exact match and wildcard patterns
        for permission_route in routes:
            if permission_route == route:
                return True
            # Support wildcard patterns like "/api/v1/admin/*"
            if "*" in permission_route:
                pattern = permission_route.replace("*", ".*")
                if re.match(pattern, route):
                    return True

        return False
