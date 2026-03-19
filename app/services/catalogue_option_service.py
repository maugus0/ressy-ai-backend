"""
Service for managing catalogue customization option groups and values.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import HTTPException, status

from app.repositories.mysql_catalogue_item_option_repo import MySQLCatalogueItemOptionRepository
from app.repositories.mysql_catalogue_option_repo import MySQLCatalogueOptionRepository
from app.repositories.mysql_catalogue_repo import MySQLCatalogueRepository


class CatalogueOptionService:
    """Service for CRUD and mapping operations for catalogue options."""

    FREE_ALLOWANCE_STRATEGIES = {"HIGHEST_PRICE_FIRST", "LOWEST_PRICE_FIRST"}

    def __init__(
        self,
        option_repo: Optional[MySQLCatalogueOptionRepository] = None,
        item_option_repo: Optional[MySQLCatalogueItemOptionRepository] = None,
        catalogue_repo: Optional[MySQLCatalogueRepository] = None,
    ):
        self.option_repo = option_repo or MySQLCatalogueOptionRepository()
        self.item_option_repo = item_option_repo or MySQLCatalogueItemOptionRepository()
        self.catalogue_repo = catalogue_repo or MySQLCatalogueRepository()

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

    @staticmethod
    def _ensure_field(data: Dict[str, Any], key: str, fallback: Optional[Any]) -> Optional[Any]:
        if key in data:
            return data[key]
        return fallback

    def _bad_request(self, message: str) -> None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=message)

    def _normalize_free_allowance_strategy(self, value: Any) -> str:
        text = str(value or "").strip().upper()
        if not text:
            text = "HIGHEST_PRICE_FIRST"
        if text not in self.FREE_ALLOWANCE_STRATEGIES:
            self._bad_request("free_allowance_strategy must be HIGHEST_PRICE_FIRST or LOWEST_PRICE_FIRST")
        return text

    def _validate_group_rules(
        self,
        *,
        selection_type: Optional[str],
        min_select: Optional[int],
        max_select: Optional[int],
        free_allowance: Optional[int],
        free_allowance_strategy: Optional[str],
        allows_quantity: Optional[bool],
        max_quantity_per_option: Optional[int],
    ) -> None:
        if max_select is not None and min_select is not None and max_select < min_select:
            self._bad_request("max_select must be greater than or equal to min_select")
        if selection_type == "single":
            if min_select is not None and min_select > 1:
                self._bad_request("min_select must be 0 or 1 for single-select groups")
            if max_select is not None and max_select > 1:
                self._bad_request("max_select must be 1 or less for single-select groups")
        if free_allowance is not None and max_select is not None and free_allowance > max_select:
            self._bad_request("free_allowance cannot exceed max_select")
        if free_allowance_strategy and free_allowance_strategy not in self.FREE_ALLOWANCE_STRATEGIES:
            self._bad_request("free_allowance_strategy must be HIGHEST_PRICE_FIRST or LOWEST_PRICE_FIRST")
        if allows_quantity is False and max_quantity_per_option is not None and max_quantity_per_option > 1:
            self._bad_request("max_quantity_per_option cannot exceed 1 when quantities are disabled")

    def _validate_group_defaults(self, *, selection_type: Optional[str], values: List[Dict[str, Any]]) -> None:
        if not values:
            return
        default_values = [value for value in values if value.get("is_default")]
        if selection_type == "single" and len(default_values) > 1:
            self._bad_request("Single-select groups can have at most one default option")
        for value in default_values:
            if not self._is_available(value.get("is_available", True)):
                self._bad_request("Default options must be available")

    def _validate_group_payload(self, data: Dict[str, Any], existing: Optional[Dict[str, Any]] = None) -> None:
        selection_type = self._ensure_field(
            data, "selection_type", existing.get("selection_type") if existing else None
        )
        min_select = self._ensure_field(data, "min_select", existing.get("min_select") if existing else 0)
        max_select = self._ensure_field(data, "max_select", existing.get("max_select") if existing else None)
        free_allowance = self._ensure_field(data, "free_allowance", existing.get("free_allowance") if existing else 0)
        free_allowance_strategy = self._ensure_field(
            data,
            "free_allowance_strategy",
            existing.get("free_allowance_strategy") if existing else "HIGHEST_PRICE_FIRST",
        )
        validate_strategy = "free_allowance_strategy" in data or existing is None
        if validate_strategy:
            free_allowance_strategy = self._normalize_free_allowance_strategy(free_allowance_strategy)
        allows_quantity = self._ensure_field(
            data, "allows_quantity", existing.get("allows_quantity") if existing else False
        )
        max_quantity_per_option = self._ensure_field(
            data,
            "max_quantity_per_option",
            existing.get("max_quantity_per_option") if existing else None,
        )
        self._validate_group_rules(
            selection_type=selection_type,
            min_select=min_select,
            max_select=max_select,
            free_allowance=free_allowance,
            free_allowance_strategy=free_allowance_strategy if validate_strategy else None,
            allows_quantity=allows_quantity,
            max_quantity_per_option=max_quantity_per_option,
        )

    def _validate_item_group_overrides(self, group: Dict[str, Any], overrides: Dict[str, Any]) -> None:
        if not overrides:
            return
        effective = {
            "selection_type": group.get("selection_type"),
            "min_select": group.get("min_select"),
            "max_select": group.get("max_select"),
            "free_allowance": group.get("free_allowance"),
            "free_allowance_strategy": None,
            "allows_quantity": group.get("allows_quantity"),
            "max_quantity_per_option": group.get("max_quantity_per_option"),
        }
        override_map = {
            "min_select": "min_select_override",
            "max_select": "max_select_override",
            "free_allowance": "free_allowance_override",
            "allows_quantity": "allows_quantity_override",
            "max_quantity_per_option": "max_quantity_per_option_override",
        }
        for field, override_field in override_map.items():
            if override_field in overrides and overrides[override_field] is not None:
                effective[field] = overrides[override_field]
        self._validate_group_rules(**effective)

    def create_option_group(self, business_id: int, data: Dict[str, Any]) -> Dict[str, Any]:
        data = dict(data)
        data["free_allowance_strategy"] = self._normalize_free_allowance_strategy(data.get("free_allowance_strategy"))
        self._validate_group_payload(data)
        values = data.get("values") or []
        self._validate_group_defaults(selection_type=data.get("selection_type"), values=values)
        group_id = self.option_repo.create_group(business_id, data)
        if not group_id:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to create group")
        selection_type = data.get("selection_type")
        if selection_type == "single" and any(value.get("is_default") for value in values):
            self.option_repo.unset_default_in_group(group_id)
        for value in values:
            self.option_repo.create_value(group_id, value)
        group = self.option_repo.get_group_by_id(group_id)
        if not group:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to load group")
        group["values"] = self.option_repo.list_values_by_group(group_id)
        return group

    def update_option_group(self, group_id: int, data: Dict[str, Any]) -> Dict[str, Any]:
        data = dict(data)
        if "free_allowance_strategy" in data:
            data["free_allowance_strategy"] = self._normalize_free_allowance_strategy(
                data.get("free_allowance_strategy")
            )
        existing = self.option_repo.get_group_by_id(group_id)
        if not existing:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Option group not found")
        self._validate_group_payload(data, existing=existing)
        effective_selection_type = self._ensure_field(data, "selection_type", existing.get("selection_type"))
        if effective_selection_type == "single":
            values = self.option_repo.list_values_by_group(group_id)
            default_count = sum(1 for value in values if value.get("is_default"))
            if default_count > 1:
                self._bad_request("Single-select groups can have at most one default option")
        if self.item_option_repo.has_group_attachment(group_id):
            defaults_count = self.option_repo.count_defaults(group_id)
            if "max_select" in data:
                effective_max_select = self._ensure_field(data, "max_select", existing.get("max_select"))
                if effective_max_select is not None and defaults_count > effective_max_select:
                    self._bad_request("max_select cannot be less than the number of default options")
            if "free_allowance" in data:
                effective_free_allowance = self._ensure_field(data, "free_allowance", existing.get("free_allowance"))
                if defaults_count > (effective_free_allowance or 0):
                    self._bad_request("free_allowance cannot be less than the number of default options")
        affected = self.option_repo.update_group(group_id, data)
        if affected == 0 and not existing:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Option group not found")
        group = self.option_repo.get_group_by_id(group_id)
        if not group:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Option group not found")
        group["values"] = self.option_repo.list_values_by_group(group_id)
        return group

    def update_option_group_for_business(
        self, business_id: int, group_id: int, data: Dict[str, Any]
    ) -> Dict[str, Any]:
        self.get_option_group_for_business(business_id, group_id)
        return self.update_option_group(group_id, data)

    def list_option_groups(self, business_id: int) -> List[Dict[str, Any]]:
        return self.option_repo.list_groups_with_values(business_id)

    def get_option_group(self, group_id: int) -> Dict[str, Any]:
        group = self.option_repo.get_group_by_id(group_id)
        if not group:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Option group not found")
        group["values"] = self.option_repo.list_values_by_group(group_id)
        return group

    def get_option_group_for_business(self, business_id: int, group_id: int) -> Dict[str, Any]:
        group = self.get_option_group(group_id)
        if group.get("business_id") != business_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Option group not found")
        return group

    def delete_option_group(self, group_id: int) -> Dict[str, Any]:
        existing = self.option_repo.get_group_by_id(group_id)
        if not existing:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Option group not found")
        if self.item_option_repo.has_group_attachment(group_id):
            self._bad_request("Option group cannot be deleted while attached to catalogue items")
        if self.option_repo.has_order_usage_for_group(group_id):
            self._bad_request("Option group cannot be deleted because it is used in orders")
        affected = self.option_repo.delete_group(group_id)
        if affected == 0:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Option group not found")
        return {"message": "Option group deleted"}

    def delete_option_group_for_business(self, business_id: int, group_id: int) -> Dict[str, Any]:
        self.get_option_group_for_business(business_id, group_id)
        return self.delete_option_group(group_id)

    def create_option_value(self, group_id: int, data: Dict[str, Any]) -> Dict[str, Any]:
        group = self.option_repo.get_group_by_id(group_id)
        if not group:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Option group not found")
        if data.get("is_default") and not self._is_available(group.get("is_available")):
            self._bad_request("Default options cannot be added to unavailable groups")
        if data.get("is_default") and not self._is_available(data.get("is_available", True)):
            self._bad_request("Default options must be available")
        if data.get("is_default") and group.get("selection_type") == "single":
            self.option_repo.unset_default_in_group(group_id)
        value_id = self.option_repo.create_value(group_id, data)
        if not value_id:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to create option value"
            )
        value = self.option_repo.get_value_by_id(value_id)
        if not value:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to load option value")
        return value

    def create_option_value_for_business(
        self, business_id: int, group_id: int, data: Dict[str, Any]
    ) -> Dict[str, Any]:
        self.get_option_group_for_business(business_id, group_id)
        return self.create_option_value(group_id, data)

    def update_option_value(self, value_id: int, data: Dict[str, Any]) -> Dict[str, Any]:
        existing = self.option_repo.get_value_by_id(value_id)
        if not existing:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Option value not found")
        group = self.option_repo.get_group_by_id(existing["group_id"])
        if not group:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Option group not found")
        effective_is_default = data.get("is_default", existing.get("is_default"))
        effective_is_available = data.get("is_available", existing.get("is_available"))
        if self._is_available(effective_is_default) and not self._is_available(effective_is_available):
            self._bad_request("Default options must be available")
        if self._is_available(effective_is_default) and not self._is_available(group.get("is_available")):
            self._bad_request("Default options cannot be added to unavailable groups")
        if data.get("is_available") is False and existing.get("is_default"):
            data = dict(data)
            data["is_default"] = False
        if data.get("is_default") and group.get("selection_type") == "single":
            self.option_repo.unset_default_in_group(existing["group_id"])
        self.option_repo.update_value(value_id, data)
        updated = self.option_repo.get_value_by_id(value_id)
        if not updated:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Option value not found")
        return updated

    def update_option_value_for_business(
        self, business_id: int, value_id: int, data: Dict[str, Any]
    ) -> Dict[str, Any]:
        existing = self.option_repo.get_value_by_id(value_id)
        if not existing:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Option value not found")
        self.get_option_group_for_business(business_id, existing["group_id"])
        return self.update_option_value(value_id, data)

    def delete_option_value(self, value_id: int) -> Dict[str, Any]:
        existing = self.option_repo.get_value_by_id(value_id)
        if not existing:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Option value not found")
        if existing.get("is_default"):
            self._bad_request("Default options cannot be deleted")
        if self.option_repo.has_order_usage_for_value(value_id):
            self._bad_request("Option value cannot be deleted because it is used in orders")
        affected = self.option_repo.delete_value(value_id)
        if affected == 0:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Option value not found")
        return {"message": "Option value deleted"}

    def delete_option_value_for_business(self, business_id: int, value_id: int) -> Dict[str, Any]:
        existing = self.option_repo.get_value_by_id(value_id)
        if not existing:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Option value not found")
        self.get_option_group_for_business(business_id, existing["group_id"])
        return self.delete_option_value(value_id)

    def attach_group_to_item(self, catalogue_item_id: int, group_id: int, overrides: Dict[str, Any]) -> Dict[str, Any]:
        catalogue_item = self.catalogue_repo.get_by_id(catalogue_item_id)
        if not catalogue_item:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Catalogue item not found")
        group = self.option_repo.get_group_by_id(group_id)
        if not group:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Option group not found")
        if catalogue_item.get("business_id") != group.get("business_id"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Option group must belong to the same business as the catalogue item",
            )
        available_count = self.option_repo.count_available_values(group_id)
        if available_count == 0:
            self._bad_request("Option group must have at least one available value to attach")
        self._validate_item_group_overrides(group, overrides)
        effective_min_select = overrides.get("min_select_override", group.get("min_select") or 0)
        effective_max_select = overrides.get("max_select_override", group.get("max_select"))
        if effective_min_select and effective_min_select > available_count:
            self._bad_request("min_select cannot exceed available option values")
        if effective_max_select is not None and effective_max_select > available_count:
            self._bad_request("max_select cannot exceed available option values")
        self.item_option_repo.upsert_item_group(catalogue_item_id, group_id, overrides)
        return {"message": "Option group attached", "catalogue_item_id": catalogue_item_id, "group_id": group_id}

    def attach_group_to_item_for_business(
        self, business_id: int, catalogue_item_id: int, group_id: int, overrides: Dict[str, Any]
    ) -> Dict[str, Any]:
        catalogue_item = self.catalogue_repo.get_by_id(catalogue_item_id)
        if not catalogue_item or catalogue_item.get("business_id") != business_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Catalogue item not found")
        group = self.option_repo.get_group_by_id(group_id)
        if not group or group.get("business_id") != business_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Option group not found")
        return self.attach_group_to_item(catalogue_item_id, group_id, overrides)

    def detach_group_from_item(self, catalogue_item_id: int, group_id: int) -> Dict[str, Any]:
        affected = self.item_option_repo.detach_item_group(catalogue_item_id, group_id)
        if affected == 0:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item-group mapping not found")
        return {"message": "Option group detached", "catalogue_item_id": catalogue_item_id, "group_id": group_id}

    def detach_group_from_item_for_business(
        self, business_id: int, catalogue_item_id: int, group_id: int
    ) -> Dict[str, Any]:
        catalogue_item = self.catalogue_repo.get_by_id(catalogue_item_id)
        if not catalogue_item or catalogue_item.get("business_id") != business_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Catalogue item not found")
        group = self.option_repo.get_group_by_id(group_id)
        if not group or group.get("business_id") != business_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Option group not found")
        return self.detach_group_from_item(catalogue_item_id, group_id)

    def list_item_groups(self, catalogue_item_id: int) -> List[Dict[str, Any]]:
        return self.item_option_repo.list_item_groups(catalogue_item_id)
