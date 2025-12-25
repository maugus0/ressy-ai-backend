"""
MySQL repository for managing restaurant client users (client-facing CRM users).
"""

from typing import Any, Dict, List, Optional, Sequence, Tuple

from mysql.connector import Error

from app.repositories.mysql_base import MySQLBaseRepository
from app.utils.permission_utils import apply_permission_normalization


class MySQLRestaurantAdminRepository(MySQLBaseRepository):
    """Repository for Restaurant_Administrators CRUD and related lookups (client users)."""

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

    # --------- Restaurant client-user CRUD ---------
    def get_client_user_by_restaurant_and_email(self, restaurant_id: int, email: str) -> Optional[Dict[str, Any]]:
        results = self._execute_query(
            """
            SELECT uuid, rest_id AS restaurant_id, email, role_id, password
            FROM Restaurant_Administrators
            WHERE rest_id = %s AND email = %s
            LIMIT 1
            """,
            (restaurant_id, email),
        )
        return results[0] if results else None

    def get_client_user_by_uuid(self, admin_uuid: str) -> Optional[Dict[str, Any]]:
        results = self._execute_query(
            """
            SELECT
                ra.uuid,
                ra.rest_id AS restaurant_id,
                r.name AS restaurant_name,
                ra.email,
                ra.role_id,
                cr.role AS role_name,
                p.routes AS permissions,
                ra.created_at,
                ra.updated_at,
                ra.last_login,
                ra.last_active
            FROM Restaurant_Administrators ra
            JOIN Restaurants r ON r.id = ra.rest_id
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
                ra.rest_id AS restaurant_id,
                r.name AS restaurant_name,
                ra.email,
                ra.role_id,
                cr.role AS role_name,
                p.routes AS permissions,
                ra.created_at,
                ra.updated_at,
                ra.last_login,
                ra.last_active
            FROM Restaurant_Administrators ra
            JOIN Restaurants r ON r.id = ra.rest_id
            JOIN Crm_roles cr ON cr.id = ra.role_id
            JOIN Permissions p ON p.id = cr.permission_id
            WHERE ra.uuid IN ({placeholders})
            ORDER BY ra.created_at DESC
        """
        rows = self._execute_query(query, tuple(uuids))
        return [apply_permission_normalization(row) for row in rows]

    def create_client_user(
        self, admin_uuid: str, restaurant_id: int, email: str, password_hash: str, role_id: int
    ) -> Dict[str, Any]:
        self._execute_insert(
            """
            INSERT INTO Restaurant_Administrators (uuid, rest_id, email, password, role_id, created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s, UTC_TIMESTAMP(), UTC_TIMESTAMP())
            """,
            (admin_uuid, restaurant_id, email, password_hash, role_id),
        )
        created = self.get_client_user_by_uuid(admin_uuid)
        return created or {}

    def bulk_create_client_users(self, restaurant_id: int, admins: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if not admins:
            return []

        insert_query = """
            INSERT INTO Restaurant_Administrators (uuid, rest_id, email, password, role_id, created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s, UTC_TIMESTAMP(), UTC_TIMESTAMP())
        """
        params = [
            (admin["uuid"], restaurant_id, admin["email"], admin["password"], admin["role_id"]) for admin in admins
        ]

        try:
            self._execute_many(insert_query, params)
        except Exception as err:
            raise RuntimeError(f"Bulk insert client users failed: {err}") from err

        uuids = [admin["uuid"] for admin in admins]
        return self._fetch_by_uuids(uuids)

    def update_client_user(self, admin_uuid: str, fields: Dict[str, Any]) -> Dict[str, Any]:
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
        query = f"UPDATE Restaurant_Administrators SET {', '.join(updates)} WHERE uuid = %s"
        affected = self._execute_update(query, tuple(params))
        if affected == 0:
            return {}
        updated = self.get_client_user_by_uuid(admin_uuid)
        return updated or {}

    def update_client_user_password(self, admin_uuid: str, password_hash: str) -> int:
        return self._execute_update(
            """
            UPDATE Restaurant_Administrators
            SET password = %s, updated_at = UTC_TIMESTAMP()
            WHERE uuid = %s
            """,
            (password_hash, admin_uuid),
        )

    def update_client_user_role(self, admin_uuid: str, role_id: int) -> int:
        return self._execute_update(
            """
            UPDATE Restaurant_Administrators
            SET role_id = %s, updated_at = UTC_TIMESTAMP()
            WHERE uuid = %s
            """,
            (role_id, admin_uuid),
        )

    def delete_client_user(self, admin_uuid: str) -> int:
        return self._execute_update("DELETE FROM Restaurant_Administrators WHERE uuid = %s", (admin_uuid,))

    def count_client_users_by_restaurant(self, restaurant_id: int) -> int:
        rows = self._execute_query(
            "SELECT COUNT(*) AS total FROM Restaurant_Administrators WHERE rest_id = %s",
            (restaurant_id,),
        )
        return int(rows[0]["total"]) if rows else 0

    # --------- Queries ---------
    def list_client_users_by_restaurant(
        self, restaurant_id: int, page: int, limit: int, role_id: Optional[int]
    ) -> Tuple[List[Dict[str, Any]], int]:
        filters = ["ra.rest_id = %s"]
        params: List[Any] = [restaurant_id]
        if role_id is not None:
            filters.append("ra.role_id = %s")
            params.append(role_id)
        where_clause = " AND ".join(filters)
        offset = (page - 1) * limit

        count_query = f"SELECT COUNT(*) AS total FROM Restaurant_Administrators ra WHERE {where_clause}"
        total_rows = self._execute_query(count_query, tuple(params))
        total = int(total_rows[0]["total"]) if total_rows else 0

        data_query = f"""
            SELECT
                ra.uuid,
                ra.rest_id AS restaurant_id,
                r.name AS restaurant_name,
                ra.email,
                ra.role_id,
                cr.role AS role_name,
                p.routes AS permissions,
                ra.created_at,
                ra.updated_at,
                ra.last_login,
                ra.last_active
            FROM Restaurant_Administrators ra
            JOIN Restaurants r ON r.id = ra.rest_id
            JOIN Crm_roles cr ON cr.id = ra.role_id
            JOIN Permissions p ON p.id = cr.permission_id
            WHERE {where_clause}
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
            WHERE user_id = %s AND user_type = 'restaurant'
            """,
            (user_uuid,),
        )
