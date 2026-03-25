from app.integrations.pos.models import POSOrderSubmissionResult
from app.services.pos_service import POSService


class _FakeProvider:
    def __init__(self, result: POSOrderSubmissionResult) -> None:
        self.result = result
        self.calls = []

    def submit_pickup_order(self, integration, request, *, idempotency_key):
        self.calls.append(
            {
                "integration": integration,
                "request": request,
                "idempotency_key": idempotency_key,
            }
        )
        return self.result


class _FakeRegistry:
    def __init__(self, provider: _FakeProvider) -> None:
        self.provider = provider

    def get_provider(self, pos_type: str):
        assert pos_type == "SQUARE"
        return self.provider


def test_sync_to_square_returns_provider_submission_result(monkeypatch):
    service = POSService()
    expected = POSOrderSubmissionResult(
        external_order_id="ord-123",
        external_payment_id="pay-123",
        status="CONFIRMED",
        payload={"order_response": {"order": {"id": "ord-123"}}},
    )
    fake_provider = _FakeProvider(expected)
    service.provider_registry = _FakeRegistry(fake_provider)
    monkeypatch.setattr(service, "_build_provider_order_request", lambda **kwargs: {"request": "payload"})

    result = service._sync_to_square(
        order_id=42,
        pos_integration={"id": 1},
        order_data={"order_details": []},
        idempotency_key="idem-42",
    )

    assert result is expected
    assert fake_provider.calls == [
        {
            "integration": {"id": 1},
            "request": {"request": "payload"},
            "idempotency_key": "idem-42",
        }
    ]


def test_build_provider_order_request_falls_back_to_snapshot_external_ids():
    service = POSService()
    service.order_item_repo = type(
        "_FakeOrderItemRepo",
        (),
        {
            "list_order_items": lambda self, order_id: [
                {
                    "id": 1,
                    "menu_item_id": 444,
                    "external_item_id_snapshot": "item-ext-1",
                    "item_name_snapshot": "Burger",
                    "quantity": 1,
                    "base_price_snapshot": 12.99,
                    "final_unit_price_snapshot": 14.49,
                    "instructions": "No onions",
                }
            ],
            "list_order_item_options": lambda self, order_id: [
                {
                    "order_item_id": 1,
                    "option_group_id": 12,
                    "option_value_id": 101,
                    "option_value_name_snapshot": "Cheese",
                    "quantity": 1,
                    "price_delta_snapshot": 1.5,
                    "external_group_id_snapshot": "grp-ext-1",
                    "external_value_id_snapshot": "val-ext-1",
                }
            ],
        },
    )()
    service.pos_menu_item_mapping_repo = type(
        "_FakeMenuMappingRepo",
        (),
        {"get_by_internal_item": lambda self, menu_item_id, pos_integration_id: None},
    )()
    service.pos_option_value_mapping_repo = type(
        "_FakeOptionValueMappingRepo",
        (),
        {"get_by_internal_value": lambda self, option_value_id, pos_integration_id: None},
    )()
    service.pos_option_group_mapping_repo = type(
        "_FakeOptionGroupMappingRepo",
        (),
        {"get_by_internal_group": lambda self, option_group_id, pos_integration_id: None},
    )()

    request = service._build_provider_order_request(
        order_id=42,
        pos_integration={"id": 1, "restaurant_id": 9, "location_id": "loc-1", "currency": "USD"},
        order_data={"order_details": []},
        order={"restaurant_id": 9},
        customization={},
    )

    assert len(request.line_items) == 1
    assert request.line_items[0].external_item_id == "item-ext-1"
    assert request.line_items[0].discount_amount == 0.0
    assert request.line_items[0].modifiers[0].external_group_id == "grp-ext-1"
    assert request.line_items[0].modifiers[0].external_value_id == "val-ext-1"


def test_submit_order_to_pos_retries_once_immediately_with_same_sync_record(monkeypatch):
    service = POSService()
    service.pos_integration_repo = type(
        "_FakeIntegrationRepo",
        (),
        {
            "get_enabled_integrations": lambda self, restaurant_id: [
                {"id": 7, "pos_type": "SQUARE", "location_id": "loc-1"}
            ]
        },
    )()
    service.order_sync_repo = type(
        "_FakeSyncRepo",
        (),
        {"create_sync_record": lambda self, order_id, restaurant_id, integration_id, idempotency_key: 55},
    )()
    monkeypatch.setattr(
        service,
        "_build_order_submission_context",
        lambda order_id: ({"id": order_id, "restaurant_id": 9}, {"order_details": []}, {}),
    )

    calls = []

    def _fake_process(**kwargs):
        calls.append(dict(kwargs))
        if len(calls) == 1:
            return {
                "success": False,
                "status": "FAILED",
                "retry_scheduled": False,
                "retryable": True,
                "error": "timeout",
            }
        return {
            "success": True,
            "status": "CONFIRMED",
            "retry_scheduled": False,
            "retryable": False,
            "external_order_id": "ord-1",
        }

    monkeypatch.setattr(service, "_process_integration_submission", _fake_process)

    result = service.submit_order_to_pos(
        order_id=42,
        restaurant_id=9,
        schedule_retry_on_failure=False,
        immediate_retry_attempts=1,
    )

    assert result["success"] is True
    assert result["status"] == "CONFIRMED"
    assert len(calls) == 2
    assert calls[0]["sync_id"] == 55
    assert calls[1]["sync_id"] == 55
    assert calls[0]["idempotency_key"] == calls[1]["idempotency_key"]
    assert calls[0]["attempt_count"] == 1
    assert calls[1]["attempt_count"] == 2
    assert calls[0]["schedule_retry_on_failure"] is False
    assert calls[1]["schedule_retry_on_failure"] is False
