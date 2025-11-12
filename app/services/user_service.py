from app.repositories.user_repo import UserRepository

class UserService:
    def __init__(self):
        self.user_repo = UserRepository()
    
    def create_user(self, data: dict) -> dict:
        """Create a new user."""
        user_id = self.user_repo.create_user(
            restaurant_id=data["restaurant_id"],
            email=data["email"],
            role=data.get("role", "staff"),
            permissions=data.get("permissions", [])
        )
        return {"message": "User created successfully", "user_id": user_id}
    
    def list_users(self, restaurant_id: str) -> list:
        """List all users for a restaurant."""
        return self.user_repo.get_users_by_restaurant(restaurant_id)
    
    def update_user(self, user_id: str, data: dict) -> dict:
        """Update an existing user."""
        self.user_repo.update_user(user_id, data)
        return {"message": "User updated"}
    
    def delete_user(self, user_id: str) -> dict:
        """Delete a user."""
        self.user_repo.delete_user(user_id)
        return {"message": "User deleted"}

