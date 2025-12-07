from fastapi import APIRouter, Body, Depends, Query, status

from app.middleware.auth_middleware import get_current_admin_user
from app.models.user_models import (
    BaseBulkCreateRequest,
    BasePasswordResetRequest,
    BaseRoleUpdateRequest,
    BaseUserCreateRequest,
    BaseUserUpdateRequest,
)
from app.services.restaurant_admin_service import RestaurantAdministratorService
from app.utils.payload_validator import validate_payload


class ClientUserCreateRequest(BaseUserCreateRequest):
    pass


class ClientUserUpdateRequest(BaseUserUpdateRequest):
    pass


class ClientPasswordResetRequest(BasePasswordResetRequest):
    pass


class ClientRoleUpdateRequest(BaseRoleUpdateRequest):
    pass


class ClientBulkCreateRequest(BaseBulkCreateRequest):
    users: list[ClientUserCreateRequest]


def get_restaurant_admin_service() -> RestaurantAdministratorService:
    return RestaurantAdministratorService()


router = APIRouter(
    prefix="/api/v1/admin",
    tags=["Client Users"],
    dependencies=[Depends(get_current_admin_user)],
)


@router.post(
    "/restaurants/{restaurant_id}/client-users",
    status_code=status.HTTP_201_CREATED,
    summary="Create client user",
    description="Create a new client CRM user (restaurant admin/staff). Admin access only.",
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {
                "application/json": {
                    "schema": ClientUserCreateRequest.model_json_schema(),
                    "example": {"email": "manager@example.com", "password": "StrongPass1", "role_id": 2},
                }
            },
        }
    },
)
async def create_client_user(
    restaurant_id: int,
    payload: dict | None = Body(None, description="Client user payload"),
    service: RestaurantAdministratorService = Depends(get_restaurant_admin_service),
):
    """
    Create a new client CRM user for a restaurant.

    **Authentication**: Required (Admin CRM)

    **Path Parameters**:
    - `restaurant_id`: Restaurant ID to associate the user with

    **Request Body**:
    - `email` (required): User email (normalized to lowercase)
    - `password` (required): Must include uppercase, lowercase, number, min length 8
    - `role_id` (required): Role from `Crm_roles`

    **Response**: Created client-user record including role and permissions.
    """
    data = validate_payload(ClientUserCreateRequest, payload)
    return service.create_client_user(restaurant_id, data.email, data.password, data.role_id)


@router.get(
    "/restaurants/{restaurant_id}/client-users",
    summary="List client users for restaurant",
    description="Get paginated client users with role details and last login. Admin access only.",
)
async def list_client_users_for_restaurant(
    restaurant_id: int,
    page: int = Query(1, description="Page number (1-based)"),
    limit: int = Query(20, description="Items per page"),
    role_id: int | None = Query(None, description="Optional role filter"),
    service: RestaurantAdministratorService = Depends(get_restaurant_admin_service),
):
    """
    List client CRM users for a restaurant.

    **Authentication**: Required (Admin CRM)

    **Query Parameters**:
    - `page` (int, default 1): Page number (1-based)
    - `limit` (int, default 20): Items per page
    - `role_id` (int, optional): Filter by role

    **Response**: Paginated list with `items` and `pagination`.
    """
    return service.list_client_users_for_restaurant(restaurant_id, page, limit, role_id)


@router.get(
    "/restaurants/{restaurant_id}/client-users/{uuid}",
    summary="Get client user by UUID",
    description="Fetch a client user including restaurant, role, permissions, and activity timestamps.",
)
async def get_client_user(
    restaurant_id: int,
    uuid: str,
    service: RestaurantAdministratorService = Depends(get_restaurant_admin_service),
):
    """
    Get a specific client CRM user by UUID.

    **Authentication**: Required (Admin CRM)

    **Path Parameters**:
    - `restaurant_id`: Restaurant ID
    - `uuid`: Client user's UUID

    **Response**: Client user with restaurant, role, permissions, and timestamps.
    """
    return service.get_client_user(restaurant_id, uuid)


@router.put(
    "/restaurants/{restaurant_id}/client-users/{uuid}",
    summary="Update client user",
    description="Update a client user's email, password, or role. Admin access only.",
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {
                "application/json": {
                    "schema": ClientUserUpdateRequest.model_json_schema(),
                    "example": {"email": "updated@example.com", "role_id": 3},
                }
            },
        }
    },
)
async def update_client_user(
    restaurant_id: int,
    uuid: str,
    payload: dict | None = Body(None, description="Client user update payload"),
    service: RestaurantAdministratorService = Depends(get_restaurant_admin_service),
):
    """
    Update a client CRM user.

    **Authentication**: Required (Admin CRM)

    **Path Parameters**:
    - `restaurant_id`: Restaurant ID
    - `uuid`: Client user's UUID

    **Request Body**: Any combination of `email`, `password`, or `role_id`.

    **Response**: Updated client user record.
    """
    data = validate_payload(ClientUserUpdateRequest, payload)
    return service.update_client_user(restaurant_id, uuid, data.model_dump(exclude_unset=True))


@router.delete(
    "/restaurants/{restaurant_id}/client-users/{uuid}",
    summary="Delete client user",
    description="Delete a client user. Prevents deleting the last user for a restaurant.",
)
async def delete_client_user(
    restaurant_id: int,
    uuid: str,
    service: RestaurantAdministratorService = Depends(get_restaurant_admin_service),
):
    """
    Delete a client CRM user.

    **Authentication**: Required (Admin CRM)

    **Path Parameters**:
    - `restaurant_id`: Restaurant ID
    - `uuid`: Client user's UUID

    **Behavior**:
    - Prevents deleting the final user for a restaurant
    - Revokes active sessions for the deleted user

    **Response**: `{"message": "User deleted"}` on success.
    """
    return service.delete_client_user(restaurant_id, uuid)


@router.post(
    "/restaurants/{restaurant_id}/client-users/{uuid}/reset-password",
    summary="Reset client user password",
    description="Reset password, hash with bcrypt, revoke sessions, and apply rate limiting.",
)
async def reset_client_user_password(
    restaurant_id: int,
    uuid: str,
    payload: dict | None = Body(None, description="Payload with new_password"),
    service: RestaurantAdministratorService = Depends(get_restaurant_admin_service),
):
    """
    Reset a client CRM user's password.

    **Authentication**: Required (Admin CRM)

    **Path Parameters**:
    - `restaurant_id`: Restaurant ID
    - `uuid`: Client user's UUID

    **Request Body**:
    - `new_password`: New password that meets complexity requirements

    **Rate Limit**: 5 requests per minute per user (429 on breach).

    **Response**: `{"message": "Password reset successful"}`.
    """
    data = validate_payload(ClientPasswordResetRequest, payload)
    return service.reset_client_user_password(restaurant_id, uuid, data.new_password)


@router.patch(
    "/restaurants/{restaurant_id}/client-users/{uuid}/role",
    summary="Update client user role",
    description="Update the role_id for a client user and return the updated record.",
)
async def update_client_user_role(
    restaurant_id: int,
    uuid: str,
    payload: dict | None = Body(None, description="Payload with role_id"),
    service: RestaurantAdministratorService = Depends(get_restaurant_admin_service),
):
    """
    Update a client CRM user's role.

    **Authentication**: Required (Admin CRM)

    **Path Parameters**:
    - `restaurant_id`: Restaurant ID
    - `uuid`: Client user's UUID

    **Request Body**:
    - `role_id` (int, required): Role to assign

    **Response**: Updated client user record.
    """
    data = validate_payload(ClientRoleUpdateRequest, payload)
    return service.update_client_user_role(restaurant_id, uuid, data.role_id)


@router.post(
    "/restaurants/{restaurant_id}/client-users/bulk",
    status_code=status.HTTP_201_CREATED,
    summary="Bulk create client users",
    description="Create multiple client users for a restaurant in one transaction.",
)
async def bulk_create_client_users(
    restaurant_id: int,
    payload: dict | None = Body(None, description="Payload with client users array"),
    service: RestaurantAdministratorService = Depends(get_restaurant_admin_service),
):
    """
    Bulk create client CRM users for a restaurant.

    **Authentication**: Required (Admin CRM)

    **Path Parameters**:
    - `restaurant_id`: Restaurant ID

    **Request Body**:
    - `users` (array): List of users (`email`, `password`, `role_id`)

    **Validation**:
    - Rejects duplicate emails in payload
    - Rejects emails that already exist for the restaurant

    **Response**: `{"items": [...]}` containing created users.
    """
    data = validate_payload(ClientBulkCreateRequest, payload)
    created = service.bulk_create_client_users(restaurant_id, [admin.model_dump() for admin in data.users])
    return {"items": created}
