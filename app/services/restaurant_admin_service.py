import logging
import threading
import uuid
from typing import Any, Dict, List, Optional

from fastapi import HTTPException, status

from app.repositories.mysql_restaurant_admin_repo import MySQLRestaurantAdminRepository
from app.repositories.mysql_restaurant_repo import MySQLRestaurantRepository
from app.services.admin_user_common import (
    build_pagination,
    enforce_reset_rate_limit,
    hash_password,
    validate_email,
    validate_password,
    validate_uuid,
)


class RestaurantAdministratorService:
    """Business logic for managing restaurant client CRM users (admins/staff)."""

    PASSWORD_RESET_MAX_ATTEMPTS = 5
    PASSWORD_RESET_WINDOW_SECONDS = 60
    _password_reset_buckets: dict[str, List[float]] = {}
    _password_reset_lock = threading.Lock()

    def __init__(
        self,
        admin_repo: Optional[MySQLRestaurantAdminRepository] = None,
        restaurant_repo: Optional[MySQLRestaurantRepository] = None,
    ):
        self.admin_repo = admin_repo or MySQLRestaurantAdminRepository()
        self.restaurant_repo = restaurant_repo or MySQLRestaurantRepository()
        self.logger = logging.getLogger(__name__)

    def _require_restaurant(self, restaurant_id: int) -> Dict[str, Any]:
        restaurant = self.restaurant_repo.get_by_id(int(restaurant_id))
        if not restaurant:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Restaurant not found")
        return restaurant

    def _require_role(self, role_id: Optional[int]) -> Dict[str, Any]:
        if role_id is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="role_id is required")
        role = self.admin_repo.get_role_with_permissions(int(role_id))
        if not role:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Role not found")
        return role

    def _serialize_client_user(self, record: Dict[str, Any]) -> Dict[str, Any]:
        if not record:
            return {}
        return {
            "uuid": record.get("uuid"),
            "restaurant_id": record.get("restaurant_id"),
            "restaurant_name": record.get("restaurant_name"),
            "email": record.get("email"),
            "role_id": record.get("role_id"),
            "role": record.get("role_name"),
            "permissions": record.get("permissions", []),
            "created_at": record.get("created_at"),
            "updated_at": record.get("updated_at"),
            "last_login": record.get("last_login"),
            "last_active": record.get("last_active"),
        }

    @staticmethod
    def _ensure_restaurant_match(admin: Dict[str, Any], restaurant_id: Optional[int]):
        if restaurant_id is None or not admin:
            return
        admin_rest_id = admin.get("restaurant_id")
        if admin_rest_id is None:
            return
        if int(admin_rest_id) != int(restaurant_id):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found for restaurant")

    # --------- Core operations ---------
    def create_client_user(self, restaurant_id: int, email: str, password: str, role_id: int) -> Dict[str, Any]:
        self._require_restaurant(restaurant_id)
        self._require_role(role_id)

        normalized_email = validate_email(email)
        validate_password(password)

        existing = self.admin_repo.get_client_user_by_restaurant_and_email(restaurant_id, normalized_email)
        if existing:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already exists for restaurant")

        admin_uuid = str(uuid.uuid4())
        password_hash = hash_password(password)

        try:
            created = self.admin_repo.create_client_user(
                admin_uuid, restaurant_id, normalized_email, password_hash, int(role_id)
            )
        except Exception:
            self.logger.exception("Failed to create client user for restaurant_id=%s", restaurant_id)
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to create user")

        if not created:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to create user")
        return self._serialize_client_user(created)

    def list_client_users_for_restaurant(
        self, restaurant_id: int, page: int = 1, limit: int = 20, role_id: Optional[int] = None
    ) -> Dict[str, Any]:
        self._require_restaurant(restaurant_id)
        if page < 1 or limit < 1:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="page and limit must be positive")
        items, total = self.admin_repo.list_client_users_by_restaurant(restaurant_id, page, limit, role_id)
        return {
            "items": [self._serialize_client_user(item) for item in items],
            "pagination": build_pagination(page, limit, total),
        }

    def get_client_user(self, restaurant_id: int, admin_uuid: str) -> Dict[str, Any]:
        admin_uuid = validate_uuid(admin_uuid)
        admin = self.admin_repo.get_client_user_by_uuid(admin_uuid)
        if not admin:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
        self._ensure_restaurant_match(admin, restaurant_id)
        return self._serialize_client_user(admin)

    def update_client_user(self, restaurant_id: int, admin_uuid: str, updates: Dict[str, Any]) -> Dict[str, Any]:
        admin_uuid = validate_uuid(admin_uuid)
        current = self.admin_repo.get_client_user_by_uuid(admin_uuid)
        if not current:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
        self._ensure_restaurant_match(current, restaurant_id)

        update_fields: Dict[str, Any] = {}

        if "email" in updates:
            normalized_email = validate_email(updates.get("email"), required=False)
            if normalized_email:
                existing = self.admin_repo.get_client_user_by_restaurant_and_email(
                    int(current.get("restaurant_id")), normalized_email
                )
                if existing and existing.get("uuid") != admin_uuid:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST, detail="Email already exists for restaurant"
                    )
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

        updated = self.admin_repo.update_client_user(admin_uuid, update_fields)
        if not updated:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
        self._ensure_restaurant_match(updated, restaurant_id)
        return self._serialize_client_user(updated)

    def delete_client_user(self, restaurant_id: int, admin_uuid: str) -> Dict[str, str]:
        admin_uuid = validate_uuid(admin_uuid)
        current = self.admin_repo.get_client_user_by_uuid(admin_uuid)
        if not current:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
        self._ensure_restaurant_match(current, restaurant_id)

        restaurant_id = int(current.get("restaurant_id")) if current.get("restaurant_id") else None
        if restaurant_id is not None:
            total = self.admin_repo.count_client_users_by_restaurant(restaurant_id)
            if total <= 1:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Cannot delete the last user for this restaurant",
                )

        deleted = self.admin_repo.delete_client_user(admin_uuid)
        if not deleted:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
        self.admin_repo.revoke_sessions_for_user(admin_uuid)
        return {"message": "User deleted"}

    def reset_client_user_password(self, restaurant_id: int, admin_uuid: str, new_password: str) -> Dict[str, str]:
        admin_uuid = validate_uuid(admin_uuid)
        enforce_reset_rate_limit(
            admin_uuid,
            self._password_reset_buckets,
            self._password_reset_lock,
            self.PASSWORD_RESET_MAX_ATTEMPTS,
            self.PASSWORD_RESET_WINDOW_SECONDS,
        )
        current = self.admin_repo.get_client_user_by_uuid(admin_uuid)
        if not current:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
        self._ensure_restaurant_match(current, restaurant_id)

        password = validate_password(new_password)
        hashed = hash_password(password)
        updated = self.admin_repo.update_client_user_password(admin_uuid, hashed)
        if not updated:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to update password")
        self.admin_repo.revoke_sessions_for_user(admin_uuid)
        return {"message": "Password reset successful"}

    def update_client_user_role(self, restaurant_id: int, admin_uuid: str, role_id: int) -> Dict[str, Any]:
        admin_uuid = validate_uuid(admin_uuid)
        current = self.admin_repo.get_client_user_by_uuid(admin_uuid)
        if not current:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
        self._ensure_restaurant_match(current, restaurant_id)
        self._require_role(role_id)
        updated = self.admin_repo.update_client_user_role(admin_uuid, int(role_id))
        if not updated:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
        refreshed = self.admin_repo.get_client_user_by_uuid(admin_uuid)
        if not refreshed:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
        self._ensure_restaurant_match(refreshed, restaurant_id)
        return self._serialize_client_user(refreshed)

    def bulk_create_client_users(self, restaurant_id: int, admins: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        self._require_restaurant(restaurant_id)
        if not admins:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="client users list cannot be empty")

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

            existing = self.admin_repo.get_client_user_by_restaurant_and_email(restaurant_id, email)
            if existing:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST, detail=f"Email {email} already exists for restaurant"
                )

            prepared.append(
                {
                    "uuid": str(uuid.uuid4()),
                    "email": email,
                    "password": hash_password(password),
                    "role_id": int(role_id),
                }
            )

        try:
            created = self.admin_repo.bulk_create_client_users(restaurant_id, prepared)
        except Exception:
            self.logger.exception("Bulk create client users failed for restaurant_id=%s", restaurant_id)
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to create users")

        return [self._serialize_client_user(item) for item in created]
