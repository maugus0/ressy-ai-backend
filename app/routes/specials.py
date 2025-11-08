from fastapi import APIRouter, Depends, HTTPException
from app.utils.security import get_current_active_user, require_role
from app.models.database import DynamoDBManager
import uuid, datetime

router = APIRouter()
db = DynamoDBManager()

# CREATE
@router.post("/{restaurant_id}", dependencies=[Depends(require_role(["admin"]))])
async def create_special(restaurant_id: str, data: dict, current_user: dict = Depends(get_current_active_user)):
    special_id = str(uuid.uuid4())
    item = {
        "restaurant_id": restaurant_id,
        "special_id": special_id,
        "created_at": datetime.datetime.utcnow().isoformat(),
        **data
    }
    db.specials_table.put_item(Item=item)
    return {"message": "Special created", "special_id": special_id}

# READ ALL
@router.get("/{restaurant_id}", dependencies=[Depends(require_role(["admin", "client"]))])
async def list_specials(restaurant_id: str, current_user: dict = Depends(get_current_active_user)):
    resp = db.specials_table.scan(
        FilterExpression="restaurant_id = :rid",
        ExpressionAttributeValues={":rid": restaurant_id}
    )
    return resp.get("Items", [])

# READ ONE
@router.get("/{restaurant_id}/{special_id}", dependencies=[Depends(require_role(["admin", "client"]))])
async def get_special(restaurant_id: str, special_id: str, current_user: dict = Depends(get_current_active_user)):
    resp = db.specials_table.get_item(Key={"restaurant_id": restaurant_id, "special_id": special_id})
    return resp.get("Item", {})

# UPDATE
@router.put("/{restaurant_id}/{special_id}", dependencies=[Depends(require_role(["admin", "client"]))])
async def update_special(restaurant_id: str, special_id: str, data: dict, current_user: dict = Depends(get_current_active_user)):

    db.specials_table.update_item(
        Key={"restaurant_id": restaurant_id, "special_id": special_id},
        UpdateExpression="SET " + ", ".join(f"#{k}=:{k}" for k in data.keys()),
        ExpressionAttributeNames={f"#{k}": k for k in data.keys()},
        ExpressionAttributeValues={f":{k}": v for k, v in data.items()}
    )
    return {"message": "Special updated"}

# DELETE
@router.delete("/{restaurant_id}/{special_id}", dependencies=[Depends(require_role(["admin"]))])
async def delete_special(restaurant_id: str, special_id: str, current_user: dict = Depends(get_current_active_user)):

    db.specials_table.delete_item(Key={"restaurant_id": restaurant_id, "special_id": special_id})
    return {"message": "Special deleted"}
