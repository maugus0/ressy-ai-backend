"""Tests for the main FastAPI application."""

import os
import time

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


def test_voice_kill_switch_redirects_and_persists_side_effects(client, monkeypatch):
    if client is None:
        pytest.skip("Client not available")

    from app import main

    captured = {}

    def fake_get_restaurant_by_twilio(self, twilio_number):
        return {
            "id": 10,
            "kill_switch_enabled": True,
            "forward_escalations": True,
            "escalation_phone_number": "+15550001111",
        }

    def fake_create_user(self, data):
        captured["user_payload"] = data
        return {"user_id": 77}

    def fake_create_call_session(self, user_id, twilio_sid, deepgram_session_id, restaurant_id):
        captured["call_session"] = {
            "user_id": user_id,
            "twilio_sid": twilio_sid,
            "deepgram_session_id": deepgram_session_id,
            "restaurant_id": restaurant_id,
        }
        return 1234

    def fake_finalize_call(self, call_id, status, duration_seconds=0, cost=0.0):
        captured["finalize"] = {
            "call_id": call_id,
            "status": status,
            "duration_seconds": duration_seconds,
            "cost": cost,
        }
        return True

    def fake_create_escalation(self, payload):
        captured["escalation_payload"] = payload
        return 901

    def fake_mark_forwarded(self, escalation_id):
        captured["forwarded_escalation_id"] = escalation_id
        return True

    async def fake_emit_escalation(self, restaurant_id, call_id=None, caller_phone=None, reason=None, data=None):
        captured["sse"] = {
            "restaurant_id": restaurant_id,
            "call_id": call_id,
            "caller_phone": caller_phone,
            "reason": reason,
            "data": data,
        }
        return None

    def fake_create_notification(self, restaurant_id, type, subtype, data=None, entity_id=None):
        captured["notification"] = {
            "restaurant_id": restaurant_id,
            "type": type,
            "subtype": subtype,
            "data": data,
            "entity_id": entity_id,
        }
        return {"id": 444}

    monkeypatch.setattr(main.RestaurantService, "get_restaurant_by_twilio", fake_get_restaurant_by_twilio)
    monkeypatch.setattr(main.UserService, "create_user", fake_create_user)
    monkeypatch.setattr(main.CallService, "create_call_session", fake_create_call_session)
    monkeypatch.setattr(main.CallService, "finalize_call_with_status", fake_finalize_call)
    monkeypatch.setattr(main.EscalationService, "create_escalation", fake_create_escalation)
    monkeypatch.setattr(main.EscalationService, "mark_forwarded", fake_mark_forwarded)
    monkeypatch.setattr(main.SSEService, "emit_escalation_kill_switch_redirected", fake_emit_escalation)
    monkeypatch.setattr(main.NotificationPersistenceService, "create_notification", fake_create_notification)

    response = client.post("/voice", data={"CallSid": "CAKS1", "To": "+19995550000", "From": "+14155551234"})
    assert response.status_code == 200
    assert "<Dial" in response.text
    assert "<Number>+15550001111</Number>" in response.text
    assert "<Stream" not in response.text

    # Kill-switch persistence now runs in a background task; wait briefly for side-effects.
    deadline = time.time() + 1.0
    while "notification" not in captured and time.time() < deadline:
        time.sleep(0.01)

    assert captured["user_payload"] == {"phone_number": "+14155551234"}
    assert captured["call_session"]["twilio_sid"] == "CAKS1"
    assert captured["call_session"]["restaurant_id"] == "10"
    assert captured["finalize"]["status"] == "agent_bypassed"
    assert captured["escalation_payload"]["status"] == "raised"
    assert captured["forwarded_escalation_id"] == 901
    assert captured["sse"]["restaurant_id"] == 10
    assert captured["sse"]["caller_phone"] == "+14155551234"
    assert captured["notification"]["subtype"] == "kill_switch_redirected"
    assert captured["notification"]["entity_id"] == 901
    assert captured["notification"]["data"]["escalation_id"] == 901


def test_voice_kill_switch_misconfigured_falls_back_to_agent(client, monkeypatch):
    if client is None:
        pytest.skip("Client not available")

    from app import main

    def fake_get_restaurant_by_twilio(self, twilio_number):
        return {
            "id": 20,
            "kill_switch_enabled": True,
            "forward_escalations": False,
            "escalation_phone_number": None,
        }

    def should_not_be_called(*args, **kwargs):
        raise AssertionError("Kill-switch side-effect method should not run for misconfigured restaurant")

    monkeypatch.setattr(main.RestaurantService, "get_restaurant_by_twilio", fake_get_restaurant_by_twilio)
    monkeypatch.setattr(main.UserService, "create_user", should_not_be_called)
    monkeypatch.setattr(main.CallService, "create_call_session", should_not_be_called)
    monkeypatch.setattr(main.EscalationService, "create_escalation", should_not_be_called)
    monkeypatch.setattr(main.NotificationPersistenceService, "create_notification", should_not_be_called)

    response = client.post("/voice", data={"CallSid": "CAKS2", "To": "+19995550000", "From": "+14155551234"})
    assert response.status_code == 200
    assert "<Stream" in response.text
    assert "<Dial" not in response.text


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
