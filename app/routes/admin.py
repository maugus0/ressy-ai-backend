from fastapi import APIRouter, Depends, HTTPException
from app.utils.security import get_current_active_user

router = APIRouter()

@router.get("/users")
async def get_all_users(current_user: dict = Depends(get_current_active_user)):
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Not authorized")
    
    # Implement admin user listing logic here
    return {"message": "Admin endpoint - implement user listing"}