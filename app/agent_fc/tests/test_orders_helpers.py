from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.agent_fc.functions.orders import OrderItem, _has_menu_item_id, _match_menu_item


def test_order_item_allows_zero_item_id_for_custom_item() -> None:
    item = OrderItem.model_validate({"item_id": 0, "name": "Custom soup", "quantity": 1})
    assert item.item_id == 0


def test_order_item_rejects_negative_item_id() -> None:
    with pytest.raises(ValidationError):
        OrderItem.model_validate({"item_id": -1, "name": "Invalid", "quantity": 1})


def test_has_menu_item_id_requires_positive_integer() -> None:
    assert _has_menu_item_id(None) is False
    assert _has_menu_item_id(0) is False
    assert _has_menu_item_id(7) is True


def test_match_menu_item_falls_back_to_name_for_custom_item() -> None:
    menu_items = [
        {"id": 10, "item_name": "Burger"},
        {"id": 11, "item_name": "Fries"},
    ]
    request = OrderItem.model_validate({"item_id": 0, "name": "Fries", "quantity": 1})
    matched = _match_menu_item(menu_items, request)
    assert matched is not None
    assert matched["id"] == 11
