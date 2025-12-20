from fastapi import APIRouter, Body, Depends, HTTPException, Query, status

from app.api.client_users import (
    ClientBulkCreateRequest,
    ClientPasswordResetRequest,
    ClientRoleUpdateRequest,
    ClientUserCreateRequest,
    ClientUserListResponse,
    ClientUserResponse,
    ClientUserUpdateRequest,
    get_restaurant_admin_service,
)
from app.middleware.auth_middleware import get_current_restaurant_user
from app.services.restaurant_admin_service import RestaurantAdministratorService
from app.utils.payload_validator import validate_payload


def _require_manager(claims: dict) -> None:
    role = (claims.get("role") or "").lower()
    if role != "manager":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Manager role required")


router = APIRouter(
    prefix="/api/v1/client",
    tags=["Client Users"],
    dependencies=[Depends(get_current_restaurant_user)],
)


@router.post(
    "/users",
    status_code=status.HTTP_201_CREATED,
    summary="Create client user (Client)",
    description="Manager-only. Create a new client CRM user for your restaurant.",
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {
                "application/json": {
                    "schema": ClientUserCreateRequest.model_json_schema(),
                    "example": {"email": "staff@example.com", "password": "StrongPass1", "role_id": 2},
                }
            },
        },
        "responses": {
            201: {
                "description": "Client user created",
                "content": {
                    "application/json": {
                        "example": {
                            "uuid": "a1b2",
                            "restaurant_id": 10,
                            "restaurant_name": "Ressy Test Kitchen",
                            "email": "manager@example.com",
                            "role_id": 1,
                            "role": "manager",
                            "permissions": ["/menus"],
                        }
                    }
                },
            }
        },
    },
    response_model=ClientUserResponse,
    response_description="Created client user for the restaurant.",
)
async def create_client_user(
    payload: dict | None = Body(None, description="Client user payload"),
    service: RestaurantAdministratorService = Depends(get_restaurant_admin_service),
    claims: dict = Depends(get_current_restaurant_user),
):
    _require_manager(claims)
    restaurant_id = int(claims["restaurant_id"])
    data = validate_payload(ClientUserCreateRequest, payload)
    return service.create_client_user(restaurant_id, data.email, data.password, data.role_id)


@router.get(
    "/users",
    summary="List client users (Client)",
    description="Manager-only. List client users for your restaurant.",
    response_model=ClientUserListResponse,
    response_description="Paginated client users for the restaurant.",
    openapi_extra={
        "responses": {
            200: {
                "description": "Client users list",
                "content": {
                    "application/json": {
                        "example": {
                            "items": [
                                {
                                    "uuid": "a1b2",
                                    "restaurant_id": 10,
                                    "restaurant_name": "Ressy Test Kitchen",
                                    "email": "manager@example.com",
                                    "role_id": 1,
                                    "role": "manager",
                                    "permissions": ["/menus"],
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
async def list_client_users(
    page: int = Query(1, description="Page number (1-based)"),
    limit: int = Query(20, description="Items per page"),
    role_id: int | None = Query(None, description="Optional role filter"),
    service: RestaurantAdministratorService = Depends(get_restaurant_admin_service),
    claims: dict = Depends(get_current_restaurant_user),
):
    _require_manager(claims)
    restaurant_id = int(claims["restaurant_id"])
    return service.list_client_users_for_restaurant(restaurant_id, page, limit, role_id)


@router.get(
    "/users/{uuid}",
    summary="Get client user by UUID (Client)",
    response_model=ClientUserResponse,
    description="Manager-only. Fetch a client user within your restaurant.",
    response_description="Client user within the restaurant.",
    openapi_extra={
        "responses": {
            200: {
                "description": "Client user retrieved",
                "content": {
                    "application/json": {
                        "example": {
                            "uuid": "a1b2",
                            "restaurant_id": 10,
                            "restaurant_name": "Ressy Test Kitchen",
                            "email": "manager@example.com",
                            "role_id": 1,
                            "role": "manager",
                            "permissions": ["/menus"],
                        }
                    }
                },
            }
        }
    },
)
async def get_client_user(
    uuid: str,
    service: RestaurantAdministratorService = Depends(get_restaurant_admin_service),
    claims: dict = Depends(get_current_restaurant_user),
):
    _require_manager(claims)
    restaurant_id = int(claims["restaurant_id"])
    return service.get_client_user(restaurant_id, uuid)


@router.put(
    "/users/{uuid}",
    summary="Update client user (Client)",
    description="Manager-only. Update a client user within your restaurant.",
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {
                "application/json": {
                    "schema": ClientUserUpdateRequest.model_json_schema(),
                    "example": {"email": "updated@example.com", "role_id": 3},
                }
            },
        },
        "responses": {
            200: {
                "description": "Client user updated",
                "content": {
                    "application/json": {
                        "example": {
                            "uuid": "a1b2",
                            "restaurant_id": 10,
                            "restaurant_name": "Ressy Test Kitchen",
                            "email": "updated@example.com",
                            "role_id": 1,
                            "role": "manager",
                            "permissions": ["/menus"],
                        }
                    }
                },
            }
        },
    },
    response_model=ClientUserResponse,
)
async def update_client_user(
    uuid: str,
    payload: dict | None = Body(None, description="Client user payload"),
    service: RestaurantAdministratorService = Depends(get_restaurant_admin_service),
    claims: dict = Depends(get_current_restaurant_user),
):
    _require_manager(claims)
    restaurant_id = int(claims["restaurant_id"])
    data = validate_payload(ClientUserUpdateRequest, payload)
    return service.update_client_user(restaurant_id, uuid, data.model_dump(exclude_unset=True))


@router.delete(
    "/users/{uuid}",
    summary="Delete client user (Client)",
    description="Manager-only. Delete a client user within your restaurant.",
    response_description="Deletion confirmation.",
    openapi_extra={
        "responses": {
            200: {
                "description": "User deleted",
                "content": {"application/json": {"example": {"message": "User deleted"}}},
            }
        }
    },
)
async def delete_client_user(
    uuid: str,
    service: RestaurantAdministratorService = Depends(get_restaurant_admin_service),
    claims: dict = Depends(get_current_restaurant_user),
):
    _require_manager(claims)
    restaurant_id = int(claims["restaurant_id"])
    return service.delete_client_user(restaurant_id, uuid)


@router.post(
    "/users/{uuid}/reset-password",
    summary="Reset another user's password (Client)",
    description="Manager-only. Reset a client user's password within your restaurant.",
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {
                "application/json": {
                    "schema": ClientPasswordResetRequest.model_json_schema(),
                    "example": {"new_password": "NewStrongPass1"},
                }
            },
        },
        "responses": {
            200: {
                "description": "Password reset",
                "content": {"application/json": {"example": {"message": "Password reset successful"}}},
            }
        },
    },
)
async def reset_client_user_password(
    uuid: str,
    payload: dict | None = Body(None, description="New password payload"),
    service: RestaurantAdministratorService = Depends(get_restaurant_admin_service),
    claims: dict = Depends(get_current_restaurant_user),
):
    _require_manager(claims)
    restaurant_id = int(claims["restaurant_id"])
    data = validate_payload(ClientPasswordResetRequest, payload)
    return service.reset_client_user_password(restaurant_id, uuid, data.new_password)


@router.put(
    "/users/{uuid}/role",
    summary="Update client user role (Client)",
    description="Manager-only. Update a client user's role within your restaurant.",
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {
                "application/json": {
                    "schema": ClientRoleUpdateRequest.model_json_schema(),
                    "example": {"role_id": 2},
                }
            },
        },
        "responses": {
            200: {
                "description": "Role updated",
                "content": {
                    "application/json": {
                        "example": {
                            "uuid": "a1b2",
                            "restaurant_id": 10,
                            "role_id": 2,
                            "role": "staff",
                            "permissions": ["/orders:view"],
                        }
                    }
                },
            }
        },
    },
    response_model=ClientUserResponse,
)
async def update_client_user_role(
    uuid: str,
    payload: dict | None = Body(None, description="Role update payload"),
    service: RestaurantAdministratorService = Depends(get_restaurant_admin_service),
    claims: dict = Depends(get_current_restaurant_user),
):
    _require_manager(claims)
    restaurant_id = int(claims["restaurant_id"])
    data = validate_payload(ClientRoleUpdateRequest, payload)
    return service.update_client_user_role(restaurant_id, uuid, data.role_id)


@router.post(
    "/users/bulk",
    status_code=status.HTTP_201_CREATED,
    summary="Bulk create client users (Client)",
    description="Manager-only. Bulk create client users for your restaurant.",
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {
                "application/json": {
                    "schema": ClientBulkCreateRequest.model_json_schema(),
                    "example": {
                        "users": [
                            {"email": "staff1@example.com", "password": "StrongPass1", "role_id": 2},
                            {"email": "staff2@example.com", "password": "StrongPass2", "role_id": 3},
                        ]
                    },
                }
            },
        },
        "responses": {
            201: {
                "description": "Users created",
                "content": {
                    "application/json": {
                        "example": {
                            "items": [
                                {"uuid": "u1", "email": "a@test.com", "role_id": 1},
                                {"uuid": "u2", "email": "b@test.com", "role_id": 2},
                            ]
                        }
                    }
                },
            }
        },
    },
)
async def bulk_create_client_users(
    payload: dict | None = Body(None, description="Bulk client users payload"),
    service: RestaurantAdministratorService = Depends(get_restaurant_admin_service),
    claims: dict = Depends(get_current_restaurant_user),
):
    _require_manager(claims)
    restaurant_id = int(claims["restaurant_id"])
    data = validate_payload(ClientBulkCreateRequest, payload)
    created = service.bulk_create_client_users(restaurant_id, [user.model_dump() for user in data.users])
    return {"items": created}


@router.post(
    "/me/reset-password",
    summary="Reset own password (Client)",
    description="Self-service password reset for the authenticated restaurant user.",
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {
                "application/json": {
                    "schema": ClientPasswordResetRequest.model_json_schema(),
                    "example": {"new_password": "NewStrongPass1"},
                }
            },
        },
        "responses": {
            200: {
                "description": "Password reset",
                "content": {"application/json": {"example": {"message": "Password reset successful"}}},
            }
        },
    },
)
async def reset_own_password(
    payload: dict | None = Body(None, description="New password payload"),
    service: RestaurantAdministratorService = Depends(get_restaurant_admin_service),
    claims: dict = Depends(get_current_restaurant_user),
):
    restaurant_id = int(claims["restaurant_id"])
    token_uuid = str(claims.get("sub") or "")
    if not token_uuid:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    data = validate_payload(ClientPasswordResetRequest, payload)
    return service.reset_client_user_password(restaurant_id, token_uuid, data.new_password)
