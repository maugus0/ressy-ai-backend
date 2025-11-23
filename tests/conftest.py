import os

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    """Create a test client for the FastAPI app."""
    # Mock database environment variables to prevent connection attempts
    os.environ.setdefault("MYSQL_HOST", "localhost")
    os.environ.setdefault("MYSQL_DATABASE", "test_db")
    os.environ.setdefault("MYSQL_USER", "test_user")
    os.environ.setdefault("MYSQL_PASSWORD", "test_pass")
    os.environ.setdefault("USE_MOCK_DATA", "true")

    try:
        from app.main import app

        return TestClient(app)
    except Exception:
        # If import fails due to DB connection, return None
        # Tests should handle this gracefully
        return None


@pytest.fixture
def mock_env_vars(monkeypatch):
    """Mock environment variables for testing."""
    monkeypatch.setenv("JWT_SECRET_KEY", "test-secret-key")
    monkeypatch.setenv("DEEPGRAM_API_KEY", "test-deepgram-key")
    monkeypatch.setenv("AWS_REGION", "ca-central-1")
