from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterable, Optional

import jwt
from fastapi import HTTPException, status

from app.config import settings


class JWTUtil:
    """
    Centralized JWT helper for generating and validating Ressy access/refresh tokens.
    """

    def __init__(self, config=settings):
        self.private_key = config.JWT_PRIVATE_KEY
        self.public_key = config.JWT_PUBLIC_KEY
        self.access_ttl_seconds = int(config.JWT_ACCESS_TOKEN_EXP_SECONDS)
        self.refresh_ttl_seconds = int(config.JWT_REFRESH_TOKEN_EXP_SECONDS)
        self.issuer = config.JWT_ISSUER
        self.admin_audience = config.JWT_ADMIN_AUDIENCE
        self.client_audience = config.JWT_CLIENT_AUDIENCE
        self.auth_audience = config.JWT_AUTH_AUDIENCE

    def generate_access_token(self, user: Any, user_type: str, session_id: Optional[str] = None) -> str:
        """
        Create a signed access token for the given user and session.
        """
        self._require_private_key()
        user_type = user_type.lower()
        if user_type not in {"admin", "restaurant"}:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported user type")

        now = self._now()
        exp = now + timedelta(seconds=self.access_ttl_seconds)

        payload: Dict[str, Any] = {
            "iss": self.issuer,
            "aud": self.admin_audience if user_type == "admin" else self.client_audience,
            "sub": self._get_value(user, "uuid"),
            "email": self._get_value(user, "email"),
            "user_type": user_type,
            "role": self._get_value(user, "role"),
            "permissions": self._normalize_permissions(self._get_value(user, "permissions", [])),
            "iat": int(now.timestamp()),
            "exp": int(exp.timestamp()),
            "token_type": "access",
        }

        if session_id:
            payload["sid"] = session_id

        if user_type == "restaurant":
            restaurant_id = self._get_value(user, "restaurant_id") or self._get_value(user, "rest_id")
            restaurant_name = self._get_value(user, "restaurant_name")
            payload["restaurant_id"] = restaurant_id
            if restaurant_name:
                payload["restaurant_name"] = restaurant_name

        return jwt.encode(payload, self.private_key, algorithm="RS256")

    def generate_refresh_token(self, user: Any, user_type: str, session_id: str, token_id: Optional[str] = None) -> str:
        """
        Create a signed refresh token bound to a specific session.
        """
        self._require_private_key()
        user_type = user_type.lower()
        if user_type not in {"admin", "restaurant"}:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported user type")

        now = self._now()
        exp = now + timedelta(seconds=self.refresh_ttl_seconds)

        payload = {
            "iss": self.issuer,
            "aud": self.auth_audience,
            "sub": self._get_value(user, "uuid"),
            "user_type": user_type,
            "sid": session_id,
            "iat": int(now.timestamp()),
            "exp": int(exp.timestamp()),
            "token_type": "refresh",
        }

        if token_id:
            payload["jti"] = token_id

        return jwt.encode(payload, self.private_key, algorithm="RS256")

    def validate_token(self, token: str, expected_audience: str) -> Dict[str, Any]:
        """
        Validate a JWT and return its claims.
        """
        self._require_public_key()
        if not expected_audience:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Audience is required for validation")

        try:
            return jwt.decode(
                token,
                self.public_key,
                algorithms=["RS256"],
                audience=expected_audience,
                issuer=self.issuer,
            )
        except jwt.ExpiredSignatureError:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired")
        except jwt.InvalidAudienceError:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token audience")
        except jwt.InvalidIssuerError:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token issuer")
        except jwt.InvalidTokenError:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    @staticmethod
    def is_refresh_token(claims: Dict[str, Any]) -> bool:
        return claims.get("token_type") == "refresh"

    @staticmethod
    def extract_uuid(claims: Dict[str, Any]) -> Optional[str]:
        return claims.get("sub")

    @staticmethod
    def extract_email(claims: Dict[str, Any]) -> Optional[str]:
        return claims.get("email")

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)

    def _require_private_key(self):
        if not self.private_key:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="JWT private key not set")

    def _require_public_key(self):
        if not self.public_key:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="JWT public key not set")

    @staticmethod
    def _get_value(obj: Any, key: str, default: Any = None) -> Any:
        if isinstance(obj, dict):
            return obj.get(key, default)
        return getattr(obj, key, default)

    @staticmethod
    def _normalize_permissions(permissions: Any) -> list[str]:
        if permissions is None:
            return []
        if isinstance(permissions, str):
            try:
                parsed = json.loads(permissions)
                if isinstance(parsed, list):
                    return [str(p) for p in parsed]
            except (json.JSONDecodeError, TypeError):
                return [permissions]
        if isinstance(permissions, Iterable) and not isinstance(permissions, str):
            return [str(p) for p in permissions]
        return [str(permissions)]
