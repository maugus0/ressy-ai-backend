from fastapi import APIRouter, Depends

from app.middleware.auth_middleware import get_current_active_user, require_role
from app.services.special_service import SpecialService

router = APIRouter()
special_service = SpecialService()


# CREATE
@router.post(
    "/{restaurant_id}",
    dependencies=[Depends(require_role(["admin"]))],
    summary="Create Special",
    description="Create a new special or promotion for a restaurant. Admin access only. Specials are featured items that the voice agent can mention to customers.",
    response_description="Returns the created special with assigned ID and details.",
)
async def create_special(restaurant_id: str, data: dict, current_user: dict = Depends(get_current_active_user)):
    """
    Create a new special or promotion for a restaurant.
    
    **Authentication**: Required (admin role only)
    
    **Path Parameters**:
    - restaurant_id: ID of the restaurant
    
    **Request Body**: Special data including:
    - name: Name of the special
    - description: Description of the special
    - price: Price of the special
    - valid_from: Start date/time
    - valid_until: End date/time
    - Other special details
    
    **Response**: Created special object with all details.
    """
    return special_service.create_special(restaurant_id, data)


# READ ALL
@router.get(
    "/{restaurant_id}",
    dependencies=[Depends(require_role(["admin", "client"]))],
    summary="List Specials",
    description="Retrieve all active and inactive specials for a restaurant. Used by the voice agent to inform customers about current promotions.",
    response_description="List of specials with details including validity dates.",
)
async def list_specials(restaurant_id: str, current_user: dict = Depends(get_current_active_user)):
    """
    Get all specials for a restaurant.
    
    **Authentication**: Required (admin or restaurant client role)
    
    **Path Parameters**:
    - restaurant_id: ID of the restaurant
    
    **Response**: List of all specials for the restaurant.
    """
    return special_service.list_specials(restaurant_id)


# READ ONE
@router.get(
    "/{restaurant_id}/{special_id}",
    dependencies=[Depends(require_role(["admin", "client"]))],
    summary="Get Special Details",
    description="Retrieve detailed information for a specific special including validity dates and pricing.",
    response_description="Complete special object with all details.",
)
async def get_special(restaurant_id: str, special_id: str, current_user: dict = Depends(get_current_active_user)):
    """
    Get detailed information for a specific special.
    
    **Authentication**: Required (admin or restaurant client role)
    
    **Path Parameters**:
    - restaurant_id: ID of the restaurant
    - special_id: Unique identifier of the special
    
    **Response**: Complete special object with all details.
    """
    return special_service.get_special(restaurant_id, special_id)


# UPDATE
@router.put(
    "/{restaurant_id}/{special_id}",
    dependencies=[Depends(require_role(["admin", "client"]))],
    summary="Update Special",
    description="Update special information such as description, price, or validity dates. Partial updates are supported.",
    response_description="Updated special object with modified fields.",
)
async def update_special(
    restaurant_id: str, special_id: str, data: dict, current_user: dict = Depends(get_current_active_user)
):
    """
    Update special information.
    
    **Authentication**: Required (admin or restaurant client role)
    
    **Path Parameters**:
    - restaurant_id: ID of the restaurant
    - special_id: Unique identifier of the special to update
    
    **Request Body**: Dictionary with fields to update
    
    **Response**: Updated special object.
    """
    return special_service.update_special(restaurant_id, special_id, data)


# DELETE
@router.delete(
    "/{restaurant_id}/{special_id}",
    dependencies=[Depends(require_role(["admin"]))],
    summary="Delete Special",
    description="Permanently delete a special from the system. Admin access only. This action cannot be undone.",
    response_description="Confirmation message or deleted special details.",
)
async def delete_special(restaurant_id: str, special_id: str, current_user: dict = Depends(get_current_active_user)):
    """
    Delete a special from the system.
    
    **Authentication**: Required (admin role only)
    
    **Path Parameters**:
    - restaurant_id: ID of the restaurant
    - special_id: Unique identifier of the special to delete
    
    **Warning**: This action is permanent and cannot be undone.
    
    **Response**: Confirmation of deletion.
    """
    return special_service.delete_special(restaurant_id, special_id)
