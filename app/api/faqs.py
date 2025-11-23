from fastapi import APIRouter, Depends

from app.middleware.auth_middleware import get_current_active_user, require_role
from app.services.faq_service import FAQService

router = APIRouter()
faq_service = FAQService()


# CREATE
@router.post("/{restaurant_id}", dependencies=[Depends(require_role(["admin"]))])
async def create_faq(restaurant_id: str, data: dict, current_user: dict = Depends(get_current_active_user)):
    return faq_service.create_faq(restaurant_id, data)


# READ ALL
@router.get("/{restaurant_id}", dependencies=[Depends(require_role(["admin"]))])
async def list_faqs(restaurant_id: str, current_user: dict = Depends(get_current_active_user)):
    return faq_service.list_faqs(restaurant_id)


# UPDATE
@router.put("/{restaurant_id}/{faq_id}", dependencies=[Depends(require_role(["admin"]))])
async def update_faq(restaurant_id: str, faq_id: str, data: dict,
                     current_user: dict = Depends(get_current_active_user)):
    return faq_service.update_faq(restaurant_id, faq_id, data)


# DELETE
@router.delete("/{restaurant_id}/{faq_id}", dependencies=[Depends(require_role(["admin"]))])
async def delete_faq(restaurant_id: str, faq_id: str, current_user: dict = Depends(get_current_active_user)):
    return faq_service.delete_faq(restaurant_id, faq_id)
