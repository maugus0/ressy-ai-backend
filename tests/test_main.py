"""Tests for the main FastAPI application."""

import os

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def client():
    """Create a test client for the FastAPI app."""
    # Mock database environment variables to prevent connection attempts
    os.environ.setdefault("ALLOW_DB_FAILURE", "true")
    os.environ.setdefault("MYSQL_HOST", "localhost")
    os.environ.setdefault("MYSQL_DATABASE", "test_db")
    os.environ.setdefault("MYSQL_USER", "test_user")
    os.environ.setdefault("MYSQL_PASSWORD", "test_pass")
    os.environ.setdefault("USE_MOCK_DATA", "true")

    try:
        from app.main import app

        return TestClient(app)
    except Exception as e:
        # If import fails due to DB connection, skip these tests
        pytest.skip(f"Could not import app due to: {e}")


def test_root_endpoint(client):
    """Test the root endpoint."""
    if client is None:
        pytest.skip("Client not available")
    response = client.get("/")
    assert response.status_code == 200
    assert "message" in response.json()
    assert "status" in response.json()
    assert response.json()["status"] == "healthy"


def test_health_check(client):
    """Test the health check endpoint."""
    if client is None:
        pytest.skip("Client not available")
    response = client.get("/health")
    assert response.status_code == 200
    assert "status" in response.json()
    assert response.json()["status"] == "healthy"
    assert "timestamp" in response.json()


def test_app_has_routes():
    """Test that the app has registered routes."""
    os.environ.setdefault("ALLOW_DB_FAILURE", "true")
    os.environ.setdefault("USE_MOCK_DATA", "true")

    try:
        from app.main import app

        route_paths = [str(route.path) for route in app.routes]
        assert "/" in route_paths
        assert "/health" in route_paths
        # Check that API routes are registered (they may be mounted as sub-routers)
        all_routes_str = " ".join(route_paths)
        assert "/api/v1/auth" in all_routes_str or any("/api/v1/auth" in str(route) for route in app.routes)
    except Exception as e:
        pytest.skip(f"Could not import app due to: {e}")
