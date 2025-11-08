from fastapi import APIRouter, Depends, HTTPException
from app.utils.security import get_current_active_user, require_role
from app.models.database import DynamoDBManager
import uuid, datetime

router = APIRouter()
db = DynamoDBManager()

# CREATE
@router.post("/{restaurant_id}", dependencies=[Depends(require_role(["admin"]))])
async def create_faq(restaurant_id: str, data: dict, current_user: dict = Depends(get_current_active_user)):
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
@router.get("/{restaurant_id}", dependencies=[Depends(require_role(["admin"]))])
async def list_faqs(restaurant_id: str, current_user: dict = Depends(get_current_active_user)):
    resp = db.faqs_table.query(
        IndexName="restaurant_id-faq_id-index",
        KeyConditionExpression="restaurant_id = :rid",
        ExpressionAttributeValues={":rid": restaurant_id}
    )
    return resp.get("Items", [])

# UPDATE
@router.put("/{restaurant_id}/{faq_id}", dependencies=[Depends(require_role(["admin"]))])
async def update_faq(restaurant_id: str, faq_id: str, data: dict, current_user: dict = Depends(get_current_active_user)):
    db.faqs_table.update_item(
        Key={"restaurant_id": restaurant_id, "faq_id": faq_id},
        UpdateExpression="SET " + ", ".join(f"#{k}=:{k}" for k in data.keys()),
        ExpressionAttributeNames={f"#{k}": k for k in data.keys()},
        ExpressionAttributeValues={f":{k}": v for k, v in data.items()}
    )
    return {"message": "FAQ updated"}

# DELETE
@router.delete("/{restaurant_id}/{faq_id}", dependencies=[Depends(require_role(["admin"]))])
async def delete_faq(restaurant_id: str, faq_id: str, current_user: dict = Depends(get_current_active_user)):
    db.faqs_table.delete_item(Key={"restaurant_id": restaurant_id, "faq_id": faq_id})
    return {"message": "FAQ deleted"}
