"""
MySQL repository for managing Ressy platform admin users (Admin CRM users).
"""

from typing import Any, Dict, List, Optional, Sequence, Tuple

from mysql.connector import Error

from app.repositories.mysql_base import MySQLBaseRepository
from app.utils.permission_utils import apply_permission_normalization


class MySQLRessyAdminRepository(MySQLBaseRepository):
    """Repository for Ressy_Administrator CRUD and related lookups (admin users)."""

    # --------- Role lookups ---------
    def get_role_with_permissions(self, role_id: int) -> Optional[Dict[str, Any]]:
        results = self._execute_query(
            """
            SELECT r.id, r.role, p.routes AS permissions
            FROM Crm_roles r
            JOIN Permissions p ON p.id = r.permission_id
            WHERE r.id = %s
            LIMIT 1
            """,
            (role_id,),
        )
        if not results:
            return None
        return apply_permission_normalization(results[0])

    # --------- Ressy admin user CRUD ---------
    def get_admin_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        results = self._execute_query(
            """
            SELECT uuid, email, role_id, password
            FROM Ressy_Administrator
            WHERE email = %s
            LIMIT 1
            """,
            (email,),
        )
        return results[0] if results else None

    def get_admin_by_uuid(self, admin_uuid: str) -> Optional[Dict[str, Any]]:
        results = self._execute_query(
            """
            SELECT
                ra.uuid,
                ra.email,
                ra.role_id,
                cr.role AS role_name,
                p.routes AS permissions,
                ra.created_at,
                ra.updated_at,
                ra.last_login,
                ra.last_active
            FROM Ressy_Administrator ra
            JOIN Crm_roles cr ON cr.id = ra.role_id
            JOIN Permissions p ON p.id = cr.permission_id
            WHERE ra.uuid = %s
            LIMIT 1
            """,
            (admin_uuid,),
        )
        if not results:
            return None
        return apply_permission_normalization(results[0])

    def _fetch_by_uuids(self, uuids: Sequence[str]) -> List[Dict[str, Any]]:
        if not uuids:
            return []
        placeholders = ",".join(["%s"] * len(uuids))
        query = f"""
            SELECT
                ra.uuid,
                ra.email,
                ra.role_id,
                cr.role AS role_name,
                p.routes AS permissions,
                ra.created_at,
                ra.updated_at,
                ra.last_login,
                ra.last_active
            FROM Ressy_Administrator ra
            JOIN Crm_roles cr ON cr.id = ra.role_id
            JOIN Permissions p ON p.id = cr.permission_id
            WHERE ra.uuid IN ({placeholders})
            ORDER BY ra.created_at DESC
        """
        rows = self._execute_query(query, tuple(uuids))
        return [apply_permission_normalization(row) for row in rows]

    def create_admin_user(self, admin_uuid: str, email: str, password_hash: str, role_id: int) -> Dict[str, Any]:
        self._execute_insert(
            """
            INSERT INTO Ressy_Administrator (uuid, email, password, role_id, created_at, updated_at)
            VALUES (%s, %s, %s, %s, UTC_TIMESTAMP(), UTC_TIMESTAMP())
            """,
            (admin_uuid, email, password_hash, role_id),
        )
        created = self.get_admin_by_uuid(admin_uuid)
        return created or {}

    def bulk_create_admin_users(self, admins: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if not admins:
            return []

        insert_query = """
            INSERT INTO Ressy_Administrator (uuid, email, password, role_id, created_at, updated_at)
            VALUES (%s, %s, %s, %s, UTC_TIMESTAMP(), UTC_TIMESTAMP())
        """
        params = [(admin["uuid"], admin["email"], admin["password"], admin["role_id"]) for admin in admins]

        try:
            self._execute_many(insert_query, params)
        except Exception as err:
            raise RuntimeError(f"Bulk insert admin users failed: {err}") from err

        uuids = [admin["uuid"] for admin in admins]
        return self._fetch_by_uuids(uuids)

    def update_admin_user(self, admin_uuid: str, fields: Dict[str, Any]) -> Dict[str, Any]:
        if not fields:
            return {}
        updates = []
        params: List[Any] = []
        for key in ["email", "password", "role_id", "last_login", "last_active"]:
            if key in fields:
                updates.append(f"{key} = %s")
                params.append(fields[key])
        updates.append("updated_at = UTC_TIMESTAMP()")
        params.append(admin_uuid)
        query = f"UPDATE Ressy_Administrator SET {', '.join(updates)} WHERE uuid = %s"
        affected = self._execute_update(query, tuple(params))
        if affected == 0:
            return {}
        updated = self.get_admin_by_uuid(admin_uuid)
        return updated or {}

    def update_admin_user_password(self, admin_uuid: str, password_hash: str) -> int:
        return self._execute_update(
            """
            UPDATE Ressy_Administrator
            SET password = %s, updated_at = UTC_TIMESTAMP()
            WHERE uuid = %s
            """,
            (password_hash, admin_uuid),
        )

    def update_admin_user_role(self, admin_uuid: str, role_id: int) -> int:
        return self._execute_update(
            """
            UPDATE Ressy_Administrator
            SET role_id = %s, updated_at = UTC_TIMESTAMP()
            WHERE uuid = %s
            """,
            (role_id, admin_uuid),
        )

    def delete_admin_user(self, admin_uuid: str) -> int:
        return self._execute_update("DELETE FROM Ressy_Administrator WHERE uuid = %s", (admin_uuid,))

    def count_admin_users(self) -> int:
        rows = self._execute_query("SELECT COUNT(*) AS total FROM Ressy_Administrator")
        return int(rows[0]["total"]) if rows else 0

    # --------- Queries ---------
    def list_admin_users(self, page: int, limit: int, role_id: Optional[int]) -> Tuple[List[Dict[str, Any]], int]:
        filters = []
        params: List[Any] = []
        if role_id is not None:
            filters.append("ra.role_id = %s")
            params.append(role_id)
        where_clause = " AND ".join(filters)
        where_sql = f"WHERE {where_clause}" if where_clause else ""
        offset = (page - 1) * limit

        count_query = f"SELECT COUNT(*) AS total FROM Ressy_Administrator ra {where_sql}"
        total_rows = self._execute_query(count_query, tuple(params))
        total = int(total_rows[0]["total"]) if total_rows else 0

        data_query = f"""
            SELECT
                ra.uuid,
                ra.email,
                ra.role_id,
                cr.role AS role_name,
                p.routes AS permissions,
                ra.created_at,
                ra.updated_at,
                ra.last_login,
                ra.last_active
            FROM Ressy_Administrator ra
            JOIN Crm_roles cr ON cr.id = ra.role_id
            JOIN Permissions p ON p.id = cr.permission_id
            {where_sql}
            ORDER BY ra.created_at DESC
            LIMIT %s OFFSET %s
        """
        items = self._execute_query(data_query, tuple(params + [limit, offset]))
        return [apply_permission_normalization(item) for item in items], total

    # --------- Session revocation ---------
    def revoke_sessions_for_user(self, user_uuid: str) -> int:
        return self._execute_update(
            """
            UPDATE Auth_Sessions
            SET revoked = 1, expires_at = UTC_TIMESTAMP()
            WHERE user_id = %s AND user_type = 'admin'
            """,
            (user_uuid,),
        )
