import uuid
from app.repositories.faq_repo import FAQRepository

class FAQService:
    def __init__(self):
        self.faq_repo = FAQRepository()
    
    def create_faq(self, restaurant_id: str, data: dict) -> dict:
        """Create a new FAQ."""
        faq_id = str(uuid.uuid4())
        self.faq_repo.create(restaurant_id, faq_id, data)
        return {"message": "FAQ created", "faq_id": faq_id}
    
    def list_faqs(self, restaurant_id: str) -> list:
        """List all FAQs for a restaurant."""
        return self.faq_repo.get_by_restaurant(restaurant_id)
    
    def update_faq(self, restaurant_id: str, faq_id: str, data: dict) -> dict:
        """Update an existing FAQ."""
        self.faq_repo.update(restaurant_id, faq_id, data)
        return {"message": "FAQ updated"}
    
    def delete_faq(self, restaurant_id: str, faq_id: str) -> dict:
        """Delete an FAQ."""
        self.faq_repo.delete(restaurant_id, faq_id)
        return {"message": "FAQ deleted"}

