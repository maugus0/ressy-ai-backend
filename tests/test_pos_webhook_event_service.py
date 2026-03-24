from __future__ import annotations

import base64
import hashlib
import hmac
import json
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from app.config import settings
from app.services.pos_webhook_event_service import POSWebhookEventService


class _FakeWebhookEventRepo:
    def __init__(self):
        self.events: Dict[int, Dict[str, Any]] = {}
        self.next_id = 1

    def get_by_provider_event(self, *, pos_type: str, provider_event_id: str) -> Optional[Dict[str, Any]]:
        for event in self.events.values():
            if event["pos_type"] == pos_type and event["provider_event_id"] == provider_event_id:
                return dict(event)
        return None

    def get_by_id(self, webhook_event_id: int) -> Optional[Dict[str, Any]]:
        event = self.events.get(webhook_event_id)
        return dict(event) if event else None

    def create_event(
        self,
        *,
        pos_type: str,
        provider_event_id: str,
        event_type: str,
        external_account_id: Optional[str],
        location_id: Optional[str],
        payload: Dict[str, Any],
        last_retry_number: Optional[int],
        last_retry_reason: Optional[str],
    ) -> int:
        webhook_event_id = self.next_id
        self.next_id += 1
        self.events[webhook_event_id] = {
            "id": webhook_event_id,
            "pos_type": pos_type,
            "provider_event_id": provider_event_id,
            "event_type": event_type,
            "external_account_id": external_account_id,
            "location_id": location_id,
            "status": "PENDING",
            "delivery_count": 1,
            "processing_attempts": 0,
            "last_retry_number": last_retry_number,
            "last_retry_reason": last_retry_reason,
            "next_retry_at": None,
            "processed_at": None,
            "last_error": None,
            "payload": payload,
            "updated_at": datetime.now(timezone.utc),
        }
        return webhook_event_id

    def record_delivery(
        self,
        webhook_event_id: int,
        *,
        status: Optional[str] = None,
        last_retry_number: Optional[int] = None,
        last_retry_reason: Optional[str] = None,
        payload: Optional[Dict[str, Any]] = None,
        external_account_id: Optional[str] = None,
        location_id: Optional[str] = None,
    ) -> int:
        event = self.events[webhook_event_id]
        event["delivery_count"] += 1
        if status is not None:
            event["status"] = status
        if last_retry_number is not None:
            event["last_retry_number"] = last_retry_number
        if last_retry_reason is not None:
            event["last_retry_reason"] = last_retry_reason
        if payload is not None:
            event["payload"] = payload
        if external_account_id is not None:
            event["external_account_id"] = external_account_id
        if location_id is not None:
            event["location_id"] = location_id
        event["updated_at"] = datetime.now(timezone.utc)
        return 1

    def mark_processing(self, webhook_event_id: int) -> int:
        event = self.events[webhook_event_id]
        event["status"] = "PROCESSING"
        event["processing_attempts"] += 1
        event["next_retry_at"] = None
        event["updated_at"] = datetime.now(timezone.utc)
        return 1

    def mark_processed(self, webhook_event_id: int) -> int:
        event = self.events[webhook_event_id]
        event["status"] = "PROCESSED"
        event["processed_at"] = datetime.now(timezone.utc)
        event["next_retry_at"] = None
        event["last_error"] = None
        event["updated_at"] = datetime.now(timezone.utc)
        return 1

    def mark_ignored(self, webhook_event_id: int, *, error: Optional[str] = None) -> int:
        event = self.events[webhook_event_id]
        event["status"] = "IGNORED"
        event["processed_at"] = datetime.now(timezone.utc)
        event["next_retry_at"] = None
        event["last_error"] = error
        event["updated_at"] = datetime.now(timezone.utc)
        return 1

    def mark_failed(self, webhook_event_id: int, *, error: str, next_retry_at) -> int:
        event = self.events[webhook_event_id]
        event["status"] = "FAILED"
        event["last_error"] = error
        event["next_retry_at"] = next_retry_at
        event["updated_at"] = datetime.now(timezone.utc)
        return 1

    def list_pending(
        self,
        *,
        limit: int = 50,
        pos_type: Optional[str] = None,
        stale_processing_minutes: int = 0,
    ) -> List[Dict[str, Any]]:
        results = [
            dict(event)
            for event in self.events.values()
            if (
                event["status"] in {"PENDING", "FAILED"}
                or (
                    event["status"] == "PROCESSING"
                    and stale_processing_minutes > 0
                    and event.get("updated_at") is not None
                    and event["updated_at"] <= datetime.now(timezone.utc) - timedelta(minutes=stale_processing_minutes)
                )
            )
            and (pos_type is None or event["pos_type"] == pos_type)
        ]
        return results[:limit]


class _FakePOSIntegrationRepo:
    def __init__(self, *, by_location=None, by_account=None, all_enabled=None):
        self.by_location = by_location or {}
        self.by_account = by_account or {}
        self.all_enabled = all_enabled or []

    def list_enabled_by_location(self, *, pos_type: str, location_id: str):
        return list(self.by_location.get((pos_type, location_id), []))

    def list_enabled_by_account(self, *, pos_type: str, external_account_id: str):
        return list(self.by_account.get((pos_type, external_account_id), []))

    def list_all_enabled_integrations(self, pos_type: Optional[str] = None):
        if pos_type is None:
            return list(self.all_enabled)
        return [item for item in self.all_enabled if item.get("pos_type") == pos_type]


class _FakeImportService:
    def __init__(self, *, should_fail: bool = False):
        self.should_fail = should_fail
        self.calls: List[Dict[str, Any]] = []

    def sync_integration(self, integration_id: int, *, trigger_source: str, triggered_by: str):
        self.calls.append(
            {
                "method": "catalog",
                "integration_id": integration_id,
                "trigger_source": trigger_source,
                "triggered_by": triggered_by,
            }
        )
        if self.should_fail:
            return {"success": False, "status": "FAILED", "error": "sync failed"}
        return {"success": True, "status": "SUCCEEDED"}

    def sync_integration_availability(
        self,
        integration_id: int,
        *,
        begin_time: Optional[str] = None,
        trigger_source: str,
        triggered_by: str,
    ):
        self.calls.append(
            {
                "method": "availability",
                "integration_id": integration_id,
                "begin_time": begin_time,
                "trigger_source": trigger_source,
                "triggered_by": triggered_by,
            }
        )
        if self.should_fail:
            return {"success": False, "status": "FAILED", "error": "sync failed"}
        return {"success": True, "status": "SUCCEEDED"}


def _build_service(
    *,
    event_repo: Optional[_FakeWebhookEventRepo] = None,
    pos_integration_repo: Optional[_FakePOSIntegrationRepo] = None,
    import_service: Optional[_FakeImportService] = None,
) -> POSWebhookEventService:
    service = POSWebhookEventService.__new__(POSWebhookEventService)
    service.event_repo = event_repo or _FakeWebhookEventRepo()
    service.pos_integration_repo = pos_integration_repo or _FakePOSIntegrationRepo()
    service.import_service = import_service or _FakeImportService()
    return service


def _sign_square_payload(payload: Dict[str, Any], *, signature_key: str, notification_url: str) -> tuple[bytes, str]:
    raw_body = json.dumps(payload).encode("utf-8")
    digest = hmac.new(
        signature_key.encode("utf-8"),
        f"{notification_url}{raw_body.decode('utf-8')}".encode("utf-8"),
        hashlib.sha256,
    ).digest()
    return raw_body, base64.b64encode(digest).decode("utf-8")


def test_ingest_square_webhook_deduplicates_processed_retries(monkeypatch):
    monkeypatch.setattr(settings, "SQUARE_WEBHOOK_SIGNATURE_KEY", "test-key")
    monkeypatch.setattr(settings, "SQUARE_WEBHOOK_NOTIFICATION_URL", "https://example.com/api/v1/webhooks/square")

    service = _build_service()

    payload = {
        "event_id": "evt-1",
        "type": "inventory.count.updated",
        "merchant_id": "merchant-1",
        "data": {
            "object": {
                "inventory_count": {
                    "location_id": "loc-1",
                }
            }
        },
    }
    raw_body, signature = _sign_square_payload(
        payload,
        signature_key=settings.SQUARE_WEBHOOK_SIGNATURE_KEY,
        notification_url=settings.SQUARE_WEBHOOK_NOTIFICATION_URL,
    )

    first = service.ingest_square_webhook(
        raw_body=raw_body,
        headers={"x-square-hmacsha256-signature": signature},
    )
    assert first["is_duplicate"] is False
    assert first["should_process"] is True

    service.event_repo.mark_processed(int(first["webhook_event_id"]))

    second = service.ingest_square_webhook(
        raw_body=raw_body,
        headers={
            "x-square-hmacsha256-signature": signature,
            "square-retry-number": "2",
            "square-retry-reason": "TIMEOUT",
        },
    )

    stored = service.event_repo.get_by_id(int(first["webhook_event_id"]))
    assert second["is_duplicate"] is True
    assert second["should_process"] is False
    assert stored["delivery_count"] == 2
    assert stored["last_retry_number"] == 2
    assert stored["last_retry_reason"] == "TIMEOUT"


def test_process_square_event_routes_by_location_and_syncs_integration(monkeypatch):
    monkeypatch.setattr(settings, "POS_WEBHOOK_MAX_RETRY_ATTEMPTS", 3)

    service = _build_service(
        pos_integration_repo=_FakePOSIntegrationRepo(
            by_location={("SQUARE", "loc-1"): [{"id": 11, "pos_type": "SQUARE"}]}
        ),
        import_service=_FakeImportService(),
    )
    webhook_event_id = service.event_repo.create_event(
        pos_type="SQUARE",
        provider_event_id="evt-2",
        event_type="catalog.version.updated",
        external_account_id="merchant-1",
        location_id="loc-1",
        payload={
            "type": "catalog.version.updated",
            "data": {"object": {"catalog_version": {"updated_at": "2026-03-24T14:22:21.109Z"}}},
        },
        last_retry_number=None,
        last_retry_reason=None,
    )

    result = service.process_square_event(webhook_event_id)

    assert result["status"] == "PROCESSED"
    assert result["sync_results"] == [{"pos_integration_id": 11, "success": True, "status": "SUCCEEDED"}]
    assert service.import_service.calls == [
        {
            "method": "catalog",
            "integration_id": 11,
            "trigger_source": "WEBHOOK",
            "triggered_by": "square:evt-2",
        }
    ]
    assert service.event_repo.get_by_id(webhook_event_id)["status"] == "PROCESSED"


def test_process_inventory_count_event_routes_to_availability_refresh(monkeypatch):
    monkeypatch.setattr(settings, "POS_WEBHOOK_MAX_RETRY_ATTEMPTS", 3)

    service = _build_service(
        pos_integration_repo=_FakePOSIntegrationRepo(
            by_location={("SQUARE", "loc-1"): [{"id": 21, "pos_type": "SQUARE"}]}
        ),
        import_service=_FakeImportService(),
    )
    webhook_event_id = service.event_repo.create_event(
        pos_type="SQUARE",
        provider_event_id="evt-availability",
        event_type="inventory.count.updated",
        external_account_id="merchant-1",
        location_id="loc-1",
        payload={
            "type": "inventory.count.updated",
            "data": {"object": {"inventory_count": {"calculated_at": "2026-03-24T14:30:00.000Z"}}},
        },
        last_retry_number=None,
        last_retry_reason=None,
    )

    result = service.process_square_event(webhook_event_id)

    assert result["status"] == "PROCESSED"
    assert service.import_service.calls == [
        {
            "method": "availability",
            "integration_id": 21,
            "begin_time": "2026-03-24T14:30:00.000Z",
            "trigger_source": "WEBHOOK",
            "triggered_by": "square:evt-availability",
        }
    ]


def test_process_square_event_schedules_retry_on_sync_failure(monkeypatch):
    monkeypatch.setattr(settings, "POS_WEBHOOK_MAX_RETRY_ATTEMPTS", 3)
    monkeypatch.setattr(settings, "POS_WEBHOOK_RETRY_BASE_MINUTES", 1)

    service = _build_service(
        pos_integration_repo=_FakePOSIntegrationRepo(
            by_location={("SQUARE", "loc-1"): [{"id": 12, "pos_type": "SQUARE"}]}
        ),
        import_service=_FakeImportService(should_fail=True),
    )
    webhook_event_id = service.event_repo.create_event(
        pos_type="SQUARE",
        provider_event_id="evt-3",
        event_type="catalog.version.updated",
        external_account_id="merchant-1",
        location_id="loc-1",
        payload={
            "type": "catalog.version.updated",
            "data": {"object": {"catalog_version": {"updated_at": "2026-03-24T14:22:21.109Z"}}},
        },
        last_retry_number=None,
        last_retry_reason=None,
    )

    result = service.process_square_event(webhook_event_id)

    stored = service.event_repo.get_by_id(webhook_event_id)
    assert result["status"] == "FAILED"
    assert stored["status"] == "FAILED"
    assert stored["last_error"] == "Webhook-triggered sync failed for integration_id=12: sync failed"
    assert stored["next_retry_at"] is not None


def test_ingest_square_webhook_requeues_stale_processing_event(monkeypatch):
    monkeypatch.setattr(settings, "SQUARE_WEBHOOK_SIGNATURE_KEY", "test-key")
    monkeypatch.setattr(settings, "SQUARE_WEBHOOK_NOTIFICATION_URL", "https://example.com/api/v1/webhooks/square")
    monkeypatch.setattr(settings, "POS_WEBHOOK_PROCESSING_STALE_MINUTES", 5)

    service = _build_service()
    webhook_event_id = service.event_repo.create_event(
        pos_type="SQUARE",
        provider_event_id="evt-stale",
        event_type="inventory.count.updated",
        external_account_id="merchant-1",
        location_id="loc-1",
        payload={"event_id": "evt-stale", "type": "inventory.count.updated"},
        last_retry_number=None,
        last_retry_reason=None,
    )
    service.event_repo.mark_processing(webhook_event_id)
    service.event_repo.events[webhook_event_id]["updated_at"] = datetime(2000, 1, 1, tzinfo=timezone.utc)

    payload = {
        "event_id": "evt-stale",
        "type": "inventory.count.updated",
        "merchant_id": "merchant-1",
        "data": {"object": {"inventory_count": {"location_id": "loc-1"}}},
    }
    raw_body, signature = _sign_square_payload(
        payload,
        signature_key=settings.SQUARE_WEBHOOK_SIGNATURE_KEY,
        notification_url=settings.SQUARE_WEBHOOK_NOTIFICATION_URL,
    )

    result = service.ingest_square_webhook(
        raw_body=raw_body,
        headers={"x-square-hmacsha256-signature": signature},
    )

    stored = service.event_repo.get_by_id(webhook_event_id)
    assert result["is_duplicate"] is True
    assert result["should_process"] is True
    assert stored["status"] == "PENDING"
