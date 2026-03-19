"""
MySQL User Restaurant Metadata Repository.
Handles user-business associations for dashboard user management.
"""

from typing import Dict, List, Optional

from app.repositories.mysql_base import MySQLBaseRepository


class MySQLUserRestaurantMetadataRepository(MySQLBaseRepository):
    """Repository for user-business metadata operations."""

    def create_mapping(
        self,
        user_id: int,
        business_id: int,
        source: str = "dashboard",
        notes: Optional[str] = None,
    ) -> int:
        """
        Create a user-business mapping.

        Args:
            user_id: User ID
            business_id: Restaurant ID
            source: How the association was created (dashboard, reservation, call)
            notes: Optional notes about the relationship

        Returns:
            Mapping ID
        """
        # NOTE: Using row alias syntax (AS new_row) instead of deprecated VALUES() function
        # VALUES() was deprecated in MySQL 8.0.20 and removed in MySQL 9.0
        query = """
            INSERT INTO User_Business_Metadata
            (user_id, business_id, source, notes, created_at, updated_at)
            VALUES (%s, %s, %s, %s, NOW(), NOW()) AS new_row
            ON DUPLICATE KEY UPDATE
                source = new_row.source,
                notes = COALESCE(new_row.notes, User_Business_Metadata.notes),
                updated_at = NOW()
        """
        return self._execute_insert(query, (user_id, business_id, source, notes))

    def get_mapping(self, user_id: int, business_id: int) -> Optional[Dict]:
        """
        Get a specific user-business mapping.

        Args:
            user_id: User ID
            business_id: Restaurant ID

        Returns:
            Mapping dict or None
        """
        query = """
            SELECT id, user_id, business_id, source, notes, created_at, updated_at
            FROM User_Business_Metadata
            WHERE user_id = %s AND business_id = %s
            LIMIT 1
        """
        results = self._execute_query(query, (user_id, business_id))
        return results[0] if results else None

    def get_user_businesss(self, user_id: int) -> List[Dict]:
        """
        Get all businesss associated with a user.

        Args:
            user_id: User ID

        Returns:
            List of business mappings
        """
        query = """
            SELECT id, user_id, business_id, source, notes, created_at, updated_at
            FROM User_Business_Metadata
            WHERE user_id = %s
            ORDER BY created_at DESC
        """
        return self._execute_query(query, (user_id,))

    def get_business_users(
        self,
        business_id: int,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Dict]:
        """
        Get all users mapped to a business via metadata.

        Args:
            business_id: Restaurant ID
            limit: Maximum results
            offset: Pagination offset

        Returns:
            List of user mappings
        """
        query = """
            SELECT id, user_id, business_id, source, notes, created_at, updated_at
            FROM User_Business_Metadata
            WHERE business_id = %s
            ORDER BY created_at DESC
            LIMIT %s OFFSET %s
        """
        return self._execute_query(query, (business_id, limit, offset))

    def user_belongs_to_business(self, user_id: int, business_id: int) -> bool:
        """
        Check if a user is associated with a business via metadata.

        Args:
            user_id: User ID
            business_id: Restaurant ID

        Returns:
            True if mapping exists
        """
        query = """
            SELECT 1
            FROM User_Business_Metadata
            WHERE user_id = %s AND business_id = %s
            LIMIT 1
        """
        results = self._execute_query(query, (user_id, business_id))
        return len(results) > 0

    def delete_mapping(self, user_id: int, business_id: int) -> int:
        """
        Delete a user-business mapping.

        Args:
            user_id: User ID
            business_id: Restaurant ID

        Returns:
            Number of rows deleted
        """
        query = """
            DELETE FROM User_Business_Metadata
            WHERE user_id = %s AND business_id = %s
        """
        return self._execute_update(query, (user_id, business_id))

    def delete_all_user_mappings(self, user_id: int) -> int:
        """
        Delete all mappings for a user.

        Args:
            user_id: User ID

        Returns:
            Number of rows deleted
        """
        query = "DELETE FROM User_Business_Metadata WHERE user_id = %s"
        return self._execute_update(query, (user_id,))
