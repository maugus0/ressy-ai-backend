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
    assert request.line_items[0].modifiers[0].external_group_id == "grp-ext-1"
    assert request.line_items[0].modifiers[0].external_value_id == "val-ext-1"
