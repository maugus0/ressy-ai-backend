from __future__ import annotations

import pytest
from fastapi import HTTPException

from app.services.menu_option_service import MenuOptionService


class _FakeRepo:
    pass


class _FakeOptionRepo:
    def __init__(
        self,
        group: dict | None = None,
        values: list[dict] | None = None,
        defaults_count: int | None = None,
        available_count: int | None = None,
        order_usage_group: bool = False,
        order_usage_value: bool = False,
        value: dict | None = None,
    ):
        self.group = group
        self.values = values or []
        self.defaults_count = defaults_count
        self.available_count = available_count
        self.order_usage_group = order_usage_group
        self.order_usage_value = order_usage_value
        self.value = value
        self.unset_default_called = False
        self.unset_default_calls = 0
        self._next_group_id = max((group or {}).get("id", 0) + 1, 1)
        existing_value_ids = [int(item.get("id", 0)) for item in self.values]
        if value is not None:
            existing_value_ids.append(int(value.get("id", 0)))
        self._next_value_id = max(existing_value_ids + [0]) + 1

    def get_group_by_id(self, group_id: int) -> dict | None:
        return self.group

    def list_values_by_group(self, group_id: int) -> list[dict]:
        return self.values

    def create_group(self, restaurant_id: int, data: dict) -> int:
        group_id = self._next_group_id
        self._next_group_id += 1
        self.group = {"id": group_id, "restaurant_id": restaurant_id, **data}
        return group_id

    def count_defaults(self, group_id: int) -> int:
        if self.defaults_count is not None:
            return self.defaults_count
        return sum(1 for value in self.values if value.get("is_default"))

    def count_available_values(self, group_id: int) -> int:
        if self.available_count is not None:
            return self.available_count
        return sum(1 for value in self.values if value.get("is_available"))

    def has_order_usage_for_group(self, group_id: int) -> bool:
        return self.order_usage_group

    def has_order_usage_for_value(self, value_id: int) -> bool:
        return self.order_usage_value

    def unset_default_in_group(self, group_id: int) -> int:
        self.unset_default_called = True
        self.unset_default_calls += 1
        for item in self.values:
            item["is_default"] = False
        return 1

    def create_value(self, group_id: int, value: dict) -> int:
        value_id = int(value.get("id", self._next_value_id))
        self._next_value_id = max(self._next_value_id, value_id + 1)
        stored = {"id": value_id, "group_id": group_id, **value}
        self.values.append(stored)
        self.value = stored
        return value_id

    def update_group(self, group_id: int, data: dict) -> int:
        if self.group is not None:
            self.group.update(data)
        return 1

    def delete_group(self, group_id: int) -> int:
        self.group = None
        return 1

    def get_value_by_id(self, value_id: int) -> dict | None:
        if self.value is not None and int(self.value.get("id", 0)) == value_id:
            return self.value
        for item in self.values:
            if int(item.get("id", 0)) == value_id:
                return item
        return None

    def update_value(self, value_id: int, data: dict) -> int:
        existing = self.get_value_by_id(value_id)
        if existing is None:
            return 0
        existing.update(data)
        return 1

    def delete_value(self, value_id: int) -> int:
        before = len(self.values)
        self.values = [item for item in self.values if int(item.get("id", 0)) != value_id]
        if self.value is not None and int(self.value.get("id", 0)) == value_id:
            self.value = None
        return 1 if len(self.values) != before else 0


class _FakeItemOptionRepo:
    def __init__(self, has_attachment: bool = False):
        self.has_attachment = has_attachment
        self.upsert_calls: list[tuple[int, int, dict]] = []

    def has_group_attachment(self, group_id: int) -> bool:
        return self.has_attachment

    def upsert_item_group(self, menu_item_id: int, group_id: int, overrides: dict) -> int:
        self.upsert_calls.append((menu_item_id, group_id, overrides))
        return 1


class _FakeMenuRepo:
    def __init__(self, menu_item: dict | None):
        self.menu_item = menu_item

    def get_by_id(self, menu_item_id: int) -> dict | None:
        return self.menu_item


def test_single_select_rejects_max_over_one():
    service = MenuOptionService(option_repo=_FakeRepo(), item_option_repo=_FakeRepo(), menu_repo=_FakeRepo())
    payload = {
        "selection_type": "single",
        "min_select": 0,
        "max_select": 2,
        "free_allowance": 0,
        "allows_quantity": False,
        "max_quantity_per_option": None,
    }
    with pytest.raises(HTTPException):
        service._validate_group_payload(payload)


def test_single_select_rejects_multiple_defaults():
    service = MenuOptionService(option_repo=_FakeRepo(), item_option_repo=_FakeRepo(), menu_repo=_FakeRepo())
    values = [
        {"name": "Mild", "price_delta": 0, "is_default": True, "is_available": True},
        {"name": "Hot", "price_delta": 0, "is_default": True, "is_available": True},
    ]
    with pytest.raises(HTTPException):
        service._validate_group_defaults(selection_type="single", values=values)


def test_defaults_allow_mysql_tinyint_is_available():
    service = MenuOptionService(option_repo=_FakeRepo(), item_option_repo=_FakeRepo(), menu_repo=_FakeRepo())
    values = [
        {"name": "Mild", "price_delta": 0, "is_default": True, "is_available": 1},
    ]
    service._validate_group_defaults(selection_type="single", values=values)


def test_create_group_preserves_multiple_defaults_for_multi_select():
    option_repo = _FakeOptionRepo()
    service = MenuOptionService(
        option_repo=option_repo,
        item_option_repo=_FakeItemOptionRepo(),
        menu_repo=_FakeRepo(),
    )
    payload = {
        "name": "Sauces",
        "selection_type": "multiple",
        "values": [
            {"name": "Mild", "price_delta": 0, "is_default": True, "is_available": True},
            {"name": "Spicy", "price_delta": 0, "is_default": True, "is_available": True},
        ],
    }
    group = service.create_option_group(restaurant_id=1, data=payload)
    assert option_repo.unset_default_calls == 0
    assert sum(1 for value in group["values"] if value.get("is_default")) == 2


def test_create_group_single_select_unsets_existing_default():
    option_repo = _FakeOptionRepo()
    service = MenuOptionService(
        option_repo=option_repo,
        item_option_repo=_FakeItemOptionRepo(),
        menu_repo=_FakeRepo(),
    )
    payload = {
        "name": "Spice",
        "selection_type": "single",
        "values": [
            {"name": "Mild", "price_delta": 0, "is_default": True, "is_available": True},
            {"name": "Hot", "price_delta": 0, "is_default": False, "is_available": True},
        ],
    }
    service.create_option_group(restaurant_id=1, data=payload)
    assert option_repo.unset_default_calls == 1


def test_attach_overrides_reject_invalid_ranges():
    service = MenuOptionService(option_repo=_FakeRepo(), item_option_repo=_FakeRepo(), menu_repo=_FakeRepo())
    group = {
        "selection_type": "multiple",
        "min_select": 0,
        "max_select": 2,
        "free_allowance": 0,
        "allows_quantity": False,
        "max_quantity_per_option": None,
    }
    overrides = {"min_select_override": 3}
    with pytest.raises(HTTPException):
        service._validate_item_group_overrides(group, overrides)


def test_attach_rejects_group_with_no_available_values():
    group = {"id": 1, "restaurant_id": 1, "min_select": 0, "max_select": 2}
    option_repo = _FakeOptionRepo(group=group, available_count=0)
    service = MenuOptionService(
        option_repo=option_repo,
        item_option_repo=_FakeItemOptionRepo(),
        menu_repo=_FakeMenuRepo({"id": 10, "restaurant_id": 1}),
    )
    with pytest.raises(HTTPException):
        service.attach_group_to_item(10, 1, {})


def test_attach_rejects_min_select_over_available_values():
    group = {"id": 1, "restaurant_id": 1, "min_select": 0, "max_select": 3}
    option_repo = _FakeOptionRepo(group=group, available_count=1)
    service = MenuOptionService(
        option_repo=option_repo,
        item_option_repo=_FakeItemOptionRepo(),
        menu_repo=_FakeMenuRepo({"id": 10, "restaurant_id": 1}),
    )
    with pytest.raises(HTTPException):
        service.attach_group_to_item(10, 1, {"min_select_override": 2})


def test_update_group_blocks_lower_max_select_when_attached():
    group = {"id": 5, "selection_type": "multiple", "max_select": 3, "free_allowance": 0, "is_available": True}
    option_repo = _FakeOptionRepo(group=group, defaults_count=2)
    service = MenuOptionService(
        option_repo=option_repo,
        item_option_repo=_FakeItemOptionRepo(has_attachment=True),
        menu_repo=_FakeRepo(),
    )
    with pytest.raises(HTTPException):
        service.update_option_group(5, {"max_select": 1})


def test_update_group_keeps_defaults_when_unavailable():
    group = {"id": 7, "selection_type": "multiple", "is_available": True}
    option_repo = _FakeOptionRepo(group=group)
    service = MenuOptionService(
        option_repo=option_repo,
        item_option_repo=_FakeItemOptionRepo(),
        menu_repo=_FakeRepo(),
    )
    service.update_option_group(7, {"is_available": False})
    assert option_repo.unset_default_called is False


def test_delete_value_blocks_default_or_used():
    option_repo = _FakeOptionRepo(value={"id": 9, "group_id": 2, "is_default": True})
    service = MenuOptionService(option_repo=option_repo, item_option_repo=_FakeRepo(), menu_repo=_FakeRepo())
    with pytest.raises(HTTPException):
        service.delete_option_value(9)
    option_repo = _FakeOptionRepo(value={"id": 10, "group_id": 2, "is_default": False}, order_usage_value=True)
    service = MenuOptionService(option_repo=option_repo, item_option_repo=_FakeRepo(), menu_repo=_FakeRepo())
    with pytest.raises(HTTPException):
        service.delete_option_value(10)


def test_delete_group_blocks_attachment_or_usage():
    option_repo = _FakeOptionRepo(group={"id": 3}, order_usage_group=True)
    service = MenuOptionService(option_repo=option_repo, item_option_repo=_FakeItemOptionRepo(), menu_repo=_FakeRepo())
    with pytest.raises(HTTPException):
        service.delete_option_group(3)
    option_repo = _FakeOptionRepo(group={"id": 4})
    service = MenuOptionService(
        option_repo=option_repo, item_option_repo=_FakeItemOptionRepo(has_attachment=True), menu_repo=_FakeRepo()
    )
    with pytest.raises(HTTPException):
        service.delete_option_group(4)
