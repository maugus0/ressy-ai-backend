import uuid
from app.repositories.menu_repo import MenuRepository

class SpecialService:
    def __init__(self):
        self.menu_repo = MenuRepository()
    
    def create_special(self, restaurant_id: str, data: dict) -> dict:
        """Create a new special."""
        special_id = str(uuid.uuid4())
        self.menu_repo.create_special(restaurant_id, special_id, data)
        return {"message": "Special created", "special_id": special_id}
    
    def list_specials(self, restaurant_id: str) -> list:
        """List all specials for a restaurant."""
        return self.menu_repo.get_specials_by_restaurant(restaurant_id)
    
    def get_special(self, restaurant_id: str, special_id: str) -> dict:
        """Get a specific special by ID."""
        return self.menu_repo.get_special_by_id(restaurant_id, special_id)
    
    def update_special(self, restaurant_id: str, special_id: str, data: dict) -> dict:
        """Update an existing special."""
        self.menu_repo.update_special(restaurant_id, special_id, data)
        return {"message": "Special updated"}
    
    def delete_special(self, restaurant_id: str, special_id: str) -> dict:
        """Delete a special."""
        self.menu_repo.delete_special(restaurant_id, special_id)
        return {"message": "Special deleted"}

