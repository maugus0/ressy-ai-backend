from app.repositories.mysql_menu_repo import MySQLMenuRepository


class SpecialService:
    def __init__(self):
        self.menu_repo = MySQLMenuRepository()

    def create_special(self, restaurant_id: str, data: dict) -> dict:
        """Create a new special."""
        special_id = self.menu_repo.create_special(int(restaurant_id), data)
        return {"message": "Special created", "special_id": special_id}

    def list_specials(self, restaurant_id: str) -> list:
        """List all specials for a restaurant."""
        return self.menu_repo.get_specials_by_restaurant(int(restaurant_id))

    def get_special(self, restaurant_id: str, special_id: str) -> dict:
        """Get a specific special by ID."""
        return self.menu_repo.get_special_by_id(int(restaurant_id), int(special_id))

    def update_special(self, restaurant_id: str, special_id: str, data: dict) -> dict:
        """Update an existing special."""
        self.menu_repo.update_special(int(restaurant_id), int(special_id), data)
        return {"message": "Special updated"}

    def delete_special(self, restaurant_id: str, special_id: str) -> dict:
        """Delete a special."""
        self.menu_repo.delete_special(int(restaurant_id), int(special_id))
        return {"message": "Special deleted"}
