from app.repositories.base import BaseRepository
from app.config import settings
from datetime import datetime
from typing import Dict, List, Any
from boto3.dynamodb.conditions import Key


class FAQRepository(BaseRepository):
    """Repository for FAQ data access."""
    
    def _init_tables(self):
        self.faqs_table = self.dynamodb.Table(settings.FAQS_TABLE)
    
    def create(self, restaurant_id: str, faq_id: str, data: dict) -> None:
        """Create a new FAQ."""
        item = {
            "restaurant_id": restaurant_id,
            "faq_id": faq_id,
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
            **data
        }
        self._with_retries(self.faqs_table.put_item, Item=item)
    
    def get_by_restaurant(self, restaurant_id: str) -> List[Dict[str, Any]]:
        """Get all FAQs for a restaurant."""
        resp = self._with_retries(
            self.faqs_table.query,
            IndexName="restaurant_id-faq_id-index",
            KeyConditionExpression=Key("restaurant_id").eq(restaurant_id)
        )
        return resp.get("Items", [])
    
    def update(self, restaurant_id: str, faq_id: str, data: dict) -> None:
        """Update FAQ."""
        self._with_retries(
            self.faqs_table.update_item,
            Key={"restaurant_id": restaurant_id, "faq_id": faq_id},
            UpdateExpression="SET " + ", ".join(f"#{k}=:{k}" for k in data.keys()),
            ExpressionAttributeNames={f"#{k}": k for k in data.keys()},
            ExpressionAttributeValues={f":{k}": v for k, v in data.items()}
        )
    
    def delete(self, restaurant_id: str, faq_id: str) -> None:
        """Delete FAQ."""
        self._with_retries(
            self.faqs_table.delete_item,
            Key={"restaurant_id": restaurant_id, "faq_id": faq_id}
        )

