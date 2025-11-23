from app.repositories.mysql_user_repo import MySQLUserRepository


class UserService:
    def __init__(self):
        self.user_repo = MySQLUserRepository()

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
