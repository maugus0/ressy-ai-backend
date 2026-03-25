"""
Admin helpers for catalog sync runs, issues, and inactive imported objects.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List

from app.repositories.mysql_menu_option_repo import MySQLMenuOptionRepository
from app.repositories.mysql_menu_repo import MySQLMenuRepository
from app.repositories.mysql_pos_catalog_sync_issue_repo import MySQLPOSCatalogSyncIssueRepository
from app.repositories.mysql_pos_catalog_sync_run_repo import MySQLPOSCatalogSyncRunRepository
from app.repositories.mysql_pos_menu_item_mapping_repo import MySQLPOSMenuItemMappingRepository
from app.repositories.mysql_pos_option_group_mapping_repo import MySQLPOSOptionGroupMappingRepository
from app.repositories.mysql_pos_option_value_mapping_repo import MySQLPOSOptionValueMappingRepository


class POSCatalogAdminService:
    """Provides read/write admin operations around async POS catalog imports."""

    def __init__(self):
        self.menu_repo = MySQLMenuRepository()
        self.option_repo = MySQLMenuOptionRepository()
        self.sync_run_repo = MySQLPOSCatalogSyncRunRepository()
        self.sync_issue_repo = MySQLPOSCatalogSyncIssueRepository()
        self.menu_item_mapping_repo = MySQLPOSMenuItemMappingRepository()
        self.option_group_mapping_repo = MySQLPOSOptionGroupMappingRepository()
        self.option_value_mapping_repo = MySQLPOSOptionValueMappingRepository()

    def list_sync_runs(self, restaurant_id: int, pos_integration_id: int, limit: int = 20) -> List[Dict[str, Any]]:
        return self.sync_run_repo.list_by_integration(restaurant_id, pos_integration_id, limit=limit)

    def get_sync_run(self, restaurant_id: int, pos_integration_id: int, sync_run_id: int) -> Dict[str, Any]:
        run = self.sync_run_repo.get_by_id(sync_run_id)
        if not run:
            raise ValueError(f"Sync run {sync_run_id} not found")
        if int(run["restaurant_id"]) != int(restaurant_id) or int(run["pos_integration_id"]) != int(pos_integration_id):
            raise ValueError(f"Sync run {sync_run_id} does not belong to the requested integration")
        issues = self.sync_issue_repo.list_issues(
            restaurant_id=restaurant_id,
            pos_integration_id=pos_integration_id,
        )
        run["issues"] = [issue for issue in issues if issue.get("sync_run_id") == sync_run_id]
        return run

    def update_issue_status(
        self,
        *,
        restaurant_id: int,
        pos_integration_id: int,
        issue_id: int,
        status: str,
    ) -> Dict[str, Any]:
        issue = self.sync_issue_repo.get_by_id(issue_id)
        if not issue:
            raise ValueError(f"Issue {issue_id} not found")
        if int(issue["restaurant_id"]) != int(restaurant_id) or int(issue["pos_integration_id"]) != int(
            pos_integration_id
        ):
            raise ValueError(f"Issue {issue_id} does not belong to the requested integration")

        resolved_at = datetime.now(timezone.utc) if status in {"RESOLVED", "IGNORED"} else None
        self.sync_issue_repo.update_issue(issue_id, status=status, resolved_at=resolved_at)
        updated = self.sync_issue_repo.get_by_id(issue_id)
        if not updated:
            raise ValueError(f"Issue {issue_id} could not be reloaded after update")
        return updated

    def list_inactive_catalog(self, restaurant_id: int, pos_integration_id: int) -> Dict[str, Any]:
        inactive_items = []
        for mapping in self.menu_item_mapping_repo.list_by_restaurant(restaurant_id, pos_integration_id):
            if mapping.get("is_active"):
                continue
            item = self.menu_repo.get_by_id(int(mapping["menu_item_id"]))
            inactive_items.append({"mapping": mapping, "item": item})

        inactive_groups = []
        for mapping in self.option_group_mapping_repo.list_by_restaurant(restaurant_id, pos_integration_id):
            if mapping.get("is_active"):
                continue
            group = self.option_repo.get_group_by_id(int(mapping["option_group_id"]))
            inactive_groups.append({"mapping": mapping, "group": group})

        inactive_values = []
        for mapping in self.option_value_mapping_repo.list_by_restaurant(restaurant_id, pos_integration_id):
            if mapping.get("is_active"):
                continue
            value = self.option_repo.get_value_by_id(int(mapping["option_value_id"]))
            inactive_values.append({"mapping": mapping, "value": value})

        return {
            "restaurant_id": restaurant_id,
            "pos_integration_id": pos_integration_id,
            "inactive_items": inactive_items,
            "inactive_option_groups": inactive_groups,
            "inactive_option_values": inactive_values,
        }
