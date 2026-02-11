import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from fastapi.security import HTTPBearer
from pydantic import BaseModel, Field

from app.middleware.auth_middleware import require_role
from app.repositories.mysql_pos_integration_repo import MySQLPOSIntegrationRepository
from app.services.menu_pos_mapping_service import MenuPOSMappingService
from app.services.pos_retry_service import POSRetryService

logger = logging.getLogger(__name__)

security = HTTPBearer(
    scheme_name="HTTPBearer",
    description="Enter your JWT access token obtained from login endpoints",
)

router = APIRouter(
    dependencies=[Depends(security)],
)


def get_pos_integration_repo() -> MySQLPOSIntegrationRepository:
    return MySQLPOSIntegrationRepository()


def get_menu_mapping_service() -> MenuPOSMappingService:
    return MenuPOSMappingService()


def get_pos_retry_service() -> POSRetryService:
    return POSRetryService()


def _check_restaurant_access(current_user: dict, restaurant_id: int):
    user_type = current_user.get("user_type")
    if user_type == "admin":
        return
    if user_type == "restaurant":
        user_restaurant_id = current_user.get("restaurant_id")
        if user_restaurant_id is None:
            raise HTTPException(
                status_code=403,
                detail="Your account is not associated with any restaurant",
            )
        if int(user_restaurant_id) != int(restaurant_id):
            raise HTTPException(
                status_code=403,
                detail=f"You can only access POS integrations for your own restaurant (ID: {user_restaurant_id})",
            )
        return
    raise HTTPException(status_code=403, detail="Access denied - unknown user type")


class CreatePOSIntegrationRequest(BaseModel):
    pos_type: str = Field(..., description="POS type (SQUARE or TOAST)")
    enabled: bool = Field(True, description="Whether integration is enabled")
    credentials: Dict[str, Any] = Field(..., description="POS credentials (access tokens, etc.)")
    location_id: str = Field(..., description="Square location_id or Toast restaurant external ID")
    currency: Optional[str] = Field("USD", max_length=3, description="Currency code (ISO 4217, e.g., USD, CAD, EUR)")
    default_order_options: Optional[Dict[str, Any]] = Field(None, description="Default order options")


class UpdatePOSIntegrationRequest(BaseModel):
    enabled: Optional[bool] = None
    credentials: Optional[Dict[str, Any]] = None
    location_id: Optional[str] = None
    currency: Optional[str] = Field(None, max_length=3, description="Currency code (ISO 4217, e.g., USD, CAD, EUR)")
    default_order_options: Optional[Dict[str, Any]] = None


class SyncMenuRequest(BaseModel):
    access_token: str = Field(..., description="Toast access token")
    location_id: str = Field(..., description="Toast restaurant external ID")


@router.get(
    "/restaurants/{restaurant_id}/pos-integrations",
    summary="Get POS integrations for a restaurant",
)
async def get_pos_integrations(
    restaurant_id: int,
    current_user: dict = Depends(require_role(["admin", "client"])),
    pos_repo: MySQLPOSIntegrationRepository = Depends(get_pos_integration_repo),
):
    _check_restaurant_access(current_user, restaurant_id)
    integrations = pos_repo.get_enabled_integrations(restaurant_id)
    return {"restaurant_id": restaurant_id, "integrations": integrations}


@router.post(
    "/restaurants/{restaurant_id}/pos-integrations",
    summary="Create POS integration",
)
async def create_pos_integration(
    restaurant_id: int,
    request: CreatePOSIntegrationRequest,
    current_user: dict = Depends(require_role(["admin", "client"])),
    pos_repo: MySQLPOSIntegrationRepository = Depends(get_pos_integration_repo),
):
    _check_restaurant_access(current_user, restaurant_id)
    if request.pos_type not in ["SQUARE", "TOAST"]:
        raise HTTPException(status_code=400, detail="pos_type must be SQUARE or TOAST")
    integration_data = {
        "restaurant_id": restaurant_id,
        "pos_type": request.pos_type,
        "enabled": request.enabled,
        "credentials": request.credentials,
        "location_id": request.location_id,
        "default_order_options": request.default_order_options,
    }
    integration_id = pos_repo.create(integration_data)
    integration = pos_repo.get_by_id(integration_id)
    return integration


@router.put(
    "/pos-integrations/{pos_integration_id}",
    summary="Update POS integration",
)
async def update_pos_integration(
    pos_integration_id: int,
    request: UpdatePOSIntegrationRequest,
    current_user: dict = Depends(require_role(["admin", "client"])),
    pos_repo: MySQLPOSIntegrationRepository = Depends(get_pos_integration_repo),
):
    integration = pos_repo.get_by_id(pos_integration_id)
    if not integration:
        raise HTTPException(status_code=404, detail="POS integration not found")
    _check_restaurant_access(current_user, integration["restaurant_id"])
    updates = request.model_dump(exclude_unset=True)
    pos_repo.update(pos_integration_id, updates)
    updated = pos_repo.get_by_id(pos_integration_id)
    return updated


@router.delete(
    "/pos-integrations/{pos_integration_id}",
    summary="Delete POS integration",
)
async def delete_pos_integration(
    pos_integration_id: int,
    current_user: dict = Depends(require_role(["admin", "client"])),
    pos_repo: MySQLPOSIntegrationRepository = Depends(get_pos_integration_repo),
):
    integration = pos_repo.get_by_id(pos_integration_id)
    if not integration:
        raise HTTPException(status_code=404, detail="POS integration not found")
    _check_restaurant_access(current_user, integration["restaurant_id"])
    pos_repo.delete(pos_integration_id)
    return {"message": "POS integration deleted successfully"}


@router.post(
    "/restaurants/{restaurant_id}/pos-integrations/{pos_integration_id}/sync-menu",
    summary="Sync menu to Toast POS",
)
async def sync_menu_to_toast(
    restaurant_id: int,
    pos_integration_id: int,
    request: SyncMenuRequest,
    current_user: dict = Depends(require_role(["admin", "client"])),
    pos_repo: MySQLPOSIntegrationRepository = Depends(get_pos_integration_repo),
    mapping_service: MenuPOSMappingService = Depends(get_menu_mapping_service),
):
    _check_restaurant_access(current_user, restaurant_id)
    integration = pos_repo.get_by_id(pos_integration_id)
    if not integration:
        raise HTTPException(status_code=404, detail="POS integration not found")
    if integration["pos_type"] != "TOAST":
        raise HTTPException(status_code=400, detail="Menu sync is only available for Toast POS")
    result = mapping_service.sync_menu_to_toast(
        restaurant_id, pos_integration_id, request.access_token, request.location_id
    )
    return result


@router.post(
    "/pos-retry/process",
    summary="Process pending POS sync retries",
)
async def process_pos_retries(
    current_user: dict = Depends(require_role(["admin"])),
    retry_service: POSRetryService = Depends(get_pos_retry_service),
):
    result = retry_service.process_pending_retries()
    return result
