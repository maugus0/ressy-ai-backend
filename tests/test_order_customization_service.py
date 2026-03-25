from __future__ import annotations

from typing import Any, Dict, List

from app.services.order_customization_service import OrderCustomizationService


class FakeMenuRepo:
    def __init__(self, groups: List[Dict[str, Any]]):
        self._groups = groups

    def get_option_groups_for_item(self, menu_item_id: int) -> List[Dict[str, Any]]:
        return self._groups


def test_validation_applies_defaults_for_single_select():
    groups = [
        {
            "id": 1,
            "name": "Spice Level",
            "selection_type": "single",
            "min_select": 0,
            "max_select": 1,
            "free_allowance": 0,
            "allows_quantity": False,
            "max_quantity_per_option": None,
            "is_required": False,
            "is_available": True,
            "values": [
                {"id": 10, "name": "Mild", "price_delta": 0, "is_default": True, "is_available": True},
                {"id": 11, "name": "Hot", "price_delta": 0, "is_default": False, "is_available": True},
            ],
        }
    ]
    service = OrderCustomizationService(menu_repo=FakeMenuRepo(groups))
    result = service.validate_item_options(menu_item_id=99, raw_options=None)
    assert result.is_valid
    assert result.normalized_options
    assert result.normalized_options[0].group_id == 1
    assert result.normalized_options[0].selections[0].value_id == 10


def test_validation_flags_quantity_not_allowed():
    groups = [
        {
            "id": 2,
            "name": "Cheese",
            "selection_type": "single",
            "min_select": 0,
            "max_select": 1,
            "free_allowance": 0,
            "allows_quantity": False,
            "max_quantity_per_option": None,
            "is_required": False,
            "is_available": True,
            "values": [{"id": 20, "name": "Extra Cheese", "price_delta": 1, "is_default": False, "is_available": True}],
        }
    ]
    service = OrderCustomizationService(menu_repo=FakeMenuRepo(groups))
    result = service.validate_item_options(
        menu_item_id=100,
        raw_options=[{"group_id": 2, "selections": [{"value_id": 20, "quantity": 2}]}],
    )
    assert not result.is_valid
    assert any(issue.issue_code == "QUANTITY_NOT_ALLOWED" for issue in result.issues)


def test_pricing_applies_free_allowance_to_highest_delta():
    groups = [
        {
            "id": 3,
            "name": "Toppings",
            "selection_type": "multiple",
            "min_select": 0,
            "max_select": None,
            "free_allowance": 1,
            "allows_quantity": False,
            "max_quantity_per_option": None,
            "is_required": False,
            "is_available": True,
            "values": [
                {"id": 30, "name": "Pepperoni", "price_delta": 2, "is_default": False, "is_available": True},
                {"id": 31, "name": "Olives", "price_delta": 1, "is_default": False, "is_available": True},
            ],
        }
    ]
    service = OrderCustomizationService(menu_repo=FakeMenuRepo(groups))
    normalized = service.validate_item_options(
        menu_item_id=101,
        raw_options=[{"group_id": 3, "selections": [{"value_id": 30, "quantity": 1}, {"value_id": 31, "quantity": 1}]}],
    ).normalized_options
    priced = service.price_item(menu_item_id=101, base_price=10.0, quantity=1, normalized_options=normalized)
    # Free allowance should zero out the highest delta (2), leaving only 1 charged.
    assert priced.option_total == 1.0
    assert priced.final_unit_price == 11.0


def test_pricing_applies_free_allowance_to_lowest_delta_when_configured():
    groups = [
        {
            "id": 4,
            "name": "Premium Toppings",
            "selection_type": "multiple",
            "min_select": 0,
            "max_select": None,
            "free_allowance": 1,
            "free_allowance_strategy": "LOWEST_PRICE_FIRST",
            "allows_quantity": False,
            "max_quantity_per_option": None,
            "is_required": False,
            "is_available": True,
            "values": [
                {"id": 40, "name": "Truffle", "price_delta": 3, "is_default": False, "is_available": True},
                {"id": 41, "name": "Garlic", "price_delta": 1, "is_default": False, "is_available": True},
            ],
        }
    ]
    service = OrderCustomizationService(menu_repo=FakeMenuRepo(groups))
    normalized = service.validate_item_options(
        menu_item_id=102,
        raw_options=[{"group_id": 4, "selections": [{"value_id": 40, "quantity": 1}, {"value_id": 41, "quantity": 1}]}],
    ).normalized_options
    priced = service.price_item(menu_item_id=102, base_price=10.0, quantity=1, normalized_options=normalized)
    # Lowest allowance strategy should zero out the 1 delta, leaving 3 charged.
    assert priced.option_total == 3.0
    assert priced.final_unit_price == 13.0


def test_pricing_defaults_to_highest_strategy_when_strategy_is_invalid():
    groups = [
        {
            "id": 5,
            "name": "Toppings",
            "selection_type": "multiple",
            "min_select": 0,
            "max_select": None,
            "free_allowance": 1,
            "free_allowance_strategy": "unexpected",
            "allows_quantity": False,
            "max_quantity_per_option": None,
            "is_required": False,
            "is_available": True,
            "values": [
                {"id": 50, "name": "A", "price_delta": 5, "is_default": False, "is_available": True},
                {"id": 51, "name": "B", "price_delta": 2, "is_default": False, "is_available": True},
            ],
        }
    ]
    service = OrderCustomizationService(menu_repo=FakeMenuRepo(groups))
    normalized = service.validate_item_options(
        menu_item_id=103,
        raw_options=[{"group_id": 5, "selections": [{"value_id": 50, "quantity": 1}, {"value_id": 51, "quantity": 1}]}],
    ).normalized_options
    priced = service.price_item(menu_item_id=103, base_price=10.0, quantity=1, normalized_options=normalized)
    # Invalid strategy falls back to highest-first, so 5 is free and 2 remains.
    assert priced.option_total == 2.0
    assert priced.final_unit_price == 12.0


def test_validation_accepts_text_customization_and_pricing_snapshots_free_text():
    groups = [
        {
            "id": 6,
            "name": "Special Instructions",
            "selection_type": "single",
            "input_type": "TEXT",
            "text_required": True,
            "max_text_length": 40,
            "min_select": 1,
            "max_select": 1,
            "free_allowance": 0,
            "allows_quantity": False,
            "max_quantity_per_option": None,
            "is_required": True,
            "is_available": True,
            "values": [],
        }
    ]
    service = OrderCustomizationService(menu_repo=FakeMenuRepo(groups))

    result = service.validate_item_options(
        menu_item_id=104,
        raw_options=[{"group_id": 6, "selections": [{"free_text_value": "Light sauce", "quantity": 1}]}],
    )

    assert result.is_valid
    assert result.normalized_options[0].selections[0].free_text_value == "Light sauce"

    priced = service.price_item(
        menu_item_id=104, base_price=10.0, quantity=1, normalized_options=result.normalized_options
    )
    assert priced.option_total == 0.0
    assert priced.option_snapshots == [
        {
            "option_group_id": 6,
            "option_value_id": None,
            "option_group_name_snapshot": "Special Instructions",
            "input_type_snapshot": "TEXT",
            "option_value_name_snapshot": "Light sauce",
            "free_text_value": "Light sauce",
            "price_delta_snapshot": 0.0,
            "quantity": 1,
        }
    ]


def test_validation_rejects_text_customization_without_text_value():
    groups = [
        {
            "id": 7,
            "name": "Special Instructions",
            "selection_type": "single",
            "input_type": "TEXT",
            "text_required": True,
            "max_text_length": 20,
            "min_select": 1,
            "max_select": 1,
            "free_allowance": 0,
            "allows_quantity": False,
            "max_quantity_per_option": None,
            "is_required": True,
            "is_available": True,
            "values": [],
        }
    ]
    service = OrderCustomizationService(menu_repo=FakeMenuRepo(groups))

    result = service.validate_item_options(
        menu_item_id=105,
        raw_options=[{"group_id": 7, "selections": [{"free_text_value": "", "quantity": 1}]}],
    )

    assert not result.is_valid
    assert any(issue.issue_code == "MISSING_TEXT_VALUE" for issue in result.issues)
