"""
Archive and restore helpers for POS-backed catalog migrations.
"""

from __future__ import annotations

import json
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional

from app.repositories.mysql_menu_item_option_repo import MySQLMenuItemOptionRepository
from app.repositories.mysql_menu_option_repo import MySQLMenuOptionRepository
from app.repositories.mysql_menu_repo import MySQLMenuRepository
from app.repositories.mysql_pos_catalog_archive_repo import MySQLPOSCatalogArchiveRepository
from app.repositories.mysql_pos_menu_item_mapping_repo import MySQLPOSMenuItemMappingRepository
from app.repositories.mysql_pos_option_group_mapping_repo import MySQLPOSOptionGroupMappingRepository
from app.repositories.mysql_pos_option_value_mapping_repo import MySQLPOSOptionValueMappingRepository


class POSCatalogArchiveService:
    """Creates rollback snapshots and restores archived catalog states."""

    def __init__(self):
        self.menu_repo = MySQLMenuRepository()
        self.option_repo = MySQLMenuOptionRepository()
        self.item_option_repo = MySQLMenuItemOptionRepository()
        self.menu_item_mapping_repo = MySQLPOSMenuItemMappingRepository()
        self.option_group_mapping_repo = MySQLPOSOptionGroupMappingRepository()
        self.option_value_mapping_repo = MySQLPOSOptionValueMappingRepository()
        self.archive_repo = MySQLPOSCatalogArchiveRepository()

    def _json_safe(self, value: Any) -> Any:
        if isinstance(value, dict):
            return {key: self._json_safe(val) for key, val in value.items()}
        if isinstance(value, list):
            return [self._json_safe(item) for item in value]
        if isinstance(value, datetime):
            return value.astimezone(timezone.utc).isoformat() if value.tzinfo else value.isoformat()
        if isinstance(value, date):
            return value.isoformat()
        if isinstance(value, Decimal):
            return float(value)
        return value

    def _build_archive_payload(self, restaurant_id: int, pos_integration_id: int) -> Dict[str, Any]:
        option_groups = self.option_repo.list_groups_with_values(restaurant_id)
        return self._json_safe(
            {
                "menus": self.menu_repo.get_menus_by_restaurant(restaurant_id),
                "option_groups": option_groups,
                "item_group_attachments": self.item_option_repo.list_by_restaurant(restaurant_id),
                "menu_item_mappings": self.menu_item_mapping_repo.list_by_restaurant(restaurant_id, pos_integration_id),
                "option_group_mappings": self.option_group_mapping_repo.list_by_restaurant(
                    restaurant_id, pos_integration_id
                ),
                "option_value_mappings": self.option_value_mapping_repo.list_by_restaurant(
                    restaurant_id, pos_integration_id
                ),
            }
        )

    def create_archive(
        self,
        *,
        restaurant_id: int,
        pos_integration_id: int,
        label: Optional[str],
        notes: Optional[str],
        created_by: Optional[str],
        deactivate_current_catalog: bool = False,
    ) -> Dict[str, Any]:
        payload = self._build_archive_payload(restaurant_id, pos_integration_id)
        archive_id = self.archive_repo.create_archive(
            restaurant_id=restaurant_id,
            pos_integration_id=pos_integration_id,
            label=label,
            notes=notes,
            created_by=created_by,
            payload=payload,
        )
        if deactivate_current_catalog:
            self.deactivate_current_catalog(restaurant_id, pos_integration_id)
        archive = self.archive_repo.get_by_id(archive_id)
        return archive or {"id": archive_id}

    def deactivate_current_catalog(self, restaurant_id: int, pos_integration_id: int) -> Dict[str, Any]:
        menus = self.menu_repo.get_active_items_by_restaurant(restaurant_id)
        menu_ids = [int(item["id"]) for item in menus if item.get("id") is not None]

        groups = self.option_repo.list_groups_with_values(restaurant_id, only_active=True)
        group_ids = [int(group["id"]) for group in groups if group.get("id") is not None]
        value_ids = [
            int(value["id"]) for group in groups for value in group.get("values", []) if value.get("id") is not None
        ]

        deactivated_items = self.menu_repo.set_active_state_by_ids(menu_ids, False) if menu_ids else 0
        deactivated_groups = self.option_repo.set_group_active_state_by_ids(group_ids, False) if group_ids else 0
        deactivated_values = self.option_repo.set_value_active_state_by_ids(value_ids, False) if value_ids else 0

        self.menu_item_mapping_repo.set_active_state_for_missing(
            restaurant_id=restaurant_id,
            pos_integration_id=pos_integration_id,
            active_external_item_ids=[],
            is_active=False,
        )
        self.option_group_mapping_repo.set_active_state_for_missing(
            restaurant_id=restaurant_id,
            pos_integration_id=pos_integration_id,
            active_external_group_ids=[],
            is_active=False,
        )
        self.option_value_mapping_repo.set_active_state_for_missing(
            restaurant_id=restaurant_id,
            pos_integration_id=pos_integration_id,
            active_external_value_ids=[],
            is_active=False,
        )

        return {
            "restaurant_id": restaurant_id,
            "pos_integration_id": pos_integration_id,
            "items_deactivated": deactivated_items,
            "groups_deactivated": deactivated_groups,
            "values_deactivated": deactivated_values,
        }

    def _restore_menu_row(self, row: Dict[str, Any]) -> None:
        query = """
            INSERT INTO Menus (
                id,
                restaurant_id,
                category,
                sub_category,
                item_name,
                item_desc,
                price,
                avg_prep_time,
                suggested_items,
                is_available,
                is_active,
                catalog_source,
                source_name,
                source_description,
                source_category,
                source_sub_category,
                is_special,
                created_at,
                updated_at
            )
            VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW()
            )
            ON DUPLICATE KEY UPDATE
                category = VALUES(category),
                sub_category = VALUES(sub_category),
                item_name = VALUES(item_name),
                item_desc = VALUES(item_desc),
                price = VALUES(price),
                avg_prep_time = VALUES(avg_prep_time),
                suggested_items = VALUES(suggested_items),
                is_available = VALUES(is_available),
                is_active = VALUES(is_active),
                catalog_source = VALUES(catalog_source),
                source_name = VALUES(source_name),
                source_description = VALUES(source_description),
                source_category = VALUES(source_category),
                source_sub_category = VALUES(source_sub_category),
                is_special = VALUES(is_special),
                updated_at = NOW()
        """
        self.menu_repo._execute_insert(  # pylint: disable=protected-access
            query,
            (
                row.get("id"),
                row.get("restaurant_id"),
                row.get("category"),
                row.get("sub_category"),
                row.get("item_name"),
                row.get("item_desc"),
                row.get("price", 0),
                row.get("avg_prep_time"),
                (
                    row.get("suggested_items")
                    if isinstance(row.get("suggested_items"), str) or row.get("suggested_items") is None
                    else json.dumps(row.get("suggested_items"))
                ),
                row.get("is_available", True),
                row.get("is_active", True),
                row.get("catalog_source", "INTERNAL"),
                row.get("source_name"),
                row.get("source_description"),
                row.get("source_category"),
                row.get("source_sub_category"),
                row.get("is_special", False),
            ),
        )

    def _restore_group_row(self, row: Dict[str, Any]) -> None:
        query = """
            INSERT INTO Menu_Option_Groups (
                id,
                restaurant_id,
                name,
                description,
                selection_type,
                min_select,
                max_select,
                free_allowance,
                free_allowance_strategy,
                allows_quantity,
                max_quantity_per_option,
                prompt_style,
                is_required,
                is_available,
                is_active,
                catalog_source,
                source_name,
                source_description,
                input_type,
                text_required,
                max_text_length,
                sort_order,
                created_at,
                updated_at
            )
            VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW()
            )
            ON DUPLICATE KEY UPDATE
                name = VALUES(name),
                description = VALUES(description),
                selection_type = VALUES(selection_type),
                min_select = VALUES(min_select),
                max_select = VALUES(max_select),
                free_allowance = VALUES(free_allowance),
                free_allowance_strategy = VALUES(free_allowance_strategy),
                allows_quantity = VALUES(allows_quantity),
                max_quantity_per_option = VALUES(max_quantity_per_option),
                prompt_style = VALUES(prompt_style),
                is_required = VALUES(is_required),
                is_available = VALUES(is_available),
                is_active = VALUES(is_active),
                catalog_source = VALUES(catalog_source),
                source_name = VALUES(source_name),
                source_description = VALUES(source_description),
                input_type = VALUES(input_type),
                text_required = VALUES(text_required),
                max_text_length = VALUES(max_text_length),
                sort_order = VALUES(sort_order),
                updated_at = NOW()
        """
        self.option_repo._execute_insert(  # pylint: disable=protected-access
            query,
            (
                row.get("id"),
                row.get("restaurant_id"),
                row.get("name"),
                row.get("description"),
                row.get("selection_type", "multiple"),
                row.get("min_select", 0),
                row.get("max_select"),
                row.get("free_allowance", 0),
                row.get("free_allowance_strategy", "HIGHEST_PRICE_FIRST"),
                row.get("allows_quantity", False),
                row.get("max_quantity_per_option"),
                row.get("prompt_style", "ASK_IF_MENTIONED"),
                row.get("is_required", False),
                row.get("is_available", True),
                row.get("is_active", True),
                row.get("catalog_source", "INTERNAL"),
                row.get("source_name"),
                row.get("source_description"),
                row.get("input_type", "SELECT"),
                row.get("text_required", False),
                row.get("max_text_length"),
                row.get("sort_order", 0),
            ),
        )

    def _restore_value_row(self, row: Dict[str, Any]) -> None:
        query = """
            INSERT INTO Menu_Option_Values (
                id,
                group_id,
                name,
                price_delta,
                is_default,
                is_available,
                is_active,
                catalog_source,
                source_name,
                sort_order,
                created_at,
                updated_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
            ON DUPLICATE KEY UPDATE
                group_id = VALUES(group_id),
                name = VALUES(name),
                price_delta = VALUES(price_delta),
                is_default = VALUES(is_default),
                is_available = VALUES(is_available),
                is_active = VALUES(is_active),
                catalog_source = VALUES(catalog_source),
                source_name = VALUES(source_name),
                sort_order = VALUES(sort_order),
                updated_at = NOW()
        """
        self.option_repo._execute_insert(  # pylint: disable=protected-access
            query,
            (
                row.get("id"),
                row.get("group_id"),
                row.get("name"),
                row.get("price_delta", 0),
                row.get("is_default", False),
                row.get("is_available", True),
                row.get("is_active", True),
                row.get("catalog_source", "INTERNAL"),
                row.get("source_name"),
                row.get("sort_order", 0),
            ),
        )

    def restore_archive(self, archive_id: int) -> Dict[str, Any]:
        archive = self.archive_repo.get_by_id(archive_id)
        if not archive:
            raise ValueError(f"Archive {archive_id} not found")

        restaurant_id = int(archive["restaurant_id"])
        pos_integration_id = int(archive["pos_integration_id"])
        payload = archive.get("payload") or {}

        archived_menus = payload.get("menus") or []
        archived_groups = payload.get("option_groups") or []
        archived_attachments = payload.get("item_group_attachments") or []
        archived_item_mappings = payload.get("menu_item_mappings") or []
        archived_group_mappings = payload.get("option_group_mappings") or []
        archived_value_mappings = payload.get("option_value_mappings") or []

        archived_menu_ids = [int(row["id"]) for row in archived_menus if row.get("id") is not None]
        archived_group_ids = [int(row["id"]) for row in archived_groups if row.get("id") is not None]
        archived_value_rows = [
            value for group in archived_groups for value in group.get("values", []) if value.get("id") is not None
        ]
        archived_value_ids = [int(row["id"]) for row in archived_value_rows]

        for row in archived_menus:
            self._restore_menu_row(row)

        for group in archived_groups:
            group_row = {key: value for key, value in group.items() if key != "values"}
            self._restore_group_row(group_row)
            for value in group.get("values", []):
                self._restore_value_row(value)

        attachments_by_menu_item: Dict[int, List[Dict[str, Any]]] = {}
        for attachment in archived_attachments:
            menu_item_id = attachment.get("menu_item_id")
            if menu_item_id is None:
                continue
            attachments_by_menu_item.setdefault(int(menu_item_id), []).append(attachment)

        for menu_item_id, attachments in attachments_by_menu_item.items():
            current_group_ids = {
                int(item["group_id"])
                for item in self.item_option_repo.list_item_groups(menu_item_id)
                if item.get("group_id") is not None
            }
            archived_group_ids_for_item = {
                int(item["group_id"]) for item in attachments if item.get("group_id") is not None
            }
            for group_id in current_group_ids - archived_group_ids_for_item:
                self.item_option_repo.detach_item_group(menu_item_id, group_id)
            for attachment in attachments:
                self.item_option_repo.upsert_item_group(
                    menu_item_id,
                    int(attachment["group_id"]),
                    {
                        "selection_type_override": attachment.get("selection_type_override"),
                        "min_select_override": attachment.get("min_select_override"),
                        "max_select_override": attachment.get("max_select_override"),
                        "free_allowance_override": attachment.get("free_allowance_override"),
                        "allows_quantity_override": attachment.get("allows_quantity_override"),
                        "max_quantity_per_option_override": attachment.get("max_quantity_per_option_override"),
                        "is_required_override": attachment.get("is_required_override"),
                        "sort_order": attachment.get("sort_order", 0),
                    },
                )

        current_menus = self.menu_repo.get_menus_by_restaurant(restaurant_id)
        current_menu_ids = [int(row["id"]) for row in current_menus if row.get("id") is not None]
        stale_menu_ids = [menu_id for menu_id in current_menu_ids if menu_id not in archived_menu_ids]
        if stale_menu_ids:
            self.menu_repo.set_active_state_by_ids(stale_menu_ids, False)

        current_groups = self.option_repo.list_groups_with_values(restaurant_id)
        current_group_ids = [int(row["id"]) for row in current_groups if row.get("id") is not None]
        stale_group_ids = [group_id for group_id in current_group_ids if group_id not in archived_group_ids]
        if stale_group_ids:
            self.option_repo.set_group_active_state_by_ids(stale_group_ids, False)

        current_value_ids = [
            int(value["id"])
            for group in current_groups
            for value in group.get("values", [])
            if value.get("id") is not None
        ]
        stale_value_ids = [value_id for value_id in current_value_ids if value_id not in archived_value_ids]
        if stale_value_ids:
            self.option_repo.set_value_active_state_by_ids(stale_value_ids, False)

        archived_external_item_ids = [
            str(row["external_item_id"]) for row in archived_item_mappings if row.get("external_item_id")
        ]
        archived_external_group_ids = [
            str(row["external_group_id"]) for row in archived_group_mappings if row.get("external_group_id")
        ]
        archived_external_value_ids = [
            str(row["external_value_id"]) for row in archived_value_mappings if row.get("external_value_id")
        ]

        self.menu_item_mapping_repo.set_active_state_for_missing(
            restaurant_id=restaurant_id,
            pos_integration_id=pos_integration_id,
            active_external_item_ids=archived_external_item_ids,
            is_active=False,
        )
        self.option_group_mapping_repo.set_active_state_for_missing(
            restaurant_id=restaurant_id,
            pos_integration_id=pos_integration_id,
            active_external_group_ids=archived_external_group_ids,
            is_active=False,
        )
        self.option_value_mapping_repo.set_active_state_for_missing(
            restaurant_id=restaurant_id,
            pos_integration_id=pos_integration_id,
            active_external_value_ids=archived_external_value_ids,
            is_active=False,
        )

        for mapping in archived_item_mappings:
            self.menu_item_mapping_repo.upsert_mapping(
                restaurant_id=restaurant_id,
                pos_integration_id=pos_integration_id,
                menu_item_id=int(mapping["menu_item_id"]),
                external_item_id=str(mapping["external_item_id"]),
                external_parent_item_id=mapping.get("external_parent_item_id"),
                external_object_type=mapping.get("external_object_type") or "ITEM",
                external_name=mapping.get("external_name"),
                external_version=mapping.get("external_version"),
                is_active=bool(mapping.get("is_active", True)),
            )

        for mapping in archived_group_mappings:
            self.option_group_mapping_repo.upsert_mapping(
                restaurant_id=restaurant_id,
                pos_integration_id=pos_integration_id,
                option_group_id=int(mapping["option_group_id"]),
                external_group_id=str(mapping["external_group_id"]),
                external_parent_id=mapping.get("external_parent_id"),
                external_object_type=mapping.get("external_object_type") or "OPTION_GROUP",
                external_name=mapping.get("external_name"),
                external_version=mapping.get("external_version"),
                is_active=bool(mapping.get("is_active", True)),
            )

        for mapping in archived_value_mappings:
            self.option_value_mapping_repo.upsert_mapping(
                restaurant_id=restaurant_id,
                pos_integration_id=pos_integration_id,
                option_group_id=int(mapping["option_group_id"]),
                option_value_id=int(mapping["option_value_id"]),
                external_value_id=str(mapping["external_value_id"]),
                external_group_id=mapping.get("external_group_id"),
                external_object_type=mapping.get("external_object_type") or "OPTION_VALUE",
                external_name=mapping.get("external_name"),
                external_version=mapping.get("external_version"),
                is_active=bool(mapping.get("is_active", True)),
            )

        self.archive_repo.update_archive(
            archive_id,
            status="RESTORED",
            restored_at=datetime.now(timezone.utc),
        )

        return {
            "archive_id": archive_id,
            "restaurant_id": restaurant_id,
            "pos_integration_id": pos_integration_id,
            "restored_menu_ids": archived_menu_ids,
            "restored_group_ids": archived_group_ids,
            "restored_value_ids": archived_value_ids,
        }
