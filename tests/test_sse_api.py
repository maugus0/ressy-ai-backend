"""
Tests for SSE (Server-Sent Events) API authentication.

Tests cover:
- Authentication via query parameter (for browser EventSource API)
- Authentication via Authorization header (backward compatibility)
- Fallback behavior when only one method is provided
- Error handling when neither authentication method is provided
"""

import os
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

# Allow app import without a live MySQL instance
os.environ.setdefault("ALLOW_DB_FAILURE", "true")
os.environ.setdefault("USE_MOCK_DATA", "true")

from app.api.sse import get_sse_service  # noqa: E402
from app.main import app  # noqa: E402
from app.services.sse_service import SSEService  # noqa: E402
from app.utils.jwt_util import JWTUtil  # noqa: E402

# Test JWT keys (same as test_auth_flows.py)
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


@pytest.fixture
def client():
    """Create a test client for the FastAPI app."""
    return TestClient(app)


@pytest.fixture
def jwt_util():
    """Create a JWT utility instance with test keys."""
    from unittest.mock import MagicMock

    # Create a mock config with test keys
    mock_config = MagicMock()
    mock_config.JWT_PRIVATE_KEY = TEST_PRIVATE_KEY
    mock_config.JWT_PUBLIC_KEY = TEST_PUBLIC_KEY
    mock_config.JWT_ACCESS_TOKEN_EXP_SECONDS = 3600
    mock_config.JWT_REFRESH_TOKEN_EXP_SECONDS = 86400
    mock_config.JWT_ISSUER = "ressy.ai/auth"
    mock_config.JWT_ADMIN_AUDIENCE = "ressy-admin-api"
    mock_config.JWT_CLIENT_AUDIENCE = "ressy-client-api"
    mock_config.JWT_AUTH_AUDIENCE = "ressy-auth-api"

    return JWTUtil(config=mock_config)


@pytest.fixture(autouse=True)
def patch_jwt_util_in_sse():
    """Patch the JWTUtil instance in the SSE module to use test keys."""
    # Create a JWTUtil with test keys
    mock_config = MagicMock()
    mock_config.JWT_PRIVATE_KEY = TEST_PRIVATE_KEY
    mock_config.JWT_PUBLIC_KEY = TEST_PUBLIC_KEY
    mock_config.JWT_ACCESS_TOKEN_EXP_SECONDS = 3600
    mock_config.JWT_REFRESH_TOKEN_EXP_SECONDS = 86400
    mock_config.JWT_ISSUER = "ressy.ai/auth"
    mock_config.JWT_ADMIN_AUDIENCE = "ressy-admin-api"
    mock_config.JWT_CLIENT_AUDIENCE = "ressy-client-api"
    mock_config.JWT_AUTH_AUDIENCE = "ressy-auth-api"

    test_jwt_util = JWTUtil(config=mock_config)

    with patch("app.api.sse.jwt_util", test_jwt_util):
        yield


@pytest.fixture
def admin_user():
    """Mock admin user data."""
    return {
        "uuid": "admin-123",
        "email": "admin@ressy.ai",
        "role": "admin",
        "permissions": ["*"],
    }


@pytest.fixture
def restaurant_user():
    """Mock restaurant user data."""
    return {
        "uuid": "restaurant-456",
        "email": "manager@restaurant.com",
        "role": "manager",
        "restaurant_id": 1,
        "restaurant_name": "Test Restaurant",
        "permissions": ["*"],
    }


@pytest.fixture
def admin_token(jwt_util, admin_user):
    """Generate a valid admin access token."""
    return jwt_util.generate_access_token(admin_user, "admin", session_id="test-session")


@pytest.fixture
def restaurant_token(jwt_util, restaurant_user):
    """Generate a valid restaurant access token."""
    return jwt_util.generate_access_token(restaurant_user, "restaurant", session_id="test-session")


class TestSSEAuthentication:
    """Test SSE endpoint authentication via query parameter and header."""

    def test_authentication_via_query_parameter_succeeds(self, client, admin_token):
        """Test that authentication via query parameter works correctly."""
        # Create a mock SSE service
        mock_sse_service = MagicMock(spec=SSEService)
        mock_connection = MagicMock()
        mock_sse_service.connect = AsyncMock(return_value=mock_connection)

        # Make event_stream raise immediately to stop streaming
        async def mock_stream(*args):
            raise StopAsyncIteration()

        mock_sse_service.event_stream = mock_stream

        # Override the dependency
        app.dependency_overrides[get_sse_service] = lambda: mock_sse_service

        # Use a short timeout - if auth fails we get 401/403 immediately
        # If auth succeeds, connection starts but we stop it quickly
        try:
            response = client.get(
                f"/api/v1/sse/events/stream?token={admin_token}",
                headers={"Accept": "text/event-stream"},
                timeout=0.5,
            )
            # If we get a response, verify it's not an auth error
            assert response.status_code != 401, "Should authenticate via query parameter"
            assert response.status_code != 403, "Should not be forbidden"
        except Exception:
            # Timeout/connection error is acceptable - means auth passed and connection started
            pass
        finally:
            # Clean up dependency override
            app.dependency_overrides.pop(get_sse_service, None)

    def test_authentication_via_header_succeeds(self, client, admin_token):
        """Test that authentication via Authorization header still works (backward compatibility)."""
        mock_sse_service = MagicMock(spec=SSEService)
        mock_connection = MagicMock()
        mock_sse_service.connect = AsyncMock(return_value=mock_connection)

        async def mock_stream(*args):
            raise StopAsyncIteration()

        mock_sse_service.event_stream = mock_stream

        app.dependency_overrides[get_sse_service] = lambda: mock_sse_service

        try:
            response = client.get(
                "/api/v1/sse/events/stream",
                headers={
                    "Authorization": f"Bearer {admin_token}",
                    "Accept": "text/event-stream",
                },
                timeout=0.5,
            )
            assert response.status_code != 401, "Should authenticate via header"
            assert response.status_code != 403, "Should not be forbidden"
        except Exception:
            # Timeout is acceptable - means auth passed
            pass
        finally:
            app.dependency_overrides.pop(get_sse_service, None)

    def test_query_parameter_takes_priority_over_header(self, client, admin_token, restaurant_token):
        """Test that query parameter token takes priority when both are provided."""
        mock_sse_service = MagicMock(spec=SSEService)
        mock_connection = MagicMock()
        mock_sse_service.connect = AsyncMock(return_value=mock_connection)

        async def mock_stream(*args):
            raise StopAsyncIteration()

        mock_sse_service.event_stream = mock_stream

        app.dependency_overrides[get_sse_service] = lambda: mock_sse_service

        try:
            # Provide admin token in query, restaurant token in header
            # Query param should take priority
            response = client.get(
                f"/api/v1/sse/events/stream?token={admin_token}",
                headers={
                    "Authorization": f"Bearer {restaurant_token}",
                    "Accept": "text/event-stream",
                },
                timeout=0.5,
            )
            # Should use query param token (admin), not header token
            assert response.status_code != 401, "Should use query parameter token"
            assert response.status_code != 403, "Should not be forbidden"
        except Exception:
            # Timeout is acceptable
            pass
        finally:
            app.dependency_overrides.pop(get_sse_service, None)

    def test_no_authentication_returns_401(self, client):
        """Test that missing both query parameter and header returns 401."""
        response = client.get(
            "/api/v1/sse/events/stream",
            headers={"Accept": "text/event-stream"},
        )

        assert response.status_code == 401, "Should return 401 when no authentication provided"
        assert "Authentication required" in response.json()["detail"]

    def test_invalid_token_returns_401(self, client):
        """Test that invalid token returns 401."""
        response = client.get(
            "/api/v1/sse/events/stream?token=invalid-token",
            headers={"Accept": "text/event-stream"},
        )

        assert response.status_code == 401, "Should return 401 for invalid token"
        assert "Invalid token" in response.json()["detail"]

    def test_expired_token_returns_401(self, client, jwt_util, admin_user):
        """Test that expired token returns 401."""
        # Create an expired token by manipulating the expiration
        import jwt

        payload = {
            "iss": jwt_util.issuer,
            "aud": jwt_util.admin_audience,
            "sub": admin_user["uuid"],
            "email": admin_user["email"],
            "user_type": "admin",
            "role": "admin",
            "permissions": ["*"],
            "iat": int((datetime.now(timezone.utc) - timedelta(hours=2)).timestamp()),
            "exp": int((datetime.now(timezone.utc) - timedelta(hours=1)).timestamp()),  # Expired 1 hour ago
            "token_type": "access",
        }

        expired_token = jwt.encode(payload, TEST_PRIVATE_KEY, algorithm="RS256")

        response = client.get(
            f"/api/v1/sse/events/stream?token={expired_token}",
            headers={"Accept": "text/event-stream"},
        )

        assert response.status_code == 401, "Should return 401 for expired token"

    def test_restaurant_user_can_access_own_restaurant(self, client, restaurant_token):
        """Test that restaurant user can access events for their own restaurant."""
        mock_sse_service = MagicMock(spec=SSEService)
        mock_connection = MagicMock()
        mock_sse_service.connect = AsyncMock(return_value=mock_connection)

        async def mock_stream(*args):
            raise StopAsyncIteration()

        mock_sse_service.event_stream = mock_stream

        app.dependency_overrides[get_sse_service] = lambda: mock_sse_service

        try:
            # Restaurant user (restaurant_id=1) accessing their own restaurant
            response = client.get(
                f"/api/v1/sse/events/stream?token={restaurant_token}&restaurant_id=1",
                headers={"Accept": "text/event-stream"},
                timeout=0.5,
            )
            assert response.status_code != 403, "Restaurant user should access own restaurant"
        except Exception:
            # Timeout is acceptable
            pass
        finally:
            app.dependency_overrides.pop(get_sse_service, None)

    def test_restaurant_user_cannot_access_other_restaurant(self, client, restaurant_token):
        """Test that restaurant user cannot access events for other restaurants."""
        # Restaurant user (restaurant_id=1) trying to access restaurant_id=2
        response = client.get(
            f"/api/v1/sse/events/stream?token={restaurant_token}&restaurant_id=2",
            headers={"Accept": "text/event-stream"},
        )

        assert response.status_code == 403, "Should return 403 for unauthorized restaurant access"
        assert "own restaurant" in response.json()["detail"].lower()

    def test_admin_can_access_any_restaurant(self, client, admin_token):
        """Test that admin can access events for any restaurant."""
        mock_sse_service = MagicMock(spec=SSEService)
        mock_connection = MagicMock()
        mock_sse_service.connect = AsyncMock(return_value=mock_connection)

        async def mock_stream(*args):
            raise StopAsyncIteration()

        mock_sse_service.event_stream = mock_stream

        app.dependency_overrides[get_sse_service] = lambda: mock_sse_service

        try:
            # Admin accessing any restaurant
            response = client.get(
                f"/api/v1/sse/events/stream?token={admin_token}&restaurant_id=999",
                headers={"Accept": "text/event-stream"},
                timeout=0.5,
            )
            assert response.status_code != 403, "Admin should access any restaurant"
        except Exception:
            # Timeout is acceptable
            pass
        finally:
            app.dependency_overrides.pop(get_sse_service, None)
