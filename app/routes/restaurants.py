from fastapi import APIRouter, Depends, HTTPException
from app.utils.security import get_current_active_user, require_role
from app.models.database import DynamoDBManager
import uuid, datetime

router = APIRouter()
db = DynamoDBManager()

# ---------- CREATE ----------
@router.post("/", dependencies=[Depends(require_role(["admin"]))], summary="Create a new restaurant (Admin only)")
async def create_restaurant(data: dict, current_user: dict = Depends(get_current_active_user)):
    restaurant_id = str(uuid.uuid4())
    item = {
        "restaurant_id": restaurant_id,
        "SK": "METADATA",
        "created_at": datetime.datetime.utcnow().isoformat(),
        "updated_at": datetime.datetime.utcnow().isoformat(),
        **data
    }
    db.restaurants_table.put_item(Item=item)
    return {"message": "Restaurant created successfully", "restaurant_id": restaurant_id}

# ---------- READ ALL ----------
@router.get("/", dependencies=[Depends(require_role(["admin"]))], summary="List all restaurants (Admin only)")
async def list_restaurants(current_user: dict = Depends(get_current_active_user)):
    resp = db.restaurants_table.scan()
    return resp.get("Items", [])

# ---------- READ ONE ----------
@router.get("/{restaurant_id}", dependencies=[Depends(require_role(["admin"]))], summary="Get restaurant details (Admin only)")
async def get_restaurant(restaurant_id: str, current_user: dict = Depends(get_current_active_user)):
    resp = db.restaurants_table.get_item(Key={"restaurant_id": restaurant_id, "SK": "METADATA"})
    return resp.get("Item", {})

# ---------- UPDATE ----------
@router.put("/{restaurant_id}", dependencies=[Depends(require_role(["admin"]))], summary="Update restaurant info (Admin only)")
async def update_restaurant(restaurant_id: str, data: dict, current_user: dict = Depends(get_current_active_user)):
    data["updated_at"] = datetime.datetime.utcnow().isoformat()
    db.restaurants_table.update_item(
        Key={"restaurant_id": restaurant_id, "SK": "METADATA"},
        UpdateExpression="SET " + ", ".join(f"#{k}=:{k}" for k in data.keys()),
        ExpressionAttributeNames={f"#{k}": k for k in data.keys()},
        ExpressionAttributeValues={f":{k}": v for k, v in data.items()}
    )
    return {"message": "Restaurant updated successfully"}

# ---------- DELETE ----------
@router.delete("/{restaurant_id}", dependencies=[Depends(require_role(["admin"]))], summary="Delete restaurant (Admin only)")
async def delete_restaurant(restaurant_id: str, current_user: dict = Depends(get_current_active_user)):
    db.restaurants_table.delete_item(Key={"restaurant_id": restaurant_id, "SK": "METADATA"})
    return {"message": "Restaurant deleted"}
