import uuid
from datetime import datetime
from typing import Any, Dict, List

from boto3.dynamodb.conditions import Key

from app.config import settings
from app.repositories.base import BaseRepository
from app.repositories.mock_data import MOCK_DATA, clone


class UserRepository(BaseRepository):
    """Repository for user data access."""

    def _init_tables(self):
        if self.use_mock:
            self.users_table = None
            return
        self.users_table = self.dynamodb.Table(settings.USERS_TABLE)

    def create_user(self, restaurant_id: str, email: str, role: str = "staff", permissions: list = None) -> str:
        """Create a new user."""
        user_id = str(uuid.uuid4())
        item = {
            "user_id": user_id,
            "restaurant_id": restaurant_id,
            "email": email,
            "role": role,
            "permissions": permissions or [],
            "status": "active",
            "created_at": datetime.utcnow().isoformat(),
        }
        print(f"[DDB] put user: {email}")
        if self.use_mock:
            MOCK_DATA["users"][user_id] = item
            return user_id
        self._with_retries(self.users_table.put_item, Item=item)
        return user_id

    def get_users_by_restaurant(self, restaurant_id: str) -> List[Dict[str, Any]]:
        """Get users by restaurant."""
        if self.use_mock:
            return [clone(user) for user in MOCK_DATA["users"].values() if user.get("restaurant_id") == restaurant_id]
        response = self._with_retries(
            self.users_table.query,
            IndexName="restaurant_id-index",
            KeyConditionExpression=Key("restaurant_id").eq(restaurant_id),
        )
        return response.get("Items", [])

    def update_user(self, user_id: str, data: dict) -> None:
        """Update user."""
        if self.use_mock:
            user = MOCK_DATA["users"].get(user_id)
            if user:
                user.update(data)
            return
        self._with_retries(
            self.users_table.update_item,
            Key={"user_id": user_id},
            UpdateExpression="SET " + ", ".join(f"#{k}=:{k}" for k in data.keys()),
            ExpressionAttributeNames={f"#{k}": k for k in data.keys()},
            ExpressionAttributeValues={f":{k}": v for k, v in data.items()},
        )

    def delete_user(self, user_id: str) -> None:
        """Delete user."""
        if self.use_mock:
            MOCK_DATA["users"].pop(user_id, None)
            return
        self._with_retries(self.users_table.delete_item, Key={"user_id": user_id})
