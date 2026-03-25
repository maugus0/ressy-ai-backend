"""
MySQL repository for POS catalog sync runs.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Dict, List, Optional

from app.repositories.mysql_base import MySQLBaseRepository


class MySQLPOSCatalogSyncRunRepository(MySQLBaseRepository):
    """Repository for POS catalog sync run tracking."""

    @staticmethod
    def _parse_summary(row: Dict[str, Any]) -> Dict[str, Any]:
        if row.get("summary") and isinstance(row["summary"], str):
            try:
                row["summary"] = json.loads(row["summary"])
            except (TypeError, json.JSONDecodeError):
                row["summary"] = {}
        elif row.get("summary") is None:
            row["summary"] = {}
        return row

    def create_run(
        self,
        *,
        restaurant_id: int,
        pos_integration_id: int,
        trigger_source: str = "SCHEDULED",
        status: str = "PENDING",
        catalog_version: Optional[str] = None,
        triggered_by: Optional[str] = None,
    ) -> int:
        query = """
            INSERT INTO POS_Catalog_Sync_Runs (
                restaurant_id,
                pos_integration_id,
                trigger_source,
                status,
                catalog_version,
                triggered_by,
                created_at,
                updated_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, NOW(), NOW())
        """
        return self._execute_insert(
            query,
            (
                restaurant_id,
                pos_integration_id,
                trigger_source,
                status,
                catalog_version,
                triggered_by,
            ),
        )

    def get_by_id(self, sync_run_id: int) -> Optional[Dict[str, Any]]:
        query = "SELECT * FROM POS_Catalog_Sync_Runs WHERE id = %s LIMIT 1"
        results = self._execute_query(query, (sync_run_id,))
        return self._parse_summary(results[0]) if results else None

    def list_by_restaurant(self, restaurant_id: int, limit: int = 20) -> List[Dict[str, Any]]:
        query = """
            SELECT * FROM POS_Catalog_Sync_Runs
            WHERE restaurant_id = %s
            ORDER BY created_at DESC
            LIMIT %s
        """
        return [self._parse_summary(row) for row in self._execute_query(query, (restaurant_id, limit))]

    def list_by_integration(self, restaurant_id: int, pos_integration_id: int, limit: int = 20) -> List[Dict[str, Any]]:
        query = """
            SELECT * FROM POS_Catalog_Sync_Runs
            WHERE restaurant_id = %s AND pos_integration_id = %s
            ORDER BY created_at DESC
            LIMIT %s
        """
        return [
            self._parse_summary(row) for row in self._execute_query(query, (restaurant_id, pos_integration_id, limit))
        ]

    def update_run(
        self,
        sync_run_id: int,
        *,
        status: Optional[str] = None,
        catalog_version: Optional[str] = None,
        summary: Optional[Dict[str, Any]] = None,
        error_message: Optional[str] = None,
        started_at: Optional[datetime] = None,
        completed_at: Optional[datetime] = None,
    ) -> int:
        fields: List[str] = []
        params: List[Any] = []
        if status is not None:
            fields.append("status = %s")
            params.append(status)
        if catalog_version is not None:
            fields.append("catalog_version = %s")
            params.append(catalog_version)
        if summary is not None:
            fields.append("summary = %s")
            params.append(json.dumps(summary))
        if error_message is not None:
            fields.append("error_message = %s")
            params.append(error_message)
        if started_at is not None:
            fields.append("started_at = %s")
            params.append(started_at)
        if completed_at is not None:
            fields.append("completed_at = %s")
            params.append(completed_at)
        if not fields:
            return 0
        fields.append("updated_at = NOW()")
        params.append(sync_run_id)
        query = f"UPDATE POS_Catalog_Sync_Runs SET {', '.join(fields)} WHERE id = %s"
        return self._execute_update(query, tuple(params))
