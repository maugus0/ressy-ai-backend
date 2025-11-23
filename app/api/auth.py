from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel

from app.services.auth_service import AuthService

router = APIRouter()
auth_service = AuthService()


class UserCreate(BaseModel):
    email: str
    password: str
    role: str = "client"
    company_name: str | None = None


class Token(BaseModel):
    access_token: str
    token_type: str


@router.post("/login", response_model=Token)
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    # Normalize '+' which may arrive as space via x-www-form-urlencoded
    email = form_data.username.replace(" ", "+")
    token = auth_service.login_user(email, form_data.password)
    if not token:
        raise HTTPException(
            status_code=401,
            detail="Incorrect email or password"
        )
    return {"access_token": token, "token_type": "bearer"}
