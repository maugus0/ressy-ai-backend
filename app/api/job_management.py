"""
Job Management API endpoints.

Provides endpoints for manually triggering jobs and monitoring job execution status.
"""

import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.security import HTTPBearer
from pydantic import BaseModel

from app.jobs.user_profile_sync_job import user_profile_sync_job
from app.middleware.auth_middleware import require_role
from app.repositories.mysql_user_sync_repo import MySQLUserSyncRepository
from app.services.job_scheduler import JobScheduler

logger = logging.getLogger(__name__)

security = HTTPBearer(
    scheme_name="HTTPBearer",
    description="Enter your JWT access token obtained from login endpoints",
)

router = APIRouter(
    prefix="/api/v1/jobs",
    tags=["Job Management"],
    dependencies=[Depends(security)],
)


# ---------- Service dependencies ----------


def get_sync_repo() -> MySQLUserSyncRepository:
    """Dependency to get a fresh sync repository instance per request."""
    return MySQLUserSyncRepository()


def get_job_scheduler() -> JobScheduler:
    """Dependency to get job scheduler instance."""
    return JobScheduler()


# ---------- Response Models ----------


class JobExecutionLogResponse(BaseModel):
    id: int
    job_name: str
    status: str
    started_at: str
    completed_at: Optional[str]
    records_processed: int
    records_updated: int
    records_failed: int
    error_message: Optional[str]
    execution_time_seconds: Optional[float]
    metadata: Optional[dict]
    created_at: str


class JobStatusResponse(BaseModel):
    job_name: str
    is_running: bool
    latest_execution: Optional[JobExecutionLogResponse]
    next_run_time: Optional[str]


class JobStatisticsResponse(BaseModel):
    total_users: int
    active_users: int
    latest_job: Optional[JobExecutionLogResponse]


class JobTriggerResponse(BaseModel):
    message: str
    job_execution_id: Optional[int]
    status: str


# ---------- API Endpoints ----------


@router.post(
    "/user-profile-sync/trigger",
    summary="Trigger User Profile Sync Job",
    description="Manually trigger the user profile sync job. Requires admin role.",
    response_model=JobTriggerResponse,
)
async def trigger_user_profile_sync(
    current_user: dict = Depends(require_role(["admin"])),
    scheduler: JobScheduler = Depends(get_job_scheduler),
):
    """
    Manually trigger the user profile sync job.

    This endpoint allows admins to immediately run the sync job instead of
    waiting for the scheduled execution.
    """
    try:
        # Run the job directly (it's async, so we can await it)
        # This allows triggering even if job isn't registered in scheduler
        await user_profile_sync_job()
        return JobTriggerResponse(
            message="User profile sync job triggered and completed successfully",
            status="completed",
        )
    except Exception as e:
        logger.exception("Error triggering user profile sync job: %s", e)
        raise HTTPException(status_code=500, detail=f"Failed to trigger job: {str(e)}")


@router.get(
    "/user-profile-sync/status",
    summary="Get User Profile Sync Job Status",
    description="Get the latest execution status of the user profile sync job.",
    response_model=JobStatusResponse,
)
async def get_user_profile_sync_status(
    current_user: dict = Depends(require_role(["admin"])),
    sync_repo: MySQLUserSyncRepository = Depends(get_sync_repo),
    scheduler: JobScheduler = Depends(get_job_scheduler),
):
    """Get the latest execution status of the user profile sync job."""
    job_name = "user_profile_sync"

    # Get latest execution log
    latest_execution = sync_repo.get_latest_job_execution(job_name)

    # Check if job is currently running
    job = scheduler.get_job(job_name)
    is_running = False
    next_run_time = None

    if job:
        is_running = job.next_run_time is not None
        if job.next_run_time:
            next_run_time = job.next_run_time.isoformat()

    latest_execution_response = None
    if latest_execution:
        latest_execution_response = JobExecutionLogResponse(**latest_execution)

    return JobStatusResponse(
        job_name=job_name,
        is_running=is_running,
        latest_execution=latest_execution_response,
        next_run_time=next_run_time,
    )


@router.get(
    "/user-profile-sync/history",
    summary="Get User Profile Sync Job History",
    description="Get execution history of the user profile sync job with pagination.",
    response_model=List[JobExecutionLogResponse],
)
async def get_user_profile_sync_history(
    limit: int = Query(50, ge=1, le=100, description="Number of records to return"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    status: Optional[str] = Query(None, description="Filter by status: running, completed, failed, cancelled"),
    current_user: dict = Depends(require_role(["admin"])),
    sync_repo: MySQLUserSyncRepository = Depends(get_sync_repo),
):
    """Get execution history of the user profile sync job."""
    logs = sync_repo.get_job_execution_logs(job_name="user_profile_sync", status=status, limit=limit, offset=offset)

    return [JobExecutionLogResponse(**log) for log in logs]


@router.get(
    "/user-profile-sync/statistics",
    summary="Get User Profile Sync Statistics",
    description="Get statistics about user profile sync operations.",
    response_model=JobStatisticsResponse,
)
async def get_user_profile_sync_statistics(
    current_user: dict = Depends(require_role(["admin"])),
    sync_repo: MySQLUserSyncRepository = Depends(get_sync_repo),
):
    """Get statistics about user profile sync operations."""
    stats = sync_repo.get_sync_statistics()

    latest_job_response = None
    if stats.get("latest_job"):
        latest_job_response = JobExecutionLogResponse(**stats["latest_job"])

    return JobStatisticsResponse(
        total_users=stats.get("total_users", 0),
        active_users=stats.get("active_users", 0),
        latest_job=latest_job_response,
    )
