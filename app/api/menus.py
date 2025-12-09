from fastapi import APIRouter, Depends

from app.middleware.auth_middleware import get_current_active_user, require_role
from app.services.menu_service import MenuService

router = APIRouter()
menu_service = MenuService()


# CREATE
@router.post(
    "/{restaurant_id}",
    dependencies=[Depends(require_role(["admin"]))],
    summary="Create Menu",
    description="Create a new menu for a restaurant. Admin access only. Menus contain categories and items that the voice agent can reference.",
    response_description="Returns the created menu with assigned ID and all menu items.",
)
async def create_menu(restaurant_id: str, data: dict, current_user: dict = Depends(get_current_active_user)):
    """
    Create a new menu for a restaurant.
    
    **Authentication**: Required (admin role only)
    
    **Path Parameters**:
    - restaurant_id: ID of the restaurant
    
    **Request Body**: Menu data including:
    - name: Menu name
    - categories: List of menu categories
    - items: List of menu items with prices and descriptions
    
    **Response**: Created menu object with all items and categories.
    """
    return menu_service.create_menu(restaurant_id, data)


# READ ALL
@router.get(
    "/{restaurant_id}",
    dependencies=[Depends(require_role(["admin", "client"]))],
    summary="List Menus",
    description="Retrieve all menus for a specific restaurant. Used by the voice agent to understand available menu items.",
    response_description="List of menus with categories and items.",
)
async def list_menus(restaurant_id: str, current_user: dict = Depends(get_current_active_user)):
    """
    Get all menus for a restaurant.
    
    **Authentication**: Required (admin or restaurant client role)
    
    **Path Parameters**:
    - restaurant_id: ID of the restaurant
    
    **Response**: List of all menus for the restaurant.
    """
    return menu_service.list_menus(restaurant_id)


# READ ONE
@router.get(
    "/{restaurant_id}/{menu_id}",
    dependencies=[Depends(require_role(["admin", "client"]))],
    summary="Get Menu Details",
    description="Retrieve detailed information for a specific menu including all categories and items.",
    response_description="Complete menu object with all categories and items.",
)
async def get_menu(restaurant_id: str, menu_id: str, current_user: dict = Depends(get_current_active_user)):
    """
    Get detailed information for a specific menu.
    
    **Authentication**: Required (admin or restaurant client role)
    
    **Path Parameters**:
    - restaurant_id: ID of the restaurant
    - menu_id: Unique identifier of the menu
    
    **Response**: Complete menu object with all categories and items.
    """
    return menu_service.get_menu(restaurant_id, menu_id)


# UPDATE
@router.put(
    "/{restaurant_id}/{menu_id}",
    dependencies=[Depends(require_role(["admin", "client"]))],
    summary="Update Menu",
    description="Update menu information, categories, or items. Partial updates are supported. Changes are reflected in voice agent prompts.",
    response_description="Updated menu object with modified fields.",
)
async def update_menu(
    restaurant_id: str, menu_id: str, data: dict, current_user: dict = Depends(get_current_active_user)
):
    """
    Update menu information.
    
    **Authentication**: Required (admin or restaurant client role)
    
    **Path Parameters**:
    - restaurant_id: ID of the restaurant
    - menu_id: Unique identifier of the menu to update
    
    **Request Body**: Dictionary with fields to update (categories, items, etc.)
    
    **Response**: Updated menu object.
    """
    return menu_service.update_menu(restaurant_id, menu_id, data)


# DELETE
@router.delete(
    "/{restaurant_id}/{menu_id}",
    dependencies=[Depends(require_role(["admin"]))],
    summary="Delete Menu",
    description="Permanently delete a menu from the system. Admin access only. This action cannot be undone.",
    response_description="Confirmation message or deleted menu details.",
)
async def delete_menu(restaurant_id: str, menu_id: str, current_user: dict = Depends(get_current_active_user)):
    """
    Delete a menu from the system.
    
    **Authentication**: Required (admin role only)
    
    **Path Parameters**:
    - restaurant_id: ID of the restaurant
    - menu_id: Unique identifier of the menu to delete
    
    **Warning**: This action is permanent and cannot be undone.
    
    **Response**: Confirmation of deletion.
    """
    return menu_service.delete_menu(restaurant_id, menu_id)
