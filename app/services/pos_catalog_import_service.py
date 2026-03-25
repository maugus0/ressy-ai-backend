"""
Asynchronous POS catalog import service.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set

from app.integrations.pos import build_default_pos_provider_registry
from app.integrations.pos.models import (
    POSCatalogAvailabilitySnapshot,
    POSCatalogIssue,
    POSCatalogMenuItem,
    POSCatalogOptionGroup,
    POSCatalogOptionValue,
    POSCatalogSnapshot,
)
from app.repositories.mysql_menu_item_option_repo import MySQLMenuItemOptionRepository
from app.repositories.mysql_menu_option_repo import MySQLMenuOptionRepository
from app.repositories.mysql_menu_repo import MySQLMenuRepository
from app.repositories.mysql_pos_catalog_sync_issue_repo import MySQLPOSCatalogSyncIssueRepository
from app.repositories.mysql_pos_catalog_sync_run_repo import MySQLPOSCatalogSyncRunRepository
from app.repositories.mysql_pos_integration_repo import MySQLPOSIntegrationRepository
from app.repositories.mysql_pos_menu_item_mapping_repo import MySQLPOSMenuItemMappingRepository
from app.repositories.mysql_pos_option_group_mapping_repo import MySQLPOSOptionGroupMappingRepository
from app.repositories.mysql_pos_option_value_mapping_repo import MySQLPOSOptionValueMappingRepository
from app.utils.logging_config import get_logger

logger = get_logger(__name__)


class POSCatalogImportService:
    """Imports provider catalogs into the internal menu/customization model."""

    def __init__(self):
        self.menu_repo = MySQLMenuRepository()
        self.option_repo = MySQLMenuOptionRepository()
        self.item_option_repo = MySQLMenuItemOptionRepository()
        self.pos_integration_repo = MySQLPOSIntegrationRepository()
        self.menu_item_mapping_repo = MySQLPOSMenuItemMappingRepository()
        self.option_group_mapping_repo = MySQLPOSOptionGroupMappingRepository()
        self.option_value_mapping_repo = MySQLPOSOptionValueMappingRepository()
        self.sync_run_repo = MySQLPOSCatalogSyncRunRepository()
        self.sync_issue_repo = MySQLPOSCatalogSyncIssueRepository()
        self.provider_registry = build_default_pos_provider_registry()

    @staticmethod
    def _merge_editable_value(
        current_value: Optional[Any], current_source_value: Optional[Any], new_source_value: Optional[Any]
    ) -> Optional[Any]:
        current_normalized = "" if current_value is None else str(current_value).strip()
        source_normalized = "" if current_source_value is None else str(current_source_value).strip()
        if not current_normalized or current_normalized == source_normalized:
            return new_source_value
        return current_value

    def _build_menu_create_payload(self, item: POSCatalogMenuItem) -> Dict[str, Any]:
        return {
            "category": item.category,
            "sub_category": item.sub_category,
            "item_name": item.name,
            "item_desc": item.description,
            "price": item.price,
            "avg_prep_time": item.avg_prep_time,
            "suggested_items": [],
            "is_available": item.is_available,
            "is_active": item.is_active,
            "catalog_source": "POS",
            "source_name": item.source_name or item.name,
            "source_description": item.source_description or item.description,
            "source_category": item.source_category or item.category,
            "source_sub_category": item.source_sub_category or item.sub_category,
            "is_special": False,
        }

    def _build_menu_update_payload(self, existing: Dict[str, Any], item: POSCatalogMenuItem) -> Dict[str, Any]:
        return {
            "category": self._merge_editable_value(
                existing.get("category"),
                existing.get("source_category"),
                item.category,
            ),
            "sub_category": self._merge_editable_value(
                existing.get("sub_category"),
                existing.get("source_sub_category"),
                item.sub_category,
            ),
            "item_name": self._merge_editable_value(existing.get("item_name"), existing.get("source_name"), item.name),
            "item_desc": self._merge_editable_value(
                existing.get("item_desc"),
                existing.get("source_description"),
                item.description,
            ),
            "price": item.price,
            "is_available": item.is_available,
            "is_active": item.is_active,
            "catalog_source": "POS",
            "source_name": item.source_name or item.name,
            "source_description": item.source_description or item.description,
            "source_category": item.source_category or item.category,
            "source_sub_category": item.source_sub_category or item.sub_category,
        }

    def _build_group_create_payload(self, restaurant_id: int, group: POSCatalogOptionGroup) -> Dict[str, Any]:
        return {
            "restaurant_id": restaurant_id,
            "name": group.name,
            "description": group.description,
            "selection_type": group.selection_type,
            "min_select": group.min_select,
            "max_select": group.max_select,
            "free_allowance": group.free_allowance,
            "free_allowance_strategy": group.free_allowance_strategy,
            "allows_quantity": group.allows_quantity,
            "max_quantity_per_option": group.max_quantity_per_option,
            "prompt_style": group.prompt_style,
            "is_required": group.is_required,
            "is_available": group.is_available,
            "is_active": True,
            "catalog_source": "POS",
            "source_name": group.source_name or group.name,
            "source_description": group.source_description or group.description,
            "input_type": group.input_type,
            "text_required": group.text_required,
            "max_text_length": group.max_text_length,
            "sort_order": group.sort_order,
        }

    def _build_group_update_payload(self, existing: Dict[str, Any], group: POSCatalogOptionGroup) -> Dict[str, Any]:
        return {
            "name": self._merge_editable_value(existing.get("name"), existing.get("source_name"), group.name),
            "description": self._merge_editable_value(
                existing.get("description"),
                existing.get("source_description"),
                group.description,
            ),
            "selection_type": group.selection_type,
            "min_select": group.min_select,
            "max_select": group.max_select,
            "free_allowance": group.free_allowance,
            "free_allowance_strategy": group.free_allowance_strategy,
            "allows_quantity": group.allows_quantity,
            "max_quantity_per_option": group.max_quantity_per_option,
            "is_required": group.is_required,
            "is_available": group.is_available,
            "is_active": True,
            "catalog_source": "POS",
            "source_name": group.source_name or group.name,
            "source_description": group.source_description or group.description,
            "input_type": group.input_type,
            "text_required": group.text_required,
            "max_text_length": group.max_text_length,
            "sort_order": group.sort_order,
        }

    def _build_value_create_payload(self, value: POSCatalogOptionValue) -> Dict[str, Any]:
        return {
            "name": value.name,
            "price_delta": value.price_delta,
            "is_default": value.is_default,
            "is_available": value.is_available,
            "is_active": True,
            "catalog_source": "POS",
            "source_name": value.source_name or value.name,
            "sort_order": value.sort_order,
        }

    def _build_value_update_payload(self, existing: Dict[str, Any], value: POSCatalogOptionValue) -> Dict[str, Any]:
        return {
            "name": self._merge_editable_value(existing.get("name"), existing.get("source_name"), value.name),
            "price_delta": value.price_delta,
            "is_default": value.is_default,
            "is_available": value.is_available,
            "is_active": True,
            "catalog_source": "POS",
            "source_name": value.source_name or value.name,
            "sort_order": value.sort_order,
        }

    def _record_issue(
        self,
        *,
        sync_run_id: int,
        restaurant_id: int,
        pos_integration_id: int,
        issue: POSCatalogIssue,
    ) -> None:
        existing_issue = self.sync_issue_repo.get_open_issue(
            restaurant_id=restaurant_id,
            pos_integration_id=pos_integration_id,
            issue_type=issue.issue_type,
            external_object_id=issue.external_object_id,
        )
        if existing_issue:
            self.sync_issue_repo.update_issue(
                existing_issue["id"],
                sync_run_id=sync_run_id,
                status="OPEN",
                title=issue.title,
                details=issue.details,
                severity=issue.severity,
                external_parent_id=issue.external_parent_id,
                payload=issue.payload,
                resolved_at=None,
            )
            return
        self.sync_issue_repo.create_issue(
            sync_run_id=sync_run_id,
            restaurant_id=restaurant_id,
            pos_integration_id=pos_integration_id,
            scope=issue.scope,
            issue_type=issue.issue_type,
            title=issue.title,
            severity=issue.severity,
            external_object_id=issue.external_object_id,
            external_parent_id=issue.external_parent_id,
            details=issue.details,
            payload=issue.payload,
        )

    def _attach_groups_to_item(
        self, menu_item_id: int, imported_group_ids: List[int], groups: List[POSCatalogOptionGroup]
    ) -> None:
        group_by_id = {group_id: group for group_id, group in zip(imported_group_ids, groups)}
        current_attachments = self.item_option_repo.list_item_groups(menu_item_id)
        current_group_ids = {
            int(attachment["group_id"]) for attachment in current_attachments if attachment.get("group_id") is not None
        }
        imported_group_id_set = set(imported_group_ids)

        for group_id, group in group_by_id.items():
            attachment = group.attachment
            self.item_option_repo.upsert_item_group(
                menu_item_id,
                group_id,
                {
                    "selection_type_override": attachment.selection_type,
                    "min_select_override": attachment.min_select,
                    "max_select_override": attachment.max_select,
                    "free_allowance_override": attachment.free_allowance,
                    "allows_quantity_override": attachment.allows_quantity,
                    "max_quantity_per_option_override": attachment.max_quantity_per_option,
                    "is_required_override": attachment.is_required,
                    "sort_order": attachment.sort_order,
                },
            )

        for current_group_id in current_group_ids - imported_group_id_set:
            self.item_option_repo.detach_item_group(menu_item_id, current_group_id)

    def _import_snapshot(
        self,
        integration: Dict[str, Any],
        snapshot: POSCatalogSnapshot,
        sync_run_id: int,
    ) -> Dict[str, Any]:
        restaurant_id = int(integration["restaurant_id"])
        pos_integration_id = int(integration["id"])

        item_mappings = {
            str(mapping["external_item_id"]): mapping
            for mapping in self.menu_item_mapping_repo.list_by_restaurant(restaurant_id, pos_integration_id)
        }
        group_mappings = {
            str(mapping["external_group_id"]): mapping
            for mapping in self.option_group_mapping_repo.list_by_restaurant(restaurant_id, pos_integration_id)
        }
        value_mappings = {
            str(mapping["external_value_id"]): mapping
            for mapping in self.option_value_mapping_repo.list_by_restaurant(restaurant_id, pos_integration_id)
        }

        seen_item_external_ids: Set[str] = set()
        seen_group_external_ids: Set[str] = set()
        seen_value_external_ids: Set[str] = set()
        summary = defaultdict(int)
        processed_groups: Dict[str, int] = {}

        for item in snapshot.items:
            seen_item_external_ids.add(item.external_id)

            item_mapping = item_mappings.get(item.external_id)
            if item_mapping:
                menu_item_id = int(item_mapping["menu_item_id"])
                existing_item = self.menu_repo.get_by_id(menu_item_id)
                if existing_item:
                    self.menu_repo.update_by_id(menu_item_id, self._build_menu_update_payload(existing_item, item))
                    summary["items_updated"] += 1
                else:
                    menu_item_id = self.menu_repo.create_menu(restaurant_id, self._build_menu_create_payload(item))
                    summary["items_created"] += 1
            else:
                menu_item_id = self.menu_repo.create_menu(restaurant_id, self._build_menu_create_payload(item))
                summary["items_created"] += 1

            self.menu_item_mapping_repo.upsert_mapping(
                restaurant_id=restaurant_id,
                pos_integration_id=pos_integration_id,
                menu_item_id=menu_item_id,
                external_item_id=item.external_id,
                external_parent_item_id=item.external_parent_id,
                external_object_type=item.external_object_type,
                external_name=item.source_name or item.name,
                external_version=item.external_version,
                is_active=item.is_active,
            )
            self.sync_issue_repo.mark_open_issues_resolved(
                restaurant_id=restaurant_id,
                pos_integration_id=pos_integration_id,
                external_object_id=item.external_id,
            )

            imported_group_ids_for_item: List[int] = []
            for group in item.option_groups:
                seen_group_external_ids.add(group.external_id)

                if group.external_id in processed_groups:
                    group_id = processed_groups[group.external_id]
                else:
                    group_mapping = group_mappings.get(group.external_id)
                    if group_mapping:
                        group_id = int(group_mapping["option_group_id"])
                        existing_group = self.option_repo.get_group_by_id(group_id)
                        if existing_group:
                            self.option_repo.update_group(
                                group_id, self._build_group_update_payload(existing_group, group)
                            )
                            summary["option_groups_updated"] += 1
                        else:
                            group_id = self.option_repo.create_group(
                                restaurant_id, self._build_group_create_payload(restaurant_id, group)
                            )
                            summary["option_groups_created"] += 1
                    else:
                        group_id = self.option_repo.create_group(
                            restaurant_id, self._build_group_create_payload(restaurant_id, group)
                        )
                        summary["option_groups_created"] += 1

                    self.option_group_mapping_repo.upsert_mapping(
                        restaurant_id=restaurant_id,
                        pos_integration_id=pos_integration_id,
                        option_group_id=group_id,
                        external_group_id=group.external_id,
                        external_parent_id=group.external_parent_id,
                        external_object_type=group.external_object_type,
                        external_name=group.source_name or group.name,
                        external_version=group.external_version,
                        is_active=True,
                    )
                    processed_groups[group.external_id] = group_id

                    existing_group_value_mappings = [
                        mapping
                        for mapping in value_mappings.values()
                        if str(mapping.get("external_group_id") or "") == group.external_id
                    ]
                    current_group_external_value_ids: Set[str] = set()
                    for value in group.values:
                        seen_value_external_ids.add(value.external_id)
                        current_group_external_value_ids.add(value.external_id)
                        value_mapping = value_mappings.get(value.external_id)
                        if value_mapping:
                            value_id = int(value_mapping["option_value_id"])
                            existing_value = self.option_repo.get_value_by_id(value_id)
                            if existing_value:
                                self.option_repo.update_value(
                                    value_id, self._build_value_update_payload(existing_value, value)
                                )
                                summary["option_values_updated"] += 1
                            else:
                                value_id = self.option_repo.create_value(
                                    group_id, self._build_value_create_payload(value)
                                )
                                summary["option_values_created"] += 1
                        else:
                            value_id = self.option_repo.create_value(group_id, self._build_value_create_payload(value))
                            summary["option_values_created"] += 1

                        self.option_value_mapping_repo.upsert_mapping(
                            restaurant_id=restaurant_id,
                            pos_integration_id=pos_integration_id,
                            option_group_id=group_id,
                            option_value_id=value_id,
                            external_value_id=value.external_id,
                            external_group_id=group.external_id,
                            external_object_type=value.external_object_type,
                            external_name=value.source_name or value.name,
                            external_version=value.external_version,
                            is_active=True,
                        )
                        self.sync_issue_repo.mark_open_issues_resolved(
                            restaurant_id=restaurant_id,
                            pos_integration_id=pos_integration_id,
                            external_object_id=value.external_id,
                        )

                    stale_group_value_ids = [
                        int(mapping["option_value_id"])
                        for mapping in existing_group_value_mappings
                        if str(mapping["external_value_id"]) not in current_group_external_value_ids
                    ]
                    if stale_group_value_ids:
                        summary["option_values_deactivated"] += self.option_repo.set_value_active_state_by_ids(
                            stale_group_value_ids,
                            False,
                        )

                    self.sync_issue_repo.mark_open_issues_resolved(
                        restaurant_id=restaurant_id,
                        pos_integration_id=pos_integration_id,
                        external_object_id=group.external_id,
                    )

                imported_group_ids_for_item.append(group_id)

            self._attach_groups_to_item(menu_item_id, imported_group_ids_for_item, item.option_groups)

        stale_menu_item_ids = [
            int(mapping["menu_item_id"])
            for mapping in item_mappings.values()
            if str(mapping["external_item_id"]) not in seen_item_external_ids
        ]
        stale_group_ids = [
            int(mapping["option_group_id"])
            for mapping in group_mappings.values()
            if str(mapping["external_group_id"]) not in seen_group_external_ids
        ]
        stale_value_ids = [
            int(mapping["option_value_id"])
            for mapping in value_mappings.values()
            if str(mapping["external_value_id"]) not in seen_value_external_ids
        ]

        self.menu_item_mapping_repo.set_active_state_for_missing(
            restaurant_id=restaurant_id,
            pos_integration_id=pos_integration_id,
            active_external_item_ids=list(seen_item_external_ids),
            is_active=False,
        )
        self.option_group_mapping_repo.set_active_state_for_missing(
            restaurant_id=restaurant_id,
            pos_integration_id=pos_integration_id,
            active_external_group_ids=list(seen_group_external_ids),
            is_active=False,
        )
        self.option_value_mapping_repo.set_active_state_for_missing(
            restaurant_id=restaurant_id,
            pos_integration_id=pos_integration_id,
            active_external_value_ids=list(seen_value_external_ids),
            is_active=False,
        )

        if stale_menu_item_ids:
            summary["items_deactivated"] += self.menu_repo.set_active_state_by_ids(stale_menu_item_ids, False)
        if stale_group_ids:
            summary["option_groups_deactivated"] += self.option_repo.set_group_active_state_by_ids(
                stale_group_ids, False
            )
        if stale_value_ids:
            summary["option_values_deactivated"] += self.option_repo.set_value_active_state_by_ids(
                stale_value_ids, False
            )

        for issue in snapshot.issues:
            self._record_issue(
                sync_run_id=sync_run_id,
                restaurant_id=restaurant_id,
                pos_integration_id=pos_integration_id,
                issue=issue,
            )

        summary["issues_count"] = len(snapshot.issues)
        summary["items_seen"] = len(seen_item_external_ids)
        summary["option_groups_seen"] = len(seen_group_external_ids)
        summary["option_values_seen"] = len(seen_value_external_ids)
        return dict(summary)

    def _apply_availability_snapshot(
        self,
        integration: Dict[str, Any],
        snapshot: POSCatalogAvailabilitySnapshot,
    ) -> Dict[str, Any]:
        restaurant_id = int(integration["restaurant_id"])
        pos_integration_id = int(integration["id"])

        item_mappings = {
            str(mapping["external_item_id"]): mapping
            for mapping in self.menu_item_mapping_repo.list_by_restaurant(restaurant_id, pos_integration_id)
            if mapping.get("external_item_id") is not None
        }
        value_mappings = {
            str(mapping["external_value_id"]): mapping
            for mapping in self.option_value_mapping_repo.list_by_restaurant(restaurant_id, pos_integration_id)
            if mapping.get("external_value_id") is not None
        }

        items_to_true: List[int] = []
        items_to_false: List[int] = []
        values_to_true: List[int] = []
        values_to_false: List[int] = []

        for item in snapshot.items:
            mapping = item_mappings.get(item.external_id)
            if not mapping or mapping.get("menu_item_id") is None:
                continue
            if item.is_available:
                items_to_true.append(int(mapping["menu_item_id"]))
            else:
                items_to_false.append(int(mapping["menu_item_id"]))

        for value in snapshot.option_values:
            mapping = value_mappings.get(value.external_id)
            if not mapping or mapping.get("option_value_id") is None:
                continue
            if value.is_available:
                values_to_true.append(int(mapping["option_value_id"]))
            else:
                values_to_false.append(int(mapping["option_value_id"]))

        items_updated = 0
        option_values_updated = 0
        if items_to_true:
            items_updated += self.menu_repo.bulk_update_availability(restaurant_id, items_to_true, True)
        if items_to_false:
            items_updated += self.menu_repo.bulk_update_availability(restaurant_id, items_to_false, False)
        if values_to_true:
            option_values_updated += self.option_repo.bulk_update_value_availability(values_to_true, True)
        if values_to_false:
            option_values_updated += self.option_repo.bulk_update_value_availability(values_to_false, False)

        return {
            "availability_items_seen": len(snapshot.items),
            "availability_option_values_seen": len(snapshot.option_values),
            "availability_items_updated": items_updated,
            "availability_option_values_updated": option_values_updated,
        }

    def sync_integration(
        self,
        pos_integration_id: int,
        *,
        trigger_source: str = "MANUAL",
        triggered_by: Optional[str] = None,
    ) -> Dict[str, Any]:
        integration = self.pos_integration_repo.get_by_id(pos_integration_id)
        if not integration:
            raise ValueError(f"POS integration {pos_integration_id} not found")

        sync_run_id = self.sync_run_repo.create_run(
            restaurant_id=int(integration["restaurant_id"]),
            pos_integration_id=pos_integration_id,
            trigger_source=trigger_source,
            status="PENDING",
            triggered_by=triggered_by,
        )
        self.sync_run_repo.update_run(sync_run_id, status="RUNNING", started_at=datetime.now(timezone.utc))

        try:
            provider = self.provider_registry.get_provider(integration.get("pos_type"))
            snapshot = provider.fetch_catalog(integration)
            external_account_id = snapshot.metadata.get("external_account_id")
            if external_account_id and external_account_id != integration.get("external_account_id"):
                self.pos_integration_repo.update(
                    pos_integration_id,
                    {"external_account_id": external_account_id},
                )
                integration["external_account_id"] = external_account_id
            summary = self._import_snapshot(integration, snapshot, sync_run_id)
            status = "PARTIAL" if summary.get("issues_count", 0) else "SUCCEEDED"
            self.sync_run_repo.update_run(
                sync_run_id,
                status=status,
                catalog_version=snapshot.catalog_version,
                summary=summary,
                completed_at=datetime.now(timezone.utc),
            )
            return {
                "success": True,
                "sync_run_id": sync_run_id,
                "status": status,
                "summary": summary,
            }
        except Exception as exc:
            error_message = str(exc)
            logger.exception("POS catalog import failed for integration_id=%s: %s", pos_integration_id, error_message)
            self.sync_run_repo.update_run(
                sync_run_id,
                status="FAILED",
                error_message=error_message,
                completed_at=datetime.now(timezone.utc),
            )
            self._record_issue(
                sync_run_id=sync_run_id,
                restaurant_id=int(integration["restaurant_id"]),
                pos_integration_id=pos_integration_id,
                issue=POSCatalogIssue(
                    scope="SYNC",
                    issue_type="IMPORT_FAILED",
                    title="POS catalog import failed",
                    details=error_message,
                ),
            )
            return {
                "success": False,
                "sync_run_id": sync_run_id,
                "status": "FAILED",
                "error": error_message,
            }

    def sync_integration_availability(
        self,
        pos_integration_id: int,
        *,
        begin_time: Optional[str] = None,
        trigger_source: str = "WEBHOOK",
        triggered_by: Optional[str] = None,
    ) -> Dict[str, Any]:
        integration = self.pos_integration_repo.get_by_id(pos_integration_id)
        if not integration:
            raise ValueError(f"POS integration {pos_integration_id} not found")

        sync_run_id = self.sync_run_repo.create_run(
            restaurant_id=int(integration["restaurant_id"]),
            pos_integration_id=pos_integration_id,
            trigger_source=trigger_source,
            status="PENDING",
            triggered_by=triggered_by,
        )
        self.sync_run_repo.update_run(sync_run_id, status="RUNNING", started_at=datetime.now(timezone.utc))

        try:
            provider = self.provider_registry.get_provider(integration.get("pos_type"))
            snapshot = provider.fetch_availability_updates(integration, begin_time=begin_time)
            summary = self._apply_availability_snapshot(integration, snapshot)
            self.sync_run_repo.update_run(
                sync_run_id,
                status="SUCCEEDED",
                summary=summary,
                completed_at=datetime.now(timezone.utc),
            )
            return {
                "success": True,
                "sync_run_id": sync_run_id,
                "status": "SUCCEEDED",
                "summary": summary,
            }
        except Exception as exc:
            error_message = str(exc)
            logger.exception(
                "POS availability sync failed for integration_id=%s begin_time=%s: %s",
                pos_integration_id,
                begin_time,
                error_message,
            )
            self.sync_run_repo.update_run(
                sync_run_id,
                status="FAILED",
                error_message=error_message,
                completed_at=datetime.now(timezone.utc),
            )
            self._record_issue(
                sync_run_id=sync_run_id,
                restaurant_id=int(integration["restaurant_id"]),
                pos_integration_id=pos_integration_id,
                issue=POSCatalogIssue(
                    scope="SYNC",
                    issue_type="AVAILABILITY_REFRESH_FAILED",
                    title="POS availability refresh failed",
                    details=error_message,
                    payload={"begin_time": begin_time},
                ),
            )
            return {
                "success": False,
                "sync_run_id": sync_run_id,
                "status": "FAILED",
                "error": error_message,
            }

    def sync_restaurant(
        self,
        restaurant_id: int,
        *,
        pos_type: Optional[str] = None,
        trigger_source: str = "MANUAL",
        triggered_by: Optional[str] = None,
    ) -> Dict[str, Any]:
        integrations = self.pos_integration_repo.get_enabled_integrations(restaurant_id)
        if pos_type:
            integrations = [integration for integration in integrations if integration.get("pos_type") == pos_type]
        results = [
            self.sync_integration(
                int(integration["id"]),
                trigger_source=trigger_source,
                triggered_by=triggered_by,
            )
            for integration in integrations
        ]
        return {
            "restaurant_id": restaurant_id,
            "results": results,
            "successful": sum(1 for result in results if result.get("success")),
            "failed": sum(1 for result in results if not result.get("success")),
        }

    def sync_all_enabled_integrations(self, *, pos_type: Optional[str] = None) -> Dict[str, Any]:
        integrations = self.pos_integration_repo.list_all_enabled_integrations(pos_type=pos_type)
        results = [
            self.sync_integration(
                int(integration["id"]),
                trigger_source="SCHEDULED",
                triggered_by="scheduler",
            )
            for integration in integrations
        ]
        return {
            "results": results,
            "successful": sum(1 for result in results if result.get("success")),
            "failed": sum(1 for result in results if not result.get("success")),
        }
