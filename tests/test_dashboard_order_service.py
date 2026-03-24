from __future__ import annotations

from types import SimpleNamespace
from typing import Any, Dict, List

import pytest

from app.services.dashboard_order_service import DashboardOrderService


class _FakeOrderRepo:
    def __init__(self) -> None:
        self.orders = {
            1: {
                "id": 1,
                "user_id": 2,
                "restaurant_id": 9,
                "status": "pending",
                "total_amount": 12.0,
                "order_details": [],
                "customization": {},
                "customer_name": "Caller",
                "customer_phone": "+15555550123",
                "customer_email": None,
            }
        }
        self.update_calls: List[Dict[str, Any]] = []
        self.status_calls: List[Dict[str, Any]] = []

    def get_order_with_user(self, order_id: int) -> Dict[str, Any]:
        return dict(self.orders.get(order_id, {}))

    def update_order(
        self,
        order_id: int,
        status: str | None = None,
        total_amount: float | None = None,
        order_details: List[Dict[str, Any]] | None = None,
        customization: Dict[str, Any] | None = None,
    ) -> bool:
        self.update_calls.append(
            {
                "order_id": order_id,
                "status": status,
                "total_amount": total_amount,
                "order_details": order_details,
                "customization": customization,
            }
        )
        order = self.orders[order_id]
        if status is not None:
            order["status"] = status
        if total_amount is not None:
            order["total_amount"] = total_amount
        if order_details is not None:
            order["order_details"] = order_details
        if customization is not None:
            order["customization"] = customization
        return True

    def update_order_status(self, order_id: int, status: str) -> bool:
        self.status_calls.append({"order_id": order_id, "status": status})
        self.orders[order_id]["status"] = status
        return True


class _FakeOrderItemRepo:
    def __init__(self) -> None:
        self.replace_calls: List[Dict[str, Any]] = []
        self._items_by_order: Dict[int, List[Dict[str, Any]]] = {}
        self._options_by_order: Dict[int, List[Dict[str, Any]]] = {}

    def replace_order_item_snapshots(self, order_id: int, items: List[Dict[str, Any]]) -> int:
        self.replace_calls.append({"order_id": order_id, "items": items})
        stored_items: List[Dict[str, Any]] = []
        stored_options: List[Dict[str, Any]] = []
        for index, item in enumerate(items, start=1):
            order_item_id = index
            stored_item = {
                "id": order_item_id,
                "menu_item_id": item.get("menu_item_id"),
                "item_name_snapshot": item.get("item_name_snapshot"),
                "base_price_snapshot": item.get("base_price_snapshot"),
                "quantity": item.get("quantity"),
                "instructions": item.get("instructions"),
                "final_unit_price_snapshot": item.get("final_unit_price_snapshot"),
                "option_total_snapshot": item.get("option_total_snapshot"),
                "total_price_snapshot": item.get("total_price_snapshot"),
                "external_item_id_snapshot": item.get("external_item_id_snapshot"),
            }
            stored_items.append(stored_item)
            for option_index, option in enumerate(item.get("option_snapshots") or [], start=1):
                stored_options.append(
                    {
                        "id": len(stored_options) + option_index,
                        "order_item_id": order_item_id,
                        **option,
                    }
                )
        self._items_by_order[order_id] = stored_items
        self._options_by_order[order_id] = stored_options
        return len(items)

    def list_order_items(self, order_id: int) -> List[Dict[str, Any]]:
        return [dict(item) for item in self._items_by_order.get(order_id, [])]

    def list_order_item_options(self, order_id: int) -> List[Dict[str, Any]]:
        return [dict(option) for option in self._options_by_order.get(order_id, [])]


class _FakePOSService:
    def __init__(self) -> None:
        self.replace_calls: List[Dict[str, Any]] = []
        self.cancel_calls: List[Dict[str, Any]] = []
        self.restore_calls: List[Dict[str, Any]] = []
        self.replace_result = {"required": True, "success": True, "status": "CONFIRMED"}
        self.cancel_result = {"required": True, "success": True, "status": "CANCELLED"}

    def attach_external_snapshot_ids(
        self, restaurant_id: int, priced_items: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        return [dict(item) for item in priced_items]

    def capture_order_state(self, order_id: int) -> Dict[str, Any]:
        return {
            "order_id": order_id,
            "status": "pending",
            "total_amount": 12.0,
            "order_details": [],
            "customization": {},
            "snapshot_items": [],
        }

    def has_confirmed_sync(self, order_id: int) -> bool:
        return True

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


class _FakeCustomizationService:
    def validate_item_options(self, menu_item_id: int, options: List[Any]) -> SimpleNamespace:
        return SimpleNamespace(is_valid=True, issues=[], normalized_options=options)

    def price_item(self, menu_item_id: int, base_price: float, quantity: int, normalized_options: List[Any]):
        return SimpleNamespace(
            final_unit_price=base_price,
            option_total=0.0,
            total_price=base_price * max(quantity, 1),
            option_snapshots=[],
        )


def _build_service() -> tuple[DashboardOrderService, _FakeOrderRepo, _FakeOrderItemRepo, _FakePOSService]:
    service = DashboardOrderService()
    order_repo = _FakeOrderRepo()
    order_item_repo = _FakeOrderItemRepo()
    pos_service = _FakePOSService()
    service.order_repo = order_repo
    service.order_item_repo = order_item_repo
    service.pos_service = pos_service
    service.customization_service = _FakeCustomizationService()
    return service, order_repo, order_item_repo, pos_service


def test_dashboard_update_order_replaces_confirmed_pos_order():
    service, _, order_item_repo, pos_service = _build_service()

    result = service.update_order(
        order_id=1,
        order_details=[{"item_id": 444, "name": "Burger", "quantity": 1, "price": 12.0, "options": []}],
    )

    assert result["id"] == 1
    assert len(order_item_repo.replace_calls) == 1
    assert len(pos_service.replace_calls) == 1
    assert pos_service.replace_calls[0]["order_id"] == 1
    assert pos_service.replace_calls[0]["reason"] == "Dashboard updated order"


def test_dashboard_cancel_order_restores_internal_state_when_pos_cancel_fails():
    service, _, _, pos_service = _build_service()
    pos_service.cancel_result = {"required": True, "success": False, "status": "FAILED", "error": "square error"}

    with pytest.raises(ValueError, match="square error"):
        service.cancel_order(1)

    assert len(pos_service.cancel_calls) == 1
    assert len(pos_service.restore_calls) == 1
