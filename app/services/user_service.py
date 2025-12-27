from typing import Dict, List, Optional

from app.repositories.mysql_user_repo import MySQLUserRepository
from app.repositories.mysql_user_restaurant_metadata_repo import (
    MySQLUserRestaurantMetadataRepository,
)


class UserService:
    def __init__(self):
        self.user_repo = MySQLUserRepository()
        self.metadata_repo = MySQLUserRestaurantMetadataRepository()

    def create_user(self, data: dict) -> dict:
        """
        Create a new user or return existing user if phone_number already exists.
        Uses atomic create_or_update_user to prevent duplicate entries.
        """
        user_id = self.user_repo.create_or_update_user(data)
        return {"message": "User created or updated successfully", "user_id": user_id}

    def list_users(self) -> list:
        """List all users."""
        return self.user_repo.list_users()

    def update_user(self, user_id: str, data: dict) -> dict:
        """Update an existing user."""
        self.user_repo.update_user(int(user_id), data)
        return {"message": "User updated"}

    def delete_user(self, user_id: str) -> dict:
        """Delete a user."""
        self.user_repo.delete_user(int(user_id))
        return {"message": "User deleted"}

    # ---------- Dashboard User Management Methods ----------

    def create_user_for_restaurant(self, restaurant_id: int, user_data: dict, notes: Optional[str] = None) -> dict:
        """
        Create or associate a user for restaurant dashboard.

        Uses atomic create_or_update_user to prevent race conditions and duplicate entries.

        If user already exists (by phone_number):
        - Check if they have an explicit metadata mapping to this restaurant
        - If not, create the user-restaurant mapping and update user data

        If user doesn't exist:
        - Create new user atomically
        - Create user-restaurant mapping

        Args:
            restaurant_id: Restaurant ID to associate the user with
            user_data: User data dict with name, phone_number, email, address, is_spam
            notes: Optional notes about the user-restaurant relationship

        Returns:
            Dict with user_id, user details, and whether user was newly created
        """
        phone_number = user_data.get("phone_number")

        # Check if user already exists BEFORE the atomic upsert
        # This lets us determine if user was new or existing
        existing_user_id = self.user_repo.get_user_id_by_phone_or_email(phone_number, user_data.get("email"))

        is_new_user = existing_user_id is None

        if existing_user_id:
            # User exists - check if they have an EXPLICIT metadata mapping to this restaurant
            # We use metadata_repo (not user_repo) because we only want to check explicit mappings,
            # not implicit associations via calls or reservations. Users should be able to be
            # explicitly added to a restaurant even if they've previously called/made reservations.
            already_has_mapping = self.metadata_repo.user_belongs_to_restaurant(existing_user_id, restaurant_id)

            if already_has_mapping:
                raise ValueError("User is already associated with this restaurant")

        # Use atomic create_or_update_user to handle race conditions
        # This ensures we don't create duplicates even under concurrent requests
        user_id = self.user_repo.create_or_update_user(user_data)

        # Create the user-restaurant metadata mapping (uses ON DUPLICATE KEY UPDATE internally)
        self.metadata_repo.create_mapping(
            user_id=user_id,
            restaurant_id=restaurant_id,
            source="dashboard",
            notes=notes,
        )

        user = self.user_repo.get_user_by_id(user_id)

        if is_new_user:
            return {
                "message": "User created successfully",
                "user_id": user_id,
                "user": user,
                "is_new_user": True,
            }
        else:
            return {
                "message": "Existing user added to restaurant successfully",
                "user_id": user_id,
                "user": user,
                "is_new_user": False,
            }

    def list_users_by_restaurant(
        self,
        restaurant_id: int,
        search: Optional[str] = None,
        is_spam: Optional[bool] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> dict:
        """
        List users for a specific restaurant with pagination and statistics.

        Args:
            restaurant_id: Restaurant ID to filter users by
            search: Optional search term for name, phone, or email
            is_spam: Optional filter for spam status
            limit: Maximum results per page
            offset: Pagination offset

        Returns:
            Dict with users list, total count, and pagination info
        """
        users = self.user_repo.list_users_by_restaurant(
            restaurant_id=restaurant_id,
            search=search,
            is_spam=is_spam,
            limit=limit,
            offset=offset,
        )

        total = self.user_repo.count_users_by_restaurant(
            restaurant_id=restaurant_id,
            search=search,
            is_spam=is_spam,
        )

        # Add statistics for each user using a batch query to avoid N+1 problem
        user_ids = [user["id"] for user in users]
        stats_by_user_id = self.user_repo.get_users_statistics(user_ids, restaurant_id)
        users_with_stats = []
        for user in users:
            stats = stats_by_user_id.get(user["id"], {})
            user_with_stats = {**user, "statistics": stats}
            users_with_stats.append(user_with_stats)

        return {
            "restaurant_id": restaurant_id,
            "users": users_with_stats,
            "total": total,
            "limit": limit,
            "offset": offset,
            "has_more": offset + len(users) < total,
        }

    def get_user_by_id(self, user_id: int) -> Optional[Dict]:
        """
        Get user by ID.

        Args:
            user_id: User ID

        Returns:
            User dict or None if not found
        """
        return self.user_repo.get_user_by_id(user_id)

    def get_user_restaurant_ids(self, user_id: int) -> List[int]:
        """
        Get all restaurant IDs associated with a user.

        Args:
            user_id: User ID

        Returns:
            List of restaurant IDs
        """
        return self.user_repo.get_user_restaurant_ids(user_id)

    def user_belongs_to_restaurant(self, user_id: int, restaurant_id: int) -> bool:
        """
        Check if a user is associated with a specific restaurant.

        Args:
            user_id: User ID
            restaurant_id: Restaurant ID

        Returns:
            True if user is associated with the restaurant
        """
        return self.user_repo.user_belongs_to_restaurant(user_id, restaurant_id)

    def get_user_with_restaurant_check(self, user_id: int) -> dict:
        """
        Get user with restaurant_ids for authorization check.

        Args:
            user_id: User ID

        Returns:
            User dict with restaurant_ids list

        Raises:
            ValueError: If user not found
        """
        user = self.user_repo.get_user_by_id(user_id)
        if not user:
            raise ValueError(f"User with ID {user_id} not found")

        # Get all associated restaurant_ids
        restaurant_ids = self.user_repo.get_user_restaurant_ids(user_id)
        user["restaurant_ids"] = restaurant_ids

        return user

    def update_user_dashboard(self, user_id: int, user_data: dict) -> dict:
        """
        Update user from dashboard.

        Args:
            user_id: User ID to update
            user_data: Fields to update

        Returns:
            Dict with updated user info

        Raises:
            ValueError: If user not found
        """
        # Verify user exists
        existing_user = self.user_repo.get_user_by_id(user_id)
        if not existing_user:
            raise ValueError(f"User with ID {user_id} not found")

        # Check for duplicate phone/email if being updated
        phone_number = user_data.get("phone_number")
        email = user_data.get("email")
        if phone_number:
            duplicate_id = self.user_repo.get_user_id_by_phone_or_email(phone_number, None)
            if duplicate_id and duplicate_id != user_id:
                raise ValueError("Another user with this phone number already exists")
        if email:
            duplicate_id = self.user_repo.get_user_id_by_phone_or_email(None, email)
            if duplicate_id and duplicate_id != user_id:
                raise ValueError("Another user with this email already exists")
        rows_affected = self.user_repo.update_user(user_id, user_data)
        if rows_affected == 0 and user_data:
            raise ValueError("No fields were updated")

        updated_user = self.user_repo.get_user_by_id(user_id)

        return {
            "message": "User updated successfully",
            "user": updated_user,
        }

    def delete_user_dashboard(self, user_id: int) -> dict:
        """
        Delete user from dashboard.

        Args:
            user_id: User ID to delete

        Returns:
            Dict with deletion confirmation

        Raises:
            ValueError: If user not found or has associated records
        """
        # Verify user exists
        existing_user = self.user_repo.get_user_by_id(user_id)
        if not existing_user:
            raise ValueError(f"User with ID {user_id} not found")

        try:
            rows_deleted = self.user_repo.delete_user(user_id)
            if rows_deleted == 0:
                raise ValueError("Failed to delete user")

            return {
                "message": "User deleted successfully",
                "user_id": user_id,
            }
        except Exception as e:
            error_msg = str(e).lower()
            if "foreign key" in error_msg or "constraint" in error_msg:
                raise ValueError(
                    "Cannot delete user with existing reservations or orders. "
                    "Cancel or complete associated records first."
                )
            raise
