from app.config import settings
from app.services.pos_retry_service import POSRetryService


def test_process_pending_retries_counts_early_failures_as_processed(monkeypatch):
    service = POSRetryService()
    service.order_sync_repo = type(
        "_FakeSyncRepo",
        (),
        {
            "get_pending_retries": lambda self: [
                {
                    "id": 1,
                    "order_id": 10,
                    "restaurant_id": 9,
                    "pos_integration_id": 7,
                    "attempts": settings.POS_MAX_RETRY_ATTEMPTS,
                }
            ],
            "update_sync_status": lambda self, sync_id, **kwargs: 1,
        },
    )()

    result = service.process_pending_retries()

    assert result == {
        "processed": 1,
        "succeeded": 0,
        "failed": 1,
        "total_pending": 1,
    }
