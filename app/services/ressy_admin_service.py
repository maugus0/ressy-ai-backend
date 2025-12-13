import logging
import threading
import uuid
from typing import Any, Dict, List, Optional

from fastapi import HTTPException, status

from app.repositories.mysql_ressy_admin_repo import MySQLRessyAdminRepository
from app.services.admin_user_common import (
    build_pagination,
    enforce_reset_rate_limit,
    hash_password,
    validate_email,
    validate_password,
    validate_uuid,
)


class RessyAdministratorService:
    """Business logic for managing Ressy platform admin users (Admin CRM users)."""

    PASSWORD_RESET_MAX_ATTEMPTS = 5
    PASSWORD_RESET_WINDOW_SECONDS = 60
    _password_reset_buckets: dict[str, List[float]] = {}
    _password_reset_lock = threading.Lock()

    def __init__(self, admin_repo: Optional[MySQLRessyAdminRepository] = None):
        self.admin_repo = admin_repo or MySQLRessyAdminRepository()
        self.logger = logging.getLogger(__name__)

    def _require_role(self, role_id: Optional[int]) -> Dict[str, Any]:
        if role_id is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="role_id is required")
        role = self.admin_repo.get_role_with_permissions(int(role_id))
        if not role:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Role not found")
        return role

    @staticmethod
    def _serialize_admin_user(record: Dict[str, Any]) -> Dict[str, Any]:
        if not record:
            return {}
        return {
            "uuid": record.get("uuid"),
            "email": record.get("email"),
            "role_id": record.get("role_id"),
            "role": record.get("role_name"),
            "permissions": record.get("permissions", []),
            "created_at": record.get("created_at"),
            "updated_at": record.get("updated_at"),
            "last_login": record.get("last_login"),
            "last_active": record.get("last_active"),
        }

    # --------- Core operations ---------
    def create_admin_user(self, email: str, password: str, role_id: int) -> Dict[str, Any]:
        self._require_role(role_id)

        normalized_email = validate_email(email)
        validate_password(password)

        existing = self.admin_repo.get_admin_by_email(normalized_email)
        if existing:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already exists")

        admin_uuid = str(uuid.uuid4())
        password_hash = hash_password(password)

        try:
            created = self.admin_repo.create_admin_user(admin_uuid, normalized_email, password_hash, int(role_id))
        except Exception:
            self.logger.exception("Failed to create Ressy admin user")
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to create user")

        if not created:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to create user")
        return self._serialize_admin_user(created)

    def list_admin_users(self, page: int = 1, limit: int = 20, role_id: Optional[int] = None) -> Dict[str, Any]:
        if page < 1 or limit < 1:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="page and limit must be positive")
        items, total = self.admin_repo.list_admin_users(page, limit, role_id)
        return {
            "items": [self._serialize_admin_user(item) for item in items],
            "pagination": build_pagination(page, limit, total),
        }

    def get_admin_user(self, admin_uuid: str) -> Dict[str, Any]:
        admin_uuid = validate_uuid(admin_uuid)
        admin = self.admin_repo.get_admin_by_uuid(admin_uuid)
        if not admin:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
        return self._serialize_admin_user(admin)

    def update_admin_user(self, admin_uuid: str, updates: Dict[str, Any]) -> Dict[str, Any]:
        admin_uuid = validate_uuid(admin_uuid)
        current = self.admin_repo.get_admin_by_uuid(admin_uuid)
        if not current:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

        update_fields: Dict[str, Any] = {}

        if "email" in updates:
            normalized_email = validate_email(updates.get("email"), required=False)
            if normalized_email:
                existing = self.admin_repo.get_admin_by_email(normalized_email)
                if existing and existing.get("uuid") != admin_uuid:
                    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already exists")
                update_fields["email"] = normalized_email

        if "password" in updates and updates.get("password") is not None:
            password = validate_password(updates.get("password"), required=False)
            if password:
                update_fields["password"] = hash_password(password)

        if "role_id" in updates and updates.get("role_id") is not None:
            role = self._require_role(int(updates.get("role_id")))
            update_fields["role_id"] = role.get("id")

        if not update_fields:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No valid fields to update")

        updated = self.admin_repo.update_admin_user(admin_uuid, update_fields)
        if not updated:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
        return self._serialize_admin_user(updated)

    def delete_admin_user(self, admin_uuid: str) -> Dict[str, str]:
        admin_uuid = validate_uuid(admin_uuid)
        current = self.admin_repo.get_admin_by_uuid(admin_uuid)
        if not current:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

        total = self.admin_repo.count_admin_users()
        if total <= 1:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot delete the last admin user")

        deleted = self.admin_repo.delete_admin_user(admin_uuid)
        if not deleted:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
        self.admin_repo.revoke_sessions_for_user(admin_uuid)
        return {"message": "User deleted"}

    def reset_admin_user_password(self, admin_uuid: str, new_password: str) -> Dict[str, str]:
        admin_uuid = validate_uuid(admin_uuid)
        enforce_reset_rate_limit(
            admin_uuid,
            self._password_reset_buckets,
            self._password_reset_lock,
            self.PASSWORD_RESET_MAX_ATTEMPTS,
            self.PASSWORD_RESET_WINDOW_SECONDS,
        )
        current = self.admin_repo.get_admin_by_uuid(admin_uuid)
        if not current:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

        password = validate_password(new_password)
        hashed = hash_password(password)
        updated = self.admin_repo.update_admin_user_password(admin_uuid, hashed)
        if not updated:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to update password")
        self.admin_repo.revoke_sessions_for_user(admin_uuid)
        return {"message": "Password reset successful"}

    def update_admin_user_role(self, admin_uuid: str, role_id: int) -> Dict[str, Any]:
        admin_uuid = validate_uuid(admin_uuid)
        current = self.admin_repo.get_admin_by_uuid(admin_uuid)
        if not current:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
        self._require_role(role_id)
        updated = self.admin_repo.update_admin_user_role(admin_uuid, int(role_id))
        if not updated:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
        refreshed = self.admin_repo.get_admin_by_uuid(admin_uuid)
        if not refreshed:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
        return self._serialize_admin_user(refreshed)

    def bulk_create_admin_users(self, admins: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if not admins:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="admin users list cannot be empty")

        seen_emails: set[str] = set()
        prepared: List[Dict[str, Any]] = []
        for admin in admins:
            email = validate_email(admin.get("email"))
            password = validate_password(admin.get("password"))
            role_id = admin.get("role_id")
            self._require_role(role_id)

            if email in seen_emails:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST, detail="Duplicate email in request payload"
                )
            seen_emails.add(email)

            existing = self.admin_repo.get_admin_by_email(email)
            if existing:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Email {email} already exists")

            prepared.append(
                {
                    "uuid": str(uuid.uuid4()),
                    "email": email,
                    "password": hash_password(password),
                    "role_id": int(role_id),
                }
            )

        try:
            created = self.admin_repo.bulk_create_admin_users(prepared)
        except Exception:
            self.logger.exception("Bulk create Ressy admin users failed")
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to create users")

        return [self._serialize_admin_user(item) for item in created]
