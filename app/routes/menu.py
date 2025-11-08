from fastapi import APIRouter, Depends, HTTPException
from app.utils.security import get_current_active_user, require_role
from app.models.database import DynamoDBManager
import uuid, datetime

router = APIRouter()
db = DynamoDBManager()

# CREATE
@router.post("/{restaurant_id}", dependencies=[Depends(require_role(["admin"]))])
async def create_menu(restaurant_id: str, data: dict, current_user: dict = Depends(get_current_active_user)):
    menu_id = str(uuid.uuid4())
    item = {
        "restaurant_id": restaurant_id,
        "menu_id": menu_id,
        "created_at": datetime.datetime.utcnow().isoformat(),
        "updated_at": datetime.datetime.utcnow().isoformat(),
        **data
    }
    db.menus_table.put_item(Item=item)
    return {"message": "Menu created successfully", "menu_id": menu_id}

# READ ALL
@router.get("/{restaurant_id}", dependencies=[Depends(require_role(["admin", "client"]))])
async def list_menus(restaurant_id: str, current_user: dict = Depends(get_current_active_user)):
    resp = db.menus_table.query(
        IndexName="restaurant_id-menu_id-index",
        KeyConditionExpression="restaurant_id = :rid",
        ExpressionAttributeValues={":rid": restaurant_id}
    )
    return resp.get("Items", [])

# READ ONE
@router.get("/{restaurant_id}/{menu_id}", dependencies=[Depends(require_role(["admin", "client"]))])
async def get_menu(restaurant_id: str, menu_id: str, current_user: dict = Depends(get_current_active_user)):
    resp = db.menus_table.get_item(Key={"restaurant_id": restaurant_id, "menu_id": menu_id})
    return resp.get("Item", {})

# UPDATE
@router.put("/{restaurant_id}/{menu_id}", dependencies=[Depends(require_role(["admin", "client"]))])
async def update_menu(restaurant_id: str, menu_id: str, data: dict, current_user: dict = Depends(get_current_active_user)):
    data["updated_at"] = datetime.datetime.utcnow().isoformat()
    db.menus_table.update_item(
        Key={"restaurant_id": restaurant_id, "menu_id": menu_id},
        UpdateExpression="SET " + ", ".join(f"#{k}=:{k}" for k in data.keys()),
        ExpressionAttributeNames={f"#{k}": k for k in data.keys()},
        ExpressionAttributeValues={f":{k}": v for k, v in data.items()}
    )
    return {"message": "Menu updated successfully"}

# DELETE
@router.delete("/{restaurant_id}/{menu_id}", dependencies=[Depends(require_role(["admin"]))])
async def delete_menu(restaurant_id: str, menu_id: str, current_user: dict = Depends(get_current_active_user)):
    db.menus_table.delete_item(Key={"restaurant_id": restaurant_id, "menu_id": menu_id})
    return {"message": "Menu deleted successfully"}
