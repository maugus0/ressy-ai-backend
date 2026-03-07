"""
Background scheduler service for syncing Square catalog to menu_pos_mapping.
Runs on a configurable schedule using APScheduler.
"""

import threading
from typing import Optional

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app.config import settings
from app.services.square_catalog_sync_service import SquareCatalogSyncService
from app.utils.logging_config import get_logger

logger = get_logger(__name__)


class SquareCatalogBackgroundSync:
    """Background service for periodically syncing Square catalog to menu_pos_mapping."""

    _instance: Optional["SquareCatalogBackgroundSync"] = None
    _lock = threading.Lock()

    def __new__(cls):
        """Singleton pattern to ensure only one scheduler instance."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self.scheduler: Optional[BackgroundScheduler] = None
        self.sync_service = SquareCatalogSyncService()
        self._running = False

    def start(self):
        """Start the background scheduler."""
        if self._running:
            logger.warning("[Square Catalog Background Sync] Scheduler is already running")
            return
        
        try:
            self.scheduler = BackgroundScheduler()
            
            # Schedule the sync job
            interval_minutes = settings.SQUARE_CATALOG_SYNC_INTERVAL_MINUTES
            self.scheduler.add_job(
                self._sync_job,
                trigger=IntervalTrigger(minutes=interval_minutes),
                id="square_catalog_sync",
                name="Square Catalog to Menu POS Mapping Sync",
                replace_existing=True,
            )
            
            self.scheduler.start()
            self._running = True
            logger.info(
                f"[Square Catalog Background Sync] Started scheduler with interval: {interval_minutes} minutes"
            )
        except Exception as e:
            logger.exception(f"[Square Catalog Background Sync] Error starting scheduler: {e}")
            self._running = False

    def stop(self):
        """Stop the background scheduler."""
        if not self._running or not self.scheduler:
            logger.warning("[Square Catalog Background Sync] Scheduler is not running")
            return
        
        try:
            self.scheduler.shutdown(wait=True)
            self._running = False
            logger.info("[Square Catalog Background Sync] Stopped scheduler")
        except Exception as e:
            logger.exception(f"[Square Catalog Background Sync] Error stopping scheduler: {e}")

    def _sync_job(self):
        """Job function that runs on schedule to sync all restaurants."""
        try:
            logger.info("[Square Catalog Background Sync] Starting scheduled sync job")
            result = self.sync_service.sync_all_restaurants()
            logger.info(
                f"[Square Catalog Background Sync] Scheduled sync completed: "
                f"created={result.get('total_mappings_created', 0)}, "
                f"updated={result.get('total_mappings_updated', 0)}, "
                f"failed={result.get('total_failed', 0)}"
            )
        except Exception as e:
            logger.exception(f"[Square Catalog Background Sync] Error in scheduled sync job: {e}")

    def trigger_manual_sync(self, restaurant_id: Optional[int] = None) -> dict:
        """
        Manually trigger a sync (for testing or on-demand use).
        
        Args:
            restaurant_id: Optional restaurant ID to sync. If None, syncs all restaurants.
        
        Returns:
            Sync result dictionary
        """
        try:
            if restaurant_id:
                logger.info(f"[Square Catalog Background Sync] Manual sync triggered for restaurant {restaurant_id}")
                return self.sync_service.sync_restaurant_catalog(restaurant_id)
            else:
                logger.info("[Square Catalog Background Sync] Manual sync triggered for all restaurants")
                return self.sync_service.sync_all_restaurants()
        except Exception as e:
            logger.exception(f"[Square Catalog Background Sync] Error in manual sync: {e}")
            return {"success": False, "error": str(e)}
