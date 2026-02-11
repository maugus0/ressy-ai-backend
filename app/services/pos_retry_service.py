import json
from datetime import datetime, timedelta
from typing import Any, Dict, List

from app.config import settings
from app.repositories.mysql_order_pos_sync_repo import MySQLOrderPOSSyncRepository
from app.repositories.mysql_order_repo import MySQLOrderRepository
from app.repositories.mysql_pos_integration_repo import MySQLPOSIntegrationRepository
from app.services.pos_service import POSService
from app.utils.logging_config import get_logger

logger = get_logger(__name__)


class POSRetryService:
    def __init__(self):
        self.order_sync_repo = MySQLOrderPOSSyncRepository()
        self.pos_integration_repo = MySQLPOSIntegrationRepository()
        self.order_repo = MySQLOrderRepository()
        self.pos_service = POSService()

    def process_pending_retries(self) -> Dict[str, Any]:
        pending_records = self.order_sync_repo.get_pending_retries()
        processed = 0
        succeeded = 0
        failed = 0

        for record in pending_records:
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

                order = self.order_repo.get_order_by_id(record["order_id"])
                if not order:
                    self.order_sync_repo.update_sync_status(
                        record["id"], status="FAILED", error="Order not found"
                    )
                    failed += 1
                    continue

                order_details = order.get("order_details", [])
                if isinstance(order_details, str):
                    try:
                        order_details = json.loads(order_details)
                    except (json.JSONDecodeError, TypeError):
                        order_details = []

                customization = order.get("customization", {})
                if isinstance(customization, str):
                    try:
                        customization = json.loads(customization)
                    except (json.JSONDecodeError, TypeError):
                        customization = {}

                customer_name = customization.get("customer_name") or ""
                customer_phone = customization.get("customer_phone") or ""
                customer_email = customization.get("customer_email") or ""

                order_data = {
                    "order_details": order_details,
                    "customer_name": customer_name,
                    "customer_phone": customer_phone,
                    "customer_email": customer_email,
                }

                pos_type = pos_integration.get("pos_type")
                idempotency_key = record.get("idempotency_key")

                if pos_type == "SQUARE":
                    response = self.pos_service._sync_to_square(
                        record["order_id"], pos_integration, order_data, idempotency_key
                    )
                    external_order_id = response.get("order", {}).get("id") if response.get("order") else None
                    self.order_sync_repo.update_sync_status(
                        record["id"],
                        status="CONFIRMED",
                        external_order_id=external_order_id,
                        attempts=record["attempts"] + 1,
                        response_payload=response,
                    )
                    succeeded += 1
                elif pos_type == "TOAST":
                    response = self.pos_service._sync_to_toast(
                        record["order_id"], pos_integration, order_data, idempotency_key
                    )
                    external_order_id = response.get("guid") if response.get("guid") else None
                    self.order_sync_repo.update_sync_status(
                        record["id"],
                        status="CONFIRMED",
                        external_order_id=external_order_id,
                        attempts=record["attempts"] + 1,
                        response_payload=response,
                    )
                    succeeded += 1
                else:
                    self.order_sync_repo.update_sync_status(
                        record["id"],
                        status="FAILED",
                        error=f"Unknown POS type: {pos_type}",
                        attempts=record["attempts"] + 1,
                    )
                    failed += 1

                processed += 1
            except Exception as e:
                error_msg = str(e)
                logger.error(f"Retry failed for sync record {record['id']}: {error_msg}")
                new_attempts = record["attempts"] + 1
                if new_attempts >= settings.POS_MAX_RETRY_ATTEMPTS:
                    self.order_sync_repo.update_sync_status(
                        record["id"], status="FAILED", error=error_msg, attempts=new_attempts
                    )
                    failed += 1
                else:
                    retry_minutes = settings.POS_RETRY_BASE_MINUTES * (2 ** new_attempts)
                    next_retry = datetime.now() + timedelta(minutes=retry_minutes)
                    self.order_sync_repo.update_sync_status(
                        record["id"],
                        status="PENDING",
                        error=error_msg,
                        attempts=new_attempts,
                        next_retry_at=next_retry,
                    )
                processed += 1

        return {
            "processed": processed,
            "succeeded": succeeded,
            "failed": failed,
            "total_pending": len(pending_records),
        }
