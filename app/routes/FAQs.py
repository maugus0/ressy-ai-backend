from fastapi import APIRouter, Depends, HTTPException
from app.utils.security import get_current_active_user
from app.models.database import DynamoDBManager
import uuid, datetime

router = APIRouter()
db = DynamoDBManager()

def _check_role(role):
    if role not in ["admin", "manager"]:
        raise HTTPException(403, "Not authorized")

# CREATE
@router.post("/{restaurant_id}")
async def create_faq(restaurant_id: str, data: dict, current_user: dict = Depends(get_current_active_user)):
    _check_role(current_user.get("role"))
    faq_id = str(uuid.uuid4())
    item = {
        "restaurant_id": restaurant_id,
        "faq_id": faq_id,
        "created_at": datetime.datetime.utcnow().isoformat(),
        "updated_at": datetime.datetime.utcnow().isoformat(),
        **data
    }
    db.faqs_table.put_item(Item=item)
    return {"message": "FAQ created", "faq_id": faq_id}

# READ ALL
@router.get("/{restaurant_id}")
async def list_faqs(restaurant_id: str, current_user: dict = Depends(get_current_active_user)):
    _check_role(current_user.get("role"))
    resp = db.faqs_table.query(
        IndexName="restaurant_id-faq_id-index",
        KeyConditionExpression="restaurant_id = :rid",
        ExpressionAttributeValues={":rid": restaurant_id}
    )
    return resp.get("Items", [])

# UPDATE
@router.put("/{restaurant_id}/{faq_id}")
async def update_faq(restaurant_id: str, faq_id: str, data: dict, current_user: dict = Depends(get_current_active_user)):
    _check_role(current_user.get("role"))
    db.faqs_table.update_item(
        Key={"restaurant_id": restaurant_id, "faq_id": faq_id},
        UpdateExpression="SET " + ", ".join(f"#{k}=:{k}" for k in data.keys()),
        ExpressionAttributeNames={f"#{k}": k for k in data.keys()},
        ExpressionAttributeValues={f":{k}": v for k, v in data.items()}
    )
    return {"message": "FAQ updated"}

# DELETE
@router.delete("/{restaurant_id}/{faq_id}")
async def delete_faq(restaurant_id: str, faq_id: str, current_user: dict = Depends(get_current_active_user)):
    _check_role(current_user.get("role"))
    db.faqs_table.delete_item(Key={"restaurant_id": restaurant_id, "faq_id": faq_id})
    return {"message": "FAQ deleted"}
