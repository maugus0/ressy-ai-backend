"""
Helpers for validating and pricing menu item customizations.
"""

from __future__ import annotations

import inspect
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from pydantic import ValidationError

from app.models.order_models import (
    OptionValidationIssue,
    OptionValidationResult,
    OrderItemOptionGroupSelection,
    OrderOptionSelection,
)
from app.repositories.mysql_menu_repo import MySQLMenuRepository


@dataclass
class PricedItem:
    option_total: float
    final_unit_price: float
    total_price: float
    option_snapshots: List[Dict[str, Any]]
    normalized_options: List[OrderItemOptionGroupSelection]


class OrderCustomizationService:
    """Validate option selections and compute pricing snapshots."""

    FREE_ALLOWANCE_STRATEGIES = {"HIGHEST_PRICE_FIRST", "LOWEST_PRICE_FIRST"}
    INPUT_TYPES = {"SELECT", "TEXT"}

    def __init__(self, menu_repo: Optional[MySQLMenuRepository] = None):
        self.menu_repo = menu_repo or MySQLMenuRepository()

    def get_effective_groups(self, menu_item_id: int) -> List[Dict[str, Any]]:
        get_groups = self.menu_repo.get_option_groups_for_item
        parameters = inspect.signature(get_groups).parameters
        supports_only_active = "only_active" in parameters or any(
            param.kind == inspect.Parameter.VAR_KEYWORD for param in parameters.values()
        )
        if supports_only_active:
            groups = get_groups(menu_item_id, only_active=True)
        else:
            groups = get_groups(menu_item_id)
        for group in groups:
            self._apply_overrides(group)
        return groups

    def validate_item_options(
        self,
        menu_item_id: int,
        raw_options: Any,
    ) -> OptionValidationResult:
        groups = self.get_effective_groups(menu_item_id)
        if not groups:
            if raw_options:
                return OptionValidationResult(
                    is_valid=False,
                    issues=[
                        OptionValidationIssue(
                            issue_code="INVALID_OPTION",
                            message="This item does not support customizations.",
                        )
                    ],
                )
            return OptionValidationResult(is_valid=True)

        try:
            normalized = self._normalize_options_payload(raw_options)
        except (ValidationError, ValueError, TypeError):
            return OptionValidationResult(
                is_valid=False,
                issues=[
                    OptionValidationIssue(
                        issue_code="INVALID_OPTION",
                        message="Invalid customization payload.",
                    )
                ],
            )
        issues: List[OptionValidationIssue] = []
        group_by_id = {group["id"]: group for group in groups if group.get("id") is not None}
        values_by_group: Dict[int, Dict[int, Dict[str, Any]]] = {}
        for group in groups:
            group_id = group.get("id")
            if group_id is None:
                continue
            values_by_group[int(group_id)] = {
                int(value["id"]): value for value in group.get("values", []) if value.get("id") is not None
            }

        normalized_by_group = {sel.group_id: sel for sel in normalized}

        for group_id, selection in normalized_by_group.items():
            group = group_by_id.get(group_id)
            if not group:
                issues.append(
                    OptionValidationIssue(
                        issue_code="INVALID_OPTION",
                        message="Selected group is not valid for this item.",
                        group_id=group_id,
                    )
                )
                continue
            if not self._is_available(group.get("is_available")):
                issues.append(
                    OptionValidationIssue(
                        issue_code="UNAVAILABLE_GROUP",
                        message="This customization group is unavailable.",
                        group_id=group_id,
                        group_name=group.get("name"),
                    )
                )
            selections = selection.selections
            input_type = self._normalize_input_type(group.get("input_type"))
            if group.get("selection_type") == "single" and len(selections) > 1:
                issues.append(
                    OptionValidationIssue(
                        issue_code="EXCEEDED_MAX_SELECT",
                        message="Only one option can be selected for this group.",
                        group_id=group_id,
                        group_name=group.get("name"),
                    )
                )
            min_select = group.get("min_select") or 0
            max_select = group.get("max_select")
            if len(selections) < min_select:
                issues.append(
                    OptionValidationIssue(
                        issue_code="BELOW_MIN_SELECT",
                        message="Not enough selections for this group.",
                        group_id=group_id,
                        group_name=group.get("name"),
                    )
                )
            if max_select is not None and len(selections) > max_select:
                issues.append(
                    OptionValidationIssue(
                        issue_code="EXCEEDED_MAX_SELECT",
                        message="Too many selections for this group.",
                        group_id=group_id,
                        group_name=group.get("name"),
                    )
                )
            for sel in selections:
                if input_type == "TEXT":
                    if sel.value_id is not None:
                        issues.append(
                            OptionValidationIssue(
                                issue_code="TEXT_NOT_ALLOWED",
                                message="This customization expects text input, not a predefined option.",
                                group_id=group_id,
                                group_name=group.get("name"),
                                value_id=sel.value_id,
                            )
                        )
                        continue
                    free_text_value = (sel.free_text_value or "").strip()
                    if not free_text_value:
                        issues.append(
                            OptionValidationIssue(
                                issue_code="MISSING_TEXT_VALUE",
                                message="A text value is required for this customization.",
                                group_id=group_id,
                                group_name=group.get("name"),
                            )
                        )
                        continue
                    max_text_length = group.get("max_text_length")
                    if max_text_length is not None and len(free_text_value) > int(max_text_length):
                        issues.append(
                            OptionValidationIssue(
                                issue_code="TEXT_TOO_LONG",
                                message="This customization exceeds the maximum text length.",
                                group_id=group_id,
                                group_name=group.get("name"),
                            )
                        )
                    if sel.quantity > 1 and not self._is_available(group.get("allows_quantity")):
                        issues.append(
                            OptionValidationIssue(
                                issue_code="QUANTITY_NOT_ALLOWED",
                                message="This option does not allow quantity changes.",
                                group_id=group_id,
                                group_name=group.get("name"),
                            )
                        )
                    max_qty = group.get("max_quantity_per_option")
                    if max_qty is not None and sel.quantity > max_qty:
                        issues.append(
                            OptionValidationIssue(
                                issue_code="EXCEEDED_MAX_QUANTITY_PER_OPTION",
                                message="Selected option exceeds the maximum quantity allowed.",
                                group_id=group_id,
                                group_name=group.get("name"),
                            )
                        )
                    continue

                if sel.free_text_value:
                    issues.append(
                        OptionValidationIssue(
                            issue_code="TEXT_NOT_ALLOWED",
                            message="This customization only accepts predefined options.",
                            group_id=group_id,
                            group_name=group.get("name"),
                        )
                    )
                    continue
                value = values_by_group.get(group_id, {}).get(sel.value_id)
                if not value:
                    issues.append(
                        OptionValidationIssue(
                            issue_code="INVALID_OPTION",
                            message="Selected option is not valid for this group.",
                            group_id=group_id,
                            group_name=group.get("name"),
                            value_id=sel.value_id,
                        )
                    )
                    continue
                if not self._is_available(value.get("is_available")):
                    issues.append(
                        OptionValidationIssue(
                            issue_code="UNAVAILABLE_OPTION",
                            message="Selected option is unavailable.",
                            group_id=group_id,
                            group_name=group.get("name"),
                            value_id=sel.value_id,
                            value_name=value.get("name"),
                        )
                    )
                if sel.quantity > 1 and not self._is_available(group.get("allows_quantity")):
                    issues.append(
                        OptionValidationIssue(
                            issue_code="QUANTITY_NOT_ALLOWED",
                            message="This option does not allow quantity changes.",
                            group_id=group_id,
                            group_name=group.get("name"),
                            value_id=sel.value_id,
                            value_name=value.get("name"),
                        )
                    )
                max_qty = group.get("max_quantity_per_option")
                if max_qty is not None and sel.quantity > max_qty:
                    issues.append(
                        OptionValidationIssue(
                            issue_code="EXCEEDED_MAX_QUANTITY_PER_OPTION",
                            message="Selected option exceeds the maximum quantity allowed.",
                            group_id=group_id,
                            group_name=group.get("name"),
                            value_id=sel.value_id,
                            value_name=value.get("name"),
                        )
                    )

        for group in groups:
            group_id = group.get("id")
            if group_id is None:
                continue
            if not self._is_available(group.get("is_available")):
                continue
            has_selection = group_id in normalized_by_group and normalized_by_group[group_id].selections
            if has_selection:
                continue
            input_type = self._normalize_input_type(group.get("input_type"))
            if input_type == "TEXT":
                min_select = group.get("min_select") or 0
                if min_select > 0:
                    issues.append(
                        OptionValidationIssue(
                            issue_code="BELOW_MIN_SELECT",
                            message="Not enough selections for this group.",
                            group_id=int(group_id),
                            group_name=group.get("name"),
                        )
                    )
                elif self._is_available(group.get("is_required")):
                    issues.append(
                        OptionValidationIssue(
                            issue_code="MISSING_REQUIRED_GROUP",
                            message="A required customization is missing.",
                            group_id=int(group_id),
                            group_name=group.get("name"),
                        )
                    )
                continue
            defaults = [
                value
                for value in group.get("values", [])
                if value.get("is_default") and self._is_available(value.get("is_available"))
            ]
            if group.get("selection_type") == "single" and defaults:
                normalized.append(
                    OrderItemOptionGroupSelection(
                        group_id=int(group_id),
                        selections=[OrderOptionSelection(value_id=int(defaults[0]["id"]), quantity=1)],
                    )
                )
                continue
            min_select = group.get("min_select") or 0
            if min_select > 0:
                issues.append(
                    OptionValidationIssue(
                        issue_code="BELOW_MIN_SELECT",
                        message="Not enough selections for this group.",
                        group_id=int(group_id),
                        group_name=group.get("name"),
                    )
                )
            elif self._is_available(group.get("is_required")):
                issues.append(
                    OptionValidationIssue(
                        issue_code="MISSING_REQUIRED_GROUP",
                        message="A required customization is missing.",
                        group_id=int(group_id),
                        group_name=group.get("name"),
                    )
                )

        return OptionValidationResult(is_valid=not issues, issues=issues, normalized_options=normalized)

    def price_item(
        self,
        menu_item_id: int,
        base_price: float,
        quantity: int,
        normalized_options: List[OrderItemOptionGroupSelection],
    ) -> PricedItem:
        groups = self.get_effective_groups(menu_item_id)
        group_by_id = {group["id"]: group for group in groups if group.get("id") is not None}
        values_by_group: Dict[int, Dict[int, Dict[str, Any]]] = {}
        for group in groups:
            group_id = group.get("id")
            if group_id is None:
                continue
            values_by_group[int(group_id)] = {
                int(value["id"]): value for value in group.get("values", []) if value.get("id") is not None
            }

        option_snapshots: List[Dict[str, Any]] = []
        option_total = 0.0

        for selection in normalized_options:
            group = group_by_id.get(selection.group_id)
            if not group:
                continue
            values = values_by_group.get(selection.group_id, {})
            deltas: List[Tuple[float, int]] = []
            input_type = self._normalize_input_type(group.get("input_type"))
            for sel in selection.selections:
                if input_type == "TEXT":
                    free_text_value = (sel.free_text_value or "").strip()
                    if not free_text_value:
                        continue
                    delta = 0.0
                    option_snapshots.append(
                        {
                            "option_group_id": selection.group_id,
                            "option_value_id": None,
                            "option_group_name_snapshot": group.get("name"),
                            "input_type_snapshot": input_type,
                            "option_value_name_snapshot": free_text_value,
                            "free_text_value": free_text_value,
                            "price_delta_snapshot": delta,
                            "quantity": sel.quantity,
                        }
                    )
                    for _ in range(max(sel.quantity, 1)):
                        deltas.append((delta, 1))
                    continue
                value = values.get(sel.value_id)
                if not value:
                    continue
                delta = float(value.get("price_delta") or 0)
                option_snapshots.append(
                    {
                        "option_group_id": selection.group_id,
                        "option_value_id": sel.value_id,
                        "option_group_name_snapshot": group.get("name"),
                        "input_type_snapshot": group.get("input_type", "SELECT"),
                        "option_value_name_snapshot": value.get("name"),
                        "price_delta_snapshot": delta,
                        "quantity": sel.quantity,
                    }
                )
                for _ in range(max(sel.quantity, 1)):
                    deltas.append((delta, 1))
            group_total = sum(delta for delta, _ in deltas)
            free_allowance = int(group.get("free_allowance") or 0)
            if free_allowance > 0 and deltas:
                strategy = self._normalize_free_allowance_strategy(group.get("free_allowance_strategy"))
                reverse = strategy == "HIGHEST_PRICE_FIRST"
                deltas_sorted = sorted(deltas, key=lambda item: item[0], reverse=reverse)
                allowance_reduction = sum(delta for delta, _ in deltas_sorted[:free_allowance])
                group_total = max(group_total - allowance_reduction, 0)
            option_total += group_total

        option_total = round(option_total, 2)
        final_unit_price = round(float(base_price) + option_total, 2)
        total_price = round(final_unit_price * max(quantity, 1), 2)
        return PricedItem(
            option_total=option_total,
            final_unit_price=final_unit_price,
            total_price=total_price,
            option_snapshots=option_snapshots,
            normalized_options=normalized_options,
        )

    @staticmethod
    def _normalize_options_payload(raw_options: Any) -> List[OrderItemOptionGroupSelection]:
        if raw_options is None:
            return []
        if isinstance(raw_options, list):
            return [OrderItemOptionGroupSelection.model_validate(item) for item in raw_options]
        if isinstance(raw_options, dict):
            normalized: List[OrderItemOptionGroupSelection] = []
            for group_id, selections in raw_options.items():
                if selections is None:
                    continue
                selection_models = []
                for selection in selections:
                    selection_models.append(OrderOptionSelection.model_validate(selection))
                normalized.append(OrderItemOptionGroupSelection(group_id=int(group_id), selections=selection_models))
            return normalized
        return []

    @staticmethod
    def _apply_overrides(group: Dict[str, Any]) -> None:
        overrides = {
            "min_select": group.get("min_select_override"),
            "max_select": group.get("max_select_override"),
            "free_allowance": group.get("free_allowance_override"),
            "allows_quantity": group.get("allows_quantity_override"),
            "max_quantity_per_option": group.get("max_quantity_per_option_override"),
            "is_required": group.get("is_required_override"),
        }
        for field, value in overrides.items():
            if value is not None:
                group[field] = value

    @staticmethod
    def _is_available(value: Any) -> bool:
        if isinstance(value, bool):
            return value
        if value is None:
            return False
        try:
            return int(value) == 1
        except (TypeError, ValueError):
            return False

    def _normalize_free_allowance_strategy(self, value: Any) -> str:
        text = str(value or "").strip().upper()
        if text in self.FREE_ALLOWANCE_STRATEGIES:
            return text
        return "HIGHEST_PRICE_FIRST"

    def _normalize_input_type(self, value: Any) -> str:
        text = str(value or "SELECT").strip().upper()
        if text in self.INPUT_TYPES:
            return text
        return "SELECT"
