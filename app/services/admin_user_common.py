import re
import threading
import time
import uuid
from typing import Dict, List, Optional

import bcrypt
from fastapi import HTTPException, status
from pydantic import EmailStr, TypeAdapter

_email_adapter: TypeAdapter[str] = TypeAdapter(EmailStr)


def validate_uuid(value: str) -> str:
    """Validate UUID format or raise HTTP 400."""
    try:
        uuid_obj = uuid.UUID(str(value))
        return str(uuid_obj)
    except (ValueError, TypeError):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid UUID format")


def validate_email(email: Optional[str], required: bool = True) -> str:
    """Normalize and validate email."""
    if not email:
        if required:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="email is required")
        return ""
    try:
        return _email_adapter.validate_python(str(email).lower())
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid email format")


def validate_password(password: Optional[str], required: bool = True) -> str:
    """Validate password strength."""
    if not password:
        if required:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="password is required")
        return ""
    if len(password) < 8:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Password must be at least 8 characters")
    if not re.search(r"[A-Z]", password):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Password must include an uppercase letter")
    if not re.search(r"[a-z]", password):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Password must include a lowercase letter")
    if not re.search(r"[0-9]", password):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Password must include a number")
    return password


def hash_password(password: str) -> str:
    """Hash password using bcrypt."""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def build_pagination(page: int, limit: int, total: int) -> Dict[str, int]:
    """Build pagination metadata."""
    pages = (total + limit - 1) // limit if limit else 0
    return {"page": page, "limit": limit, "total": total, "pages": pages}


def enforce_reset_rate_limit(
    user_uuid: str,
    buckets: Dict[str, List[float]],
    lock: threading.Lock,
    max_attempts: int,
    window_seconds: int,
):
    """Enforce per-user password reset rate limit."""
    now = time.time()
    window_start = now - window_seconds
    with lock:
        bucket = [ts for ts in buckets.get(user_uuid, []) if ts >= window_start]
        if len(bucket) >= max_attempts:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many password reset attempts, please try again later",
            )
        bucket.append(now)
        if bucket:
            buckets[user_uuid] = bucket
        else:
            buckets.pop(user_uuid, None)
