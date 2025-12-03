from datetime import datetime
from typing import Any, Dict, List

from boto3.dynamodb.conditions import Key

from app.config import settings
from app.repositories.base import BaseRepository
from app.repositories.mock_data import MOCK_DATA, clone


class MenuRepository(BaseRepository):
    """Repository for menu data access."""

    def _init_tables(self):
        if self.use_mock:
            self.menus_table = None
            self.specials_table = None
            return
        self.menus_table = self.dynamodb.Table(settings.MENUS_TABLE)
        self.specials_table = self.dynamodb.Table(settings.SPECIALS_TABLE)

    def create_menu(self, restaurant_id: str, menu_id: str, data: dict) -> None:
        """Create a new menu."""
        item = {
            "restaurant_id": restaurant_id,
            "menu_id": menu_id,
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
            **data,
        }
        if self.use_mock:
            menus = MOCK_DATA["menus"].setdefault(restaurant_id, [])
            menus = [m for m in menus if m.get("menu_id") != menu_id]
            menus.append(item)
            MOCK_DATA["menus"][restaurant_id] = menus
            return
        self._with_retries(self.menus_table.put_item, Item=item)

    def get_menu_by_id(self, restaurant_id: str, menu_id: str) -> Dict[str, Any]:
        """Get menu by ID."""
        if self.use_mock:
            for menu in MOCK_DATA["menus"].get(restaurant_id, []):
                if menu.get("menu_id") == menu_id:
                    return clone(menu)
            return {}
        resp = self._with_retries(self.menus_table.get_item, Key={"restaurant_id": restaurant_id, "menu_id": menu_id})
        return resp.get("Item", {})

    def get_menus_by_restaurant(self, restaurant_id: str) -> List[Dict[str, Any]]:
        """Get all menus for a restaurant."""
        if self.use_mock:
            return [clone(menu) for menu in MOCK_DATA["menus"].get(restaurant_id, [])]
        resp = self._with_retries(
            self.menus_table.query,
            IndexName="restaurant_id-menu_id-index",
            KeyConditionExpression=Key("restaurant_id").eq(restaurant_id),
        )
        return resp.get("Items", [])

    def update_menu(self, restaurant_id: str, menu_id: str, data: dict) -> None:
        """Update menu."""
        data["updated_at"] = datetime.utcnow().isoformat()
        if self.use_mock:
            menus = MOCK_DATA["menus"].get(restaurant_id, [])
            for menu in menus:
                if menu.get("menu_id") == menu_id:
                    menu.update(data)
            return
        self._with_retries(
            self.menus_table.update_item,
            Key={"restaurant_id": restaurant_id, "menu_id": menu_id},
            UpdateExpression="SET " + ", ".join(f"#{k}=:{k}" for k in data.keys()),
            ExpressionAttributeNames={f"#{k}": k for k in data.keys()},
            ExpressionAttributeValues={f":{k}": v for k, v in data.items()},
        )

    def delete_menu(self, restaurant_id: str, menu_id: str) -> None:
        """Delete menu."""
        if self.use_mock:
            menus = [m for m in MOCK_DATA["menus"].get(restaurant_id, []) if m.get("menu_id") != menu_id]
            MOCK_DATA["menus"][restaurant_id] = menus
            return
        self._with_retries(self.menus_table.delete_item, Key={"restaurant_id": restaurant_id, "menu_id": menu_id})

    def create_special(self, restaurant_id: str, special_id: str, data: dict) -> None:
        """Create a new special."""
        item = {
            "restaurant_id": restaurant_id,
            "special_id": special_id,
            "created_at": datetime.utcnow().isoformat(),
            **data,
        }
        if self.use_mock:
            specials = MOCK_DATA["specials"].setdefault(restaurant_id, [])
            specials = [s for s in specials if s.get("special_id") != special_id]
            specials.append(item)
            MOCK_DATA["specials"][restaurant_id] = specials
            return
        self._with_retries(self.specials_table.put_item, Item=item)

    def get_special_by_id(self, restaurant_id: str, special_id: str) -> Dict[str, Any]:
        """Get special by ID."""
        if self.use_mock:
            for special in MOCK_DATA["specials"].get(restaurant_id, []):
                if special.get("special_id") == special_id:
                    return clone(special)
            return {}
        resp = self._with_retries(
            self.specials_table.get_item, Key={"restaurant_id": restaurant_id, "special_id": special_id}
        )
        return resp.get("Item", {})

    def get_specials_by_restaurant(self, restaurant_id: str) -> List[Dict[str, Any]]:
        """Get all specials for a restaurant."""
        if self.use_mock:
            return [clone(s) for s in MOCK_DATA["specials"].get(restaurant_id, [])]
        resp = self._with_retries(
            self.specials_table.scan,
            FilterExpression="restaurant_id = :rid",
            ExpressionAttributeValues={":rid": restaurant_id},
        )
        return resp.get("Items", [])

    def update_special(self, restaurant_id: str, special_id: str, data: dict) -> None:
        """Update special."""
        if self.use_mock:
            specials = MOCK_DATA["specials"].get(restaurant_id, [])
            for special in specials:
                if special.get("special_id") == special_id:
                    special.update(data)
            return
        self._with_retries(
            self.specials_table.update_item,
            Key={"restaurant_id": restaurant_id, "special_id": special_id},
            UpdateExpression="SET " + ", ".join(f"#{k}=:{k}" for k in data.keys()),
            ExpressionAttributeNames={f"#{k}": k for k in data.keys()},
            ExpressionAttributeValues={f":{k}": v for k, v in data.items()},
        )

    def delete_special(self, restaurant_id: str, special_id: str) -> None:
        """Delete special."""
        if self.use_mock:
            specials = [s for s in MOCK_DATA["specials"].get(restaurant_id, []) if s.get("special_id") != special_id]
            MOCK_DATA["specials"][restaurant_id] = specials
            return
        self._with_retries(
            self.specials_table.delete_item, Key={"restaurant_id": restaurant_id, "special_id": special_id}
        )
