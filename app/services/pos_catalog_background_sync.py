"""
Background scheduler service for asynchronous POS catalog imports.
"""

import threading
from typing import Optional

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app.config import settings
from app.services.pos_catalog_import_service import POSCatalogImportService
from app.services.pos_webhook_event_service import POSWebhookEventService
from app.utils.logging_config import get_logger

logger = get_logger(__name__)


class POSCatalogBackgroundSync:
    """Singleton scheduler for asynchronous POS catalog imports."""

    _instance: Optional["POSCatalogBackgroundSync"] = None
    _lock = threading.Lock()

    def __new__(cls):
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
        self.import_service = POSCatalogImportService()
        self.webhook_event_service = POSWebhookEventService()
        self._running = False

    def start(self):
        if self._running:
            logger.warning("[POS Catalog Background Sync] Scheduler is already running")
            return

        self.scheduler = BackgroundScheduler()
        interval_minutes = settings.POS_CATALOG_SYNC_INTERVAL_MINUTES
        self.scheduler.add_job(
            self._sync_job,
            trigger=IntervalTrigger(minutes=interval_minutes),
            id="pos_catalog_sync",
            name="POS Catalog Import Sync",
            replace_existing=True,
        )
        self.scheduler.add_job(
            self._process_webhook_events_job,
            trigger=IntervalTrigger(minutes=settings.POS_WEBHOOK_RETRY_INTERVAL_MINUTES),
            id="pos_webhook_retry",
            name="POS Webhook Retry Processing",
            replace_existing=True,
        )
        self.scheduler.start()
        self._running = True
        logger.info("[POS Catalog Background Sync] Started scheduler with interval=%s minutes", interval_minutes)

    def stop(self):
        if not self._running or not self.scheduler:
            logger.warning("[POS Catalog Background Sync] Scheduler is not running")
            return

        self.scheduler.shutdown(wait=True)
        self._running = False
        logger.info("[POS Catalog Background Sync] Stopped scheduler")

    def _sync_job(self):
        try:
            logger.info("[POS Catalog Background Sync] Starting scheduled POS catalog import")
            result = self.import_service.sync_all_enabled_integrations()
            logger.info(
                "[POS Catalog Background Sync] Scheduled import completed successful=%s failed=%s",
                result.get("successful", 0),
                result.get("failed", 0),
            )
        except Exception as exc:
            logger.exception("[POS Catalog Background Sync] Scheduled import failed: %s", exc)

    def _process_webhook_events_job(self):
        try:
            logger.info("[POS Catalog Background Sync] Processing pending POS webhook events")
            result = self.webhook_event_service.process_pending_events(pos_type="SQUARE")
            logger.info(
                "[POS Catalog Background Sync] Webhook processing completed processed=%s succeeded=%s failed=%s ignored=%s",
                result.get("processed", 0),
                result.get("succeeded", 0),
                result.get("failed", 0),
                result.get("ignored", 0),
            )
        except Exception as exc:
            logger.exception("[POS Catalog Background Sync] Webhook processing failed: %s", exc)

    def trigger_manual_sync(self, restaurant_id: Optional[int] = None, pos_type: Optional[str] = None) -> dict:
        if restaurant_id is not None:
            return self.import_service.sync_restaurant(restaurant_id, pos_type=pos_type)
        return self.import_service.sync_all_enabled_integrations(pos_type=pos_type)
