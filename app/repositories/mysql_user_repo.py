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
        Returns user ID.
        """
        # First, try to find existing user
        user_id = self.get_user_id_by_phone_or_email(user_data.get("phone_number"), user_data.get("email"))

        if user_id:
            # Update existing user
            query = """
                UPDATE Users
                SET name = %s,
                    email = %s,
                    address = %s,
                    is_spam = %s,
                    credit_card = %s,
                    updated_at = NOW()
                WHERE id = %s
            """
            self._execute_update(
                query,
                (
                    user_data.get("name"),
                    user_data.get("email"),
                    user_data.get("address"),
                    user_data.get("is_spam", False),
                    user_data.get("credit_card"),
                    user_id,
                ),
            )
            return user_id
        else:
            # Create new user
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
        - Calls (via calls.restaurant_id matching user phone number)

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
            LEFT JOIN Calls c ON u.phone_number = c.user_id
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
            LEFT JOIN Calls c ON u.phone_number = c.user_id
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

        results = self._execute_query(query, tuple(params))
        return results[0]["total"] if results else 0

    def get_user_statistics(self, user_id: int, restaurant_id: int) -> Dict:
        """
        Get statistics for a user at a specific restaurant.

        Returns:
            Dict with total_calls, total_orders, total_reservations
        """
        # Get the user's phone number for matching calls
        user = self.get_user_by_id(user_id)
        phone_number = user.get("phone_number") if user else None

        # Count calls (calls use phone_number as user_id)
        calls_query = """
            SELECT COUNT(*) as total
            FROM Calls
            WHERE user_id = %s AND restaurant_id = %s
        """
        calls_result = self._execute_query(calls_query, (phone_number, str(restaurant_id)))
        total_calls = calls_result[0]["total"] if calls_result else 0

        # Count orders (orders don't have direct restaurant link, count all for user)
        orders_query = """
            SELECT COUNT(*) as total
            FROM Orders
            WHERE user_id = %s
        """
        orders_result = self._execute_query(orders_query, (user_id,))
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

    def get_user_restaurant_ids(self, user_id: int) -> List[int]:
        """
        Get all restaurant_ids associated with a user.
        Checks:
        - User_Restaurant_Metadata (direct mapping)
        - Reservations (via slot_bookings)
        - Calls (via phone number)

        Args:
            user_id: User ID

        Returns:
            List of restaurant_ids the user is associated with
        """
        # Get user's phone number for call matching
        user = self.get_user_by_id(user_id)
        phone_number = user.get("phone_number") if user else None

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

                -- From calls (restaurant_id is VARCHAR in Calls table)
                SELECT CAST(restaurant_id AS UNSIGNED) as restaurant_id
                FROM Calls
                WHERE user_id = %s AND restaurant_id IS NOT NULL
            ) AS combined
            WHERE restaurant_id IS NOT NULL
        """
        results = self._execute_query(query, (user_id, user_id, phone_number))
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
        # Get user's phone number for call matching
        user = self.get_user_by_id(user_id)
        phone_number = user.get("phone_number") if user else None

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
            (user_id, restaurant_id, user_id, restaurant_id, phone_number, str(restaurant_id)),
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
