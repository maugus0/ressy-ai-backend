"""
MySQL repository for POS catalog sync issues.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Dict, List, Optional

from app.repositories.mysql_base import MySQLBaseRepository


class MySQLPOSCatalogSyncIssueRepository(MySQLBaseRepository):
    """Repository for POS catalog sync issue tracking."""

    @staticmethod
    def _parse_payload(row: Dict[str, Any]) -> Dict[str, Any]:
        if row.get("payload") and isinstance(row["payload"], str):
            try:
                row["payload"] = json.loads(row["payload"])
            except (TypeError, json.JSONDecodeError):
                row["payload"] = {}
        elif row.get("payload") is None:
            row["payload"] = {}
        return row

    def create_issue(
        self,
        *,
        restaurant_id: int,
        pos_integration_id: int,
        scope: str,
        issue_type: str,
        title: str,
        sync_run_id: Optional[int] = None,
        severity: str = "ERROR",
        status: str = "OPEN",
        external_object_id: Optional[str] = None,
        external_parent_id: Optional[str] = None,
        details: Optional[str] = None,
        payload: Optional[Dict[str, Any]] = None,
    ) -> int:
        query = """
            INSERT INTO POS_Catalog_Sync_Issues (
                sync_run_id,
                restaurant_id,
                pos_integration_id,
                scope,
                issue_type,
                severity,
                status,
                external_object_id,
                external_parent_id,
                title,
                details,
                payload,
                created_at,
                updated_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
        """
        return self._execute_insert(
            query,
            (
                sync_run_id,
                restaurant_id,
                pos_integration_id,
                scope,
                issue_type,
                severity,
                status,
                external_object_id,
                external_parent_id,
                title,
                details,
                json.dumps(payload) if payload is not None else None,
            ),
        )

    def list_open_issues(self, restaurant_id: int, pos_integration_id: Optional[int] = None) -> List[Dict[str, Any]]:
        params: List[Any] = [restaurant_id]
        query = """
            SELECT * FROM POS_Catalog_Sync_Issues
            WHERE restaurant_id = %s AND status IN ('OPEN', 'ACKNOWLEDGED')
        """
        if pos_integration_id is not None:
            query += " AND pos_integration_id = %s"
            params.append(pos_integration_id)
        query += " ORDER BY created_at DESC"
        return [self._parse_payload(row) for row in self._execute_query(query, tuple(params))]

    def list_issues(
        self,
        restaurant_id: int,
        pos_integration_id: Optional[int] = None,
        statuses: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        params: List[Any] = [restaurant_id]
        query = """
            SELECT * FROM POS_Catalog_Sync_Issues
            WHERE restaurant_id = %s
        """
        if pos_integration_id is not None:
            query += " AND pos_integration_id = %s"
            params.append(pos_integration_id)
        if statuses:
            placeholders = ", ".join(["%s"] * len(statuses))
            query += f" AND status IN ({placeholders})"
            params.extend(statuses)
        query += " ORDER BY created_at DESC"
        return [self._parse_payload(row) for row in self._execute_query(query, tuple(params))]

    def get_by_id(self, issue_id: int) -> Optional[Dict[str, Any]]:
        query = "SELECT * FROM POS_Catalog_Sync_Issues WHERE id = %s LIMIT 1"
        results = self._execute_query(query, (issue_id,))
        return self._parse_payload(results[0]) if results else None

    def get_open_issue(
        self,
        *,
        restaurant_id: int,
        pos_integration_id: int,
        issue_type: str,
        external_object_id: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        params: List[Any] = [restaurant_id, pos_integration_id, issue_type]
        query = """
            SELECT * FROM POS_Catalog_Sync_Issues
            WHERE restaurant_id = %s
              AND pos_integration_id = %s
              AND issue_type = %s
              AND status IN ('OPEN', 'ACKNOWLEDGED')
        """
        if external_object_id is None:
            query += " AND external_object_id IS NULL"
        else:
            query += " AND external_object_id = %s"
            params.append(external_object_id)
        query += " ORDER BY updated_at DESC LIMIT 1"
        results = self._execute_query(query, tuple(params))
        return self._parse_payload(results[0]) if results else None

    def update_issue(
        self,
        issue_id: int,
        *,
        sync_run_id: Optional[int] = None,
        status: Optional[str] = None,
        title: Optional[str] = None,
        details: Optional[str] = None,
        severity: Optional[str] = None,
        external_parent_id: Optional[str] = None,
        payload: Optional[Dict[str, Any]] = None,
        resolved_at: Optional[datetime] = None,
    ) -> int:
        fields: List[str] = []
        params: List[Any] = []
        if sync_run_id is not None:
            fields.append("sync_run_id = %s")
            params.append(sync_run_id)
        if status is not None:
            fields.append("status = %s")
            params.append(status)
        if title is not None:
            fields.append("title = %s")
            params.append(title)
        if details is not None:
            fields.append("details = %s")
            params.append(details)
        if severity is not None:
            fields.append("severity = %s")
            params.append(severity)
        if external_parent_id is not None:
            fields.append("external_parent_id = %s")
            params.append(external_parent_id)
        if payload is not None:
            fields.append("payload = %s")
            params.append(json.dumps(payload))
        if resolved_at is not None:
            fields.append("resolved_at = %s")
            params.append(resolved_at)
        if not fields:
            return 0
        fields.append("updated_at = NOW()")
        params.append(issue_id)
        query = f"UPDATE POS_Catalog_Sync_Issues SET {', '.join(fields)} WHERE id = %s"
        return self._execute_update(query, tuple(params))

    def mark_open_issues_resolved(
        self,
        *,
        restaurant_id: int,
        pos_integration_id: int,
        issue_type: Optional[str] = None,
        external_object_id: Optional[str] = None,
    ) -> int:
        params: List[Any] = [restaurant_id, pos_integration_id]
        query = """
            UPDATE POS_Catalog_Sync_Issues
            SET status = 'RESOLVED', resolved_at = NOW(), updated_at = NOW()
            WHERE restaurant_id = %s
              AND pos_integration_id = %s
              AND status IN ('OPEN', 'ACKNOWLEDGED')
        """
        if issue_type is not None:
            query += " AND issue_type = %s"
            params.append(issue_type)
        if external_object_id is not None:
            query += " AND external_object_id = %s"
            params.append(external_object_id)
        return self._execute_update(query, tuple(params))
