from fastapi import APIRouter, Depends

from app.middleware.auth_middleware import get_current_active_user, require_role
from app.services.restaurant_service import RestaurantService

router = APIRouter()
restaurant_service = RestaurantService()


# ---------- CREATE ----------
@router.post(
    "/",
    dependencies=[Depends(require_role(["admin"]))],
    summary="Create Restaurant",
    description="Create a new restaurant in the system. Admin access only. Requires restaurant details such as name, address, phone number, and configuration.",
    response_description="Returns the created restaurant object with assigned ID and details.",
)
async def create_restaurant(data: dict, current_user: dict = Depends(get_current_active_user)):
    """
    Create a new restaurant.
    
    **Authentication**: Required (admin role only)
    
    **Request Body**: Restaurant data including:
    - name: Restaurant name
    - address: Restaurant address
    - phone_number: Contact phone number
    - Other restaurant configuration fields
    
    **Response**: Created restaurant object with all details and assigned ID.
    """
    return restaurant_service.create_restaurant(data)


# ---------- READ ALL ----------
@router.get(
    "/",
    dependencies=[Depends(require_role(["admin"]))],
    summary="List All Restaurants",
    description="Retrieve a list of all restaurants in the system. Admin access only. Returns complete restaurant information for each restaurant.",
    response_description="List of all restaurants with their details.",
)
async def list_restaurants(current_user: dict = Depends(get_current_active_user)):
    """
    Get a list of all restaurants.
    
    **Authentication**: Required (admin role only)
    
    **Response**: List of all restaurants with complete details.
    """
    return restaurant_service.list_restaurants()


# ---------- READ ONE ----------
@router.get(
    "/{restaurant_id}",
    dependencies=[Depends(require_role(["admin"]))],
    summary="Get Restaurant Details",
    description="Retrieve detailed information for a specific restaurant by ID. Admin access only.",
    response_description="Restaurant object with all details including configuration and settings.",
)
async def get_restaurant(restaurant_id: str, current_user: dict = Depends(get_current_active_user)):
    """
    Get detailed information for a specific restaurant.
    
    **Authentication**: Required (admin role only)
    
    **Path Parameters**:
    - restaurant_id: Unique identifier of the restaurant
    
    **Response**: Complete restaurant object with all details.
    """
    return restaurant_service.get_restaurant(restaurant_id)


# ---------- UPDATE ----------
@router.put(
    "/{restaurant_id}",
    dependencies=[Depends(require_role(["admin"]))],
    summary="Update Restaurant",
    description="Update restaurant information and settings. Admin access only. Partial updates are supported.",
    response_description="Updated restaurant object with modified fields.",
)
async def update_restaurant(restaurant_id: str, data: dict, current_user: dict = Depends(get_current_active_user)):
    """
    Update restaurant information.
    
    **Authentication**: Required (admin role only)
    
    **Path Parameters**:
    - restaurant_id: Unique identifier of the restaurant to update
    
    **Request Body**: Dictionary with fields to update (partial updates supported)
    
    **Response**: Updated restaurant object.
    """
    return restaurant_service.update_restaurant(restaurant_id, data)


# ---------- DELETE ----------
@router.delete(
    "/{restaurant_id}",
    dependencies=[Depends(require_role(["admin"]))],
    summary="Delete Restaurant",
    description="Permanently delete a restaurant from the system. Admin access only. This action cannot be undone.",
    response_description="Confirmation message or deleted restaurant details.",
)
async def delete_restaurant(restaurant_id: str, current_user: dict = Depends(get_current_active_user)):
    """
    Delete a restaurant from the system.
    
    **Authentication**: Required (admin role only)
    
    **Path Parameters**:
    - restaurant_id: Unique identifier of the restaurant to delete
    
    **Warning**: This action is permanent and cannot be undone.
    
    **Response**: Confirmation of deletion.
    """
    return restaurant_service.delete_restaurant(restaurant_id)
