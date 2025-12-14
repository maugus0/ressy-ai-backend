from typing import List, Optional

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.utils.jwt_util import JWTUtil

security = HTTPBearer(scheme_name="HTTPBearer")
jwt_util = JWTUtil()


def _validate_access_token(token: str, audiences: List[str]) -> dict:
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    claims = None
    last_error: Optional[HTTPException] = None
    for audience in audiences:
        try:
            claims = jwt_util.validate_token(token, audience)
            break
        except HTTPException as exc:  # noqa: PERF203 small loop
            last_error = exc
    if claims is None:
        raise last_error or HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    if claims.get("token_type") != "access":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Access token required")

    return claims


def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    token = credentials.credentials if credentials else None
    return _validate_access_token(token, [jwt_util.admin_audience, jwt_util.client_audience])


def get_current_active_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    return get_current_user(credentials)


def get_current_admin_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    claims = _validate_access_token(credentials.credentials if credentials else None, [jwt_util.admin_audience])
    if claims.get("user_type") != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return claims


def get_current_restaurant_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    claims = _validate_access_token(credentials.credentials if credentials else None, [jwt_util.client_audience])
    if claims.get("user_type") != "restaurant":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Restaurant access required")
    return claims


def require_role(roles: List[str]):
    def role_checker(
        request: Request,
        credentials: HTTPAuthorizationCredentials = Depends(security),
    ):
        claims = _validate_access_token(
            credentials.credentials if credentials else None, [jwt_util.admin_audience, jwt_util.client_audience]
        )
        user_role = claims.get("role")
        user_type = claims.get("user_type")

        if roles and not _role_matches(user_role, user_type, roles):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")

        if request and user_type == "restaurant":
            path_restaurant_id = request.path_params.get("restaurant_id")
            if path_restaurant_id:
                token_restaurant_id = str(claims.get("restaurant_id"))
                if token_restaurant_id and token_restaurant_id != str(path_restaurant_id):
                    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Restaurant access denied")

        return claims

    return role_checker


def _role_matches(user_role: Optional[str], user_type: Optional[str], allowed_roles: List[str]) -> bool:
    normalized_user_role = (user_role or "").lower()
    normalized_user_type = (user_type or "").lower()

    for role in allowed_roles:
        role_normalized = role.lower()
        if normalized_user_role == role_normalized:
            return True
        if role_normalized == "admin" and normalized_user_type == "admin":
            return True
        if role_normalized in {"client", "restaurant"} and normalized_user_type == "restaurant":
            return True
    return False
