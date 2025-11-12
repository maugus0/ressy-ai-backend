import uuid
from app.repositories.menu_repo import MenuRepository

class MenuService:
    def __init__(self):
        self.menu_repo = MenuRepository()
    
    def create_menu(self, restaurant_id: str, data: dict) -> dict:
        """Create a new menu."""
        menu_id = str(uuid.uuid4())
        self.menu_repo.create_menu(restaurant_id, menu_id, data)
        return {"message": "Menu created successfully", "menu_id": menu_id}
    
    def list_menus(self, restaurant_id: str) -> list:
        """List all menus for a restaurant."""
        return self.menu_repo.get_menus_by_restaurant(restaurant_id)
    
    def get_menu(self, restaurant_id: str, menu_id: str) -> dict:
        """Get a specific menu by ID."""
        return self.menu_repo.get_menu_by_id(restaurant_id, menu_id)
    
    def update_menu(self, restaurant_id: str, menu_id: str, data: dict) -> dict:
        """Update an existing menu."""
        self.menu_repo.update_menu(restaurant_id, menu_id, data)
        return {"message": "Menu updated successfully"}
    
    def delete_menu(self, restaurant_id: str, menu_id: str) -> dict:
        """Delete a menu."""
        self.menu_repo.delete_menu(restaurant_id, menu_id)
        return {"message": "Menu deleted successfully"}

