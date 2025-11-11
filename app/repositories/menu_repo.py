from app.repositories.base import BaseRepository
from app.config import settings
from datetime import datetime
from typing import Dict, List, Any
from boto3.dynamodb.conditions import Key


class MenuRepository(BaseRepository):
    """Repository for menu data access."""
    
    def _init_tables(self):
        self.menus_table = self.dynamodb.Table(settings.MENUS_TABLE)
        self.specials_table = self.dynamodb.Table(settings.SPECIALS_TABLE)
    
    def create_menu(self, restaurant_id: str, menu_id: str, data: dict) -> None:
        """Create a new menu."""
        item = {
            "restaurant_id": restaurant_id,
            "menu_id": menu_id,
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
            **data
        }
        self._with_retries(self.menus_table.put_item, Item=item)
    
    def get_menu_by_id(self, restaurant_id: str, menu_id: str) -> Dict[str, Any]:
        """Get menu by ID."""
        resp = self._with_retries(
            self.menus_table.get_item,
            Key={"restaurant_id": restaurant_id, "menu_id": menu_id}
        )
        return resp.get("Item", {})
    
    def get_menus_by_restaurant(self, restaurant_id: str) -> List[Dict[str, Any]]:
        """Get all menus for a restaurant."""
        resp = self._with_retries(
            self.menus_table.query,
            IndexName="restaurant_id-menu_id-index",
            KeyConditionExpression=Key("restaurant_id").eq(restaurant_id)
        )
        return resp.get("Items", [])
    
    def update_menu(self, restaurant_id: str, menu_id: str, data: dict) -> None:
        """Update menu."""
        data["updated_at"] = datetime.utcnow().isoformat()
        self._with_retries(
            self.menus_table.update_item,
            Key={"restaurant_id": restaurant_id, "menu_id": menu_id},
            UpdateExpression="SET " + ", ".join(f"#{k}=:{k}" for k in data.keys()),
            ExpressionAttributeNames={f"#{k}": k for k in data.keys()},
            ExpressionAttributeValues={f":{k}": v for k, v in data.items()}
        )
    
    def delete_menu(self, restaurant_id: str, menu_id: str) -> None:
        """Delete menu."""
        self._with_retries(
            self.menus_table.delete_item,
            Key={"restaurant_id": restaurant_id, "menu_id": menu_id}
        )
    
    def create_special(self, restaurant_id: str, special_id: str, data: dict) -> None:
        """Create a new special."""
        item = {
            "restaurant_id": restaurant_id,
            "special_id": special_id,
            "created_at": datetime.utcnow().isoformat(),
            **data
        }
        self._with_retries(self.specials_table.put_item, Item=item)
    
    def get_special_by_id(self, restaurant_id: str, special_id: str) -> Dict[str, Any]:
        """Get special by ID."""
        resp = self._with_retries(
            self.specials_table.get_item,
            Key={"restaurant_id": restaurant_id, "special_id": special_id}
        )
        return resp.get("Item", {})
    
    def get_specials_by_restaurant(self, restaurant_id: str) -> List[Dict[str, Any]]:
        """Get all specials for a restaurant."""
        resp = self._with_retries(
            self.specials_table.scan,
            FilterExpression="restaurant_id = :rid",
            ExpressionAttributeValues={":rid": restaurant_id}
        )
        return resp.get("Items", [])
    
    def update_special(self, restaurant_id: str, special_id: str, data: dict) -> None:
        """Update special."""
        self._with_retries(
            self.specials_table.update_item,
            Key={"restaurant_id": restaurant_id, "special_id": special_id},
            UpdateExpression="SET " + ", ".join(f"#{k}=:{k}" for k in data.keys()),
            ExpressionAttributeNames={f"#{k}": k for k in data.keys()},
            ExpressionAttributeValues={f":{k}": v for k, v in data.items()}
        )
    
    def delete_special(self, restaurant_id: str, special_id: str) -> None:
        """Delete special."""
        self._with_retries(
            self.specials_table.delete_item,
            Key={"restaurant_id": restaurant_id, "special_id": special_id}
        )

