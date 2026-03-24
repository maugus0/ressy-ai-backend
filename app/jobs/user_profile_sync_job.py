"""
User Profile Sync Job.

Scheduled job that periodically updates user profiles by aggregating data
from Orders, Reservations, Calls, and User_Restaurant_Metadata.
"""

import time
from datetime import datetime, timedelta
from typing import Optional

from app.config import settings
from app.repositories.mysql_user_sync_repo import MySQLUserSyncRepository
from app.services.user_profile_enrichment_service import UserProfileEnrichmentService
from app.utils.logging_config import get_logger

logger = get_logger(__name__)


async def user_profile_sync_job():
    """
    Scheduled job to sync user profiles.

    This job:
    1. Gets batch of users needing sync
    2. Enriches each user's profile with aggregated data
    3. Updates user records
    4. Logs execution statistics
    """
    if not settings.USER_PROFILE_SYNC_ENABLED:
        logger.info("[UserProfileSync] Job disabled, skipping execution")
        return

    sync_repo = MySQLUserSyncRepository()
    enrichment_service = UserProfileEnrichmentService()

    job_name = "user_profile_sync"
    log_id: Optional[int] = None
    start_time = time.time()

    try:
        # Create job execution log
        log_id = sync_repo.create_job_execution_log(
            job_name=job_name,
            status="running",
            metadata={
                "batch_size": settings.USER_PROFILE_SYNC_BATCH_SIZE,
                "conflict_strategy": settings.USER_PROFILE_SYNC_CONFLICT_STRATEGY,
            },
        )
        logger.info("[UserProfileSync] Job started, log_id=%s", log_id)

        # Get users needing sync
        last_sync_window = datetime.now() - timedelta(hours=settings.USER_PROFILE_SYNC_LAST_SYNC_WINDOW_HOURS)
        users_to_sync = sync_repo.get_users_needing_sync(
            limit=settings.USER_PROFILE_SYNC_BATCH_SIZE,
            last_sync_before=last_sync_window,
        )

        if not users_to_sync:
            logger.info("[UserProfileSync] No users need syncing")
            execution_time = time.time() - start_time
            if log_id:
                sync_repo.update_job_execution_log(
                    log_id=log_id,
                    status="completed",
                    records_processed=0,
                    records_updated=0,
                    records_failed=0,
                    execution_time_seconds=execution_time,
                )
            return

        logger.info("[UserProfileSync] Processing %d users for sync", len(users_to_sync))

        # Process each user
        records_processed = 0
        records_updated = 0
        records_failed = 0

        for user_record in users_to_sync:
            user_id = user_record.get("user_id")
            if not user_id:
                continue

            records_processed += 1

            try:
                # Enrich user profile
                result = enrichment_service.enrich_user_profile(
                    user_id=user_id,
                    conflict_strategy=settings.USER_PROFILE_SYNC_CONFLICT_STRATEGY,
                )

                if result["success"]:
                    if result.get("updated_fields"):
                        records_updated += 1
                        logger.debug(
                            "[UserProfileSync] Updated user_id=%s, fields=%s",
                            user_id,
                            result["updated_fields"],
                        )
                    else:
                        # User processed but no updates needed
                        logger.debug(
                            "[UserProfileSync] User_id=%s processed, no updates needed",
                            user_id,
                        )
                else:
                    records_failed += 1
                    logger.warning(
                        "[UserProfileSync] Failed to enrich user_id=%s: %s",
                        user_id,
                        result.get("error"),
                    )

            except Exception as e:
                records_failed += 1
                logger.exception("[UserProfileSync] Error processing user_id=%s: %s", user_id, e)

        # Update job execution log
        execution_time = time.time() - start_time
        if log_id:
            sync_repo.update_job_execution_log(
                log_id=log_id,
                status="completed",
                records_processed=records_processed,
                records_updated=records_updated,
                records_failed=records_failed,
                execution_time_seconds=round(execution_time, 2),
            )

        logger.info(
            "[UserProfileSync] Job completed: processed=%d, updated=%d, failed=%d, time=%.2fs",
            records_processed,
            records_updated,
            records_failed,
            execution_time,
        )

    except Exception as e:
        execution_time = time.time() - start_time
        error_message = str(e)
        logger.exception("[UserProfileSync] Job failed: %s", error_message)

        if log_id:
            sync_repo.update_job_execution_log(
                log_id=log_id,
                status="failed",
                error_message=error_message,
                execution_time_seconds=round(execution_time, 2),
            )

        raise
