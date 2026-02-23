"""
MySQL User Repository for user operations.
"""

from typing import Dict, List, Optional

from app.repositories.mysql_base import MySQLBaseRepository


class MySQLUserRepository(MySQLBaseRepository):
    """Repository for user data access in MySQL."""

    def create_or_update_user(self, user_data: Dict) -> int:
        """
        Create or update user based on phone_number or email.
        Uses atomic INSERT ... ON DUPLICATE KEY UPDATE to prevent race conditions.
        Returns user ID.

        If user exists (by phone_number), updates non-null fields.
        If user doesn't exist, creates new record.
        """
        phone_number = user_data.get("phone_number")
        email = user_data.get("email")
        name = user_data.get("name")
        address = user_data.get("address")
        is_spam = user_data.get("is_spam", False)
        credit_card = user_data.get("credit_card")

        if phone_number:
            # Use atomic upsert on phone_number (has unique constraint)
            # COALESCE ensures we don't overwrite existing non-null values with NULL
            # NOTE: Using row alias syntax (AS new_row) instead of deprecated VALUES() function
            # VALUES() was deprecated in MySQL 8.0.20 and removed in MySQL 9.0
            query = """
                INSERT INTO Users (name, phone_number, email, address, is_spam, credit_card, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, NOW(), NOW()) AS new_row
                ON DUPLICATE KEY UPDATE
                    name = COALESCE(new_row.name, Users.name),
                    email = COALESCE(new_row.email, Users.email),
                    address = COALESCE(new_row.address, Users.address),
                    is_spam = new_row.is_spam,
                    credit_card = COALESCE(new_row.credit_card, Users.credit_card),
                    updated_at = NOW()
            """
            self._execute_insert(
                query,
                (name, phone_number, email, address, is_spam, credit_card),
            )
            # Fetch the user ID (either newly created or existing)
            result = self._execute_query(
                "SELECT id FROM Users WHERE phone_number = %s LIMIT 1",
                (phone_number,),
            )
            if result:
                return result[0]["id"]

        # Fall back to email lookup if no phone_number or phone lookup failed
        if email:
            # Check if user exists by email
            existing = self._execute_query(
                "SELECT id FROM Users WHERE email = %s LIMIT 1",
                (email,),
            )
            if existing:
                user_id = existing[0]["id"]
                # Update existing user
                update_query = """
                    UPDATE Users
                    SET name = COALESCE(%s, name),
                        phone_number = COALESCE(%s, phone_number),
                        address = COALESCE(%s, address),
                        is_spam = %s,
                        credit_card = COALESCE(%s, credit_card),
                        updated_at = NOW()
                    WHERE id = %s
                """
                self._execute_update(
                    update_query,
                    (name, phone_number, address, is_spam, credit_card, user_id),
                )
                return user_id

        # No phone_number and no existing email match - create new user
        # This path is rare (user without phone) but we handle it gracefully
        insert_query = """
            INSERT INTO Users (name, phone_number, email, address, is_spam, credit_card, created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, NOW(), NOW())
        """
        return self._execute_insert(
            insert_query,
            (name, phone_number, email, address, is_spam, credit_card),
        )

    def get_user_id_by_phone_or_email(self, phone_number: Optional[str], email: Optional[str]) -> Optional[int]:
        """
        Get user ID by phone number or email.
        """
        if not phone_number and not email:
            return None

        query = """
            SELECT id
            FROM Users
            WHERE (phone_number = %s AND phone_number IS NOT NULL)
               OR (email = %s AND email IS NOT NULL)
            LIMIT 1
        """
        results = self._execute_query(query, (phone_number, email))
        return results[0]["id"] if results else None

    def create_user(self, user_data: Dict) -> int:
        """Create a new user."""
        query = """
            INSERT INTO Users (name, phone_number, email, address, is_spam, credit_card, created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, NOW(), NOW())
        """
        return self._execute_insert(
            query,
            (
                user_data.get("name"),
                user_data.get("phone_number"),
                user_data.get("email"),
                user_data.get("address"),
                user_data.get("is_spam", False),
                user_data.get("credit_card"),
            ),
        )

    def get_user_by_id(self, user_id: int) -> Optional[Dict]:
        """Get user by ID."""
        query = """
            SELECT id, name, phone_number, email, address, is_spam, credit_card, created_at, updated_at
            FROM Users
            WHERE id = %s
            LIMIT 1
        """
        results = self._execute_query(query, (user_id,))
        return results[0] if results else None

    def list_users(self) -> list[Dict]:
        """List all users."""
        return self._execute_query(
            "SELECT id, name, phone_number, email, address, is_spam, credit_card, created_at, updated_at FROM Users"
        )

    def list_users_by_restaurant(
        self,
        restaurant_id: int,
        search: Optional[str] = None,
        is_spam: Optional[bool] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Dict]:
        """
        List users who have interacted with a specific restaurant.
        Users are found through:
        - User_Restaurant_Metadata (direct mapping, e.g., created via dashboard)
        - Reservations (via slot_bookings.restaurant_id)
        - Calls (via Calls.user_id matching Users.id)

        Args:
            restaurant_id: The restaurant ID to filter users by
            search: Optional search term for name, phone, or email
            is_spam: Optional filter for spam status
            limit: Maximum number of results
            offset: Pagination offset

        Returns:
            List of user dictionaries
        """
        query = """
            SELECT DISTINCT
                u.id,
                u.name,
                u.phone_number,
                u.email,
                u.address,
                u.is_spam,
                u.credit_card,
                u.created_at,
                u.updated_at
            FROM Users u
            LEFT JOIN User_Restaurant_Metadata urm ON u.id = urm.user_id
            LEFT JOIN Reservations r ON u.id = r.user_id
            LEFT JOIN Slot_Bookings sb ON r.slot_booking_id = sb.id
            LEFT JOIN Calls c ON u.id = c.user_id
            WHERE (
                urm.restaurant_id = %s
                OR sb.restaurant_id = %s
                OR c.restaurant_id = %s
            )
        """
        params: List = [restaurant_id, restaurant_id, str(restaurant_id)]

        if search:
            query += """ AND (
                u.name LIKE %s OR
                u.phone_number LIKE %s OR
                u.email LIKE %s
            )"""
            search_pattern = f"%{search}%"
            params.extend([search_pattern, search_pattern, search_pattern])

        if is_spam is not None:
            query += " AND u.is_spam = %s"
            params.append(is_spam)

        query += " ORDER BY u.created_at DESC LIMIT %s OFFSET %s"
        params.extend([limit, offset])

        return self._execute_query(query, tuple(params))

    def count_users_by_restaurant(
        self,
        restaurant_id: int,
        search: Optional[str] = None,
        is_spam: Optional[bool] = None,
    ) -> int:
        """
        Count users who have interacted with a specific restaurant.

        Args:
            restaurant_id: The restaurant ID to filter users by
            search: Optional search term for name, phone, or email
            is_spam: Optional filter for spam status

        Returns:
            Total count of matching users
        """
        query = """
            SELECT COUNT(DISTINCT u.id) as total
            FROM Users u
            LEFT JOIN User_Restaurant_Metadata urm ON u.id = urm.user_id
            LEFT JOIN Reservations r ON u.id = r.user_id
            LEFT JOIN Slot_Bookings sb ON r.slot_booking_id = sb.id
            LEFT JOIN Calls c ON u.id = c.user_id
            WHERE (
                urm.restaurant_id = %s
                OR sb.restaurant_id = %s
                OR c.restaurant_id = %s
            )
        """
        params: List = [restaurant_id, restaurant_id, restaurant_id]

        if search:
            query += """ AND (
                u.name LIKE %s OR
                u.phone_number LIKE %s OR
                u.email LIKE %s
            )"""
            search_pattern = f"%{search}%"
            params.extend([search_pattern, search_pattern, search_pattern])

        if is_spam is not None:
            query += " AND u.is_spam = %s"
            params.append(is_spam)

        results = self._execute_query(query, tuple(params))
        return results[0]["total"] if results else 0

    def get_user_statistics(self, user_id: int, restaurant_id: int) -> Dict:
        """
        Get statistics for a user at a specific restaurant.

        Returns:
            Dict with total_calls, total_orders, total_reservations
        """
        # Count calls (Calls.user_id stores the numeric Users.id)
        calls_query = """
            SELECT COUNT(*) as total
            FROM Calls
            WHERE user_id = %s AND restaurant_id = %s
        """
        calls_result = self._execute_query(calls_query, (user_id, str(restaurant_id)))
        total_calls = calls_result[0]["total"] if calls_result else 0

        # Count orders for this restaurant
        orders_query = """
            SELECT COUNT(*) as total
            FROM Orders
            WHERE user_id = %s AND restaurant_id = %s AND deleted_at IS NULL
        """
        orders_result = self._execute_query(orders_query, (user_id, restaurant_id))
        total_orders = orders_result[0]["total"] if orders_result else 0

        # Count reservations for this restaurant
        reservations_query = """
            SELECT COUNT(*) as total
            FROM Reservations r
            INNER JOIN Slot_Bookings sb ON r.slot_booking_id = sb.id
            WHERE r.user_id = %s AND sb.restaurant_id = %s
        """
        reservations_result = self._execute_query(reservations_query, (user_id, restaurant_id))
        total_reservations = reservations_result[0]["total"] if reservations_result else 0

        return {
            "total_calls": total_calls,
            "total_orders": total_orders,
            "total_reservations": total_reservations,
        }

    def get_users_statistics(self, user_ids: List[int], restaurant_id: int) -> Dict[int, Dict]:
        """
        Get statistics for multiple users at a specific restaurant (batch query).
        Avoids N+1 query problem by fetching all stats in bulk.

        Args:
            user_ids: List of user IDs to get statistics for
            restaurant_id: Restaurant ID to scope statistics to

        Returns:
            Dict mapping user_id -> {total_calls, total_orders, total_reservations}
        """
        if not user_ids:
            return {}

        # Initialize result dict with zeros for all users
        result: Dict[int, Dict] = {
            uid: {"total_calls": 0, "total_orders": 0, "total_reservations": 0} for uid in user_ids
        }

        placeholders = ", ".join(["%s"] * len(user_ids))
        # Batch query for calls (Calls.user_id stores Users.id)
        calls_query = f"""
            SELECT user_id, COUNT(*) as total
            FROM Calls
            WHERE user_id IN ({placeholders}) AND restaurant_id = %s
            GROUP BY user_id
        """
        calls_params = tuple(user_ids) + (str(restaurant_id),)
        calls_results = self._execute_query(calls_query, calls_params)
        for row in calls_results:
            try:
                uid = int(row["user_id"])
            except (TypeError, ValueError):
                uid = row["user_id"]
            if uid in result:
                result[uid]["total_calls"] = row["total"]

        # Batch query for orders for this restaurant
        orders_query = f"""
            SELECT user_id, COUNT(*) as total
            FROM Orders
            WHERE user_id IN ({placeholders}) AND restaurant_id = %s AND deleted_at IS NULL
            GROUP BY user_id
        """
        orders_params = tuple(user_ids) + (restaurant_id,)
        orders_results = self._execute_query(orders_query, orders_params)
        for row in orders_results:
            uid = row["user_id"]
            if uid in result:
                result[uid]["total_orders"] = row["total"]

        # Batch query for reservations at this restaurant
        reservations_query = f"""
            SELECT r.user_id, COUNT(*) as total
            FROM Reservations r
            INNER JOIN Slot_Bookings sb ON r.slot_booking_id = sb.id
            WHERE r.user_id IN ({placeholders}) AND sb.restaurant_id = %s
            GROUP BY r.user_id
        """
        reservations_params = tuple(user_ids) + (restaurant_id,)
        reservations_results = self._execute_query(reservations_query, reservations_params)
        for row in reservations_results:
            uid = row["user_id"]
            if uid in result:
                result[uid]["total_reservations"] = row["total"]

        return result

    def get_user_restaurant_ids(self, user_id: int) -> List[int]:
        """
        Get all restaurant_ids associated with a user.
        Checks:
        - User_Restaurant_Metadata (direct mapping)
        - Reservations (via slot_bookings)
        - Calls (via user_id; stored restaurant_id is VARCHAR)

        Args:
            user_id: User ID

        Returns:
            List of restaurant_ids the user is associated with
        """
        query = """
            SELECT DISTINCT restaurant_id FROM (
                -- From metadata table
                SELECT restaurant_id
                FROM User_Restaurant_Metadata
                WHERE user_id = %s

                UNION

                -- From reservations
                SELECT sb.restaurant_id
                FROM Reservations r
                INNER JOIN Slot_Bookings sb ON r.slot_booking_id = sb.id
                WHERE r.user_id = %s

                UNION

                -- From calls
                SELECT CAST(restaurant_id AS UNSIGNED) as restaurant_id
                FROM Calls
                WHERE user_id = %s AND restaurant_id IS NOT NULL
            ) AS combined
            WHERE restaurant_id IS NOT NULL
        """
        results = self._execute_query(query, (user_id, user_id, user_id))
        return [int(r["restaurant_id"]) for r in results if r.get("restaurant_id")]

    def user_belongs_to_restaurant(self, user_id: int, restaurant_id: int) -> bool:
        """
        Check if a user is associated with a specific restaurant.
        Checks metadata, reservations, and calls.

        Args:
            user_id: User ID
            restaurant_id: Restaurant ID

        Returns:
            True if user is associated with the restaurant
        """
        query = """
            SELECT 1 FROM (
                -- Check metadata table
                SELECT 1 as found
                FROM User_Restaurant_Metadata
                WHERE user_id = %s AND restaurant_id = %s

                UNION

                -- Check reservations
                SELECT 1 as found
                FROM Reservations r
                INNER JOIN Slot_Bookings sb ON r.slot_booking_id = sb.id
                WHERE r.user_id = %s AND sb.restaurant_id = %s

                UNION

                -- Check calls
                SELECT 1 as found
                FROM Calls
                WHERE user_id = %s AND restaurant_id = %s
            ) AS combined
            LIMIT 1
        """
        results = self._execute_query(
            query,
            (user_id, restaurant_id, user_id, restaurant_id, user_id, str(restaurant_id)),
        )
        return len(results) > 0

    def update_user(self, user_id: int, user_data: Dict) -> int:
        """Update user fields."""
        fields = []
        params = []
        for key in ["name", "phone_number", "email", "address", "is_spam", "credit_card"]:
            if key in user_data:
                fields.append(f"{key} = %s")
                params.append(user_data[key])
        if not fields:
            return 0
        fields.append("updated_at = NOW()")
        params.append(user_id)
        query = f"UPDATE Users SET {', '.join(fields)} WHERE id = %s"
        return self._execute_update(query, tuple(params))

    def delete_user(self, user_id: int) -> int:
        """Delete user by id."""
        return self._execute_update("DELETE FROM Users WHERE id = %s", (user_id,))

    def mark_user_global_spam(self, user_id: int, reason: Optional[str] = None) -> int:
        """
        Mark a user as global spam in the Users table.
        Uses atomic UPDATE to prevent race conditions.

        Args:
            user_id: User ID
            reason: Optional reason for global spam marking

        Returns:
            Number of rows updated
        """
        query = "UPDATE Users SET is_spam = TRUE, updated_at = NOW() WHERE id = %s AND is_spam = FALSE"
        return self._execute_update(query, (user_id,))

    def get_user_spam_status(self, user_id: int, restaurant_id: int) -> Dict:
        """
        Get spam status for a user (both restaurant-specific and global).

        Args:
            user_id: User ID
            restaurant_id: Restaurant ID

        Returns:
            Dictionary with spam status information
        """
        user = self.get_user_by_id(user_id)
        if not user:
            return {"error": "User not found"}

        # Check restaurant-specific spam
        from app.repositories.mysql_user_restaurant_metadata_repo import (
            MySQLUserRestaurantMetadataRepository,
        )

        metadata_repo = MySQLUserRestaurantMetadataRepository()
        is_restaurant_spam = metadata_repo.is_spam(user_id, restaurant_id)
        spam_count = metadata_repo.get_spam_count_by_user(user_id)

        return {
            "user_id": user_id,
            "restaurant_id": restaurant_id,
            "is_global_spam": bool(user.get("is_spam", False)),
            "is_restaurant_spam": is_restaurant_spam,
            "spam_restaurant_count": spam_count,
        }
