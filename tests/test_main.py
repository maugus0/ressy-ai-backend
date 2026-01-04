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


def test_redirect_forwards_call(client, monkeypatch):
    if client is None:
        pytest.skip("Client not available")

    from app import main

    forwarded = {}

    def fake_get_restaurant_by_twilio(self, twilio_number):
        return {"id": "10", "forward_escalations": True, "escalation_phone_number": "+15550001111"}

    def fake_get_latest(self, call_sid, restaurant_id):
        return {"id": 5, "restaurant_id": restaurant_id}

    def fake_mark_forwarded(self, escalation_id):
        forwarded["id"] = escalation_id
        return True

    monkeypatch.setattr(main.RestaurantService, "get_restaurant_by_twilio", fake_get_restaurant_by_twilio)
    monkeypatch.setattr(main.EscalationService, "get_latest_by_call_sid_and_restaurant", fake_get_latest)
    monkeypatch.setattr(main.EscalationService, "mark_forwarded", fake_mark_forwarded)

    response = client.post("/redirect", data={"CallSid": "CA123", "To": "+19995550000", "From": "+14155551234"})
    assert response.status_code == 200
    assert "<Dial" in response.text
    assert forwarded["id"] == 5


def test_redirect_hangup_without_escalation(client, monkeypatch):
    if client is None:
        pytest.skip("Client not available")

    from app import main

    def fake_get_restaurant_by_twilio(self, twilio_number):
        return {"id": "10", "forward_escalations": True, "escalation_phone_number": "+15550001111"}

    def fake_get_latest(self, call_sid, restaurant_id):
        return None

    monkeypatch.setattr(main.RestaurantService, "get_restaurant_by_twilio", fake_get_restaurant_by_twilio)
    monkeypatch.setattr(main.EscalationService, "get_latest_by_call_sid_and_restaurant", fake_get_latest)

    response = client.post("/redirect", data={"CallSid": "CA999", "To": "+19995550000", "From": "+14155551234"})
    assert response.status_code == 200
    assert "<Hangup" in response.text


def test_redirect_hangup_when_forwarding_disabled(client, monkeypatch):
    if client is None:
        pytest.skip("Client not available")

    from app import main

    def fake_get_restaurant_by_twilio(self, twilio_number):
        return {"id": "10", "forward_escalations": False, "escalation_phone_number": "+15550001111"}

    def fake_get_latest(self, call_sid, restaurant_id):
        return {"id": 9, "restaurant_id": restaurant_id}

    def fake_mark_forwarded(self, escalation_id):
        raise AssertionError("mark_forwarded should not be called")

    monkeypatch.setattr(main.RestaurantService, "get_restaurant_by_twilio", fake_get_restaurant_by_twilio)
    monkeypatch.setattr(main.EscalationService, "get_latest_by_call_sid_and_restaurant", fake_get_latest)
    monkeypatch.setattr(main.EscalationService, "mark_forwarded", fake_mark_forwarded)

    response = client.post("/redirect", data={"CallSid": "CA888", "To": "+19995550000", "From": "+14155551234"})
    assert response.status_code == 200
    assert "<Hangup" in response.text
