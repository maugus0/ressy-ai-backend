# app/utils/security.py
from functools import lru_cache
from typing import Dict

import jwt
import requests
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

security = HTTPBearer()

# config
COGNITO_USERPOOL_ID = "YOUR_USERPOOL_ID"
COGNITO_REGION = "ca-central-1"
COGNITO_APP_CLIENT_ID = "YOUR_APP_CLIENT_ID"

JWKS_URL = f"https://cognito-idp.{COGNITO_REGION}.amazonaws.com/{COGNITO_USERPOOL_ID}/.well-known/jwks.json"


@lru_cache()
def get_jwks():
    response = requests.get(JWKS_URL)
    if response.status_code != 200:
        raise HTTPException(status_code=500, detail="Failed to fetch Cognito JWKS")
    return response.json()


def verify_cognito_token(token: str) -> Dict:
    try:
        headers = jwt.get_unverified_header(token)
        jwks = get_jwks()
        key = next((k for k in jwks["keys"] if k["kid"] == headers["kid"]), None)
        if not key:
            raise HTTPException(status_code=401, detail="Invalid token")

        public_key = jwt.algorithms.RSAAlgorithm.from_jwk(key)
        payload = jwt.decode(
            token,
            key=public_key,
            algorithms=[headers["alg"]],
            audience=COGNITO_APP_CLIENT_ID,
        )
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired")
    except jwt.InvalidTokenError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=f"Invalid token: {str(e)}")


def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    token = credentials.credentials
    payload = verify_cognito_token(token)
    return payload


def get_current_active_user(payload: dict = Depends(get_current_user)) -> dict:
    if payload.get("cognito:user_status", "CONFIRMED") != "CONFIRMED":
        raise HTTPException(status_code=400, detail="Inactive user")
    return payload


def require_role(roles: list[str]):
    def role_checker(payload: dict = Depends(get_current_active_user)):
        user_roles = payload.get("cognito:groups", [])
        if not any(role in user_roles for role in roles):
            raise HTTPException(status_code=403, detail="Not authorized")
        return payload

    return role_checker
