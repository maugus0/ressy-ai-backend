from __future__ import annotations

from typing import Any, Dict, List

from square.core.api_error import ApiError

from app.integrations.pos.models import POSOrderLineItem, POSOrderModifierSelection, POSSubmitOrderRequest
from app.integrations.pos.square_provider import SquarePOSProvider
from app.integrations.square_client import SquareClient


class _FakeModel:
    def __init__(self, payload: Dict[str, Any]):
        self._payload = payload

    def model_dump(self, mode: str = "json", by_alias: bool = True, exclude_none: bool = True) -> Dict[str, Any]:
        return self._payload


class _FakeCatalogClient:
    def __init__(self, objects: List[Dict[str, Any]]):
        self.objects = objects
        self.types = None

    def list(self, *, types=None, **kwargs):
        self.types = types
        return [_FakeModel(obj) for obj in self.objects]


class _FakeLocationsClient:
    def __init__(self, locations: List[Dict[str, Any]]):
        self.locations = locations

    def list(self):
        return _FakeModel({"locations": self.locations})


class _FakeOrdersClient:
    def __init__(self):
        self.create_calls: List[Dict[str, Any]] = []
        self.pay_calls: List[Dict[str, Any]] = []
        self.get_calls: List[Dict[str, Any]] = []
        self.update_calls: List[Dict[str, Any]] = []

    def create(self, *, order=None, idempotency_key=None, request_options=None):
        self.create_calls.append(
            {
                "order": order,
                "idempotency_key": idempotency_key,
                "request_options": request_options,
            }
        )
        return _FakeModel({"order": {"id": "ord-1", "version": 4}})

    def pay(self, order_id, *, idempotency_key, order_version=None, payment_ids=None, request_options=None):
        self.pay_calls.append(
            {
                "order_id": order_id,
                "idempotency_key": idempotency_key,
                "order_version": order_version,
                "payment_ids": payment_ids,
                "request_options": request_options,
            }
        )
        return _FakeModel({"order": {"id": order_id, "state": "COMPLETED"}})

    def get(self, order_id, *, request_options=None):
        self.get_calls.append({"order_id": order_id, "request_options": request_options})
        return _FakeModel(
            {
                "order": {
                    "id": order_id,
                    "version": 4,
                    "location_id": "loc-1",
                    "total_money": {"amount": 1599, "currency": "USD"},
                    "fulfillments": [{"uid": "ful-1", "type": "PICKUP", "state": "PROPOSED"}],
                }
            }
        )

    def update(self, order_id, *, order=None, fields_to_clear=None, idempotency_key=None, request_options=None):
        self.update_calls.append(
            {
                "order_id": order_id,
                "order": order,
                "fields_to_clear": fields_to_clear,
                "idempotency_key": idempotency_key,
                "request_options": request_options,
            }
        )
        return _FakeModel({"order": {"id": order_id, "version": 5}})


class _FakePaymentsClient:
    def __init__(self):
        self.create_calls: List[Dict[str, Any]] = []

    def create(self, **kwargs):
        self.create_calls.append(kwargs)
        return _FakeModel({"payment": {"id": "pay-1", "order_id": kwargs["order_id"]}})


class _FakeRefundsClient:
    def __init__(self):
        self.refund_calls: List[Dict[str, Any]] = []

    def refund_payment(self, **kwargs):
        self.refund_calls.append(kwargs)
        return _FakeModel({"refund": {"id": "refund-1", "payment_id": kwargs["payment_id"]}})


class _FakeSDKClient:
    def __init__(self, objects: List[Dict[str, Any]] | None = None, locations: List[Dict[str, Any]] | None = None):
        self.catalog = _FakeCatalogClient(objects or [])
        self.locations = _FakeLocationsClient(locations or [])
        self.orders = _FakeOrdersClient()
        self.payments = _FakePaymentsClient()
        self.refunds = _FakeRefundsClient()


class _FakeSquareWrapperClient:
    def __init__(self, *, raise_already_paid: bool = False):
        self.create_order_calls: List[Dict[str, Any]] = []
        self.create_payment_calls: List[Dict[str, Any]] = []
        self.pay_order_calls: List[Dict[str, Any]] = []
        self.get_order_calls: List[Dict[str, Any]] = []
        self.update_order_calls: List[Dict[str, Any]] = []
        self.refund_payment_calls: List[Dict[str, Any]] = []
        self.search_catalog_objects_calls: List[Dict[str, Any]] = []
        self.raise_already_paid = raise_already_paid

    def create_order(self, location_id, order_data, idempotency_key):
        self.create_order_calls.append(
            {
                "location_id": location_id,
                "order_data": order_data,
                "idempotency_key": idempotency_key,
            }
        )
        return {"order": {"id": "ord-1", "version": 4}}

    def create_payment(self, order_id, amount, currency, idempotency_key):
        self.create_payment_calls.append(
            {
                "order_id": order_id,
                "amount": amount,
                "currency": currency,
                "idempotency_key": idempotency_key,
            }
        )
        return {"payment": {"id": "pay-1", "order_id": order_id}}

    def pay_order(self, order_id, payment_ids, idempotency_key, order_version=None):
        if self.raise_already_paid:
            raise ApiError(
                status_code=400,
                body={"errors": [{"code": "BAD_REQUEST", "detail": "The order is already paid."}]},
            )
        self.pay_order_calls.append(
            {
                "order_id": order_id,
                "payment_ids": payment_ids,
                "idempotency_key": idempotency_key,
                "order_version": order_version,
            }
        )
        return {"order": {"id": order_id, "state": "COMPLETED"}}

    def get_order(self, order_id):
        self.get_order_calls.append({"order_id": order_id})
        return {
            "order": {
                "id": order_id,
                "version": 4,
                "location_id": "loc-1",
                "total_money": {"amount": 1599, "currency": "USD"},
                "fulfillments": [{"uid": "ful-1", "type": "PICKUP", "state": "PROPOSED"}],
            }
        }

    def update_order(self, order_id, *, order_data, idempotency_key, fields_to_clear=None):
        self.update_order_calls.append(
            {
                "order_id": order_id,
                "order_data": order_data,
                "idempotency_key": idempotency_key,
                "fields_to_clear": fields_to_clear,
            }
        )
        return {"order": {"id": order_id, "version": 5}}

    def refund_payment(self, *, payment_id, amount_cents, currency, idempotency_key, reason=None):
        self.refund_payment_calls.append(
            {
                "payment_id": payment_id,
                "amount_cents": amount_cents,
                "currency": currency,
                "idempotency_key": idempotency_key,
                "reason": reason,
            }
        )
        return {"refund": {"id": "refund-1", "payment_id": payment_id}}

    def search_catalog_objects(self, *, object_types=None, begin_time=None, limit=None):
        self.search_catalog_objects_calls.append(
            {
                "object_types": object_types,
                "begin_time": begin_time,
                "limit": limit,
            }
        )
        return {"objects": []}


def test_square_client_list_catalog_serializes_sdk_results():
    client = SquareClient("token")
    client._client = _FakeSDKClient(
        [
            {"id": "item-1", "type": "ITEM"},
            {"id": "modifier-list-1", "type": "MODIFIER_LIST"},
        ]
    )

    result = client.list_catalog(types=["ITEM", "MODIFIER_LIST"])

    assert [obj["id"] for obj in result["objects"]] == ["item-1", "modifier-list-1"]
    assert client._client.catalog.types == "ITEM,MODIFIER_LIST"


def test_square_client_list_locations_serializes_sdk_results():
    client = SquareClient("token")
    client._client = _FakeSDKClient(locations=[{"id": "loc-1", "merchant_id": "merchant-1"}])

    result = client.list_locations()

    assert result["locations"] == [{"id": "loc-1", "merchant_id": "merchant-1"}]


def test_square_client_search_catalog_objects_serializes_sdk_results():
    client = SquareClient("token")

    class _FakeSearchCatalogClient(_FakeCatalogClient):
        def __init__(self, pages):
            super().__init__([])
            self.pages = pages
            self.search_args = []

        def search(self, *, cursor=None, object_types=None, begin_time=None, limit=None, **kwargs):
            self.search_args.append(
                {
                    "cursor": cursor,
                    "object_types": object_types,
                    "begin_time": begin_time,
                    "limit": limit,
                }
            )
            page = self.pages[0] if cursor is None else self.pages[1]
            return _FakeModel(page)

    fake_catalog = _FakeSearchCatalogClient(
        [
            {
                "objects": [{"id": "variation-1", "type": "ITEM_VARIATION"}],
                "cursor": "page-2",
            },
            {
                "objects": [{"id": "variation-2", "type": "ITEM_VARIATION"}],
            },
        ]
    )
    client._client = _FakeSDKClient()
    client._client.catalog = fake_catalog

    result = client.search_catalog_objects(
        object_types=["ITEM_VARIATION"],
        begin_time="2026-03-24T14:22:21.109Z",
        limit=1000,
    )

    assert result["objects"] == [
        {"id": "variation-1", "type": "ITEM_VARIATION"},
        {"id": "variation-2", "type": "ITEM_VARIATION"},
    ]
    assert fake_catalog.search_args == [
        {
            "cursor": None,
            "object_types": ["ITEM_VARIATION"],
            "begin_time": "2026-03-24T14:22:21.109Z",
            "limit": 1000,
        },
        {
            "cursor": "page-2",
            "object_types": ["ITEM_VARIATION"],
            "begin_time": "2026-03-24T14:22:21.109Z",
            "limit": 1000,
        },
    ]


def test_square_client_pay_order_uses_sdk_client():
    client = SquareClient("token")
    client._client = _FakeSDKClient()

    result = client.pay_order(
        order_id="ord-1",
        payment_ids=["pay-1"],
        idempotency_key="idem-1",
        order_version=7,
    )

    assert result["order"]["id"] == "ord-1"
    assert client._client.orders.pay_calls == [
        {
            "order_id": "ord-1",
            "idempotency_key": "idem-1",
            "order_version": 7,
            "payment_ids": ["pay-1"],
            "request_options": None,
        }
    ]


def test_square_client_get_order_uses_sdk_client():
    client = SquareClient("token")
    client._client = _FakeSDKClient()

    result = client.get_order("ord-1")

    assert result["order"]["id"] == "ord-1"
    assert client._client.orders.get_calls == [{"order_id": "ord-1", "request_options": None}]


def test_square_client_update_order_uses_sdk_client():
    client = SquareClient("token")
    client._client = _FakeSDKClient()

    result = client.update_order(
        "ord-1",
        order_data={"location_id": "loc-1", "version": 4, "fulfillments": []},
        idempotency_key="idem-update-1",
    )

    assert result["order"]["id"] == "ord-1"
    assert client._client.orders.update_calls == [
        {
            "order_id": "ord-1",
            "order": {"location_id": "loc-1", "version": 4, "fulfillments": []},
            "fields_to_clear": None,
            "idempotency_key": "idem-update-1",
            "request_options": None,
        }
    ]


def test_square_client_refund_payment_uses_sdk_client():
    client = SquareClient("token")
    client._client = _FakeSDKClient()

    result = client.refund_payment(
        payment_id="pay-1",
        amount_cents=1599,
        currency="USD",
        idempotency_key="idem-refund-1",
        reason="Customer requested cancellation",
    )

    assert result["refund"]["payment_id"] == "pay-1"
    assert client._client.refunds.refund_calls == [
        {
            "idempotency_key": "idem-refund-1",
            "payment_id": "pay-1",
            "amount_money": {"amount": 1599, "currency": "USD"},
            "reason": "Customer requested cancellation",
        }
    ]


def test_square_provider_fetch_catalog_normalizes_items_and_modifiers(monkeypatch):
    provider = SquarePOSProvider()

    class _FakeProviderClient:
        def list_locations(self):
            return {
                "locations": [
                    {"id": "loc-1", "merchant_id": "merchant-1", "currency": "USD"},
                ]
            }

        def search_catalog_objects(self, *, object_types=None, begin_time=None, limit=None):
            return {
                "objects": [
                    {
                        "id": "modifier-1",
                        "type": "MODIFIER",
                        "modifier_data": {
                            "name": "Cheese",
                            "price_money": {"amount": 150, "currency": "USD"},
                            "on_by_default": True,
                            "location_overrides": [{"location_id": "loc-1", "sold_out": True}],
                        },
                    },
                    {
                        "id": "variation-1",
                        "type": "ITEM_VARIATION",
                        "version": 12,
                        "item_variation_data": {
                            "name": "Regular",
                            "price_money": {"amount": 1299, "currency": "USD"},
                            "sellable": True,
                            "location_overrides": [{"location_id": "loc-1", "sold_out": True}],
                        },
                    },
                ]
            }

        def list_catalog(self, types=None):
            return {
                "objects": [
                    {"id": "cat-1", "type": "CATEGORY", "category_data": {"name": "Burgers"}},
                    {
                        "id": "modifier-list-1",
                        "type": "MODIFIER_LIST",
                        "modifier_list_data": {
                            "name": "Add-ons",
                            "modifier_type": "LIST",
                            "selection_type": "MULTIPLE",
                            "modifiers": [
                                {
                                    "id": "modifier-1",
                                    "type": "MODIFIER",
                                    "modifier_data": {
                                        "name": "Cheese",
                                        "price_money": {"amount": 150, "currency": "USD"},
                                        "on_by_default": True,
                                    },
                                }
                            ],
                        },
                    },
                    {
                        "id": "item-1",
                        "type": "ITEM",
                        "item_data": {
                            "name": "Burger",
                            "description_plaintext": "House burger",
                            "category_id": "cat-1",
                            "modifier_list_info": [
                                {
                                    "modifier_list_id": "modifier-list-1",
                                    "min_selected_modifiers": 1,
                                    "max_selected_modifiers": 3,
                                    "hidden_from_customer_override": "NO",
                                }
                            ],
                            "variations": [
                                {
                                    "id": "variation-1",
                                    "type": "ITEM_VARIATION",
                                    "version": 12,
                                    "item_variation_data": {
                                        "name": "Regular",
                                        "price_money": {"amount": 1299, "currency": "USD"},
                                        "sellable": True,
                                    },
                                }
                            ],
                        },
                    },
                ]
            }

    monkeypatch.setattr(provider, "_get_client", lambda integration: _FakeProviderClient())

    snapshot = provider.fetch_catalog({"credentials": {"access_token": "token"}, "location_id": "loc-1"})

    assert snapshot.catalog_version == "12"
    assert snapshot.metadata["external_account_id"] == "merchant-1"
    assert snapshot.metadata["location_currency"] == "USD"
    assert len(snapshot.items) == 1
    item = snapshot.items[0]
    assert item.external_id == "variation-1"
    assert item.external_parent_id == "item-1"
    assert item.name == "Burger"
    assert item.price == 12.99
    assert item.category == "Burgers"
    assert item.is_available is False
    assert len(item.option_groups) == 1
    group = item.option_groups[0]
    assert group.external_id == "modifier-list-1"
    assert group.is_available is True
    assert group.min_select == 0
    assert group.max_select is None
    assert group.attachment.min_select == 1
    assert group.attachment.max_select == 3
    assert len(group.values) == 1
    value = group.values[0]
    assert value.external_id == "modifier-1"
    assert value.name == "Cheese"
    assert value.price_delta == 1.5
    assert value.is_default is True
    assert value.is_available is False


def test_square_provider_fetch_availability_updates_uses_search_catalog_objects(monkeypatch):
    provider = SquarePOSProvider()

    class _FakeProviderClient:
        def __init__(self):
            self.calls: List[Dict[str, Any]] = []

        def search_catalog_objects(self, *, object_types=None, begin_time=None, limit=None):
            self.calls.append(
                {
                    "object_types": object_types,
                    "begin_time": begin_time,
                    "limit": limit,
                }
            )
            return {
                "objects": [
                    {
                        "id": "variation-1",
                        "type": "ITEM_VARIATION",
                        "item_variation_data": {
                            "name": "Regular",
                            "sellable": True,
                            "location_overrides": [{"location_id": "loc-1", "sold_out": True}],
                        },
                    },
                    {
                        "id": "modifier-1",
                        "type": "MODIFIER",
                        "modifier_data": {
                            "name": "Cheese",
                            "modifier_list_id": "modifier-list-1",
                            "location_overrides": [{"location_id": "loc-1", "sold_out": True}],
                            "hidden_online": False,
                        },
                    },
                ]
            }

    fake_client = _FakeProviderClient()
    monkeypatch.setattr(provider, "_get_client", lambda integration: fake_client)

    snapshot = provider.fetch_availability_updates(
        {"credentials": {"access_token": "token"}, "location_id": "loc-1"},
        begin_time="2026-03-24T14:22:21.109Z",
    )

    assert len(fake_client.calls) == 1
    assert fake_client.calls[0]["object_types"] == ["ITEM_VARIATION", "MODIFIER"]
    assert fake_client.calls[0]["limit"] == 1000
    assert fake_client.calls[0]["begin_time"].startswith("2026-03-24T14:22:20")
    assert snapshot.items[0].external_id == "variation-1"
    assert snapshot.items[0].is_available is False
    assert snapshot.option_values[0].external_id == "modifier-1"
    assert snapshot.option_values[0].is_available is False


def test_square_provider_submit_pickup_order_supports_text_modifier(monkeypatch):
    provider = SquarePOSProvider()
    fake_client = _FakeSquareWrapperClient()
    monkeypatch.setattr(provider, "_get_client", lambda integration: fake_client)

    request = POSSubmitOrderRequest(
        restaurant_id=1,
        location_id="loc-1",
        currency="USD",
        reference_id="RESSY-101",
        line_items=[
            POSOrderLineItem(
                external_item_id="variation-1",
                name="Burger",
                quantity=1,
                price=12.99,
                modifiers=[
                    POSOrderModifierSelection(
                        external_group_id="modifier-list-2",
                        external_value_id=None,
                        name="Special instructions",
                        quantity=1,
                        price_delta=0,
                        free_text_value="Cut in half",
                    )
                ],
            )
        ],
    )

    provider.submit_pickup_order(
        {"credentials": {"access_token": "token"}},
        request,
        idempotency_key="idem-text-1",
    )

    assert fake_client.create_order_calls[0]["order_data"]["line_items"] == [
        {
            "catalog_object_id": "variation-1",
            "quantity": "1",
            "modifiers": [{"name": "Cut in half", "quantity": "1"}],
        }
    ]


def test_square_provider_submit_pickup_order_builds_catalog_order_and_cash_payment(monkeypatch):
    provider = SquarePOSProvider()
    fake_client = _FakeSquareWrapperClient()
    monkeypatch.setattr(provider, "_get_client", lambda integration: fake_client)

    request = POSSubmitOrderRequest(
        restaurant_id=1,
        location_id="loc-1",
        currency="USD",
        reference_id="RESSY-100",
        customer_name="Jane Doe",
        customer_phone="+15551234567",
        pickup_at="2025-01-01T10:00:00.000Z",
        line_items=[
            POSOrderLineItem(
                external_item_id="variation-1",
                name="Burger",
                quantity=2,
                price=12.99,
                note="No onions",
                modifiers=[
                    POSOrderModifierSelection(
                        external_group_id="modifier-list-1",
                        external_value_id="modifier-1",
                        name="Cheese",
                        quantity=1,
                        price_delta=1.5,
                    )
                ],
            )
        ],
    )

    result = provider.submit_pickup_order(
        {"credentials": {"access_token": "token"}},
        request,
        idempotency_key="idem-1",
    )

    assert result.external_order_id == "ord-1"
    assert result.external_payment_id == "pay-1"
    assert result.status == "CONFIRMED"

    create_call = fake_client.create_order_calls[0]
    assert create_call["idempotency_key"] == "idem-1"
    assert create_call["location_id"] == "loc-1"
    assert create_call["order_data"]["reference_id"] == "RESSY-100"
    assert create_call["order_data"]["line_items"] == [
        {
            "catalog_object_id": "variation-1",
            "quantity": "2",
            "note": "No onions",
            "modifiers": [{"catalog_object_id": "modifier-1", "quantity": "1"}],
        }
    ]
    assert create_call["order_data"]["fulfillments"] == [
        {
            "type": "PICKUP",
            "pickup_details": {
                "recipient": {
                    "phone_number": "+15551234567",
                    "display_name": "Jane Doe",
                },
                "pickup_at": "2025-01-01T10:00:00.000Z",
            },
        }
    ]

    payment_call = fake_client.create_payment_calls[0]
    assert payment_call["order_id"] == "ord-1"
    assert payment_call["amount"] == 28.98
    assert payment_call["currency"] == "USD"
    assert payment_call["idempotency_key"] == "idem-1-payment"

    assert fake_client.pay_order_calls[0] == {
        "order_id": "ord-1",
        "payment_ids": ["pay-1"],
        "idempotency_key": "idem-1-pay",
        "order_version": None,
    }


def test_square_provider_submit_pickup_order_treats_already_paid_as_success(monkeypatch):
    provider = SquarePOSProvider()
    fake_client = _FakeSquareWrapperClient(raise_already_paid=True)
    monkeypatch.setattr(provider, "_get_client", lambda integration: fake_client)

    request = POSSubmitOrderRequest(
        restaurant_id=1,
        location_id="loc-1",
        currency="USD",
        reference_id="RESSY-102",
        line_items=[
            POSOrderLineItem(
                external_item_id="variation-1",
                name="Burger",
                quantity=1,
                price=12.99,
            )
        ],
    )

    result = provider.submit_pickup_order(
        {"credentials": {"access_token": "token"}},
        request,
        idempotency_key="idem-2",
    )

    assert result.external_order_id == "ord-1"
    assert result.external_payment_id == "pay-1"
    assert result.status == "CONFIRMED"
    assert result.payload["pay_order_response"]["status"] == "ALREADY_PAID"


def test_square_provider_cancel_pickup_order_cancels_fulfillment_and_refunds(monkeypatch):
    provider = SquarePOSProvider()
    fake_client = _FakeSquareWrapperClient()
    monkeypatch.setattr(provider, "_get_client", lambda integration: fake_client)

    result = provider.cancel_pickup_order(
        {"credentials": {"access_token": "token"}, "location_id": "loc-1", "currency": "USD"},
        external_order_id="ord-1",
        external_payment_id="pay-1",
        idempotency_key="idem-cancel-1",
        reason="Customer changed order",
    )

    assert result.status == "CANCELLED"
    assert fake_client.get_order_calls == [{"order_id": "ord-1"}]
    assert fake_client.update_order_calls == [
        {
            "order_id": "ord-1",
            "order_data": {
                "location_id": "loc-1",
                "version": 4,
                "fulfillments": [{"uid": "ful-1", "type": "PICKUP", "state": "CANCELED"}],
            },
            "idempotency_key": "idem-cancel-1-cancel",
            "fields_to_clear": None,
        }
    ]
    assert fake_client.refund_payment_calls == [
        {
            "payment_id": "pay-1",
            "amount_cents": 1599,
            "currency": "USD",
            "idempotency_key": "idem-cancel-1-refund",
            "reason": "Customer changed order",
        }
    ]
