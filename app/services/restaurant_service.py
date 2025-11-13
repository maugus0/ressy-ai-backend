from app.repositories.mysql_restaurant_repo import MySQLRestaurantRepository


class RestaurantService:
    def __init__(self):
        self.restaurant_repo = MySQLRestaurantRepository()

    def create_restaurant(self, data: dict) -> dict:
        """Create a new restaurant."""
        restaurant_id = self.restaurant_repo.create(data)
        return {"message": "Restaurant created successfully", "restaurant_id": restaurant_id}

    def list_restaurants(self) -> list:
        """List all restaurants."""
        return self.restaurant_repo.get_all()

    def get_restaurant(self, restaurant_id: str) -> dict:
        """Get a specific restaurant by ID."""
        return self.restaurant_repo.get_by_id(int(restaurant_id))

    def get_restaurant_by_phone(self, phone_number: str) -> dict:
        """Get restaurant details by its published phone number."""

        if not phone_number:
            return {}
        return self.restaurant_repo.get_by_phone(phone_number)

    def update_restaurant(self, restaurant_id: str, data: dict) -> dict:
        """Update an existing restaurant."""
        self.restaurant_repo.update(int(restaurant_id), data)
        return {"message": "Restaurant updated successfully"}

    def delete_restaurant(self, restaurant_id: str) -> dict:
        """Delete a restaurant."""
        self.restaurant_repo.delete(int(restaurant_id))
        return {"message": "Restaurant deleted"}

    def get_restaurant_by_twilio(self, twilio_phone_number: str) -> dict:
        return self.restaurant_repo.get_by_twilio_number(twilio_phone_number)
