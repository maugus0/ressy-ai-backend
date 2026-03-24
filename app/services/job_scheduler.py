"""
Job Scheduler Service for managing scheduled background jobs.

Uses APScheduler to manage periodic tasks like user profile synchronization.
"""

import asyncio
from typing import Callable, Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app.utils.logging_config import get_logger

logger = get_logger(__name__)


class JobScheduler:
    """
    Job scheduler for managing background tasks.

    Uses APScheduler with AsyncIOScheduler for async job execution.
    Supports interval-based and cron-style scheduling.
    """

    _instance: Optional["JobScheduler"] = None
    _lock: Optional[asyncio.Lock] = None

    def __new__(cls):
        """Singleton pattern for job scheduler."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        """Initialize the job scheduler."""
        if self._initialized:
            return
        self._initialized = True
        self.scheduler: Optional[AsyncIOScheduler] = None
        self._jobs_registered = False

    async def start(self):
        """Start the job scheduler."""
        if self.scheduler is not None and self.scheduler.running:
            logger.warning("[JobScheduler] Scheduler already running")
            return

        try:
            self.scheduler = AsyncIOScheduler()
            self.scheduler.start()
            logger.info("[JobScheduler] Scheduler started successfully")
        except Exception as e:
            logger.exception("[JobScheduler] Failed to start scheduler: %s", e)
            raise

    async def shutdown(self):
        """Shutdown the job scheduler gracefully."""
        if self.scheduler is None:
            return

        try:
            if self.scheduler.running:
                await asyncio.to_thread(self.scheduler.shutdown, wait=True)
                logger.info("[JobScheduler] Scheduler shut down successfully")
            self.scheduler = None
            self._jobs_registered = False
        except Exception as e:
            logger.exception("[JobScheduler] Error during scheduler shutdown: %s", e)

    def register_job(
        self,
        job_id: str,
        func: Callable,
        trigger: IntervalTrigger,
        replace_existing: bool = True,
    ):
        """
        Register a job with the scheduler.

        Args:
            job_id: Unique identifier for the job
            func: Async function to execute
            trigger: APScheduler trigger (IntervalTrigger, CronTrigger, etc.)
            replace_existing: Whether to replace existing job with same ID
        """
        if self.scheduler is None:
            raise RuntimeError("Scheduler not started. Call start() first.")

        try:
            self.scheduler.add_job(
                func=func,
                trigger=trigger,
                id=job_id,
                replace_existing=replace_existing,
                max_instances=1,  # Prevent concurrent executions of same job
            )
            logger.info("[JobScheduler] Registered job: %s", job_id)
        except Exception as e:
            logger.exception("[JobScheduler] Failed to register job %s: %s", job_id, e)
            raise

    def remove_job(self, job_id: str):
        """Remove a job from the scheduler."""
        if self.scheduler is None:
            return

        try:
            self.scheduler.remove_job(job_id)
            logger.info("[JobScheduler] Removed job: %s", job_id)
        except Exception as e:
            logger.warning("[JobScheduler] Failed to remove job %s: %s", job_id, e)

    def get_job(self, job_id: str):
        """Get a job by ID."""
        if self.scheduler is None:
            return None
        return self.scheduler.get_job(job_id)

    def list_jobs(self):
        """List all registered jobs."""
        if self.scheduler is None:
            return []
        return self.scheduler.get_jobs()

    def is_running(self) -> bool:
        """Check if scheduler is running."""
        return self.scheduler is not None and self.scheduler.running

    async def trigger_job(self, job_id: str):
        """Manually trigger a job execution."""
        if self.scheduler is None:
            raise RuntimeError("Scheduler not started")

        job = self.get_job(job_id)
        if job is None:
            raise ValueError(f"Job {job_id} not found")

        try:
            # Trigger the job function directly
            if asyncio.iscoroutinefunction(job.func):
                await job.func()
            else:
                job.func()
            logger.info("[JobScheduler] Manually triggered job: %s", job_id)
        except Exception as e:
            logger.exception("[JobScheduler] Error triggering job %s: %s", job_id, e)
            raise
