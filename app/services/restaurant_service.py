import uuid
from app.repositories.restaurant_repo import RestaurantRepository

class RestaurantService:
    def __init__(self):
        self.restaurant_repo = RestaurantRepository()
    
    def create_restaurant(self, data: dict) -> dict:
        """Create a new restaurant."""
        restaurant_id = str(uuid.uuid4())
        self.restaurant_repo.create(restaurant_id, data)
        return {"message": "Restaurant created successfully", "restaurant_id": restaurant_id}
    
    def list_restaurants(self) -> list:
        """List all restaurants."""
        return self.restaurant_repo.get_all()
    
    def get_restaurant(self, restaurant_id: str) -> dict:
        """Get a specific restaurant by ID."""
        return self.restaurant_repo.get_by_id(restaurant_id)
    
    def update_restaurant(self, restaurant_id: str, data: dict) -> dict:
        """Update an existing restaurant."""
        self.restaurant_repo.update(restaurant_id, data)
        return {"message": "Restaurant updated successfully"}
    
    def delete_restaurant(self, restaurant_id: str) -> dict:
        """Delete a restaurant."""
        self.restaurant_repo.delete(restaurant_id)
        return {"message": "Restaurant deleted"}

