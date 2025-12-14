from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, EmailStr, Field

from app.services.auth_service import AuthService

router = APIRouter()
auth_service = AuthService()
security = HTTPBearer(scheme_name="HTTPBearer")


class LoginRequest(BaseModel):
    """Request model for user login."""

    email: EmailStr = Field(..., description="User email address")
    password: str = Field(..., min_length=1, description="User password")


class RefreshRequest(BaseModel):
    """Request model for token refresh."""

    refresh_token: str = Field(..., description="Refresh token to exchange for new tokens")


class TokenPairResponse(BaseModel):
    """Response model containing access and refresh tokens."""

    access_token: str = Field(..., description="JWT access token for API authentication")
    refresh_token: str = Field(..., description="Refresh token for obtaining new access tokens")
    token_type: str = Field(default="Bearer", description="Token type, typically 'Bearer'")
    expires_in: int = Field(..., description="Access token expiration time in seconds")


class AdminLoginResponse(TokenPairResponse):
    """Response model for admin user login."""

    uuid: str = Field(..., description="Unique user identifier")
    email: EmailStr = Field(..., description="User email address")
    role: str = Field(..., description="User role (e.g., 'admin', 'super_admin')")
    permissions: list[str] = Field(..., description="List of user permissions")
    user_type: str = Field(default="admin", description="Type of user, always 'admin' for this endpoint")


class ClientLoginResponse(TokenPairResponse):
    """Response model for restaurant admin/client login."""

    uuid: str = Field(..., description="Unique user identifier")
    email: EmailStr = Field(..., description="User email address")
    role: str = Field(..., description="User role (e.g., 'manager', 'staff')")
    permissions: list[str] = Field(..., description="List of user permissions")
    restaurant_id: int = Field(..., description="ID of the restaurant the user belongs to")
    restaurant_name: str = Field(..., description="Name of the restaurant")
    user_type: str = Field(default="restaurant", description="Type of user, always 'restaurant' for this endpoint")


def _extract_request_meta(request: Request) -> tuple[str | None, str | None]:
    user_agent = request.headers.get("user-agent")
    ip_address = request.client.host if request.client else None
    return user_agent, ip_address


@router.post(
    "/admin/login",
    response_model=AdminLoginResponse,
    summary="Admin Login",
    description="Authenticate an admin user and receive access tokens. This endpoint is public and does not require authentication.",
    response_description="Returns access token, refresh token, user information, role, and permissions.",
)
async def admin_login(body: LoginRequest, request: Request):
    """
    Admin login endpoint for RessyAI platform admin users (CRM).

    **Authentication**: Public (no token required)

    **Request Body**:
    - email: Admin user's email address
    - password: Admin user's password

    **Response**:
    - access_token: JWT token for API authentication
    - refresh_token: Token for refreshing access tokens
    - uuid: User unique identifier
    - email: User email address
    - role: User role (admin, super_admin, etc.)
    - permissions: List of user permissions
    - user_type: Always "admin" for this endpoint
    """
    user_agent, ip_address = _extract_request_meta(request)
    try:
        return auth_service.login_ressy_admin(body.email, body.password, user_agent, ip_address)
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Login failed")


@router.post(
    "/client/login",
    response_model=ClientLoginResponse,
    summary="Restaurant Admin Login",
    description="Authenticate a restaurant admin/client user and receive access tokens. This endpoint is public and does not require authentication.",
    response_description="Returns access token, refresh token, user information, restaurant details, role, and permissions.",
)
async def client_login(body: LoginRequest, request: Request):
    """
    Restaurant admin/client login endpoint for restaurant staff and managers.

    **Authentication**: Public (no token required)

    **Request Body**:
    - email: Restaurant user's email address
    - password: Restaurant user's password

    **Response**:
    - access_token: JWT token for API authentication
    - refresh_token: Token for refreshing access tokens
    - uuid: User unique identifier
    - email: User email address
    - role: User role (manager, staff, etc.)
    - permissions: List of user permissions
    - restaurant_id: ID of the restaurant the user belongs to
    - restaurant_name: Name of the restaurant
    - user_type: Always "restaurant" for this endpoint
    """
    user_agent, ip_address = _extract_request_meta(request)
    try:
        return auth_service.login_restaurant_admin(body.email, body.password, user_agent, ip_address)
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Login failed")


@router.post(
    "/refresh",
    response_model=TokenPairResponse,
    summary="Refresh Access Token",
    description="Exchange a refresh token for a new access token and refresh token pair. Implements token rotation for enhanced security.",
    response_description="Returns new access token and refresh token pair.",
)
async def refresh_tokens(body: RefreshRequest, request: Request):
    """
    Refresh token rotation endpoint for obtaining new access tokens.

    **Authentication**: Public (requires valid refresh_token in request body)

    **Request Body**:
    - refresh_token: Valid refresh token obtained from login

    **Response**:
    - access_token: New JWT access token
    - refresh_token: New refresh token (old one is invalidated)
    - token_type: Token type (Bearer)
    - expires_in: Access token expiration time in seconds

    **Note**: The old refresh token is invalidated upon successful refresh.
    """
    user_agent, ip_address = _extract_request_meta(request)
    return auth_service.refresh_tokens(body.refresh_token, user_agent, ip_address)


@router.post(
    "/logout",
    summary="Logout",
    description="Logout the current user session. Revokes the session identified by the access token's session ID.",
    response_description="Returns a success message confirming logout.",
)
async def logout(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """
    Logout endpoint to revoke the current user session.

    **Authentication**: Required (Bearer token)

    **Effect**:
    - Revokes the session identified by the token's session ID (sid)
    - Invalidates the current access token

    **Response**:
    - Success message confirming logout
    """
    token = credentials.credentials
    return auth_service.logout(token)
