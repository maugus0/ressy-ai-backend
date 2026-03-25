"""
MySQL repository for POS catalog archive snapshots.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Dict, List, Optional

from app.repositories.mysql_base import MySQLBaseRepository


class MySQLPOSCatalogArchiveRepository(MySQLBaseRepository):
    """Repository for archived internal catalog snapshots used during POS migrations."""

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

    def create_archive(
        self,
        *,
        restaurant_id: int,
        pos_integration_id: Optional[int],
        label: Optional[str],
        notes: Optional[str],
        created_by: Optional[str],
        payload: Dict[str, Any],
        status: str = "ACTIVE",
    ) -> int:
        query = """
            INSERT INTO POS_Catalog_Archives (
                restaurant_id,
                pos_integration_id,
                label,
                notes,
                created_by,
                status,
                payload,
                created_at,
                updated_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
        """
        return self._execute_insert(
            query,
            (
                restaurant_id,
                pos_integration_id,
                label,
                notes,
                created_by,
                status,
                json.dumps(payload),
            ),
        )

    def get_by_id(self, archive_id: int) -> Optional[Dict[str, Any]]:
        query = "SELECT * FROM POS_Catalog_Archives WHERE id = %s LIMIT 1"
        results = self._execute_query(query, (archive_id,))
        return self._parse_payload(results[0]) if results else None

    def list_by_integration(self, restaurant_id: int, pos_integration_id: int, limit: int = 20) -> List[Dict[str, Any]]:
        query = """
            SELECT * FROM POS_Catalog_Archives
            WHERE restaurant_id = %s AND pos_integration_id = %s
            ORDER BY created_at DESC
            LIMIT %s
        """
        return [
            self._parse_payload(row) for row in self._execute_query(query, (restaurant_id, pos_integration_id, limit))
        ]

    def update_archive(
        self,
        archive_id: int,
        *,
        status: Optional[str] = None,
        notes: Optional[str] = None,
        restored_at: Optional[datetime] = None,
    ) -> int:
        fields: List[str] = []
        params: List[Any] = []
        if status is not None:
            fields.append("status = %s")
            params.append(status)
        if notes is not None:
            fields.append("notes = %s")
            params.append(notes)
        if restored_at is not None:
            fields.append("restored_at = %s")
            params.append(restored_at)
        if not fields:
            return 0
        fields.append("updated_at = NOW()")
        params.append(archive_id)
        query = f"UPDATE POS_Catalog_Archives SET {', '.join(fields)} WHERE id = %s"
        return self._execute_update(query, tuple(params))
