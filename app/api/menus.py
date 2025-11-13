from fastapi import APIRouter, Depends

from app.middleware.auth_middleware import get_current_active_user, require_role
from app.services.menu_service import MenuService

router = APIRouter()
menu_service = MenuService()


# CREATE
@router.post("/{restaurant_id}", dependencies=[Depends(require_role(["admin"]))])
async def create_menu(restaurant_id: str, data: dict, current_user: dict = Depends(get_current_active_user)):
    return menu_service.create_menu(restaurant_id, data)


# READ ALL
@router.get("/{restaurant_id}", dependencies=[Depends(require_role(["admin", "client"]))])
async def list_menus(restaurant_id: str, current_user: dict = Depends(get_current_active_user)):
    return menu_service.list_menus(restaurant_id)


# READ ONE
@router.get("/{restaurant_id}/{menu_id}", dependencies=[Depends(require_role(["admin", "client"]))])
async def get_menu(restaurant_id: str, menu_id: str, current_user: dict = Depends(get_current_active_user)):
    return menu_service.get_menu(restaurant_id, menu_id)


# UPDATE
@router.put("/{restaurant_id}/{menu_id}", dependencies=[Depends(require_role(["admin", "client"]))])
async def update_menu(restaurant_id: str, menu_id: str, data: dict,
                      current_user: dict = Depends(get_current_active_user)):
    return menu_service.update_menu(restaurant_id, menu_id, data)


# DELETE
@router.delete("/{restaurant_id}/{menu_id}", dependencies=[Depends(require_role(["admin"]))])
async def delete_menu(restaurant_id: str, menu_id: str, current_user: dict = Depends(get_current_active_user)):
    return menu_service.delete_menu(restaurant_id, menu_id)
