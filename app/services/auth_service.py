import secrets
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import bcrypt
from fastapi import HTTPException, status

from app.repositories.mysql_auth_repo import MySQLAuthRepository
from app.utils.jwt_util import JWTUtil


class AuthService:
    """Authentication service providing login, refresh, and logout with session management."""

    def __init__(self, auth_repo: Optional[MySQLAuthRepository] = None, jwt_util: Optional[JWTUtil] = None):
        self.auth_repo = auth_repo or MySQLAuthRepository()
        self.jwt_util = jwt_util or JWTUtil()

    def login_ressy_admin(
        self, email: str, password: str, user_agent: Optional[str], ip_address: Optional[str]
    ) -> Dict[str, Any]:
        admin = self.auth_repo.get_admin_by_email(email)
        if not admin or not self._verify_password(password, admin.get("password")):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")

        self._ensure_active_user(admin)

        role_info = self._get_role_info(admin.get("role_id"))
        user_context = {
            "uuid": admin["uuid"],
            "email": admin["email"],
            "role": role_info.get("role"),
            "permissions": role_info.get("permissions", []),
        }

        self.auth_repo.update_admin_login_times(admin["uuid"])
        tokens = self._issue_tokens(user_context, "admin", user_agent, ip_address)

        return {
            "uuid": admin["uuid"],
            "email": admin["email"],
            "role": role_info.get("role"),
            "permissions": role_info.get("permissions", []),
            "access_token": tokens["access_token"],
            "refresh_token": tokens["refresh_token"],
            "token_type": "Bearer",
            "expires_in": self.jwt_util.access_ttl_seconds,
            "user_type": "admin",
        }

    def login_restaurant_admin(
        self, email: str, password: str, user_agent: Optional[str], ip_address: Optional[str]
    ) -> Dict[str, Any]:
        restaurant_admin = self.auth_repo.get_restaurant_admin_by_email(email)
        if not restaurant_admin or not self._verify_password(password, restaurant_admin.get("password")):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")

        self._ensure_active_user(restaurant_admin)

        role_info = self._get_role_info(restaurant_admin.get("role_id"))
        restaurant_details = self.auth_repo.get_restaurant_details(int(restaurant_admin["rest_id"]))
        if not restaurant_details:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Restaurant not found")

        user_context = {
            "uuid": restaurant_admin["uuid"],
            "email": restaurant_admin["email"],
            "role": role_info.get("role"),
            "permissions": role_info.get("permissions", []),
            "restaurant_id": restaurant_details.get("id"),
            "restaurant_name": restaurant_details.get("name"),
        }

        self.auth_repo.update_restaurant_admin_login_times(restaurant_admin["uuid"])
        tokens = self._issue_tokens(user_context, "restaurant", user_agent, ip_address)

        return {
            "uuid": restaurant_admin["uuid"],
            "email": restaurant_admin["email"],
            "role": role_info.get("role"),
            "permissions": role_info.get("permissions", []),
            "restaurant_id": restaurant_details.get("id"),
            "restaurant_name": restaurant_details.get("name"),
            "access_token": tokens["access_token"],
            "refresh_token": tokens["refresh_token"],
            "token_type": "Bearer",
            "expires_in": self.jwt_util.access_ttl_seconds,
            "user_type": "restaurant",
        }

    def refresh_tokens(
        self, refresh_token: str, user_agent: Optional[str], ip_address: Optional[str]
    ) -> Dict[str, Any]:
        claims = self.jwt_util.validate_token(refresh_token, self.jwt_util.auth_audience)
        if not self.jwt_util.is_refresh_token(claims):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token type")

        session_id = claims.get("sid")
        user_id = claims.get("sub")
        user_type = claims.get("user_type")
        token_id = claims.get("jti")

        if not session_id or not user_id or not user_type or not token_id:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Malformed refresh token")

        session = self.auth_repo.get_session(session_id)
        if not session or session.get("user_id") != user_id or session.get("user_type") != user_type:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session not found")

        if session.get("revoked"):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session revoked")

        if not self._session_is_active(session.get("expires_at")):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session expired")

        stored_hash = session.get("refresh_token_hash")
        if not stored_hash or not bcrypt.checkpw(token_id.encode("utf-8"), stored_hash.encode("utf-8")):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")

        user_context = self._load_user_context(user_type, user_id)
        new_refresh_id = secrets.token_urlsafe(64)
        new_refresh_hash = bcrypt.hashpw(new_refresh_id.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

        self.auth_repo.update_session_refresh_token(
            session_id, new_refresh_hash, self.jwt_util.refresh_ttl_seconds, user_agent, ip_address
        )
        self.auth_repo.touch_last_active(user_id, user_type)

        access_token = self.jwt_util.generate_access_token(user_context, user_type, session_id=session_id)
        rotated_refresh = self.jwt_util.generate_refresh_token(
            user_context, user_type, session_id=session_id, token_id=new_refresh_id
        )

        return {
            "access_token": access_token,
            "refresh_token": rotated_refresh,
            "token_type": "Bearer",
            "expires_in": self.jwt_util.access_ttl_seconds,
        }

    def logout(self, access_token: str) -> Dict[str, str]:
        claims = self._validate_access_token_any_audience(access_token)
        if claims.get("token_type") != "access":
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid access token")

        session_id = claims.get("sid")
        if session_id:
            self.auth_repo.revoke_session(session_id)

        return {"message": "Logged out successfully"}

    def _issue_tokens(
        self, user_context: Dict[str, Any], user_type: str, user_agent: Optional[str], ip_address: Optional[str]
    ) -> Dict[str, str]:
        session_id = str(uuid.uuid4())
        refresh_token_id = secrets.token_urlsafe(64)
        refresh_hash = bcrypt.hashpw(refresh_token_id.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

        self.auth_repo.create_session(
            session_id,
            user_context["uuid"],
            user_type,
            refresh_hash,
            self.jwt_util.refresh_ttl_seconds,
            user_agent,
            ip_address,
        )

        access_token = self.jwt_util.generate_access_token(user_context, user_type, session_id=session_id)
        refresh_token = self.jwt_util.generate_refresh_token(
            user_context, user_type, session_id=session_id, token_id=refresh_token_id
        )

        return {"access_token": access_token, "refresh_token": refresh_token, "session_id": session_id}

    def _verify_password(self, password: str, hashed_password: Optional[str]) -> bool:
        if not password or not hashed_password:
            return False
        try:
            return bcrypt.checkpw(password.encode("utf-8"), hashed_password.encode("utf-8"))
        except ValueError:
            return False

    def _get_role_info(self, role_id: Optional[int]) -> Dict[str, Any]:
        if role_id is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Role is not assigned")
        role_info = self.auth_repo.get_role_with_permissions(int(role_id))
        if not role_info:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Role not found")
        return role_info

    def _load_user_context(self, user_type: str, user_id: str) -> Dict[str, Any]:
        if user_type == "admin":
            admin = self.auth_repo.get_admin_by_uuid(user_id)
            if not admin:
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
            self._ensure_active_user(admin)
            role_info = self._get_role_info(admin.get("role_id"))
            return {
                "uuid": admin["uuid"],
                "email": admin["email"],
                "role": role_info.get("role"),
                "permissions": role_info.get("permissions", []),
            }
        if user_type == "restaurant":
            restaurant_admin = self.auth_repo.get_restaurant_admin_by_uuid(user_id)
            if not restaurant_admin:
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
            self._ensure_active_user(restaurant_admin)
            role_info = self._get_role_info(restaurant_admin.get("role_id"))
            restaurant_details = self.auth_repo.get_restaurant_details(int(restaurant_admin["rest_id"]))
            if not restaurant_details:
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Restaurant not found")
            return {
                "uuid": restaurant_admin["uuid"],
                "email": restaurant_admin["email"],
                "role": role_info.get("role"),
                "permissions": role_info.get("permissions", []),
                "restaurant_id": restaurant_details.get("id"),
                "restaurant_name": restaurant_details.get("name"),
            }
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid user type")

    def _session_is_active(self, expires_at: Any) -> bool:
        if not expires_at:
            return False
        if isinstance(expires_at, datetime):
            exp_dt = expires_at
        else:
            return False
        if exp_dt.tzinfo is None:
            exp_dt = exp_dt.replace(tzinfo=timezone.utc)
        else:
            exp_dt = exp_dt.astimezone(timezone.utc)
        return exp_dt >= datetime.now(timezone.utc)

    @staticmethod
    def _ensure_active_user(user_record: Dict[str, Any]):
        if user_record.get("is_active") is False or user_record.get("active") is False:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User is disabled")

    def _validate_access_token_any_audience(self, token: str) -> Dict[str, Any]:
        last_error: Optional[HTTPException] = None
        for audience in (self.jwt_util.admin_audience, self.jwt_util.client_audience):
            try:
                return self.jwt_util.validate_token(token, audience)
            except HTTPException as exc:  # noqa: PERF203 small loop
                last_error = exc
        if last_error:
            raise last_error
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
