from fastapi import APIRouter, Depends, HTTPException
from app.utils.security import get_current_active_user, require_role
import uuid, datetime
from app.models.database import DynamoDBManager

router = APIRouter()
db = DynamoDBManager()


# CREATE
@router.post("/{restaurant_id}", dependencies=[Depends(require_role(["admin", "client"]))])
async def create_order(restaurant_id: str, data: dict, current_user: dict = Depends(get_current_active_user)):
    order_id = str(uuid.uuid4())
    item = {
        "order_id": order_id,
        "restaurant_id": restaurant_id,
        "SK": "ORDER_METADATA",
        "created_at": datetime.datetime.utcnow().isoformat(),
        "updated_at": datetime.datetime.utcnow().isoformat(),
        **data
    }
    db.orders_table.put_item(Item=item)
    return {"message": "Order created", "order_id": order_id}

# READ ALL
@router.get("/{restaurant_id}", dependencies=[Depends(require_role(["admin", "client"]))])
async def list_orders(restaurant_id: str, current_user: dict = Depends(get_current_active_user)):
    resp = db.orders_table.scan(
        FilterExpression="restaurant_id = :rid",
        ExpressionAttributeValues={":rid": restaurant_id}
    )
    return resp.get("Items", [])

# READ ONE
@router.get("/details/{order_id}", dependencies=[Depends(require_role(["admin", "client"]))] )
async def get_order(order_id: str, current_user: dict = Depends(get_current_active_user)):
    resp = db.orders_table.get_item(Key={"order_id": order_id, "SK": "ORDER_METADATA"})
    return resp.get("Item", {})

# UPDATE
@router.put("/{order_id}", dependencies=[Depends(require_role(["admin", "client"]))])
async def update_order(order_id: str, data: dict, current_user: dict = Depends(get_current_active_user)):
    data["updated_at"] = datetime.datetime.utcnow().isoformat()
    db.orders_table.update_item(
        Key={"order_id": order_id, "SK": "ORDER_METADATA"},
        UpdateExpression="SET " + ", ".join(f"#{k}=:{k}" for k in data.keys()),
        ExpressionAttributeNames={f"#{k}": k for k in data.keys()},
        ExpressionAttributeValues={f":{k}": v for k, v in data.items()}
    )
    return {"message": "Order updated"}

# DELETE
@router.delete("/{order_id}", dependencies=[Depends(require_role(["admin"]))])
async def delete_order(order_id: str, current_user: dict = Depends(get_current_active_user)):
    db.orders_table.delete_item(Key={"order_id": order_id, "SK": "ORDER_METADATA"})
    return {"message": "Order deleted"}
