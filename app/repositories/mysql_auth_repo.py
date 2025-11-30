import json
from typing import Any, Dict, Optional

from app.repositories.mysql_base import MySQLBaseRepository


class MySQLAuthRepository(MySQLBaseRepository):
    """Repository for authentication-related data access."""

    def get_admin_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        results = self._execute_query(
            """
            SELECT uuid, email, password, role_id, last_login, last_active
            FROM Ressy_Administrator
            WHERE email = %s
            LIMIT 1
            """,
            (email,),
        )
        return results[0] if results else None

    def get_admin_by_uuid(self, user_uuid: str) -> Optional[Dict[str, Any]]:
        results = self._execute_query(
            """
            SELECT uuid, email, password, role_id, last_login, last_active
            FROM Ressy_Administrator
            WHERE uuid = %s
            LIMIT 1
            """,
            (user_uuid,),
        )
        return results[0] if results else None

    def get_restaurant_admin_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        results = self._execute_query(
            """
            SELECT uuid, rest_id, email, password, role_id, last_login, last_active
            FROM Restaurant_Administrators
            WHERE email = %s
            LIMIT 1
            """,
            (email,),
        )
        return results[0] if results else None

    def get_restaurant_admin_by_uuid(self, user_uuid: str) -> Optional[Dict[str, Any]]:
        results = self._execute_query(
            """
            SELECT uuid, rest_id, email, password, role_id, last_login, last_active
            FROM Restaurant_Administrators
            WHERE uuid = %s
            LIMIT 1
            """,
            (user_uuid,),
        )
        return results[0] if results else None

    def update_admin_login_times(self, user_uuid: str):
        return self._execute_update(
            """
            UPDATE Ressy_Administrator
            SET last_login = UTC_TIMESTAMP(), last_active = UTC_TIMESTAMP()
            WHERE uuid = %s
            """,
            (user_uuid,),
        )

    def update_restaurant_admin_login_times(self, user_uuid: str):
        return self._execute_update(
            """
            UPDATE Restaurant_Administrators
            SET last_login = UTC_TIMESTAMP(), last_active = UTC_TIMESTAMP()
            WHERE uuid = %s
            """,
            (user_uuid,),
        )

    def touch_last_active(self, user_uuid: str, user_type: str):
        if user_type == "admin":
            query = "UPDATE Ressy_Administrator SET last_active = UTC_TIMESTAMP() WHERE uuid = %s"
        elif user_type == "restaurant":
            query = "UPDATE Restaurant_Administrators SET last_active = UTC_TIMESTAMP() WHERE uuid = %s"
        else:
            return 0
        return self._execute_update(query, (user_uuid,))

    def get_role_with_permissions(self, role_id: int) -> Optional[Dict[str, Any]]:
        results = self._execute_query(
            """
            SELECT r.id, r.role, p.routes
            FROM Crm_roles r
            JOIN Permissions p ON p.id = r.permission_id
            WHERE r.id = %s
            LIMIT 1
            """,
            (role_id,),
        )
        if not results:
            return None
        role_row = results[0]
        routes = role_row.get("routes")
        permissions: list[str]
        if isinstance(routes, str):
            try:
                parsed = json.loads(routes)
                permissions = parsed if isinstance(parsed, list) else []
            except json.JSONDecodeError:
                permissions = []
        elif isinstance(routes, list):
            permissions = routes
        else:
            permissions = []
        role_row["permissions"] = [str(p) for p in permissions]
        return role_row

    def get_restaurant_details(self, restaurant_id: int) -> Optional[Dict[str, Any]]:
        results = self._execute_query(
            """
            SELECT id, name
            FROM Restaurants
            WHERE id = %s
            LIMIT 1
            """,
            (restaurant_id,),
        )
        return results[0] if results else None

    def create_session(
        self,
        session_id: str,
        user_id: str,
        user_type: str,
        refresh_token_hash: str,
        refresh_ttl_seconds: int,
        user_agent: Optional[str],
        ip_address: Optional[str],
    ):
        return self._execute_insert(
            """
            INSERT INTO Auth_Sessions (
                id,
                user_id,
                user_type,
                refresh_token_hash,
                created_at,
                expires_at,
                revoked,
                user_agent,
                ip_address
            ) VALUES (
                %s,
                %s,
                %s,
                %s,
                UTC_TIMESTAMP(),
                DATE_ADD(UTC_TIMESTAMP(), INTERVAL %s SECOND),
                0,
                %s,
                %s
            )
            """,
            (session_id, user_id, user_type, refresh_token_hash, refresh_ttl_seconds, user_agent, ip_address),
        )

    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        results = self._execute_query(
            """
            SELECT
                id,
                user_id,
                user_type,
                refresh_token_hash,
                created_at,
                expires_at,
                revoked,
                user_agent,
                ip_address
            FROM Auth_Sessions
            WHERE id = %s
            LIMIT 1
            """,
            (session_id,),
        )
        return results[0] if results else None

    def update_session_refresh_token(
        self,
        session_id: str,
        refresh_token_hash: str,
        refresh_ttl_seconds: int,
        user_agent: Optional[str],
        ip_address: Optional[str],
    ):
        return self._execute_update(
            """
            UPDATE Auth_Sessions
            SET refresh_token_hash = %s,
                expires_at = DATE_ADD(UTC_TIMESTAMP(), INTERVAL %s SECOND),
                revoked = 0,
                user_agent = %s,
                ip_address = %s
            WHERE id = %s
            """,
            (refresh_token_hash, refresh_ttl_seconds, user_agent, ip_address, session_id),
        )

    def revoke_session(self, session_id: str):
        return self._execute_update(
            """
            UPDATE Auth_Sessions
            SET revoked = 1,
                expires_at = UTC_TIMESTAMP()
            WHERE id = %s
            """,
            (session_id,),
        )
