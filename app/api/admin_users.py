from datetime import datetime

from fastapi import APIRouter, Body, Depends, Query, status
from pydantic import BaseModel, ConfigDict, Field

from app.middleware.auth_middleware import get_current_admin_user
from app.models.common_models import PaginationResponse
from app.models.user_models import (
    BaseBulkCreateRequest,
    BasePasswordResetRequest,
    BaseRoleUpdateRequest,
    BaseUserCreateRequest,
    BaseUserUpdateRequest,
)
from app.services.ressy_admin_service import RessyAdministratorService
from app.utils.payload_validator import validate_payload


class RessyAdminCreateRequest(BaseUserCreateRequest):
    pass


class RessyAdminUpdateRequest(BaseUserUpdateRequest):
    pass


class RessyPasswordResetRequest(BasePasswordResetRequest):
    pass


class RessyRoleUpdateRequest(BaseRoleUpdateRequest):
    pass


class RessyBulkCreateRequest(BaseBulkCreateRequest):
    users: list[RessyAdminCreateRequest]


def get_ressy_admin_service() -> RessyAdministratorService:
    return RessyAdministratorService()


class AdminUserResponse(BaseModel):
    uuid: str
    email: str
    role_id: int | None = None
    role: str | None = None
    permissions: list[str] = Field(default_factory=list)
    created_at: datetime | None = None
    updated_at: datetime | None = None
    last_login: datetime | None = None
    last_active: datetime | None = None
    model_config = ConfigDict(extra="ignore")


class AdminUserListResponse(BaseModel):
    items: list[AdminUserResponse]
    pagination: PaginationResponse
    model_config = ConfigDict(extra="ignore")


router = APIRouter(
    prefix="/api/v1/admin",
    tags=["Admin Users"],
    dependencies=[Depends(get_current_admin_user)],
)


@router.post(
    "/admin-users",
    status_code=status.HTTP_201_CREATED,
    summary="Create Ressy admin user",
    description="Create a new Ressy platform admin user (Admin CRM) with a role and permissions. Admin access only.",
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {
                "application/json": {
                    "schema": RessyAdminCreateRequest.model_json_schema(),
                    "example": {"email": "ops@example.com", "password": "StrongPass1", "role_id": 1},
                }
            },
        }
    },
)
async def create_ressy_admin_user(
    payload: dict | None = Body(None, description="Admin user payload"),
    service: RessyAdministratorService = Depends(get_ressy_admin_service),
):
    """
    Create a new Ressy admin user.

    **Authentication**: Required (Admin CRM)

    **Request Body**:
    - `email` (string, required): Admin email (normalized to lowercase)
    - `password` (string, required): Must include uppercase, lowercase, number, min length 8
    - `role_id` (integer, required): Role from `Crm_roles`

    **Response**: Created admin record including role and permissions.
    """
    data = validate_payload(RessyAdminCreateRequest, payload)
    return service.create_admin_user(data.email, data.password, data.role_id)


@router.get(
    "/admin-users",
    summary="List Ressy admin users",
    description="Get paginated Ressy admin users with role details and last login. Admin access only.",
    response_model=AdminUserListResponse,
    response_description="Paginated admin users with role/permission info.",
    openapi_extra={
        "responses": {
            200: {
                "description": "Admin users list",
                "content": {
                    "application/json": {
                        "example": {
                            "items": [
                                {
                                    "uuid": "e7a2f7c4-1234-4b20-9a89-0f1234567890",
                                    "email": "ops@example.com",
                                    "role_id": 1,
                                    "role": "superadmin",
                                    "permissions": ["/dash", "/users"],
                                    "last_login": "2024-02-01T10:00:00Z",
                                    "last_active": "2024-02-01T10:05:00Z",
                                    "created_at": "2024-01-01T08:00:00Z",
                                    "updated_at": "2024-01-05T09:00:00Z",
                                }
                            ],
                            "pagination": {"page": 1, "limit": 20, "total": 1, "pages": 1},
                        }
                    }
                },
            }
        }
    },
)
async def list_ressy_admin_users(
    page: int = Query(1, description="Page number (1-based)"),
    limit: int = Query(20, description="Items per page"),
    role_id: int | None = Query(None, description="Optional role filter"),
    service: RessyAdministratorService = Depends(get_ressy_admin_service),
):
    """
    List Ressy admin users.

    **Authentication**: Required (Admin CRM)

    **Query Parameters**:
    - `page` (int, default 1): Page number (1-based)
    - `limit` (int, default 20): Items per page
    - `role_id` (int, optional): Filter by role

    **Response**: Paginated list with `items` and `pagination` metadata.
    """
    return service.list_admin_users(page, limit, role_id)


@router.get(
    "/admin-users/{uuid}",
    summary="Get Ressy admin user by UUID",
    description="Fetch a Ressy admin user including role, permissions, and activity timestamps.",
    response_model=AdminUserResponse,
    response_description="Admin user with role and permission details.",
    openapi_extra={
        "responses": {
            200: {
                "description": "Admin user record",
                "content": {
                    "application/json": {
                        "example": {
                            "uuid": "e7a2f7c4-1234-4b20-9a89-0f1234567890",
                            "email": "ops@example.com",
                            "role_id": 1,
                            "role": "superadmin",
                            "permissions": ["/dash", "/users"],
                            "last_login": "2024-02-01T10:00:00Z",
                            "last_active": "2024-02-01T10:05:00Z",
                            "created_at": "2024-01-01T08:00:00Z",
                            "updated_at": "2024-01-05T09:00:00Z",
                        }
                    }
                },
            }
        }
    },
)
async def get_ressy_admin_user(
    uuid: str,
    service: RessyAdministratorService = Depends(get_ressy_admin_service),
):
    """
    Get a specific Ressy admin user.

    **Authentication**: Required (Admin CRM)

    **Path Parameters**:
    - `uuid`: Admin user's UUID

    **Response**: Admin user with role, permissions, and audit timestamps.
    """
    return service.get_admin_user(uuid)


@router.put(
    "/admin-users/{uuid}",
    summary="Update Ressy admin user",
    description="Update a Ressy admin user's email, password, or role. Admin access only.",
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {
                "application/json": {
                    "schema": RessyAdminUpdateRequest.model_json_schema(),
                    "example": {"email": "updated@example.com", "role_id": 3},
                }
            },
        }
    },
)
async def update_ressy_admin_user(
    uuid: str,
    payload: dict | None = Body(None, description="Admin user update payload"),
    service: RessyAdministratorService = Depends(get_ressy_admin_service),
):
    """
    Update a Ressy admin user.

    **Authentication**: Required (Admin CRM)

    **Path Parameters**:
    - `uuid`: Admin user's UUID

    **Request Body**: Any combination of `email`, `password`, or `role_id`.

    **Response**: Updated admin record.
    """
    data = validate_payload(RessyAdminUpdateRequest, payload)
    return service.update_admin_user(uuid, data.model_dump(exclude_unset=True))


@router.delete(
    "/admin-users/{uuid}",
    summary="Delete Ressy admin user",
    description="Delete a Ressy admin user. Prevents deleting the last admin account.",
)
async def delete_ressy_admin_user(
    uuid: str,
    service: RessyAdministratorService = Depends(get_ressy_admin_service),
):
    """
    Delete a Ressy admin user.

    **Authentication**: Required (Admin CRM)

    **Path Parameters**:
    - `uuid`: Admin user's UUID

    **Behavior**:
    - Fails with 400 if attempting to delete the final admin account
    - Revokes active sessions for the deleted user

    **Response**: `{"message": "User deleted"}` on success.
    """
    return service.delete_admin_user(uuid)


@router.post(
    "/admin-users/{uuid}/reset-password",
    summary="Reset Ressy admin password",
    description="Reset password, hash with bcrypt, revoke sessions, and apply rate limiting.",
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {
                "application/json": {
                    "schema": RessyPasswordResetRequest.model_json_schema(),
                    "example": {"new_password": "NewStrongPass1"},
                }
            },
        }
    },
)
async def reset_ressy_admin_password(
    uuid: str,
    payload: dict | None = Body(None, description="Payload with new_password"),
    service: RessyAdministratorService = Depends(get_ressy_admin_service),
):
    """
    Reset a Ressy admin password.

    **Authentication**: Required (Admin CRM)

    **Path Parameters**:
    - `uuid`: Admin user's UUID

    **Request Body**:
    - `new_password`: New password that meets complexity requirements

    **Rate Limit**: 5 requests per minute per user (429 on breach).

    **Response**: `{"message": "Password reset successful"}`.
    """
    data = validate_payload(RessyPasswordResetRequest, payload)
    return service.reset_admin_user_password(uuid, data.new_password)


@router.patch(
    "/admin-users/{uuid}/role",
    summary="Update Ressy admin role",
    description="Update the role_id for a Ressy admin user and return the updated record.",
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {
                "application/json": {
                    "schema": RessyRoleUpdateRequest.model_json_schema(),
                    "example": {"role_id": 2},
                }
            },
        }
    },
)
async def update_ressy_admin_role(
    uuid: str,
    payload: dict | None = Body(None, description="Payload with role_id"),
    service: RessyAdministratorService = Depends(get_ressy_admin_service),
):
    """
    Update a Ressy admin role.

    **Authentication**: Required (Admin CRM)

    **Path Parameters**:
    - `uuid`: Admin user's UUID

    **Request Body**:
    - `role_id` (int, required): Role to assign

    **Response**: Updated admin record.
    """
    data = validate_payload(RessyRoleUpdateRequest, payload)
    return service.update_admin_user_role(uuid, data.role_id)


@router.post(
    "/admin-users/bulk",
    status_code=status.HTTP_201_CREATED,
    summary="Bulk create Ressy admin users",
    description="Create multiple Ressy admin users in one transaction. Rejects duplicates and existing emails.",
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {
                "application/json": {
                    "schema": RessyBulkCreateRequest.model_json_schema(),
                    "example": {
                        "users": [
                            {"email": "ops1@example.com", "password": "StrongPass1", "role_id": 1},
                            {"email": "ops2@example.com", "password": "AnotherPass2", "role_id": 2},
                        ]
                    },
                }
            },
        }
    },
)
async def bulk_create_ressy_admin_users(
    payload: dict | None = Body(None, description="Payload with admin users array"),
    service: RessyAdministratorService = Depends(get_ressy_admin_service),
):
    """
    Bulk create Ressy admin users.

    **Authentication**: Required (Admin CRM)

    **Request Body**:
    - `users` (array): List of admin user objects (`email`, `password`, `role_id`)

    **Validation**:
    - Rejects duplicate emails in payload
    - Rejects emails that already exist in the database

    **Response**: `{"items": [...]}` containing created users.
    """
    data = validate_payload(RessyBulkCreateRequest, payload)
    created = service.bulk_create_admin_users([admin.model_dump() for admin in data.users])
    return {"items": created}
