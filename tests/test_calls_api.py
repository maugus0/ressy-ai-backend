import json
import os

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("ALLOW_DB_FAILURE", "true")
os.environ.setdefault("USE_MOCK_DATA", "true")

from app.api import calls, client_calls  # noqa: E402
from app.main import app  # noqa: E402
from app.middleware.auth_middleware import get_current_admin_user, get_current_restaurant_user  # noqa: E402
from app.services.call_service import CallService  # noqa: E402
from tests.fake_repos import InMemoryCallRepository  # noqa: E402


def _admin_claims() -> dict:
    return {"user_type": "admin", "role": "admin", "sub": "admin-1"}


def _client_claims(rest_id: int) -> dict:
    return {"user_type": "restaurant", "role": "manager", "restaurant_id": rest_id, "sub": f"user-{rest_id}"}


def _make_call_repo():
    return InMemoryCallRepository(
        calls=[
            {
                "id": 1,
                "restaurant_id": "10",
                "restaurant_name": "Alpha",
                "user_id": "+14155551234",
                "caller_phone": "+14155551234",
                "call_duration": 120,
                "call_status": "completed",
                "started_at": "2024-03-01T12:00:00Z",
                "call_transcript": json.dumps(
                    {"conversation": [{"sequence": 1, "role": "user", "content": "book a table", "timestamp": "t1"}]}
                ),
            },
            {
                "id": 2,
                "restaurant_id": "20",
                "restaurant_name": "Beta",
                "user_id": "+14155550000",
                "caller_phone": "+14155550000",
                "call_duration": 45,
                "call_status": "failed",
                "started_at": "2024-03-01T13:00:00Z",
                "call_transcript": None,
            },
        ]
    )


@pytest.fixture
def client_with_calls():
    repo = _make_call_repo()
    service = CallService()
    # Override factory method to return fake repo
    service._get_call_repo = lambda: repo

    app.dependency_overrides[calls.get_call_service] = lambda: service
    app.dependency_overrides[client_calls.get_call_service] = lambda: service
    app.dependency_overrides[get_current_admin_user] = _admin_claims
    app.dependency_overrides[get_current_restaurant_user] = lambda: _client_claims(10)

    client = TestClient(app)
    yield client, repo
    app.dependency_overrides = {}


def test_admin_list_calls(client_with_calls):
    client, _ = client_with_calls
    resp = client.get("/api/v1/admin/calls?restaurant_id=10")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["restaurant_name"] == "Alpha"
    assert data["items"][0]["has_transcript"] is True


def test_admin_call_detail_and_delete_transcript(client_with_calls):
    client, repo = client_with_calls
    resp = client.get("/api/v1/admin/calls/1")
    assert resp.status_code == 200
    detail = resp.json()
    assert detail["call_id"] == "1"
    assert detail["has_transcript"] is True
    assert "twilio_cost" in detail
    assert "deepgram_cost" in detail
    assert "ressy_cost" in detail
    assert detail["transcript"][0]["content"] == "book a table"

    delete_tx = client.delete("/api/v1/admin/calls/1/transcript")
    assert delete_tx.status_code == 200
    assert repo._calls[1]["call_transcript"] is None


def test_admin_search_calls(client_with_calls):
    client, _ = client_with_calls
    resp = client.get("/api/v1/admin/calls/search?q=book")
    assert resp.status_code == 200
    assert resp.json()["total"] == 1


def test_client_calls_scoped_and_forbidden(client_with_calls):
    client, _ = client_with_calls
    # default claims restaurant_id=10
    resp = client.get("/api/v1/client/calls")
    assert resp.status_code == 200
    assert resp.json()["total"] == 1

    # detail allowed
    detail = client.get("/api/v1/client/calls/1")
    assert detail.status_code == 200

    # override to different restaurant
    app.dependency_overrides[get_current_restaurant_user] = lambda: _client_claims(99)
    forbidden = client.get("/api/v1/client/calls/1")
    assert forbidden.status_code == 403


def test_client_export_csv(client_with_calls):
    client, _ = client_with_calls
    resp = client.get("/api/v1/client/calls/export")
    assert resp.status_code == 200
    body = resp.content.decode()
    assert "timestamp,caller_phone,duration_seconds,status,summary" in body
    assert "+14155551234" in body


def test_admin_analytics_requires_dates(client_with_calls):
    client, _ = client_with_calls
    missing = client.get("/api/v1/admin/calls/analytics")
    assert missing.status_code == 422  # missing required params
    ok = client.get("/api/v1/admin/calls/analytics?date_from=2024-01-01&date_to=2024-01-31")
    assert ok.status_code == 200
    assert ok.json()["total_calls"] == 2


def test_update_call_cost_preserves_escalated_status():
    repo = InMemoryCallRepository(
        calls=[
            {
                "id": 3,
                "restaurant_id": "10",
                "user_id": "+14155551234",
                "caller_phone": "+14155551234",
                "call_duration": 0,
                "call_status": "escalated",
                "started_at": "2024-03-01T12:00:00Z",
                "call_transcript": None,
            }
        ]
    )
    service = CallService()
    service._get_call_repo = lambda: repo

    service.update_call_cost(call_id=3, duration_seconds=120)

    assert repo._calls[3]["call_status"] == "escalated"
