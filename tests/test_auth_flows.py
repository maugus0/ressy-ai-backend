import uuid
from datetime import datetime, timedelta, timezone

import bcrypt
import pytest
from fastapi import HTTPException

from app.config import settings
from app.services.auth_service import AuthService
from app.utils.jwt_util import JWTUtil

TEST_PRIVATE_KEY = """-----BEGIN PRIVATE KEY-----
MIIEvQIBADANBgkqhkiG9w0BAQEFAASCBKcwggSjAgEAAoIBAQCqBNgoP9H0Tt0Y
RU7/3AqaiyaGp+iGniGvYkjImzz/UfHeupBI48qaPpVjzQH1ntWU1NfXvLZZiUgk
IxFHk/BTG7lYbbUuJPWYmI7vsFqNas0IRoTvKMYzBQlzpUPuBXbiy4xK0szhQKF4
oottlq0P9v77ImDDFgORs8lQgujAejsi+Egqz8dAO34ff1dfjA0z6j+r6UxR5+6i
0crXbRv46rPqXUPXFuXPqchZIkofgDYFYsr7hI7/OCPFPWeldTYyguQBFNKB/R/O
XkzBwFE6mUqfdjfepIoFuVfVV+wEJKWaZ4eYJ9iu2BJl36N46L1iniMQJDUvLJwh
UCon2bYtAgMBAAECggEAHs+pb6PfM+fd3AHldutE1ax9gx4nPswl/R9x4r71Tyzl
yRAkyTzU0N6iGpfCsOVDvgjTg+KMZk4Bb6EWRtM51Inb7TlWggILKwgMsUXTpzix
ZvxGp4PLZWAWjilnVdmSKbgrGL06iWC50n+chnPtsYy4uUDJ6djRtUQwacGLliPU
yfH2c4OeHE9v/UigZISZ/U0Tt3qso6xXZmUhr+2RlN1BOxPhdkiVkTZuSCeeWNiK
Ywj+2aDlWI4Zq7PCGrG1YonwbWlQToQASIQ7ajQ6uQS2NSvbUXAt3LyiSDeajTgg
VOU1Z6CcyEU6/dlc1GdOmy8oeM9yqrj2GJ+xrJ5wKQKBgQDfwcshYldL6fq1WzHL
UJHiteTC7eKPg230bZrrhVuq2uSLqqWYbJHLWFjugoXS2FGckAxkRKeY8w40Nlse
MQeq7YlteVJ82wA0hylt2tYL8hmW5EEgGbcBLledxmuUWqOI006f2hIRaT+bKli/
YLY11EI9OMMtlZ04tvu3G4fmNQKBgQDChLLR5q74LDGBmsJTpu7GLyE2LoRxLKC9
8PBof7iMzOVHYgZX7P1Zfxd7sNw5iQt+GTAv62cgnn/89Wp2iZqj4o3Ui2AHkvI7
dLgPQYnwVKmZfa2Vfdco3upKrA8/+M+j+q6n01Zwagy56832vS9dvBem94Yzh7MC
7H96Gx6vGQKBgEeGNf1c5xTAHUDdfsRD4+45QH/C9Nn1JC+u3YeNoGi0AbxXdwmL
IuuCOSM8m7RzK1tFfICMpZoxj4fHHEdBWvcbaQOSdXittJoV3ntcKXG2GNHv8pVl
QudgvecUJw1MD9xL12UnmwDvyMI7vhSmwHfieq4BN/qZSaF4dGvqo/1FAoGAGXmV
jcXfbmMjTKz+/EOli9EKUXVAJS5KEvYmFhl8Cvyenn2pBQTlnT32zl04SlS3a5lS
5UO4Kt53NqLRgZq95O670nU6a2OEU+MSY/UaYp5D4/VAsY5cil6/Ym4sRR2J3Bjt
nM8hx/Ern4HRZJocRPNoSZarPb5s5Foiy9QXbakCgYEAvLfsBukyCeyyxxuOJex1
vHswOAkdpiZaXosacTd/KbQMcLUfUeQtU3ZAoMZftPOHVQCoxlQypk/8RTqw9Ywb
QOIeAM9J9g7SofA50VTFL9EgoGCblpDnj57tr2AfSP3L1hasdycCfZkId77XjXP4
wggbqyiU5M6JUKO5CF4kp9Y=
-----END PRIVATE KEY-----"""

TEST_PUBLIC_KEY = """-----BEGIN PUBLIC KEY-----
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAqgTYKD/R9E7dGEVO/9wK
mosmhqfohp4hr2JIyJs8/1Hx3rqQSOPKmj6VY80B9Z7VlNTX17y2WYlIJCMRR5Pw
Uxu5WG21LiT1mJiO77BajWrNCEaE7yjGMwUJc6VD7gV24suMStLM4UCheKKLbZat
D/b++yJgwxYDkbPJUILowHo7IvhIKs/HQDt+H39XX4wNM+o/q+lMUefuotHK120b
+Oqz6l1D1xblz6nIWSJKH4A2BWLK+4SO/zgjxT1npXU2MoLkARTSgf0fzl5MwcBR
OplKn3Y33qSKBblX1VfsBCSlmmeHmCfYrtgSZd+jeOi9Yp4jECQ1LyycIVAqJ9m2
LQIDAQAB
-----END PUBLIC KEY-----"""


class StubAuthRepo:
    def __init__(self, admin_user: dict, restaurant_user: dict, restaurant_details: dict):
        self.admin_user = admin_user
        self.restaurant_user = restaurant_user
        self.restaurant_details = restaurant_details
        self.sessions: dict[str, dict] = {}
        self.last_active_touches: list[tuple[str, str]] = []

    # Admin lookups
    def get_admin_by_email(self, email: str):
        if self.admin_user and email == self.admin_user["email"]:
            return dict(self.admin_user)
        return None

    def get_admin_by_uuid(self, user_uuid: str):
        if self.admin_user and user_uuid == self.admin_user["uuid"]:
            return dict(self.admin_user)
        return None

    def update_admin_login_times(self, user_uuid: str):
        return 1

    # Restaurant admin lookups
    def get_restaurant_admin_by_email(self, email: str):
        if self.restaurant_user and email == self.restaurant_user["email"]:
            return dict(self.restaurant_user)
        return None

    def get_restaurant_admin_by_uuid(self, user_uuid: str):
        if self.restaurant_user and user_uuid == self.restaurant_user["uuid"]:
            return dict(self.restaurant_user)
        return None

    def update_restaurant_admin_login_times(self, user_uuid: str):
        return 1

    def touch_last_active(self, user_uuid: str, user_type: str):
        self.last_active_touches.append((user_uuid, user_type))
        return 1

    def get_role_with_permissions(self, role_id: int):
        role_name = "admin" if role_id == 1 else "manager"
        return {"id": role_id, "role": role_name, "permissions": ["perm:view", "perm:edit"]}

    def get_restaurant_details(self, restaurant_id: int):
        if self.restaurant_details and restaurant_id == self.restaurant_details["id"]:
            return dict(self.restaurant_details)
        return None

    # Session operations
    def create_session(
        self,
        session_id: str,
        user_id: str,
        user_type: str,
        refresh_token_hash: str,
        refresh_ttl_seconds: int,
        user_agent: str | None,
        ip_address: str | None,
    ):
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=refresh_ttl_seconds)
        self.sessions[session_id] = {
            "id": session_id,
            "user_id": user_id,
            "user_type": user_type,
            "refresh_token_hash": refresh_token_hash,
            "expires_at": expires_at,
            "revoked": 0,
            "user_agent": user_agent,
            "ip_address": ip_address,
        }
        return 1

    def get_session(self, session_id: str):
        session = self.sessions.get(session_id)
        return dict(session) if session else None

    def update_session_refresh_token(
        self,
        session_id: str,
        refresh_token_hash: str,
        refresh_ttl_seconds: int,
        user_agent: str | None,
        ip_address: str | None,
    ):
        if session_id not in self.sessions:
            return 0
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=refresh_ttl_seconds)
        self.sessions[session_id].update(
            {
                "refresh_token_hash": refresh_token_hash,
                "expires_at": expires_at,
                "revoked": 0,
                "user_agent": user_agent,
                "ip_address": ip_address,
            }
        )
        return 1

    def revoke_session(self, session_id: str):
        if session_id not in self.sessions:
            return 0
        self.sessions[session_id]["revoked"] = 1
        self.sessions[session_id]["expires_at"] = datetime.now(timezone.utc)
        return 1


@pytest.fixture
def jwt_settings(monkeypatch):
    monkeypatch.setattr(settings, "JWT_PRIVATE_KEY", TEST_PRIVATE_KEY)
    monkeypatch.setattr(settings, "JWT_PUBLIC_KEY", TEST_PUBLIC_KEY)
    monkeypatch.setattr(settings, "JWT_ADMIN_AUDIENCE", "test-admin-api")
    monkeypatch.setattr(settings, "JWT_CLIENT_AUDIENCE", "test-client-api")
    monkeypatch.setattr(settings, "JWT_AUTH_AUDIENCE", "test-auth")
    monkeypatch.setattr(settings, "JWT_ACCESS_TOKEN_EXP_SECONDS", 300)
    monkeypatch.setattr(settings, "JWT_REFRESH_TOKEN_EXP_SECONDS", 600)
    yield


def _build_stub_repo(password: str) -> StubAuthRepo:
    hashed_password = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    admin_user = {"uuid": str(uuid.uuid4()), "email": "admin@example.com", "password": hashed_password, "role_id": 1}
    restaurant_user = {
        "uuid": str(uuid.uuid4()),
        "email": "rest@example.com",
        "password": hashed_password,
        "role_id": 2,
        "rest_id": 42,
    }
    restaurant_details = {"id": 42, "name": "Demo Restaurant"}
    return StubAuthRepo(admin_user, restaurant_user, restaurant_details)


def test_jwt_util_generates_and_validates_tokens(jwt_settings):
    util = JWTUtil()
    user = {"uuid": "user-1", "email": "user@example.com", "role": "admin", "permissions": ["p1", "p2"]}
    access_token = util.generate_access_token(user, "admin", session_id="session-123")
    access_claims = util.validate_token(access_token, settings.JWT_ADMIN_AUDIENCE)
    assert access_claims["sub"] == "user-1"
    assert access_claims["sid"] == "session-123"
    assert access_claims["token_type"] == "access"

    refresh_token = util.generate_refresh_token(user, "admin", session_id="session-123", token_id="refresh-id")
    refresh_claims = util.validate_token(refresh_token, settings.JWT_AUTH_AUDIENCE)
    assert util.is_refresh_token(refresh_claims) is True
    assert refresh_claims["jti"] == "refresh-id"


def test_admin_login_creates_session_and_tokens(jwt_settings):
    raw_password = "StrongPass!23"
    repo = _build_stub_repo(raw_password)
    service = AuthService(auth_repo=repo, jwt_util=JWTUtil())

    result = service.login_ressy_admin("admin@example.com", raw_password, "test-agent", "127.0.0.1")
    assert "access_token" in result and "refresh_token" in result
    claims = service.jwt_util.validate_token(result["access_token"], settings.JWT_ADMIN_AUDIENCE)
    session_id = claims["sid"]
    assert session_id in repo.sessions
    session = repo.sessions[session_id]
    assert session["user_agent"] == "test-agent"
    assert session["ip_address"] == "127.0.0.1"
    refresh_claims = service.jwt_util.validate_token(result["refresh_token"], settings.JWT_AUTH_AUDIENCE)
    assert bcrypt.checkpw(refresh_claims["jti"].encode("utf-8"), session["refresh_token_hash"].encode("utf-8"))


def test_refresh_rotation_invalidates_previous_token(jwt_settings):
    raw_password = "AnotherPass!23"
    repo = _build_stub_repo(raw_password)
    service = AuthService(auth_repo=repo, jwt_util=JWTUtil())

    initial = service.login_ressy_admin("admin@example.com", raw_password, "ua1", "10.0.0.1")
    first_refresh = initial["refresh_token"]
    rotated = service.refresh_tokens(first_refresh, "ua2", "10.0.0.2")
    assert rotated["refresh_token"] != first_refresh

    with pytest.raises(HTTPException):
        service.refresh_tokens(first_refresh, None, None)


def test_logout_revokes_session(jwt_settings):
    raw_password = "LogoutPass!23"
    repo = _build_stub_repo(raw_password)
    service = AuthService(auth_repo=repo, jwt_util=JWTUtil())

    tokens = service.login_ressy_admin("admin@example.com", raw_password, None, None)
    claims = service.jwt_util.validate_token(tokens["access_token"], settings.JWT_ADMIN_AUDIENCE)
    session_id = claims["sid"]

    service.logout(tokens["access_token"])
    assert repo.sessions[session_id]["revoked"] == 1

    with pytest.raises(HTTPException):
        service.refresh_tokens(tokens["refresh_token"], None, None)


def test_restaurant_login_includes_scope(jwt_settings):
    raw_password = "RestScope!23"
    repo = _build_stub_repo(raw_password)
    service = AuthService(auth_repo=repo, jwt_util=JWTUtil())

    result = service.login_restaurant_admin("rest@example.com", raw_password, "ua", "8.8.8.8")
    claims = service.jwt_util.validate_token(result["access_token"], settings.JWT_CLIENT_AUDIENCE)
    assert claims["user_type"] == "restaurant"
    assert claims["restaurant_id"] == repo.restaurant_details["id"]
    assert claims["restaurant_name"] == repo.restaurant_details["name"]
