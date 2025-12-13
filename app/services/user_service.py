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
        """Create a new user."""
        user_id = self.user_repo.create_user(data)
        return {"message": "User created successfully", "user_id": user_id}

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

        If user already exists (by phone/email):
        - Check if they're already associated with this restaurant
        - If not, create the user-restaurant mapping

        If user doesn't exist:
        - Create new user
        - Create user-restaurant mapping

        Args:
            restaurant_id: Restaurant ID to associate the user with
            user_data: User data dict with name, phone_number, email, address, is_spam
            notes: Optional notes about the user-restaurant relationship

        Returns:
            Dict with user_id, user details, and whether user was newly created
        """
        # Check if user already exists
        existing_user_id = self.user_repo.get_user_id_by_phone_or_email(
            user_data.get("phone_number"), user_data.get("email")
        )

        if existing_user_id:
            # User exists - check if already associated with this restaurant
            already_associated = self.user_repo.user_belongs_to_restaurant(existing_user_id, restaurant_id)

            if already_associated:
                raise ValueError("User is already associated with this restaurant")

            # User exists but not associated - create mapping
            self.metadata_repo.create_mapping(
                user_id=existing_user_id,
                restaurant_id=restaurant_id,
                source="dashboard",
                notes=notes,
            )

            user = self.user_repo.get_user_by_id(existing_user_id)

            return {
                "message": "Existing user added to restaurant successfully",
                "user_id": existing_user_id,
                "user": user,
                "is_new_user": False,
            }

        # User doesn't exist - create new user
        user_id = self.user_repo.create_user(user_data)

        # Create the user-restaurant metadata mapping
        self.metadata_repo.create_mapping(
            user_id=user_id,
            restaurant_id=restaurant_id,
            source="dashboard",
            notes=notes,
        )

        user = self.user_repo.get_user_by_id(user_id)

        return {
            "message": "User created successfully",
            "user_id": user_id,
            "user": user,
            "is_new_user": True,
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

        # Add statistics for each user
        users_with_stats = []
        for user in users:
            stats = self.user_repo.get_user_statistics(user["id"], restaurant_id)
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
        if user_data.get("phone_number") or user_data.get("email"):
            duplicate_id = self.user_repo.get_user_id_by_phone_or_email(
                user_data.get("phone_number"), user_data.get("email")
            )
            if duplicate_id and duplicate_id != user_id:
                raise ValueError("Another user with this phone number or email already exists")

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
