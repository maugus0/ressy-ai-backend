from fastapi import APIRouter, Depends, HTTPException
from app.utils.security import get_current_active_user, require_role
from app.models.database import UserDatabase

router = APIRouter()
user_db = UserDatabase()

# CREATE
@router.post("/", dependencies=[Depends(require_role(["admin"]))])
async def create_user(data: dict, current_user: dict = Depends(get_current_active_user)):
    user_id = user_db.create_user(
        restaurant_id=data["restaurant_id"],
        email=data["email"],
        role=data.get("role", "staff"),
        permissions=data.get("permissions", [])
    )
    return {"message": "User created successfully", "user_id": user_id}

# READ ALL
@router.get("/{restaurant_id}", dependencies=[Depends(require_role(["admin"]))])
async def list_users(restaurant_id: str, current_user: dict = Depends(get_current_active_user)):
    return user_db.get_users_by_restaurant(restaurant_id)

# UPDATE
@router.put("/{user_id}", dependencies=[Depends(require_role(["admin"]))])
async def update_user(user_id: str, data: dict, current_user: dict = Depends(get_current_active_user)):
    from app.models.database import DynamoDBManager
    db = DynamoDBManager()
    db.users_table.update_item(
        Key={"user_id": user_id},
        UpdateExpression="SET " + ", ".join(f"#{k}=:{k}" for k in data.keys()),
        ExpressionAttributeNames={f"#{k}": k for k in data.keys()},
        ExpressionAttributeValues={f":{k}": v for k, v in data.items()}
    )
    return {"message": "User updated"}

# DELETE
@router.delete("/{user_id}", dependencies=[Depends(require_role(["admin"]))])
async def delete_user(user_id: str, current_user: dict = Depends(get_current_active_user)):

    from app.models.database import DynamoDBManager
    db = DynamoDBManager()
    db.users_table.delete_item(Key={"user_id": user_id})
    return {"message": "User deleted"}
