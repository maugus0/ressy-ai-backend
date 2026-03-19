"""
Dashboard API routes for user management.
Includes RBAC: admins can access all, managers can only access their business's users.
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.security import HTTPBearer
from pydantic import BaseModel, EmailStr, Field

from app.middleware.auth_middleware import require_role
from app.services.user_service import UserService

security = HTTPBearer(
    scheme_name="HTTPBearer",
    description="Enter your JWT access token obtained from login endpoints. Just paste the token without 'Bearer ' prefix.",
)

router = APIRouter(
    dependencies=[Depends(security)],
)


# ---------- Service dependencies ----------


def get_user_service() -> UserService:
    """Dependency to get a fresh user service instance per request."""
    return UserService()


# ---------- Pydantic models for request validation ----------


class CreateUserRequest(BaseModel):
    """Request model for creating a user."""

    name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="User's full name",
        json_schema_extra={"example": "John Smith"},
    )
    phone_number: str = Field(
        ...,
        min_length=1,
        max_length=20,
        pattern=r"^\+[1-9]\d{9,14}$",
        description="User's phone number in E.164 format (e.g., +1234567890)",
        json_schema_extra={"example": "+1234567890"},
    )
    email: Optional[EmailStr] = Field(
        None,
        description="User's email address",
        json_schema_extra={"example": "john@example.com"},
    )
    address: Optional[str] = Field(
        None,
        description="User's address",
        json_schema_extra={"example": "123 Main St, City, State 12345"},
    )
    is_spam: Optional[bool] = Field(
        False,
        description="Mark user as spam/blocked",
        json_schema_extra={"example": False},
    )
    credit_card: Optional[str] = Field(
        None,
        max_length=255,
        description="Encrypted credit card info",
        json_schema_extra={"example": "****1234"},
    )


class UpdateUserRequest(BaseModel):
    """Request model for updating a user."""

    name: Optional[str] = Field(
        None,
        min_length=1,
        max_length=255,
        description="User's full name",
        json_schema_extra={"example": "John Smith"},
    )
    phone_number: Optional[str] = Field(
        None,
        min_length=1,
        max_length=20,
        description="User's phone number",
        json_schema_extra={"example": "+1234567890"},
    )
    email: Optional[EmailStr] = Field(
        None,
        description="User's email address",
        json_schema_extra={"example": "john@example.com"},
    )
    address: Optional[str] = Field(
        None,
        description="User's address",
        json_schema_extra={"example": "123 Main St, City, State 12345"},
    )
    is_spam: Optional[bool] = Field(
        None,
        description="Mark user as spam/blocked",
        json_schema_extra={"example": False},
    )
    credit_card: Optional[str] = Field(
        None,
        max_length=255,
        description="Encrypted credit card info",
        json_schema_extra={"example": "****1234"},
    )


# ---------- Helper functions for RBAC ----------


def _check_business_access(current_user: dict, business_id: int):
    """
    Check if the current user has access to the specified business.
    Admins have access to all businesss.
    Restaurant users (managers) can only access their own business.

    Args:
        current_user: JWT claims dict containing user_type, business_id (for business users)
        business_id: The business ID to check access for (from path param)

    Raises:
        HTTPException 403: If user doesn't have access to this business
    """
    user_type = current_user.get("user_type")

    # Admins (Ressy platform admins) can access all businesss
    if user_type == "admin":
        return

    # Restaurant users (managers/staff) can only access their own business
    if user_type == "business":
        user_business_id = current_user.get("business_id")

        if user_business_id is None:
            raise HTTPException(
                status_code=403,
                detail="Your account is not associated with any business",
            )

        if int(user_business_id) != int(business_id):
            raise HTTPException(
                status_code=403,
                detail=f"You can only access users for your own business (ID: {user_business_id})",
            )
        return

    raise HTTPException(status_code=403, detail="Access denied - unknown user type")


def _check_user_access(current_user: dict, user_id: int, user_service: UserService):
    """
    Check if the current user has access to the specified user.
    Validates that the user is associated with the current user's business
    via metadata, reservations, or calls.

    Args:
        current_user: JWT claims dict
        user_id: The user ID to check access for
        user_service: The user service instance to use

    Returns:
        The user dict if access is granted

    Raises:
        HTTPException 404: If user not found
        HTTPException 403: If user doesn't have access
    """
    try:
        user = user_service.get_user_with_business_check(user_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    user_type = current_user.get("user_type")

    # Admins can access any user
    if user_type == "admin":
        return user

    # Restaurant users can only access users associated with their business
    if user_type == "business":
        user_business_id = current_user.get("business_id")
        target_business_ids = user.get("business_ids", [])

        # Check if the user is associated with the current user's business
        if target_business_ids:
            if int(user_business_id) not in target_business_ids:
                raise HTTPException(
                    status_code=403,
                    detail="You can only access users for your own business",
                )
        else:
            # User has no business associations - deny access for business users
            raise HTTPException(
                status_code=403,
                detail="This user is not associated with any business",
            )
        return user

    raise HTTPException(status_code=403, detail="Access denied - unknown user type")


# ---------- CREATE USER (Dashboard) ----------
@router.post(
    "/businesss/{business_id}/users",
    summary="Create or add a user (Dashboard)",
    description="""
Create a new user or add an existing user to the business.

**Behavior**:
- If user doesn't exist (by phone/email): Creates new user and associates with business
- If user exists but not associated with this business: Associates existing user with business
- If user exists and already associated: Returns error

**Authentication**: Required (admin or business manager role)

**Authorization**:
- Admins can create/add users for any business
- Restaurant managers can only create/add users for their own business

**Request Body**:
- `name`: User's full name (required)
- `phone_number`: User's phone number (required)
- `email`: User's email address (optional)
- `address`: User's address (optional)
- `is_spam`: Mark user as spam/blocked (default: false)
- `credit_card`: Encrypted credit card info (optional)

**Response** includes `is_new_user` field to indicate if user was newly created or existing.
""",
    response_description="Created or added user with all details",
    responses={
        200: {
            "description": "User created or added successfully",
            "content": {
                "application/json": {
                    "examples": {
                        "new_user": {
                            "summary": "New user created",
                            "value": {
                                "message": "User created successfully",
                                "user_id": 123,
                                "user": {
                                    "id": 123,
                                    "name": "John Smith",
                                    "phone_number": "+1234567890",
                                    "email": "john@example.com",
                                    "address": "123 Main St",
                                    "is_spam": False,
                                    "credit_card": None,
                                    "created_at": "2025-12-13T10:00:00Z",
                                    "updated_at": "2025-12-13T10:00:00Z",
                                },
                                "is_new_user": True,
                            },
                        },
                        "existing_user": {
                            "summary": "Existing user added to business",
                            "value": {
                                "message": "Existing user added to business successfully",
                                "user_id": 123,
                                "user": {
                                    "id": 123,
                                    "name": "John Smith",
                                    "phone_number": "+1234567890",
                                    "email": "john@example.com",
                                    "address": "123 Main St",
                                    "is_spam": False,
                                    "credit_card": None,
                                    "created_at": "2025-12-13T10:00:00Z",
                                    "updated_at": "2025-12-13T10:00:00Z",
                                },
                                "is_new_user": False,
                            },
                        },
                    }
                }
            },
        },
        400: {
            "description": "User already associated with this business",
            "content": {"application/json": {"example": {"detail": "User is already associated with this business"}}},
        },
        403: {"description": "Access denied - cannot access this business"},
    },
)
async def create_user(
    business_id: int,
    request: CreateUserRequest,
    current_user: dict = Depends(require_role(["admin", "client"])),
    user_service: UserService = Depends(get_user_service),
):
    """Create a new user from the dashboard."""
    _check_business_access(current_user, business_id)

    try:
        user_data = request.model_dump(exclude_none=True)
        result = user_service.create_user_for_business(
            business_id=business_id,
            user_data=user_data,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creating user: {str(e)}")


# ---------- GET USERS BY RESTAURANT (Dashboard) ----------
@router.get(
    "/businesss/{business_id}/users",
    summary="Get users for a business (Dashboard)",
    description="""
Retrieve all users who have interacted with a specific business.

Users are identified through their direct dashboard associations (User_Restaurant_Metadata), reservations, and calls to the business.
Each user includes statistics: total calls, total orders, and total reservations.

**Authentication**: Required (admin or business manager role)

**Authorization**:
- Admins can view users for any business
- Restaurant managers can only view users for their own business

**Query Parameters**:
- `search`: Search by name, phone number, or email
- `is_spam`: Filter by spam status (true/false)
- `limit`: Maximum number of results (default: 50, max: 500)
- `offset`: Pagination offset (default: 0)
""",
    response_description="List of users with their details and statistics",
    responses={
        200: {
            "description": "Users retrieved successfully",
            "content": {
                "application/json": {
                    "example": {
                        "business_id": 1,
                        "users": [
                            {
                                "id": 123,
                                "name": "John Smith",
                                "phone_number": "+1234567890",
                                "email": "john@example.com",
                                "address": "123 Main St",
                                "is_spam": False,
                                "credit_card": None,
                                "created_at": "2025-12-13T10:00:00Z",
                                "updated_at": "2025-12-13T10:00:00Z",
                                "statistics": {
                                    "total_calls": 5,
                                    "total_orders": 3,
                                    "total_reservations": 8,
                                },
                            }
                        ],
                        "total": 1,
                        "limit": 50,
                        "offset": 0,
                        "has_more": False,
                    }
                }
            },
        },
        403: {"description": "Access denied - cannot access this business's users"},
    },
)
async def get_business_users(
    business_id: int,
    search: Optional[str] = Query(
        None,
        description="Search by name, phone, or email",
        json_schema_extra={"example": "john"},
    ),
    is_spam: Optional[bool] = Query(
        None,
        description="Filter by spam status",
        json_schema_extra={"example": False},
    ),
    limit: int = Query(50, ge=1, le=500, description="Limit results"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    current_user: dict = Depends(require_role(["admin", "client"])),
    user_service: UserService = Depends(get_user_service),
):
    """Get users for a business with optional filters and statistics."""
    _check_business_access(current_user, business_id)

    try:
        result = user_service.list_users_by_business(
            business_id=business_id,
            search=search,
            is_spam=is_spam,
            limit=limit,
            offset=offset,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching users: {str(e)}")


# ---------- GET USER BY ID (Dashboard) ----------
@router.get(
    "/users/{user_id}",
    summary="Get a user by ID (Dashboard)",
    description="""
Retrieve detailed information about a specific user.

**Authentication**: Required (admin or business manager role)

**Authorization**:
- Admins can view any user
- Restaurant managers can only view users associated with their business
""",
    response_description="User details",
    responses={
        200: {
            "description": "User retrieved successfully",
            "content": {
                "application/json": {
                    "example": {
                        "id": 123,
                        "name": "John Smith",
                        "phone_number": "+1234567890",
                        "email": "john@example.com",
                        "address": "123 Main St",
                        "is_spam": False,
                        "credit_card": None,
                        "created_at": "2025-12-13T10:00:00Z",
                        "updated_at": "2025-12-13T10:00:00Z",
                    }
                }
            },
        },
        403: {"description": "Access denied - cannot access this user"},
        404: {"description": "User not found"},
    },
)
async def get_user_dashboard(
    user_id: int,
    current_user: dict = Depends(require_role(["admin", "client"])),
    user_service: UserService = Depends(get_user_service),
):
    """Get a user by ID with authorization check."""
    user = _check_user_access(current_user, user_id, user_service)

    # Remove business_ids from response for clients (business users)
    # Admins should see business_ids, but clients should not
    user_type = current_user.get("user_type")
    if user_type == "business" and "business_ids" in user:
        user = {k: v for k, v in user.items() if k != "business_ids"}

    return user


# ---------- UPDATE USER (Dashboard) ----------
@router.put(
    "/users/{user_id}",
    summary="Update a user (Dashboard)",
    description="""
Update user information.

**Authentication**: Required (admin or business manager role)

**Authorization**:
- Admins can update any user
- Restaurant managers can only update users associated with their business

**Updatable Fields**:
- `name`: User's full name
- `phone_number`: User's phone number (must be unique)
- `email`: User's email address (must be unique if provided)
- `address`: User's address
- `is_spam`: Mark user as spam/blocked
- `credit_card`: Encrypted credit card info

**Note**: Only provided fields will be updated. Omit fields you don't want to change.
""",
    response_description="Updated user with all details",
    responses={
        200: {
            "description": "User updated successfully",
            "content": {
                "application/json": {
                    "example": {
                        "message": "User updated successfully",
                        "user": {
                            "id": 123,
                            "name": "John Smith Updated",
                            "phone_number": "+1234567890",
                            "email": "john.updated@example.com",
                            "address": "456 New St",
                            "is_spam": False,
                            "credit_card": None,
                            "created_at": "2025-12-13T10:00:00Z",
                            "updated_at": "2025-12-13T12:00:00Z",
                        },
                    }
                }
            },
        },
        400: {"description": "Invalid request data or duplicate phone/email"},
        403: {"description": "Access denied - cannot access this user"},
        404: {"description": "User not found"},
    },
)
async def update_user(
    user_id: int,
    request: UpdateUserRequest,
    current_user: dict = Depends(require_role(["admin", "client"])),
    user_service: UserService = Depends(get_user_service),
):
    """Update user details."""
    _check_user_access(current_user, user_id, user_service)

    try:
        user_data = request.model_dump(exclude_none=True)
        if not user_data:
            raise HTTPException(status_code=400, detail="No fields provided for update")

        result = user_service.update_user_dashboard(user_id, user_data)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error updating user: {str(e)}")
