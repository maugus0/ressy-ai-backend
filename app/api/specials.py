from fastapi import APIRouter, Depends
from app.middleware.auth_middleware import get_current_active_user, require_role
from app.services.special_service import SpecialService

router = APIRouter()
special_service = SpecialService()

# CREATE
@router.post("/{restaurant_id}", dependencies=[Depends(require_role(["admin"]))])
async def create_special(restaurant_id: str, data: dict, current_user: dict = Depends(get_current_active_user)):
    return special_service.create_special(restaurant_id, data)

# READ ALL
@router.get("/{restaurant_id}", dependencies=[Depends(require_role(["admin", "client"]))])
async def list_specials(restaurant_id: str, current_user: dict = Depends(get_current_active_user)):
    return special_service.list_specials(restaurant_id)

# READ ONE
@router.get("/{restaurant_id}/{special_id}", dependencies=[Depends(require_role(["admin", "client"]))])
async def get_special(restaurant_id: str, special_id: str, current_user: dict = Depends(get_current_active_user)):
    return special_service.get_special(restaurant_id, special_id)

# UPDATE
@router.put("/{restaurant_id}/{special_id}", dependencies=[Depends(require_role(["admin", "client"]))])
async def update_special(restaurant_id: str, special_id: str, data: dict, current_user: dict = Depends(get_current_active_user)):
    return special_service.update_special(restaurant_id, special_id, data)

# DELETE
@router.delete("/{restaurant_id}/{special_id}", dependencies=[Depends(require_role(["admin"]))])
async def delete_special(restaurant_id: str, special_id: str, current_user: dict = Depends(get_current_active_user)):
    return special_service.delete_special(restaurant_id, special_id)

