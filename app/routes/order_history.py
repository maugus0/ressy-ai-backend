from fastapi import APIRouter, Depends
from app.utils.security import get_current_active_user
from app.models.database import DynamoDBManager

router = APIRouter()
db = DynamoDBManager()

@router.get("/{order_id}/history")
async def get_order_history(order_id: str, current_user: dict = Depends(get_current_active_user)):
    return db.order_history_table.query(
        KeyConditionExpression=f"order_id = :oid",
        ExpressionAttributeValues={":oid": order_id}
    ).get("Items", [])
