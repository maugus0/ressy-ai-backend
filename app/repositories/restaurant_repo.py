from app.repositories.base import BaseRepository
from app.config import settings
from datetime import datetime
from typing import Dict, List, Any


class RestaurantRepository(BaseRepository):
    """Repository for restaurant data access."""
    
    def _init_tables(self):
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
        self._with_retries(self.restaurants_table.put_item, Item=item)
    
    def get_by_id(self, restaurant_id: str) -> Dict[str, Any]:
        """Get restaurant by ID."""
        resp = self._with_retries(
            self.restaurants_table.get_item,
            Key={"restaurant_id": restaurant_id, "SK": "METADATA"}
        )
        return resp.get("Item", {})
    
    def get_all(self) -> List[Dict[str, Any]]:
        """Get all restaurants."""
        resp = self._with_retries(self.restaurants_table.scan)
        return resp.get("Items", [])
    
    def update(self, restaurant_id: str, data: dict) -> None:
        """Update restaurant."""
        data["updated_at"] = datetime.utcnow().isoformat()
        self._with_retries(
            self.restaurants_table.update_item,
            Key={"restaurant_id": restaurant_id, "SK": "METADATA"},
            UpdateExpression="SET " + ", ".join(f"#{k}=:{k}" for k in data.keys()),
            ExpressionAttributeNames={f"#{k}": k for k in data.keys()},
            ExpressionAttributeValues={f":{k}": v for k, v in data.items()}
        )
    
    def delete(self, restaurant_id: str) -> None:
        """Delete restaurant."""
        self._with_retries(
            self.restaurants_table.delete_item,
            Key={"restaurant_id": restaurant_id, "SK": "METADATA"}
        )

