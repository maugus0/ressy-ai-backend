from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
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
        self.soft_delete_calls: List[int] = []
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
        if order.get("deleted_at") is not None:
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
            and order.get("deleted_at") is None
        ]
        if not matching:
            return {}
        latest = max(matching, key=lambda row: row.get("id", 0))
        return dict(latest)

    def update_order_status(self, order_id: int, status: str) -> int:
        self.orders[order_id]["status"] = status
        return 1

    def soft_delete_order(self, order_id: int) -> bool:
        order = self.orders.get(order_id)
        if not order:
            return False
        order["deleted_at"] = datetime.now(timezone.utc)
        self.soft_delete_calls.append(order_id)
        return True


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


class _FakePOSService:
    def __init__(self, result: Dict[str, Any] | None = None) -> None:
        self.result = result or {
            "required": False,
            "success": True,
            "status": "SKIPPED",
            "retry_scheduled": False,
            "retryable": False,
            "results": [],
        }
        self.calls: List[Dict[str, Any]] = []
        self.snapshot_attach_calls: List[Dict[str, Any]] = []
        self.replace_calls: List[Dict[str, Any]] = []
        self.cancel_calls: List[Dict[str, Any]] = []
        self.restore_calls: List[Dict[str, Any]] = []
        self.confirmed_sync = False
        self.replace_result: Dict[str, Any] = {
            "required": True,
            "success": True,
            "status": "CONFIRMED",
            "results": [{"success": True, "status": "CONFIRMED"}],
            "rollback_performed": False,
            "rollback_success": True,
        }
        self.cancel_result: Dict[str, Any] = {
            "required": True,
            "success": True,
            "status": "CANCELLED",
            "results": [{"success": True, "status": "CANCELLED"}],
        }

    def submit_order_to_pos(self, order_id: int, restaurant_id: int, **kwargs) -> Dict[str, Any]:
        self.calls.append({"order_id": order_id, "restaurant_id": restaurant_id, **kwargs})
        return dict(self.result)

    def attach_external_snapshot_ids(
        self, restaurant_id: int, priced_items: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        self.snapshot_attach_calls.append({"restaurant_id": restaurant_id, "priced_items": priced_items})
        return [dict(item) for item in priced_items]

    def capture_order_state(self, order_id: int) -> Dict[str, Any]:
        return {
            "order_id": order_id,
            "status": "pending",
            "total_amount": 20.0,
            "order_details": [],
            "customization": {},
            "snapshot_items": [],
        }

    def has_confirmed_sync(self, order_id: int) -> bool:
        return self.confirmed_sync

    def replace_order_after_internal_update(
        self,
        order_id: int,
        restaurant_id: int,
        *,
        previous_state: Dict[str, Any],
        reason: str | None = None,
    ) -> Dict[str, Any]:
        self.replace_calls.append(
            {
                "order_id": order_id,
                "restaurant_id": restaurant_id,
                "previous_state": previous_state,
                "reason": reason,
            }
        )
        return dict(self.replace_result)

    def cancel_order_in_pos(
        self,
        order_id: int,
        restaurant_id: int,
        *,
        reason: str | None = None,
    ) -> Dict[str, Any]:
        self.cancel_calls.append({"order_id": order_id, "restaurant_id": restaurant_id, "reason": reason})
        return dict(self.cancel_result)

    def restore_order_state(self, order_id: int, state: Dict[str, Any]) -> None:
        self.restore_calls.append({"order_id": order_id, "state": state})


def _item_payload() -> List[Dict[str, Any]]:
    return [{"item_id": 444, "name": "OG Hot Chicken", "quantity": 1, "options": [{"group_id": 1, "selections": [2]}]}]


async def _run_direct(func, *args, **kwargs):
    result = func(*args, **kwargs)
    if hasattr(result, "__await__"):
        return await result
    return result


class _FakeMenuRepoAvailability:
    def __init__(self, items_by_id: Dict[int, Dict[str, Any]]) -> None:
        self.items_by_id = items_by_id

    def get_by_ids(self, menu_ids: List[int]) -> Dict[int, Dict[str, Any]]:
        return {menu_id: dict(self.items_by_id[menu_id]) for menu_id in menu_ids if menu_id in self.items_by_id}


class _FakeCustomizationService:
    def validate_item_options(self, menu_item_id: int, options: List[Any]) -> SimpleNamespace:
        return SimpleNamespace(is_valid=True, issues=[], normalized_options=options)

    def price_item(
        self,
        menu_item_id: int,
        base_price: float,
        quantity: int,
        normalized_options: List[Any],
    ) -> SimpleNamespace:
        return SimpleNamespace(
            option_total=0.0,
            final_unit_price=base_price,
            total_price=base_price * max(quantity, 1),
            option_snapshots=[],
            normalized_options=normalized_options,
        )


def _patch_common(monkeypatch, order_repo: _FakeOrderRepo, *, restaurant: Dict[str, Any] | None = None):
    emitted_events: List[Dict[str, Any]] = []
    sent_sms: List[Dict[str, Any]] = []
    emitted_escalations: List[Dict[str, Any]] = []
    created_escalations: List[Dict[str, Any]] = []
    escalated_calls: List[int] = []
    fake_pos_service = _FakePOSService()
    restaurant_payload = restaurant or {"id": 9, "name": "Test Resto"}

    async def _fake_load_restaurant(restaurant_id: int) -> Dict[str, Any]:
        payload = dict(restaurant_payload)
        payload.setdefault("id", restaurant_id)
        return payload

    async def _fake_populate_missing_prices(restaurant_id: int, items: List[Any]) -> None:
        return None

    async def _fake_validate_and_price_items(items: List[Any]):
        return (
            [{"total_price": 20.0, "final_unit_price": 20.0, "option_total": 0.0, "option_snapshots": []}],
            None,
        )

    async def _fake_emit_order_sse_event(**kwargs) -> None:
        emitted_events.append(kwargs)
        return None

    async def _fake_send_voice_order_sms(**kwargs) -> None:
        sent_sms.append(kwargs)
        return None

    async def _fake_emit_pos_failure_escalation_event(**kwargs) -> None:
        emitted_escalations.append(kwargs)
        return None

    class _FakeEscalationService:
        def create_escalation(self, payload: Dict[str, Any]) -> int:
            created_escalations.append(payload)
            return len(created_escalations)

    class _FakeCallService:
        def mark_escalated(self, call_id: int) -> bool:
            escalated_calls.append(call_id)
            return True

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
    monkeypatch.setattr(orders, "_emit_pos_failure_escalation_event", _fake_emit_pos_failure_escalation_event)
    monkeypatch.setattr(orders, "_get_pos_service", lambda: fake_pos_service)
    monkeypatch.setattr(orders, "EscalationService", _FakeEscalationService)
    monkeypatch.setattr(orders, "CallService", _FakeCallService)
    return (
        order_item_repo,
        fake_pos_service,
        emitted_events,
        sent_sms,
        emitted_escalations,
        created_escalations,
        escalated_calls,
    )


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
    _, fake_pos_service, _, _, _, _, _ = _patch_common(monkeypatch, order_repo)
    fake_pos_service.confirmed_sync = True

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
    assert len(fake_pos_service.replace_calls) == 1
    assert fake_pos_service.replace_calls[0]["order_id"] == 200
    assert fake_pos_service.replace_calls[0]["restaurant_id"] == 9
    assert fake_pos_service.replace_calls[0]["reason"] == "Voice caller updated order"


@pytest.mark.asyncio
async def test_create_order_custom_item_snapshot_uses_null_menu_item_id(monkeypatch) -> None:
    order_repo = _FakeOrderRepo()
    order_item_repo, _, _, _, _, _, _ = _patch_common(monkeypatch, order_repo)
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


@pytest.mark.asyncio
async def test_create_order_returns_confirmed_for_pos_backed_restaurant(monkeypatch) -> None:
    order_repo = _FakeOrderRepo()
    _, fake_pos_service, emitted_events, sent_sms, _, _, _ = _patch_common(monkeypatch, order_repo)
    fake_pos_service.result = {
        "required": True,
        "success": True,
        "status": "CONFIRMED",
        "retry_scheduled": False,
        "results": [{"success": True, "status": "CONFIRMED"}],
    }
    order_session_state = {}

    response = await orders.create_order(
        items=_item_payload(),
        restaurant_id=9,
        customer_contact="+15555550123",
        call_sid="CA-4",
        order_session_state=order_session_state,
    )

    assert response["status"] == "CONFIRMED"
    assert fake_pos_service.calls == [
        {
            "order_id": response["order_id"],
            "restaurant_id": 9,
            "schedule_retry_on_failure": False,
            "immediate_retry_attempts": 1,
        }
    ]
    assert order_session_state["active_order_id"] == response["order_id"]
    assert len(emitted_events) == 1
    assert len(sent_sms) == 1


@pytest.mark.asyncio
async def test_update_order_details_cancels_pos_order_when_requested(monkeypatch) -> None:
    order_repo = _FakeOrderRepo()
    _, fake_pos_service, _, _, _, _, _ = _patch_common(monkeypatch, order_repo)
    fake_pos_service.confirmed_sync = True
    order_repo.orders[200] = {
        "id": 200,
        "user_id": 2,
        "restaurant_id": 9,
        "status": "pending",
        "total_amount": 19.0,
        "order_details": [],
        "customization": {},
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }

    response = await orders.update_order_details(
        items=_item_payload(),
        status="cancelled",
        restaurant_id=9,
        customer_contact="+15555550123",
        call_sid="CA-7",
        order_session_state={"active_order_id": 200},
    )

    assert response["status"] == "UPDATED"
    assert fake_pos_service.cancel_calls == [
        {
            "order_id": 200,
            "restaurant_id": 9,
            "reason": "Voice caller cancelled order",
        }
    ]


@pytest.mark.asyncio
async def test_update_order_details_fails_when_pos_replace_fails(monkeypatch) -> None:
    order_repo = _FakeOrderRepo()
    _, fake_pos_service, emitted_events, _, _, _, _ = _patch_common(monkeypatch, order_repo)
    fake_pos_service.confirmed_sync = True
    fake_pos_service.replace_result = {
        "required": True,
        "success": False,
        "status": "FAILED",
        "error": "square error",
        "rollback_performed": True,
        "rollback_success": True,
    }
    order_repo.orders[200] = {
        "id": 200,
        "user_id": 2,
        "restaurant_id": 9,
        "status": "pending",
        "total_amount": 19.0,
        "order_details": [],
        "customization": {},
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }

    response = await orders.update_order_details(
        items=_item_payload(),
        restaurant_id=9,
        customer_contact="+15555550123",
        call_sid="CA-8",
        order_session_state={"active_order_id": 200},
    )

    assert response["status"] == "FAILED"
    assert emitted_events == []


@pytest.mark.asyncio
async def test_create_order_does_not_confirm_when_pos_submission_fails(monkeypatch) -> None:
    order_repo = _FakeOrderRepo()
    _, fake_pos_service, emitted_events, sent_sms, emitted_escalations, created_escalations, _ = _patch_common(
        monkeypatch, order_repo
    )
    fake_pos_service.result = {
        "required": True,
        "success": False,
        "status": "FAILED",
        "retry_scheduled": False,
        "retryable": False,
        "results": [{"success": False, "status": "FAILED"}],
        "error": "config error",
    }
    order_session_state = {}

    response = await orders.create_order(
        items=_item_payload(),
        restaurant_id=9,
        customer_contact="+15555550123",
        call_sid="CA-5",
        order_session_state=order_session_state,
    )

    assert response["status"] == "FAILED"
    assert response["forwarding"] is False
    assert response["escalated"] is True
    assert "active_order_id" not in order_session_state
    assert emitted_events == []
    assert sent_sms == []
    assert emitted_escalations and emitted_escalations[0]["order_id"] == response["order_id"]
    assert created_escalations and "config error" in created_escalations[0]["reason"]
    assert order_repo.soft_delete_calls == [response["order_id"]]


@pytest.mark.asyncio
async def test_create_order_escalates_after_retryable_pos_failure(monkeypatch) -> None:
    order_repo = _FakeOrderRepo()
    _, fake_pos_service, emitted_events, sent_sms, _, created_escalations, _ = _patch_common(monkeypatch, order_repo)
    fake_pos_service.result = {
        "required": True,
        "success": False,
        "status": "FAILED",
        "retry_scheduled": False,
        "retryable": True,
        "results": [{"success": False, "status": "FAILED", "retryable": True}],
        "error": "timeout",
    }
    order_session_state = {}

    response = await orders.create_order(
        items=_item_payload(),
        restaurant_id=9,
        customer_contact="+15555550123",
        call_sid="CA-6",
        order_session_state=order_session_state,
    )

    assert response["status"] == "FAILED"
    assert response["forwarding"] is False
    assert "active_order_id" not in order_session_state
    assert emitted_events == []
    assert sent_sms == []
    assert created_escalations and "timeout" in created_escalations[0]["reason"]
    assert order_repo.soft_delete_calls == [response["order_id"]]


@pytest.mark.asyncio
async def test_create_order_forwards_call_when_pos_failure_escalation_allows_transfer(monkeypatch) -> None:
    order_repo = _FakeOrderRepo()
    _, fake_pos_service, emitted_events, sent_sms, _, created_escalations, escalated_calls = _patch_common(
        monkeypatch,
        order_repo,
        restaurant={
            "id": 9,
            "name": "Test Resto",
            "forward_escalations": 1,
            "escalation_phone_number": "+15550001111",
            "escalation_mode": "always",
        },
    )
    fake_pos_service.result = {
        "required": True,
        "success": False,
        "status": "FAILED",
        "retry_scheduled": False,
        "retryable": True,
        "results": [{"success": False, "status": "FAILED", "retryable": True}],
        "error": "timeout",
    }

    response = await orders.create_order(
        items=_item_payload(),
        restaurant_id=9,
        customer_contact="+15555550123",
        call_sid="CA-9",
        call_id=501,
        order_session_state={},
    )

    assert isinstance(response, orders.AgentFunctionResult)
    assert response.content["status"] == "FAILED"
    assert response.content["forwarding"] is True
    assert response.side_effects[0].payload["type"] == "InjectAgentMessage"
    assert response.side_effects[1].payload["type"] == "close"
    assert emitted_events == []
    assert sent_sms == []
    assert created_escalations and created_escalations[0]["escalation_phone_number"] == "+15550001111"
    assert escalated_calls == [501]


@pytest.mark.asyncio
async def test_validate_and_price_items_rejects_unavailable_base_item(monkeypatch) -> None:
    monkeypatch.setattr(
        orders,
        "_get_menu_repo",
        lambda: _FakeMenuRepoAvailability({444: {"id": 444, "is_active": 1, "is_available": 0}}),
    )
    monkeypatch.setattr(orders, "_get_customization_service", lambda: _FakeCustomizationService())
    monkeypatch.setattr(orders, "_run_service_call", _run_direct)

    priced_items, issues = await orders._validate_and_price_items(
        [orders.OrderItem(item_id=444, name="OG Hot Chicken", quantity=1, price=12.0, options=[])]
    )

    assert priced_items == []
    assert issues == [
        {
            "item_id": 444,
            "item_name": "OG Hot Chicken",
            "issues": [
                {
                    "issue_code": "UNAVAILABLE_ITEM",
                    "message": "This item is currently unavailable.",
                }
            ],
        }
    ]
