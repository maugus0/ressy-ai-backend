from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, EmailStr

from app.services.auth_service import AuthService

router = APIRouter()
auth_service = AuthService()
security = HTTPBearer()


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class TokenPairResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "Bearer"
    expires_in: int


class AdminLoginResponse(TokenPairResponse):
    uuid: str
    email: EmailStr
    role: str
    permissions: list[str]
    user_type: str = "admin"


class ClientLoginResponse(TokenPairResponse):
    uuid: str
    email: EmailStr
    role: str
    permissions: list[str]
    restaurant_id: int
    restaurant_name: str
    user_type: str = "restaurant"


def _extract_request_meta(request: Request) -> tuple[str | None, str | None]:
    user_agent = request.headers.get("user-agent")
    ip_address = request.client.host if request.client else None
    return user_agent, ip_address


@router.post("/admin/login", response_model=AdminLoginResponse)
async def admin_login(body: LoginRequest, request: Request):
    """
    Admin login endpoint.
    - Auth: Public
    - Request: email, password
    - Response: access_token, refresh_token, role, permissions, user_type=admin
    """
    user_agent, ip_address = _extract_request_meta(request)
    try:
        return auth_service.login_ressy_admin(body.email, body.password, user_agent, ip_address)
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Login failed")


@router.post("/client/login", response_model=ClientLoginResponse)
async def client_login(body: LoginRequest, request: Request):
    """
    Restaurant admin login endpoint.
    - Auth: Public
    - Request: email, password
    - Response: access_token, refresh_token, role, permissions, restaurant_id/name, user_type=restaurant
    """
    user_agent, ip_address = _extract_request_meta(request)
    try:
        return auth_service.login_restaurant_admin(body.email, body.password, user_agent, ip_address)
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Login failed")


@router.post("/refresh", response_model=TokenPairResponse)
async def refresh_tokens(body: RefreshRequest, request: Request):
    """
    Refresh token rotation endpoint.
    - Auth: Public (requires valid refresh_token in body)
    - Request: refresh_token
    - Response: new access_token and refresh_token for the same session
    """
    user_agent, ip_address = _extract_request_meta(request)
    return auth_service.refresh_tokens(body.refresh_token, user_agent, ip_address)


@router.post("/logout")
async def logout(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """
    Logout endpoint (per-session).
    - Auth: Bearer access token
    - Effect: revokes the session identified by the token's sid
    - Response: success message
    """
    token = credentials.credentials
    return auth_service.logout(token)
