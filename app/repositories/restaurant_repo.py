from datetime import datetime
from typing import Any, Dict, List

from boto3.dynamodb.conditions import Attr

from app.config import settings
from app.repositories.base import BaseRepository
from app.repositories.mock_data import MOCK_DATA, clone


class RestaurantRepository(BaseRepository):
    """Repository for restaurant data access."""

    def _init_tables(self):
        if self.use_mock:
            self.restaurants_table = None
            return
        self.restaurants_table = self.dynamodb.Table(settings.RESTAURANTS_TABLE)

    def create(self, restaurant_id: str, data: dict) -> None:
        """Create a new restaurant."""
        item = {
            "restaurant_id": restaurant_id,
            "SK": "METADATA",
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
            **data
        }
        if self.use_mock:
            MOCK_DATA["restaurants"][restaurant_id] = item
            return
        self._with_retries(self.restaurants_table.put_item, Item=item)

    def get_by_id(self, restaurant_id: str) -> Dict[str, Any]:
        """Get restaurant by ID."""
        if self.use_mock:
            return clone(MOCK_DATA["restaurants"].get(restaurant_id, {}))
        resp = self._with_retries(
            self.restaurants_table.get_item,
            Key={"restaurant_id": restaurant_id, "SK": "METADATA"}
        )
        return resp.get("Item", {})

    def get_all(self) -> List[Dict[str, Any]]:
        """Get all restaurants."""
        if self.use_mock:
            return [clone(item) for item in MOCK_DATA["restaurants"].values()]
        resp = self._with_retries(self.restaurants_table.scan)
        return resp.get("Items", [])

    def get_by_phone(self, phone_number: str) -> Dict[str, Any]:
        """Look up a restaurant by its public phone number."""

        if self.use_mock:
            for item in MOCK_DATA["restaurants"].values():
                if item.get("phone_number") == phone_number:
                    return clone(item)
            return {}
        resp = self._with_retries(
            self.restaurants_table.scan,
            FilterExpression=Attr("phone_number").eq(phone_number),
        )
        items = resp.get("Items", [])
        return items[0] if items else {}

    def update(self, restaurant_id: str, data: dict) -> None:
        """Update restaurant."""
        data["updated_at"] = datetime.utcnow().isoformat()
        if self.use_mock:
            existing = MOCK_DATA["restaurants"].get(restaurant_id, {})
            existing.update(data)
            MOCK_DATA["restaurants"][restaurant_id] = existing
            return
        self._with_retries(
            self.restaurants_table.update_item,
            Key={"restaurant_id": restaurant_id, "SK": "METADATA"},
            UpdateExpression="SET " + ", ".join(f"#{k}=:{k}" for k in data.keys()),
            ExpressionAttributeNames={f"#{k}": k for k in data.keys()},
            ExpressionAttributeValues={f":{k}": v for k, v in data.items()}
        )

    def delete(self, restaurant_id: str) -> None:
        """Delete restaurant."""
        if self.use_mock:
            MOCK_DATA["restaurants"].pop(restaurant_id, None)
            return
        self._with_retries(
            self.restaurants_table.delete_item,
            Key={"restaurant_id": restaurant_id, "SK": "METADATA"}
        )
