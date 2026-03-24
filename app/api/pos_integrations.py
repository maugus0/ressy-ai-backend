from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPBearer
from pydantic import BaseModel, Field

from app.middleware.auth_middleware import require_role
from app.repositories.mysql_pos_integration_repo import MySQLPOSIntegrationRepository
from app.services.pos_catalog_admin_service import POSCatalogAdminService
from app.services.pos_catalog_archive_service import POSCatalogArchiveService
from app.services.pos_catalog_import_service import POSCatalogImportService
from app.services.pos_retry_service import POSRetryService

security = HTTPBearer(
    scheme_name="HTTPBearer",
    description="Enter your JWT access token obtained from login endpoints",
)

router = APIRouter(dependencies=[Depends(security)])


def get_pos_integration_repo() -> MySQLPOSIntegrationRepository:
    return MySQLPOSIntegrationRepository()


def get_pos_retry_service() -> POSRetryService:
    return POSRetryService()


def get_pos_catalog_import_service() -> POSCatalogImportService:
    return POSCatalogImportService()


def get_pos_catalog_admin_service() -> POSCatalogAdminService:
    return POSCatalogAdminService()


def get_pos_catalog_archive_service() -> POSCatalogArchiveService:
    return POSCatalogArchiveService()


def _check_restaurant_access(current_user: dict, restaurant_id: int):
    user_type = current_user.get("user_type")
    if user_type == "admin":
        return
    if user_type in {"restaurant", "client"}:
        user_restaurant_id = current_user.get("restaurant_id")
        if user_restaurant_id is None:
            raise HTTPException(status_code=403, detail="Your account is not associated with any restaurant")
        if int(user_restaurant_id) != int(restaurant_id):
            raise HTTPException(
                status_code=403,
                detail=f"You can only access POS integrations for your own restaurant (ID: {user_restaurant_id})",
            )
        return
    raise HTTPException(status_code=403, detail="Access denied - unknown user type")


def _get_integration_or_404(
    *,
    pos_repo: MySQLPOSIntegrationRepository,
    restaurant_id: int,
    pos_integration_id: int,
) -> Dict[str, Any]:
    integration = pos_repo.get_by_id(pos_integration_id)
    if not integration or int(integration["restaurant_id"]) != int(restaurant_id):
        raise HTTPException(status_code=404, detail="POS integration not found")
    return integration


class CreatePOSIntegrationRequest(BaseModel):
    pos_type: str = Field(..., description="POS type (SQUARE)")
    enabled: bool = Field(True, description="Whether integration is enabled")
    credentials: Dict[str, Any] = Field(..., description="POS credentials (access tokens, etc.)")
    location_id: str = Field(..., description="Square location_id")
    currency: Optional[str] = Field("USD", max_length=3, description="Currency code (ISO 4217)")
    default_order_options: Optional[Dict[str, Any]] = Field(None, description="Default order options")


class UpdatePOSIntegrationRequest(BaseModel):
    enabled: Optional[bool] = None
    credentials: Optional[Dict[str, Any]] = None
    location_id: Optional[str] = None
    currency: Optional[str] = Field(None, max_length=3, description="Currency code (ISO 4217)")
    default_order_options: Optional[Dict[str, Any]] = None


class UpdateSyncIssueRequest(BaseModel):
    status: str = Field(..., description="OPEN, ACKNOWLEDGED, RESOLVED, or IGNORED")


class CreateCatalogArchiveRequest(BaseModel):
    label: Optional[str] = Field(None, description="Optional label for the archive")
    notes: Optional[str] = Field(None, description="Optional archive notes")
    deactivate_current_catalog: bool = Field(
        False,
        description="Whether to immediately deactivate the current internal catalog after archiving it",
    )


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
    if request.pos_type != "SQUARE":
        raise HTTPException(status_code=400, detail="pos_type must be SQUARE")
    integration_id = pos_repo.create(
        {
            "restaurant_id": restaurant_id,
            "pos_type": request.pos_type,
            "enabled": request.enabled,
            "credentials": request.credentials,
            "location_id": request.location_id,
            "currency": request.currency,
            "default_order_options": request.default_order_options,
        }
    )
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
    pos_repo.update(pos_integration_id, request.model_dump(exclude_unset=True))
    return pos_repo.get_by_id(pos_integration_id)


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
    "/pos-retry/process",
    summary="Process pending POS sync retries",
)
async def process_pos_retries(
    current_user: dict = Depends(require_role(["admin"])),
    retry_service: POSRetryService = Depends(get_pos_retry_service),
):
    return retry_service.process_pending_retries()


@router.post(
    "/restaurants/{restaurant_id}/pos-integrations/{pos_integration_id}/sync-catalog",
    summary="Trigger async POS catalog import for an integration",
)
async def sync_pos_catalog(
    restaurant_id: int,
    pos_integration_id: int,
    current_user: dict = Depends(require_role(["admin", "client"])),
    pos_repo: MySQLPOSIntegrationRepository = Depends(get_pos_integration_repo),
    import_service: POSCatalogImportService = Depends(get_pos_catalog_import_service),
):
    _check_restaurant_access(current_user, restaurant_id)
    _get_integration_or_404(
        pos_repo=pos_repo,
        restaurant_id=restaurant_id,
        pos_integration_id=pos_integration_id,
    )
    triggered_by = f"{current_user.get('user_type', 'unknown')}:{current_user.get('id', 'unknown')}"
    return import_service.sync_integration(
        pos_integration_id,
        trigger_source="MANUAL",
        triggered_by=triggered_by,
    )


@router.get(
    "/restaurants/{restaurant_id}/pos-integrations/{pos_integration_id}/sync-runs",
    summary="List catalog sync runs for an integration",
)
async def list_pos_catalog_sync_runs(
    restaurant_id: int,
    pos_integration_id: int,
    limit: int = 20,
    current_user: dict = Depends(require_role(["admin", "client"])),
    pos_repo: MySQLPOSIntegrationRepository = Depends(get_pos_integration_repo),
    admin_service: POSCatalogAdminService = Depends(get_pos_catalog_admin_service),
):
    _check_restaurant_access(current_user, restaurant_id)
    _get_integration_or_404(
        pos_repo=pos_repo,
        restaurant_id=restaurant_id,
        pos_integration_id=pos_integration_id,
    )
    return {
        "restaurant_id": restaurant_id,
        "pos_integration_id": pos_integration_id,
        "sync_runs": admin_service.list_sync_runs(restaurant_id, pos_integration_id, limit=limit),
    }


@router.get(
    "/restaurants/{restaurant_id}/pos-integrations/{pos_integration_id}/sync-runs/{sync_run_id}",
    summary="Get a catalog sync run with attached issues",
)
async def get_pos_catalog_sync_run(
    restaurant_id: int,
    pos_integration_id: int,
    sync_run_id: int,
    current_user: dict = Depends(require_role(["admin", "client"])),
    pos_repo: MySQLPOSIntegrationRepository = Depends(get_pos_integration_repo),
    admin_service: POSCatalogAdminService = Depends(get_pos_catalog_admin_service),
):
    _check_restaurant_access(current_user, restaurant_id)
    _get_integration_or_404(
        pos_repo=pos_repo,
        restaurant_id=restaurant_id,
        pos_integration_id=pos_integration_id,
    )
    try:
        return admin_service.get_sync_run(restaurant_id, pos_integration_id, sync_run_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get(
    "/restaurants/{restaurant_id}/pos-integrations/{pos_integration_id}/sync-issues",
    summary="List open POS catalog sync issues for an integration",
)
async def list_pos_catalog_sync_issues(
    restaurant_id: int,
    pos_integration_id: int,
    current_user: dict = Depends(require_role(["admin", "client"])),
    pos_repo: MySQLPOSIntegrationRepository = Depends(get_pos_integration_repo),
    admin_service: POSCatalogAdminService = Depends(get_pos_catalog_admin_service),
):
    _check_restaurant_access(current_user, restaurant_id)
    _get_integration_or_404(
        pos_repo=pos_repo,
        restaurant_id=restaurant_id,
        pos_integration_id=pos_integration_id,
    )
    return {
        "restaurant_id": restaurant_id,
        "pos_integration_id": pos_integration_id,
        "issues": admin_service.sync_issue_repo.list_open_issues(restaurant_id, pos_integration_id),
    }


@router.patch(
    "/restaurants/{restaurant_id}/pos-integrations/{pos_integration_id}/sync-issues/{issue_id}",
    summary="Update the status of a POS catalog sync issue",
)
async def update_pos_catalog_sync_issue(
    restaurant_id: int,
    pos_integration_id: int,
    issue_id: int,
    request: UpdateSyncIssueRequest,
    current_user: dict = Depends(require_role(["admin", "client"])),
    pos_repo: MySQLPOSIntegrationRepository = Depends(get_pos_integration_repo),
    admin_service: POSCatalogAdminService = Depends(get_pos_catalog_admin_service),
):
    _check_restaurant_access(current_user, restaurant_id)
    _get_integration_or_404(
        pos_repo=pos_repo,
        restaurant_id=restaurant_id,
        pos_integration_id=pos_integration_id,
    )
    try:
        return admin_service.update_issue_status(
            restaurant_id=restaurant_id,
            pos_integration_id=pos_integration_id,
            issue_id=issue_id,
            status=request.status,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get(
    "/restaurants/{restaurant_id}/pos-integrations/{pos_integration_id}/inactive-catalog",
    summary="List inactive imported items and customizations for an integration",
)
async def list_inactive_catalog(
    restaurant_id: int,
    pos_integration_id: int,
    current_user: dict = Depends(require_role(["admin", "client"])),
    pos_repo: MySQLPOSIntegrationRepository = Depends(get_pos_integration_repo),
    admin_service: POSCatalogAdminService = Depends(get_pos_catalog_admin_service),
):
    _check_restaurant_access(current_user, restaurant_id)
    _get_integration_or_404(
        pos_repo=pos_repo,
        restaurant_id=restaurant_id,
        pos_integration_id=pos_integration_id,
    )
    return admin_service.list_inactive_catalog(restaurant_id, pos_integration_id)


@router.post(
    "/restaurants/{restaurant_id}/pos-integrations/{pos_integration_id}/archives",
    summary="Create a rollback archive for the current internal catalog",
)
async def create_catalog_archive(
    restaurant_id: int,
    pos_integration_id: int,
    request: CreateCatalogArchiveRequest,
    current_user: dict = Depends(require_role(["admin", "client"])),
    pos_repo: MySQLPOSIntegrationRepository = Depends(get_pos_integration_repo),
    archive_service: POSCatalogArchiveService = Depends(get_pos_catalog_archive_service),
):
    _check_restaurant_access(current_user, restaurant_id)
    _get_integration_or_404(
        pos_repo=pos_repo,
        restaurant_id=restaurant_id,
        pos_integration_id=pos_integration_id,
    )
    created_by = f"{current_user.get('user_type', 'unknown')}:{current_user.get('id', 'unknown')}"
    return archive_service.create_archive(
        restaurant_id=restaurant_id,
        pos_integration_id=pos_integration_id,
        label=request.label,
        notes=request.notes,
        created_by=created_by,
        deactivate_current_catalog=request.deactivate_current_catalog,
    )


@router.get(
    "/restaurants/{restaurant_id}/pos-integrations/{pos_integration_id}/archives",
    summary="List rollback archives for an integration",
)
async def list_catalog_archives(
    restaurant_id: int,
    pos_integration_id: int,
    limit: int = 20,
    current_user: dict = Depends(require_role(["admin", "client"])),
    pos_repo: MySQLPOSIntegrationRepository = Depends(get_pos_integration_repo),
    archive_service: POSCatalogArchiveService = Depends(get_pos_catalog_archive_service),
):
    _check_restaurant_access(current_user, restaurant_id)
    _get_integration_or_404(
        pos_repo=pos_repo,
        restaurant_id=restaurant_id,
        pos_integration_id=pos_integration_id,
    )
    return {
        "restaurant_id": restaurant_id,
        "pos_integration_id": pos_integration_id,
        "archives": archive_service.archive_repo.list_by_integration(restaurant_id, pos_integration_id, limit=limit),
    }


@router.post(
    "/restaurants/{restaurant_id}/pos-integrations/{pos_integration_id}/archives/{archive_id}/restore",
    summary="Restore a previously archived internal catalog snapshot",
)
async def restore_catalog_archive(
    restaurant_id: int,
    pos_integration_id: int,
    archive_id: int,
    current_user: dict = Depends(require_role(["admin", "client"])),
    pos_repo: MySQLPOSIntegrationRepository = Depends(get_pos_integration_repo),
    archive_service: POSCatalogArchiveService = Depends(get_pos_catalog_archive_service),
):
    _check_restaurant_access(current_user, restaurant_id)
    _get_integration_or_404(
        pos_repo=pos_repo,
        restaurant_id=restaurant_id,
        pos_integration_id=pos_integration_id,
    )
    try:
        return archive_service.restore_archive(archive_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
