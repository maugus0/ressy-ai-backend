"""
Webhook ingestion and processing for POS providers.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterable, Optional

from app.config import settings
from app.repositories.mysql_pos_integration_repo import MySQLPOSIntegrationRepository
from app.repositories.mysql_pos_webhook_event_repo import MySQLPOSWebhookEventRepository
from app.services.pos_catalog_import_service import POSCatalogImportService
from app.utils.logging_config import get_logger

logger = get_logger(__name__)


class POSWebhookEventService:
    """Validates, persists, and processes provider webhook events."""

    SQUARE_PATH = "/api/v1/webhooks/square"
    SQUARE_POS_TYPE = "SQUARE"
    SUPPORTED_SQUARE_EVENT_TYPES = {
        "catalog.version.updated",
        "inventory.count.updated",
    }

    def __init__(self):
        self.event_repo = MySQLPOSWebhookEventRepository()
        self.pos_integration_repo = MySQLPOSIntegrationRepository()
        self.import_service = POSCatalogImportService()

    @staticmethod
    def _coerce_utc_datetime(value: Any) -> Optional[datetime]:
        if isinstance(value, datetime):
            result = value
        elif value is None:
            return None
        else:
            try:
                result = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
            except (TypeError, ValueError):
                return None
        if result.tzinfo is None:
            return result.replace(tzinfo=timezone.utc)
        return result.astimezone(timezone.utc)

    def _get_square_notification_url(self) -> str:
        configured_url = str(settings.SQUARE_WEBHOOK_NOTIFICATION_URL or "").strip()
        if configured_url:
            return configured_url.rstrip("/")
        base_url = str(settings.PUBLIC_BASE_URL or "").strip().rstrip("/")
        if not base_url:
            raise ValueError("PUBLIC_BASE_URL must be configured to validate Square webhooks")
        return f"{base_url}{self.SQUARE_PATH}"

    def _verify_square_signature(self, raw_body: bytes, signature: Optional[str]) -> bool:
        signature_key = str(settings.SQUARE_WEBHOOK_SIGNATURE_KEY or "").strip()
        if not signature_key or not signature:
            return False
        notification_url = self._get_square_notification_url()
        body_text = raw_body.decode("utf-8")
        digest = hmac.new(
            signature_key.encode("utf-8"),
            f"{notification_url}{body_text}".encode("utf-8"),
            hashlib.sha256,
        ).digest()
        expected_signature = base64.b64encode(digest).decode("utf-8")
        return hmac.compare_digest(expected_signature, signature)

    @staticmethod
    def _extract_square_location_id(payload: Dict[str, Any]) -> Optional[str]:
        data = payload.get("data") or {}
        obj = data.get("object") or {}
        inventory_count = obj.get("inventory_count") or {}
        location_id = inventory_count.get("location_id") or obj.get("location_id")
        return str(location_id) if location_id else None

    @staticmethod
    def _parse_retry_number(headers: Dict[str, str]) -> Optional[int]:
        retry_number = headers.get("square-retry-number") or headers.get("x-square-retry-number")
        if retry_number is None:
            return None
        try:
            return int(retry_number)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _extract_square_event_fields(payload: Dict[str, Any]) -> Dict[str, Optional[str]]:
        return {
            "provider_event_id": payload.get("event_id") or payload.get("eventId"),
            "event_type": payload.get("type"),
            "external_account_id": payload.get("merchant_id") or payload.get("merchantId"),
            "location_id": POSWebhookEventService._extract_square_location_id(payload),
        }

    @staticmethod
    def _extract_square_begin_time(payload: Dict[str, Any]) -> Optional[str]:
        event_type = str(payload.get("type") or "")
        data = payload.get("data") or {}
        obj = data.get("object") or {}
        if event_type == "catalog.version.updated":
            catalog_version = obj.get("catalog_version") or {}
            timestamp = catalog_version.get("updated_at")
            return str(timestamp) if timestamp else None
        if event_type == "inventory.count.updated":
            inventory_count = obj.get("inventory_count") or {}
            timestamp = (
                inventory_count.get("calculated_at") or inventory_count.get("occurred_at") or payload.get("created_at")
            )
            return str(timestamp) if timestamp else None
        return None

    def _is_processing_stale(self, event: Dict[str, Any]) -> bool:
        if str(event.get("status") or "") != "PROCESSING":
            return False
        updated_at = self._coerce_utc_datetime(event.get("updated_at"))
        if updated_at is None:
            return True
        stale_after = timedelta(minutes=settings.POS_WEBHOOK_PROCESSING_STALE_MINUTES)
        return updated_at <= datetime.now(timezone.utc) - stale_after

    def ingest_square_webhook(self, *, raw_body: bytes, headers: Dict[str, str]) -> Dict[str, Any]:
        normalized_headers = {str(key).lower(): value for key, value in headers.items()}
        signature = normalized_headers.get("x-square-hmacsha256-signature")
        if not self._verify_square_signature(raw_body, signature):
            raise ValueError("Invalid Square webhook signature")

        try:
            payload = json.loads(raw_body.decode("utf-8"))
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            raise ValueError("Invalid Square webhook payload") from exc

        event_fields = self._extract_square_event_fields(payload)
        provider_event_id = event_fields.get("provider_event_id")
        event_type = event_fields.get("event_type")
        if not provider_event_id or not event_type:
            raise ValueError("Square webhook payload is missing event_id or type")

        retry_number = self._parse_retry_number(normalized_headers)
        retry_reason = normalized_headers.get("square-retry-reason") or normalized_headers.get("x-square-retry-reason")
        existing = self.event_repo.get_by_provider_event(
            pos_type=self.SQUARE_POS_TYPE,
            provider_event_id=str(provider_event_id),
        )
        should_process = True
        is_duplicate = existing is not None
        if existing:
            status = existing.get("status")
            should_process = status in {"PENDING", "FAILED"} or self._is_processing_stale(existing)
            self.event_repo.record_delivery(
                int(existing["id"]),
                status="PENDING" if should_process else None,
                last_retry_number=retry_number,
                last_retry_reason=retry_reason,
                payload=payload,
                external_account_id=event_fields.get("external_account_id"),
                location_id=event_fields.get("location_id"),
            )
            webhook_event_id = int(existing["id"])
        else:
            webhook_event_id = self.event_repo.create_event(
                pos_type=self.SQUARE_POS_TYPE,
                provider_event_id=str(provider_event_id),
                event_type=str(event_type),
                external_account_id=(
                    str(event_fields["external_account_id"]) if event_fields.get("external_account_id") else None
                ),
                location_id=str(event_fields["location_id"]) if event_fields.get("location_id") else None,
                payload=payload,
                last_retry_number=retry_number,
                last_retry_reason=retry_reason,
            )

        return {
            "webhook_event_id": webhook_event_id,
            "provider_event_id": str(provider_event_id),
            "event_type": str(event_type),
            "is_duplicate": is_duplicate,
            "should_process": should_process,
        }

    def _get_integrations_for_square_event(self, event: Dict[str, Any]) -> list[Dict[str, Any]]:
        event_type = str(event.get("event_type") or "")
        location_id = event.get("location_id")
        external_account_id = event.get("external_account_id")

        integrations: list[Dict[str, Any]] = []
        if location_id:
            integrations = self.pos_integration_repo.list_enabled_by_location(
                pos_type=self.SQUARE_POS_TYPE,
                location_id=str(location_id),
            )
            if integrations:
                return integrations

        if external_account_id:
            integrations = self.pos_integration_repo.list_enabled_by_account(
                pos_type=self.SQUARE_POS_TYPE,
                external_account_id=str(external_account_id),
            )
            if integrations:
                return integrations

        # Catalog version events apply at the account level. If older integrations have not yet
        # been backfilled with external_account_id, fall back to enabled Square integrations.
        if event_type == "catalog.version.updated":
            return self.pos_integration_repo.list_all_enabled_integrations(pos_type=self.SQUARE_POS_TYPE)

        return []

    @staticmethod
    def _iter_supported_square_event_types() -> Iterable[str]:
        return POSWebhookEventService.SUPPORTED_SQUARE_EVENT_TYPES

    def process_square_event(self, webhook_event_id: int) -> Dict[str, Any]:
        event = self.event_repo.get_by_id(webhook_event_id)
        if not event:
            raise ValueError(f"Webhook event {webhook_event_id} not found")

        status = str(event.get("status") or "")
        if status in {"PROCESSED", "IGNORED"}:
            return {
                "webhook_event_id": webhook_event_id,
                "status": status,
            }

        event_type = str(event.get("event_type") or "")
        if event_type not in self._iter_supported_square_event_types():
            self.event_repo.mark_ignored(
                webhook_event_id,
                error=f"Unsupported Square webhook event type: {event_type}",
            )
            return {
                "webhook_event_id": webhook_event_id,
                "status": "IGNORED",
            }

        attempts = int(event.get("processing_attempts") or 0) + 1
        if attempts > settings.POS_WEBHOOK_MAX_RETRY_ATTEMPTS:
            self.event_repo.mark_ignored(
                webhook_event_id,
                error=f"Exceeded maximum webhook processing attempts for event type {event_type}",
            )
            return {
                "webhook_event_id": webhook_event_id,
                "status": "IGNORED",
            }

        self.event_repo.mark_processing(webhook_event_id)

        try:
            integrations = self._get_integrations_for_square_event(event)
            if not integrations:
                self.event_repo.mark_ignored(
                    webhook_event_id,
                    error="No enabled POS integration matched this Square webhook",
                )
                return {
                    "webhook_event_id": webhook_event_id,
                    "status": "IGNORED",
                }

            sync_results = []
            payload = event.get("payload") or {}
            begin_time = self._extract_square_begin_time(payload if isinstance(payload, dict) else {})
            for integration in integrations:
                if event_type == "inventory.count.updated":
                    result = self.import_service.sync_integration_availability(
                        int(integration["id"]),
                        begin_time=begin_time,
                        trigger_source="WEBHOOK",
                        triggered_by=f"square:{event.get('provider_event_id')}",
                    )
                else:
                    result = self.import_service.sync_integration(
                        int(integration["id"]),
                        trigger_source="WEBHOOK",
                        triggered_by=f"square:{event.get('provider_event_id')}",
                    )
                sync_results.append(
                    {
                        "pos_integration_id": integration.get("id"),
                        "success": result.get("success", False),
                        "status": result.get("status"),
                    }
                )
                if not result.get("success", False):
                    raise RuntimeError(
                        f"Webhook-triggered sync failed for integration_id={integration.get('id')}: {result.get('error')}"
                    )

            self.event_repo.mark_processed(webhook_event_id)
            return {
                "webhook_event_id": webhook_event_id,
                "status": "PROCESSED",
                "sync_results": sync_results,
            }
        except Exception as exc:
            retry_attempts = attempts
            if retry_attempts >= settings.POS_WEBHOOK_MAX_RETRY_ATTEMPTS:
                self.event_repo.mark_ignored(webhook_event_id, error=str(exc))
                logger.exception("POS webhook processing exhausted retries event_id=%s: %s", webhook_event_id, exc)
                return {
                    "webhook_event_id": webhook_event_id,
                    "status": "IGNORED",
                    "error": str(exc),
                }

            next_retry_at = datetime.now(timezone.utc) + timedelta(
                minutes=settings.POS_WEBHOOK_RETRY_BASE_MINUTES * (2 ** (retry_attempts - 1))
            )
            self.event_repo.mark_failed(
                webhook_event_id,
                error=str(exc),
                next_retry_at=next_retry_at,
            )
            logger.exception("POS webhook processing failed event_id=%s: %s", webhook_event_id, exc)
            return {
                "webhook_event_id": webhook_event_id,
                "status": "FAILED",
                "error": str(exc),
                "next_retry_at": next_retry_at.isoformat(),
            }

    def process_pending_events(self, *, limit: int = 50, pos_type: Optional[str] = None) -> Dict[str, Any]:
        pending_events = self.event_repo.list_pending(
            limit=limit,
            pos_type=pos_type,
            stale_processing_minutes=settings.POS_WEBHOOK_PROCESSING_STALE_MINUTES,
        )
        processed = 0
        succeeded = 0
        failed = 0
        ignored = 0

        for event in pending_events:
            result = self.process_square_event(int(event["id"]))
            processed += 1
            status = result.get("status")
            if status == "PROCESSED":
                succeeded += 1
            elif status == "IGNORED":
                ignored += 1
            else:
                failed += 1

        return {
            "processed": processed,
            "succeeded": succeeded,
            "failed": failed,
            "ignored": ignored,
            "total_pending": len(pending_events),
        }
