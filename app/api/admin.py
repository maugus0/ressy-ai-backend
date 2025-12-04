from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, Field

from app.middleware.admin_middleware import require_admin_role
from app.services.admin_auth_service import AdminAuthService
from app.services.admin_restaurant_service import AdminRestaurantService
from app.services.admin_service import AdminService

router = APIRouter()
admin_service = AdminService()
admin_restaurant_service = AdminRestaurantService()
admin_auth_service = AdminAuthService()


# Pydantic models for restaurant requests
class CreateRestaurantRequest(BaseModel):
    name: str = Field(..., max_length=255, description="Restaurant name (required)")
    address: Optional[str] = Field(None, description="Restaurant address")
    phone_number: Optional[str] = Field(None, max_length=20, description="Phone number")
    twilio_phone_number: Optional[str] = Field(None, max_length=20, description="Twilio phone number")
    twilio_details: Optional[Dict[str, Any]] = Field(None, description="Twilio configuration JSON")
    deepgram_details: Optional[Dict[str, Any]] = Field(None, description="Deepgram configuration JSON")
    open_table_details: Optional[Dict[str, Any]] = Field(None, description="OpenTable integration details JSON")
    forward_minutes: Optional[int] = Field(0, ge=0, description="Forward booking window in minutes")
    backward_minutes: Optional[int] = Field(0, ge=0, description="Backward booking window in minutes")
    is_credit_card_required_for_reservation: Optional[bool] = Field(
        False, description="Require credit card for reservation"
    )


class UpdateRestaurantRequest(BaseModel):
    name: Optional[str] = Field(None, max_length=255, description="Restaurant name")
    address: Optional[str] = Field(None, description="Restaurant address")
    phone_number: Optional[str] = Field(None, max_length=20, description="Phone number")
    twilio_phone_number: Optional[str] = Field(None, max_length=20, description="Twilio phone number")
    twilio_details: Optional[Dict[str, Any]] = Field(None, description="Twilio configuration JSON")
    deepgram_details: Optional[Dict[str, Any]] = Field(None, description="Deepgram configuration JSON")
    open_table_details: Optional[Dict[str, Any]] = Field(None, description="OpenTable integration details JSON")
    forward_minutes: Optional[int] = Field(None, ge=0, description="Forward booking window in minutes")
    backward_minutes: Optional[int] = Field(None, ge=0, description="Backward booking window in minutes")
    is_credit_card_required_for_reservation: Optional[bool] = Field(
        None, description="Require credit card for reservation"
    )


class AdminToken(BaseModel):
    access_token: str
    token_type: str


@router.post("/login", response_model=AdminToken, summary="Admin login")
async def admin_login(form_data: OAuth2PasswordRequestForm = Depends()):
    """
    Login endpoint for Ressy Administrators.
    Returns JWT token for authenticated admin users.
    """
    # Normalize '+' which may arrive as space via x-www-form-urlencoded
    email = form_data.username.replace(" ", "+")

    admin_data = admin_auth_service.authenticate_admin(email, form_data.password)
    if not admin_data:
        raise HTTPException(status_code=401, detail="Incorrect email or password")

    token = admin_auth_service.generate_token(admin_data)
    return {"access_token": token, "token_type": "bearer"}


@router.get("/users", summary="Get all users (Admin only)")
async def get_all_users(current_admin: dict = Depends(require_admin_role(["admin"]))):
    """
    Get all users - admin only operation.
    Requires admin role.
    """
    return admin_service.get_all_users()


# ---------- RESTAURANT MANAGEMENT ENDPOINTS ----------


@router.post("/restaurants", status_code=201, summary="Create a new restaurant")
async def create_restaurant(
    request: CreateRestaurantRequest, current_admin: dict = Depends(require_admin_role(["admin"]))
):
    """
    Create a new restaurant.
    Requires admin authentication.
    """
    data = request.dict(exclude_unset=True)
    return admin_restaurant_service.create_restaurant(data)


@router.get("/restaurants", summary="Get all restaurants with pagination and filtering")
async def get_all_restaurants(
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(20, ge=1, le=100, description="Items per page (max 100)"),
    search: Optional[str] = Query(None, description="Search by restaurant name"),
    is_credit_card_required: Optional[bool] = Query(None, description="Filter by credit card requirement"),
    current_admin: dict = Depends(require_admin_role(["admin"])),
):
    """
    Get all restaurants with pagination, search, and filtering.
    Requires admin authentication.
    """
    return admin_restaurant_service.get_all_restaurants(
        page=page, limit=limit, search=search, is_credit_card_required=is_credit_card_required
    )


@router.get("/restaurants/{restaurant_id}", summary="Get restaurant by ID")
async def get_restaurant_by_id(restaurant_id: int, current_admin: dict = Depends(require_admin_role(["admin"]))):
    """
    Get restaurant by ID.
    Requires admin authentication.
    """
    return admin_restaurant_service.get_restaurant_by_id(restaurant_id)


@router.put("/restaurants/{restaurant_id}", summary="Update restaurant")
async def update_restaurant(
    restaurant_id: int, request: UpdateRestaurantRequest, current_admin: dict = Depends(require_admin_role(["admin"]))
):
    """
    Update restaurant by ID.
    Requires admin authentication.
    Accepts partial updates - only provided fields will be updated.
    """
    data = request.dict(exclude_unset=True)
    return admin_restaurant_service.update_restaurant(restaurant_id, data)


@router.delete("/restaurants/{restaurant_id}", summary="Delete restaurant")
async def delete_restaurant(restaurant_id: int, current_admin: dict = Depends(require_admin_role(["admin"]))):
    """
    Delete restaurant by ID.
    Requires admin authentication.
    Cascade deletion will handle associated data automatically.
    """
    return admin_restaurant_service.delete_restaurant(restaurant_id)


@router.get("/restaurants/{restaurant_id}/stats", summary="Get restaurant statistics")
async def get_restaurant_statistics(restaurant_id: int, current_admin: dict = Depends(require_admin_role(["admin"]))):
    """
    Get statistics for a restaurant including:
    - Total menu items
    - Available menu items
    - Special items count
    - Total FAQs
    - Total administrators
    - Total calls
    - Total minute usage
    Requires admin authentication.
    """
    return admin_restaurant_service.get_restaurant_statistics(restaurant_id)
