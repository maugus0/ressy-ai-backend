"""
MySQL User Restaurant Metadata Repository.
Handles user-restaurant associations for dashboard user management.
"""

from typing import Dict, List, Optional

from app.repositories.mysql_base import MySQLBaseRepository


class MySQLUserRestaurantMetadataRepository(MySQLBaseRepository):
    """Repository for user-restaurant metadata operations."""

    def create_mapping(
        self,
        user_id: int,
        restaurant_id: int,
        source: str = "dashboard",
        notes: Optional[str] = None,
    ) -> int:
        """
        Create a user-restaurant mapping.

        Args:
            user_id: User ID
            restaurant_id: Restaurant ID
            source: How the association was created (dashboard, reservation, call)
            notes: Optional notes about the relationship

        Returns:
            Mapping ID
        """
        # NOTE: Using row alias syntax (AS new_row) instead of deprecated VALUES() function
        # VALUES() was deprecated in MySQL 8.0.20 and removed in MySQL 9.0
        query = """
            INSERT INTO User_Restaurant_Metadata
            (user_id, restaurant_id, source, notes, created_at, updated_at)
            VALUES (%s, %s, %s, %s, NOW(), NOW()) AS new_row
            ON DUPLICATE KEY UPDATE
                source = new_row.source,
                notes = COALESCE(new_row.notes, User_Restaurant_Metadata.notes),
                updated_at = NOW()
        """
        return self._execute_insert(query, (user_id, restaurant_id, source, notes))

    def get_mapping(self, user_id: int, restaurant_id: int) -> Optional[Dict]:
        """
        Get a specific user-restaurant mapping.

        Args:
            user_id: User ID
            restaurant_id: Restaurant ID

        Returns:
            Mapping dict or None
        """
        query = """
            SELECT id, user_id, restaurant_id, source, notes, created_at, updated_at
            FROM User_Restaurant_Metadata
            WHERE user_id = %s AND restaurant_id = %s
            LIMIT 1
        """
        results = self._execute_query(query, (user_id, restaurant_id))
        return results[0] if results else None

    def get_user_restaurants(self, user_id: int) -> List[Dict]:
        """
        Get all restaurants associated with a user.

        Args:
            user_id: User ID

        Returns:
            List of restaurant mappings
        """
        query = """
            SELECT id, user_id, restaurant_id, source, notes, created_at, updated_at
            FROM User_Restaurant_Metadata
            WHERE user_id = %s
            ORDER BY created_at DESC
        """
        return self._execute_query(query, (user_id,))

    def get_restaurant_users(
        self,
        restaurant_id: int,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Dict]:
        """
        Get all users mapped to a restaurant via metadata.

        Args:
            restaurant_id: Restaurant ID
            limit: Maximum results
            offset: Pagination offset

        Returns:
            List of user mappings
        """
        query = """
            SELECT id, user_id, restaurant_id, source, notes, created_at, updated_at
            FROM User_Restaurant_Metadata
            WHERE restaurant_id = %s
            ORDER BY created_at DESC
            LIMIT %s OFFSET %s
        """
        return self._execute_query(query, (restaurant_id, limit, offset))

    def user_belongs_to_restaurant(self, user_id: int, restaurant_id: int) -> bool:
        """
        Check if a user is associated with a restaurant via metadata.

        Args:
            user_id: User ID
            restaurant_id: Restaurant ID

        Returns:
            True if mapping exists
        """
        query = """
            SELECT 1
            FROM User_Restaurant_Metadata
            WHERE user_id = %s AND restaurant_id = %s
            LIMIT 1
        """
        results = self._execute_query(query, (user_id, restaurant_id))
        return len(results) > 0

    def delete_mapping(self, user_id: int, restaurant_id: int) -> int:
        """
        Delete a user-restaurant mapping.

        Args:
            user_id: User ID
            restaurant_id: Restaurant ID

        Returns:
            Number of rows deleted
        """
        query = """
            DELETE FROM User_Restaurant_Metadata
            WHERE user_id = %s AND restaurant_id = %s
        """
        return self._execute_update(query, (user_id, restaurant_id))

    def delete_all_user_mappings(self, user_id: int) -> int:
        """
        Delete all mappings for a user.

        Args:
            user_id: User ID

        Returns:
            Number of rows deleted
        """
        query = "DELETE FROM User_Restaurant_Metadata WHERE user_id = %s"
        return self._execute_update(query, (user_id,))

    def mark_as_spam(
        self,
        user_id: int,
        restaurant_id: int,
        reason: Optional[str] = None,
        ai_summary: Optional[str] = None,
    ) -> int:
        """
        Mark a user as spam for a specific restaurant.

        Args:
            user_id: User ID
            restaurant_id: Restaurant ID
            reason: Optional reason for marking as spam
            ai_summary: Optional AI summary of the call

        Returns:
            Number of rows updated
        """
        # Create or update mapping with is_spam = TRUE
        notes = f"Marked as spam. Reason: {reason}" if reason else "Marked as spam"
        if ai_summary:
            notes += f" | AI Summary: {ai_summary}"

        query = """
            INSERT INTO User_Restaurant_Metadata
            (user_id, restaurant_id, source, notes, is_spam, created_at, updated_at)
            VALUES (%s, %s, 'spam_marking', %s, TRUE, NOW(), NOW())
            ON DUPLICATE KEY UPDATE
                is_spam = TRUE,
                notes = COALESCE(VALUES(notes), User_Restaurant_Metadata.notes),
                updated_at = NOW()
        """
        return self._execute_insert(query, (user_id, restaurant_id, notes))

    def unmark_as_spam(self, user_id: int, restaurant_id: int) -> int:
        """
        Unmark a user as spam for a specific restaurant.

        Args:
            user_id: User ID
            restaurant_id: Restaurant ID

        Returns:
            Number of rows updated
        """
        query = """
            UPDATE User_Restaurant_Metadata
            SET is_spam = FALSE, updated_at = NOW()
            WHERE user_id = %s AND restaurant_id = %s
        """
        return self._execute_update(query, (user_id, restaurant_id))

    def is_spam(self, user_id: int, restaurant_id: int) -> bool:
        """
        Check if a user is marked as spam for a specific restaurant.

        Args:
            user_id: User ID
            restaurant_id: Restaurant ID

        Returns:
            True if user is marked as spam for this restaurant
        """
        query = """
            SELECT 1
            FROM User_Restaurant_Metadata
            WHERE user_id = %s AND restaurant_id = %s AND is_spam = TRUE
            LIMIT 1
        """
        results = self._execute_query(query, (user_id, restaurant_id))
        return len(results) > 0

    def get_spam_count_by_user(self, user_id: int) -> int:
        """
        Count how many restaurants have marked a user as spam.

        Args:
            user_id: User ID

        Returns:
            Number of restaurants that marked this user as spam
        """
        query = """
            SELECT COUNT(*) as spam_count
            FROM User_Restaurant_Metadata
            WHERE user_id = %s AND is_spam = TRUE
        """
        results = self._execute_query(query, (user_id,))
        return results[0].get("spam_count", 0) if results else 0