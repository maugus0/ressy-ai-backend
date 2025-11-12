from app.repositories.base import BaseRepository
from app.config import settings
from datetime import datetime
from typing import Dict, List, Any
from boto3.dynamodb.conditions import Key


class OrderRepository(BaseRepository):
    """Repository for order data access."""
    
    def _init_tables(self):
        self.orders_table = self.dynamodb.Table(settings.ORDERS_TABLE)
        self.order_history_table = self.dynamodb.Table(settings.ORDER_HISTORY_TABLE)
    
    def create(self, order_id: str, restaurant_id: str, data: dict) -> None:
        """Create a new order."""
        item = {
            "order_id": order_id,
            "restaurant_id": restaurant_id,
            "SK": "ORDER_METADATA",
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
            **data
        }
        self._with_retries(self.orders_table.put_item, Item=item)
    
    def get_by_id(self, order_id: str) -> Dict[str, Any]:
        """Get order by ID."""
        resp = self._with_retries(
            self.orders_table.get_item,
            Key={"order_id": order_id, "SK": "ORDER_METADATA"}
        )
        return resp.get("Item", {})
    
    def get_by_restaurant(self, restaurant_id: str) -> List[Dict[str, Any]]:
        """Get all orders for a restaurant."""
        resp = self._with_retries(
            self.orders_table.scan,
            FilterExpression="restaurant_id = :rid",
            ExpressionAttributeValues={":rid": restaurant_id}
        )
        return resp.get("Items", [])
    
    def update(self, order_id: str, data: dict) -> None:
        """Update order."""
        data["updated_at"] = datetime.utcnow().isoformat()
        self._with_retries(
            self.orders_table.update_item,
            Key={"order_id": order_id, "SK": "ORDER_METADATA"},
            UpdateExpression="SET " + ", ".join(f"#{k}=:{k}" for k in data.keys()),
            ExpressionAttributeNames={f"#{k}": k for k in data.keys()},
            ExpressionAttributeValues={f":{k}": v for k, v in data.items()}
        )
    
    def delete(self, order_id: str) -> None:
        """Delete order."""
        self._with_retries(
            self.orders_table.delete_item,
            Key={"order_id": order_id, "SK": "ORDER_METADATA"}
        )
    
    def get_history(self, order_id: str) -> List[Dict[str, Any]]:
        """Get order history."""
        resp = self._with_retries(
            self.order_history_table.query,
            KeyConditionExpression=Key("order_id").eq(order_id)
        )
        return resp.get("Items", [])

