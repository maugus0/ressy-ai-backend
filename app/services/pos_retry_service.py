from typing import Any, Dict

from app.config import settings
from app.repositories.mysql_order_pos_sync_repo import MySQLOrderPOSSyncRepository
from app.repositories.mysql_pos_integration_repo import MySQLPOSIntegrationRepository
from app.services.pos_service import POSService
from app.utils.logging_config import get_logger

logger = get_logger(__name__)


class POSRetryService:
    def __init__(self):
        self.order_sync_repo = MySQLOrderPOSSyncRepository()
        self.pos_integration_repo = MySQLPOSIntegrationRepository()
        self.pos_service = POSService()

    def process_pending_retries(self) -> Dict[str, Any]:
        pending_records = self.order_sync_repo.get_pending_retries()
        processed = 0
        succeeded = 0
        failed = 0

        for record in pending_records:
            processed += 1
            if record["attempts"] >= settings.POS_MAX_RETRY_ATTEMPTS:
                self.order_sync_repo.update_sync_status(record["id"], status="FAILED")
                failed += 1
                continue

            try:
                pos_integration = self.pos_integration_repo.get_by_id(record["pos_integration_id"])
                if not pos_integration or not pos_integration.get("enabled"):
                    self.order_sync_repo.update_sync_status(
                        record["id"], status="FAILED", error="POS integration disabled or not found"
                    )
                    failed += 1
                    continue

                order, order_data, customization = self.pos_service._build_order_submission_context(record["order_id"])
                if not order:
                    self.order_sync_repo.update_sync_status(record["id"], status="FAILED", error="Order not found")
                    failed += 1
                    continue

                result = self.pos_service._process_integration_submission(
                    sync_id=record["id"],
                    order_id=record["order_id"],
                    restaurant_id=record["restaurant_id"],
                    pos_integration=pos_integration,
                    order=order,
                    order_data=order_data,
                    customization=customization,
                    idempotency_key=record.get("idempotency_key"),
                    attempt_count=record["attempts"] + 1,
                )

                if result.get("success"):
                    succeeded += 1
                elif not result.get("retry_scheduled"):
                    failed += 1
            except Exception as e:
                error_msg = str(e)
                logger.error(f"Retry failed for sync record {record['id']}: {error_msg}")
                self.order_sync_repo.update_sync_status(
                    record["id"], status="FAILED", error=error_msg, attempts=record["attempts"] + 1
                )
                failed += 1

        return {
            "processed": processed,
            "succeeded": succeeded,
            "failed": failed,
            "total_pending": len(pending_records),
        }
