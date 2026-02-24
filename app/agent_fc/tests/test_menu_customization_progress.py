from __future__ import annotations

import pytest

from app.agent_fc.functions import menu


class _FakeMenuRepo:
    def __init__(self, groups: list[dict], found: bool = True):
        self._groups = groups
        self._found = found

    def get_menu_by_id(self, restaurant_id: int, item_id: int) -> dict:
        if not self._found:
            return {}
        return {"id": item_id, "restaurant_id": restaurant_id}

    def get_option_groups_for_item(self, item_id: int) -> list[dict]:
        return self._groups


class _FailingMenuRepo:
    def get_menu_by_id(self, restaurant_id: int, item_id: int) -> dict:
        raise RuntimeError("boom")


def _groups_fixture() -> list[dict]:
    return [
        {
            "id": 1,
            "name": "Spice Level",
            "description": "Choose your heat level",
            "selection_type": "single",
            "min_select": 0,
            "max_select": 1,
            "free_allowance": 0,
            "allows_quantity": False,
            "max_quantity_per_option": None,
            "prompt_style": "ASK_ALWAYS",
            "is_required": False,
            "is_available": True,
            "sort_order": 1,
            "values": [{"id": 10, "name": "Mild", "price_delta": 0, "is_default": True, "is_available": True}],
        },
        {
            "id": 3,
            "name": "Make It Combo",
            "description": "Upgrade to a combo",
            "selection_type": "single",
            "min_select": 0,
            "max_select": 1,
            "free_allowance": 0,
            "allows_quantity": False,
            "max_quantity_per_option": None,
            "prompt_style": "ASK_ALWAYS",
            "is_required": False,
            "is_available": True,
            "sort_order": 2,
            "values": [
                {"id": 30, "name": "Waffle Fries", "price_delta": 4.5, "is_default": False, "is_available": True}
            ],
        },
        {
            "id": 2,
            "name": "Extra Toppings",
            "description": "Optional extras",
            "selection_type": "multiple",
            "min_select": 0,
            "max_select": None,
            "free_allowance": 0,
            "allows_quantity": False,
            "max_quantity_per_option": None,
            "prompt_style": "ASK_IF_MENTIONED",
            "is_required": False,
            "is_available": True,
            "sort_order": 3,
            "values": [
                {"id": 20, "name": "Extra Cheese", "price_delta": 1.0, "is_default": False, "is_available": True}
            ],
        },
    ]


@pytest.mark.asyncio
async def test_customization_progress_keeps_pending_group_until_completed(monkeypatch) -> None:
    monkeypatch.setattr(menu, "_get_menu_repo", lambda: _FakeMenuRepo(_groups_fixture()))
    progress_store: dict[int, dict] = {}

    first = await menu.get_menu_item_customizations(
        item_id=444,
        restaurant_id=9,
        call_sid="CA123",
        customization_progress_by_item=progress_store,
    )
    second = await menu.get_menu_item_customizations(
        item_id=444,
        restaurant_id=9,
        call_sid="CA123",
        customization_progress_by_item=progress_store,
    )

    assert first["status"] == "FOUND"
    assert first["next_group"]["id"] == 1
    assert second["status"] == "FOUND"
    assert second["next_group"]["id"] == 1
    assert progress_store[444]["pending_group_id"] == 1
    assert progress_store[444]["completed_group_ids"] == set()


@pytest.mark.asyncio
async def test_customization_progress_advances_when_completed_group_is_reported(monkeypatch) -> None:
    monkeypatch.setattr(menu, "_get_menu_repo", lambda: _FakeMenuRepo(_groups_fixture()))
    progress_store: dict[int, dict] = {}

    await menu.get_menu_item_customizations(
        item_id=444,
        restaurant_id=9,
        call_sid="CA123",
        customization_progress_by_item=progress_store,
    )
    follow_up = await menu.get_menu_item_customizations(
        item_id=444,
        completed_group_ids=[1],
        restaurant_id=9,
        call_sid="CA123",
        customization_progress_by_item=progress_store,
    )

    assert follow_up["status"] == "FOUND"
    assert follow_up["next_group"]["id"] == 3
    assert follow_up["completed_group_ids"] == [1]
    assert progress_store[444]["pending_group_id"] == 3


@pytest.mark.asyncio
async def test_customization_progress_latches_include_ask_if_mentioned(monkeypatch) -> None:
    monkeypatch.setattr(menu, "_get_menu_repo", lambda: _FakeMenuRepo(_groups_fixture()))
    progress_store: dict[int, dict] = {}

    await menu.get_menu_item_customizations(
        item_id=444,
        restaurant_id=9,
        call_sid="CA123",
        customization_progress_by_item=progress_store,
    )
    await menu.get_menu_item_customizations(
        item_id=444,
        completed_group_ids=[1],
        restaurant_id=9,
        call_sid="CA123",
        customization_progress_by_item=progress_store,
    )
    ask_if_mentioned = await menu.get_menu_item_customizations(
        item_id=444,
        completed_group_ids=[1, 3],
        include_ask_if_mentioned=True,
        restaurant_id=9,
        call_sid="CA123",
        customization_progress_by_item=progress_store,
    )
    sticky_retry = await menu.get_menu_item_customizations(
        item_id=444,
        completed_group_ids=[1, 3],
        include_ask_if_mentioned=False,
        restaurant_id=9,
        call_sid="CA123",
        customization_progress_by_item=progress_store,
    )

    assert ask_if_mentioned["next_group"]["id"] == 2
    assert ask_if_mentioned["include_ask_if_mentioned"] is True
    assert sticky_retry["next_group"]["id"] == 2
    assert sticky_retry["include_ask_if_mentioned"] is True


@pytest.mark.asyncio
async def test_customization_progress_reset_restarts_flow(monkeypatch) -> None:
    monkeypatch.setattr(menu, "_get_menu_repo", lambda: _FakeMenuRepo(_groups_fixture()))
    progress_store: dict[int, dict] = {}

    await menu.get_menu_item_customizations(
        item_id=444,
        restaurant_id=9,
        call_sid="CA123",
        customization_progress_by_item=progress_store,
    )
    await menu.get_menu_item_customizations(
        item_id=444,
        completed_group_ids=[1],
        restaurant_id=9,
        call_sid="CA123",
        customization_progress_by_item=progress_store,
    )
    reset = await menu.get_menu_item_customizations(
        item_id=444,
        reset_progress=True,
        restaurant_id=9,
        call_sid="CA123",
        customization_progress_by_item=progress_store,
    )

    assert reset["status"] == "FOUND"
    assert reset["next_group"]["id"] == 1
    assert reset["completed_group_ids"] == []
    assert progress_store[444]["pending_group_id"] == 1


@pytest.mark.asyncio
async def test_customization_progress_is_not_mutated_on_fetch_error(monkeypatch) -> None:
    monkeypatch.setattr(menu, "_get_menu_repo", lambda: _FailingMenuRepo())
    progress_store: dict[int, dict] = {
        444: {"completed_group_ids": {1}, "pending_group_id": 3, "include_ask_if_mentioned": False}
    }

    result = await menu.get_menu_item_customizations(
        item_id=444,
        completed_group_ids=[3],
        include_ask_if_mentioned=True,
        restaurant_id=9,
        call_sid="CA123",
        customization_progress_by_item=progress_store,
    )

    assert result["status"] == "ERROR"
    assert progress_store[444]["completed_group_ids"] == {1}
    assert progress_store[444]["pending_group_id"] == 3
    assert progress_store[444]["include_ask_if_mentioned"] is False
