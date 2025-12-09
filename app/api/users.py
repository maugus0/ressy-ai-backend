from fastapi import APIRouter, Depends

from app.middleware.auth_middleware import get_current_active_user, require_role
from app.services.user_service import UserService

router = APIRouter()
user_service = UserService()


# CREATE
@router.post(
    "/",
    dependencies=[Depends(require_role(["admin"]))],
    summary="Create User",
    description="Create a new user account for a restaurant. Admin access only. Users can be assigned roles such as manager or staff.",
    response_description="Returns the created user object with assigned ID and role information.",
)
async def create_user(data: dict, current_user: dict = Depends(get_current_active_user)):
    """
    Create a new user account.
    
    **Authentication**: Required (admin role only)
    
    **Request Body**: User data including:
    - email: User email address
    - password: User password
    - role: User role (manager, staff, etc.)
    - restaurant_id: ID of the restaurant the user belongs to
    - Other user details
    
    **Response**: Created user object with all details.
    """
    return user_service.create_user(data)


# READ ALL
@router.get(
    "/{restaurant_id}",
    dependencies=[Depends(require_role(["admin"]))],
    summary="List Users",
    description="Retrieve all users in the system. Admin access only. Note: The restaurant_id parameter is accepted but all users are returned.",
    response_description="List of all users with their details and roles.",
)
async def list_users(restaurant_id: str, current_user: dict = Depends(get_current_active_user)):
    """
    Get a list of all users.
    
    **Authentication**: Required (admin role only)
    
    **Path Parameters**:
    - restaurant_id: Restaurant ID (parameter accepted but not currently used for filtering)
    
    **Response**: List of all users with their details.
    """
    return user_service.list_users()


# UPDATE
@router.put(
    "/{user_id}",
    dependencies=[Depends(require_role(["admin"]))],
    summary="Update User",
    description="Update user information such as email, role, or permissions. Partial updates are supported.",
    response_description="Updated user object with modified fields.",
)
async def update_user(user_id: str, data: dict, current_user: dict = Depends(get_current_active_user)):
    """
    Update user information.
    
    **Authentication**: Required (admin role only)
    
    **Path Parameters**:
    - user_id: Unique identifier of the user to update
    
    **Request Body**: Dictionary with fields to update (email, role, permissions, etc.)
    
    **Response**: Updated user object.
    """
    return user_service.update_user(user_id, data)


# DELETE
@router.delete(
    "/{user_id}",
    dependencies=[Depends(require_role(["admin"]))],
    summary="Delete User",
    description="Permanently delete a user account from the system. Admin access only. This action cannot be undone.",
    response_description="Confirmation message or deleted user details.",
)
async def delete_user(user_id: str, current_user: dict = Depends(get_current_active_user)):
    """
    Delete a user account from the system.
    
    **Authentication**: Required (admin role only)
    
    **Path Parameters**:
    - user_id: Unique identifier of the user to delete
    
    **Warning**: This action is permanent and cannot be undone.
    
    **Response**: Confirmation of deletion.
    """
    return user_service.delete_user(user_id)
