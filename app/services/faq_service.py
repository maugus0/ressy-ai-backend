import uuid

from app.repositories.mysql_faq_repo import MySQLFAQRepository


class FAQService:
    def __init__(self):
        self.faq_repo = MySQLFAQRepository()

    def create_faq(self, restaurant_id: str, data: dict) -> dict:
        """Create a new FAQ."""
        faq_id = str(uuid.uuid4())
        new_id = self.faq_repo.create(int(restaurant_id), data)
        return {"message": "FAQ created", "faq_id": new_id or faq_id}

    def list_faqs(self, restaurant_id: str) -> list:
        """List all FAQs for a restaurant."""
        return self.faq_repo.get_by_restaurant(int(restaurant_id))

    def update_faq(self, restaurant_id: str, faq_id: str, data: dict) -> dict:
        """Update an existing FAQ."""
        self.faq_repo.update(int(restaurant_id), int(faq_id), data)
        return {"message": "FAQ updated"}

    def delete_faq(self, restaurant_id: str, faq_id: str) -> dict:
        """Delete an FAQ."""
        self.faq_repo.delete(int(restaurant_id), int(faq_id))
        return {"message": "FAQ deleted"}
