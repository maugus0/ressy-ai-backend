from datetime import datetime
from typing import Any, Dict, List

from boto3.dynamodb.conditions import Key

from app.config import settings
from app.repositories.base import BaseRepository
from app.repositories.mock_data import MOCK_DATA, clone


class FAQRepository(BaseRepository):
    """Repository for FAQ data access."""

    def _init_tables(self):
        if self.use_mock:
            self.faqs_table = None
            return
        self.faqs_table = self.dynamodb.Table(settings.FAQS_TABLE)

    def create(self, restaurant_id: str, faq_id: str, data: dict) -> None:
        """Create a new FAQ."""
        item = {
            "restaurant_id": restaurant_id,
            "faq_id": faq_id,
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
            **data,
        }
        if self.use_mock:
            faqs = MOCK_DATA["faqs"].setdefault(restaurant_id, [])
            faqs = [f for f in faqs if f.get("faq_id") != faq_id]
            faqs.append(item)
            MOCK_DATA["faqs"][restaurant_id] = faqs
            return
        self._with_retries(self.faqs_table.put_item, Item=item)

    def get_by_restaurant(self, restaurant_id: str) -> List[Dict[str, Any]]:
        """Get all FAQs for a restaurant."""
        if self.use_mock:
            return [clone(faq) for faq in MOCK_DATA["faqs"].get(restaurant_id, [])]
        resp = self._with_retries(
            self.faqs_table.query,
            IndexName="restaurant_id-faq_id-index",
            KeyConditionExpression=Key("restaurant_id").eq(restaurant_id),
        )
        return resp.get("Items", [])

    def update(self, restaurant_id: str, faq_id: str, data: dict) -> None:
        """Update FAQ."""
        if self.use_mock:
            for faq in MOCK_DATA["faqs"].get(restaurant_id, []):
                if faq.get("faq_id") == faq_id:
                    faq.update(data)
            return
        self._with_retries(
            self.faqs_table.update_item,
            Key={"restaurant_id": restaurant_id, "faq_id": faq_id},
            UpdateExpression="SET " + ", ".join(f"#{k}=:{k}" for k in data.keys()),
            ExpressionAttributeNames={f"#{k}": k for k in data.keys()},
            ExpressionAttributeValues={f":{k}": v for k, v in data.items()},
        )

    def delete(self, restaurant_id: str, faq_id: str) -> None:
        """Delete FAQ."""
        if self.use_mock:
            faqs = [f for f in MOCK_DATA["faqs"].get(restaurant_id, []) if f.get("faq_id") != faq_id]
            MOCK_DATA["faqs"][restaurant_id] = faqs
            return
        self._with_retries(self.faqs_table.delete_item, Key={"restaurant_id": restaurant_id, "faq_id": faq_id})
