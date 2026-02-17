from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List

import pytest

from app.agent_fc.functions import orders


class _FakeUserRepo:
    def create_or_update_user(self, data: Dict[str, Any]) -> int:
        return 2

    def get_user_id_by_phone_or_email(self, phone: str, email: Any) -> int:
        return 2


class _FakeMetadataRepo:
    def create_mapping(self, **kwargs) -> None:
        return None


class _FakeOrderRepo:
    def __init__(self) -> None:
        self.orders: Dict[int, Dict[str, Any]] = {}
        self.create_calls = 0
        self.update_calls = 0
        self._next_id = 100

    def create_order(self, user_id: int, order_data: Dict[str, Any]) -> int:
        self.create_calls += 1
        order_id = self._next_id
        self._next_id += 1
        self.orders[order_id] = {
            "id": order_id,
            "user_id": user_id,
            "restaurant_id": order_data.get("restaurant_id"),
            "status": order_data.get("status", "pending"),
            "total_amount": order_data.get("total_amount", 0.0),
            "order_details": order_data.get("order_details", []),
            "customization": order_data.get("customization", {}),
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        }
        return order_id

    def get_order_by_id_with_verification(self, order_id: int, restaurant_id: int, user_id: int) -> Dict[str, Any]:
        order = self.orders.get(order_id)
        if not order:
            return {}
        if order.get("restaurant_id") != restaurant_id or order.get("user_id") != user_id:
            return {}
        return dict(order)

    def update_order_details(
        self,
        order_id: int,
        order_details: List[Dict[str, Any]],
        customization: Dict[str, Any] | None = None,
        total_amount: float | None = None,
    ) -> int:
        self.update_calls += 1
        order = self.orders[order_id]
        order["order_details"] = order_details
        if customization is not None:
            order["customization"] = customization
        if total_amount is not None:
            order["total_amount"] = total_amount
        order["updated_at"] = datetime.now(timezone.utc)
        return 1

    def get_order_by_id(self, order_id: int) -> Dict[str, Any]:
        return dict(self.orders.get(order_id, {}))

    def create_order_details(self, order_id: int, menu_item_id: int) -> int:
        return 1

    def get_latest_order_by_user(self, user_id: int, restaurant_id: int | None = None) -> Dict[str, Any]:
        matching = [
            order
            for order in self.orders.values()
            if order.get("user_id") == user_id
            and (restaurant_id is None or order.get("restaurant_id") == restaurant_id)
        ]
        if not matching:
            return {}
        latest = max(matching, key=lambda row: row.get("id", 0))
        return dict(latest)

    def update_order_status(self, order_id: int, status: str) -> int:
        self.orders[order_id]["status"] = status
        return 1


class _FakeOrderItemRepo:
    def __init__(self) -> None:
        self.created_items: List[Dict[str, Any]] = []

    def create_order_item(self, order_id: int, data: Dict[str, Any]) -> int:
        self.created_items.append({"order_id": order_id, **data})
        return 1

    def create_order_item_options(self, order_item_id: int, options: List[Dict[str, Any]]) -> int:
        return len(options)

    def delete_order_items_by_order(self, order_id: int) -> int:
        return 1


class _FakeHistoryService:
    def log_order_created(self, **kwargs) -> int:
        return 1

    def log_order_updated(self, **kwargs) -> int:
        return 1


def _item_payload() -> List[Dict[str, Any]]:
    return [{"item_id": 444, "name": "OG Hot Chicken", "quantity": 1, "options": [{"group_id": 1, "selections": [2]}]}]


async def _run_direct(func, *args, **kwargs):
    result = func(*args, **kwargs)
    if hasattr(result, "__await__"):
        return await result
    return result


def _patch_common(monkeypatch, order_repo: _FakeOrderRepo) -> _FakeOrderItemRepo:
    async def _fake_load_restaurant(restaurant_id: int) -> Dict[str, Any]:
        return {"id": restaurant_id, "name": "Test Resto"}

    async def _fake_populate_missing_prices(restaurant_id: int, items: List[Any]) -> None:
        return None

    async def _fake_validate_and_price_items(items: List[Any]):
        return (
            [{"total_price": 20.0, "final_unit_price": 20.0, "option_total": 0.0, "option_snapshots": []}],
            None,
        )

    async def _fake_emit_order_sse_event(**kwargs) -> None:
        return None

    async def _fake_send_voice_order_sms(**kwargs) -> None:
        return None

    order_item_repo = _FakeOrderItemRepo()
    monkeypatch.setattr(orders, "_get_user_repo", lambda: _FakeUserRepo())
    monkeypatch.setattr(orders, "_get_metadata_repo", lambda: _FakeMetadataRepo())
    monkeypatch.setattr(orders, "_get_order_repo", lambda: order_repo)
    monkeypatch.setattr(orders, "_get_order_item_repo", lambda: order_item_repo)
    monkeypatch.setattr(orders, "_get_history_service", lambda: _FakeHistoryService())
    monkeypatch.setattr(orders, "load_restaurant", _fake_load_restaurant)
    monkeypatch.setattr(orders, "is_restaurant_open_now", lambda restaurant: True)
    monkeypatch.setattr(orders, "_populate_missing_prices", _fake_populate_missing_prices)
    monkeypatch.setattr(orders, "_validate_and_price_items", _fake_validate_and_price_items)
    monkeypatch.setattr(orders, "_run_service_call", _run_direct)
    monkeypatch.setattr(orders, "_emit_order_sse_event", _fake_emit_order_sse_event)
    monkeypatch.setattr(orders, "_send_voice_order_sms", _fake_send_voice_order_sms)
    return order_item_repo


@pytest.mark.asyncio
async def test_create_order_updates_existing_active_order_in_same_call(monkeypatch) -> None:
    order_repo = _FakeOrderRepo()
    _patch_common(monkeypatch, order_repo)
    order_session_state = {}

    first = await orders.create_order(
        items=_item_payload(),
        restaurant_id=9,
        customer_contact="+15555550123",
        call_sid="CA-1",
        order_session_state=order_session_state,
    )
    second = await orders.create_order(
        items=_item_payload(),
        restaurant_id=9,
        customer_contact="+15555550123",
        call_sid="CA-1",
        order_session_state=order_session_state,
    )

    assert first["status"] == "CREATED"
    assert second["status"] == "UPDATED"
    assert order_repo.create_calls == 1
    assert order_repo.update_calls == 1
    assert order_session_state["active_order_id"] == first["order_id"]
    assert second["order_id"] == first["order_id"]


@pytest.mark.asyncio
async def test_update_order_details_prefers_active_order_id_over_latest(monkeypatch) -> None:
    order_repo = _FakeOrderRepo()
    _patch_common(monkeypatch, order_repo)

    order_repo.orders[200] = {
        "id": 200,
        "user_id": 2,
        "restaurant_id": 9,
        "status": "pending",
        "total_amount": 15.0,
        "order_details": [],
        "customization": {},
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }
    order_repo.orders[201] = {
        "id": 201,
        "user_id": 2,
        "restaurant_id": 9,
        "status": "pending",
        "total_amount": 19.0,
        "order_details": [],
        "customization": {},
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }
    order_session_state = {"active_order_id": 200}

    response = await orders.update_order_details(
        items=_item_payload(),
        restaurant_id=9,
        customer_contact="+15555550123",
        call_sid="CA-2",
        order_session_state=order_session_state,
    )

    assert response["status"] == "UPDATED"
    assert response["order"]["id"] == 200
    assert order_session_state["active_order_id"] == 200


@pytest.mark.asyncio
async def test_create_order_custom_item_snapshot_uses_null_menu_item_id(monkeypatch) -> None:
    order_repo = _FakeOrderRepo()
    order_item_repo = _patch_common(monkeypatch, order_repo)
    order_session_state = {}

    response = await orders.create_order(
        items=[{"item_id": 0, "name": "Custom Request", "quantity": 1, "price": 9.5, "options": []}],
        restaurant_id=9,
        customer_contact="+15555550123",
        call_sid="CA-3",
        order_session_state=order_session_state,
    )

    assert response["status"] == "CREATED"
    assert order_item_repo.created_items
    assert order_item_repo.created_items[0]["menu_item_id"] is None
