import os

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("ALLOW_DB_FAILURE", "true")
os.environ.setdefault("USE_MOCK_DATA", "true")

from app.api import client_escalations, escalations  # noqa: E402
from app.main import app  # noqa: E402
from app.middleware.auth_middleware import get_current_admin_user, get_current_restaurant_user  # noqa: E402
from app.services.escalation_service import EscalationService  # noqa: E402
from tests.fake_repos import InMemoryEscalationRepository  # noqa: E402


def _admin_claims() -> dict:
    return {"user_type": "admin", "role": "admin", "sub": "admin-1"}


def _client_claims(rest_id: int) -> dict:
    return {"user_type": "restaurant", "role": "manager", "restaurant_id": rest_id, "sub": f"user-{rest_id}"}


def _make_escalation_repo() -> InMemoryEscalationRepository:
    return InMemoryEscalationRepository(
        escalations=[
            {
                "id": 1,
                "call_id": 101,
                "user_id": "456",
                "restaurant_id": "10",
                "restaurant_name": "Alpha",
                "twilio_call_sid": "CA123",
                "caller_phone": "+14155551234",
                "escalation_phone_number": "+15550001111",
                "urgency": "high",
                "reason": "customer asked for a manager",
                "status": "raised",
                "requested_at": "2024-03-01T12:00:00Z",
                "created_at": "2024-03-01T12:00:00Z",
                "updated_at": "2024-03-01T12:00:00Z",
            },
            {
                "id": 2,
                "call_id": 202,
                "user_id": "789",
                "restaurant_id": "20",
                "restaurant_name": "Beta",
                "twilio_call_sid": "CA999",
                "caller_phone": "+14155550000",
                "escalation_phone_number": "+15550002222",
                "urgency": "low",
                "reason": "caller requested callback",
                "status": "failed",
                "requested_at": "2024-03-02T09:00:00Z",
                "created_at": "2024-03-02T09:00:00Z",
                "updated_at": "2024-03-02T09:00:00Z",
            },
        ]
    )


@pytest.fixture
def client_with_escalations():
    repo = _make_escalation_repo()
    service = EscalationService(escalation_repo=repo)

    app.dependency_overrides[escalations.get_escalation_service] = lambda: service
    app.dependency_overrides[client_escalations.get_escalation_service] = lambda: service
    app.dependency_overrides[get_current_admin_user] = _admin_claims
    app.dependency_overrides[get_current_restaurant_user] = lambda: _client_claims(10)

    client = TestClient(app)
    yield client, repo
    app.dependency_overrides = {}


def test_admin_list_escalations(client_with_escalations):
    client, _ = client_with_escalations
    resp = client.get("/api/v1/admin/escalations?status=raised")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["restaurant_name"] == "Alpha"


def test_admin_get_escalation_detail(client_with_escalations):
    client, _ = client_with_escalations
    resp = client.get("/api/v1/admin/escalations/1")
    assert resp.status_code == 200
    detail = resp.json()
    assert detail["call_id"] == "101"
    assert detail["call_sid"] == "CA123"


def test_client_scoped_escalations(client_with_escalations):
    client, _ = client_with_escalations
    resp = client.get("/api/v1/client/escalations")
    assert resp.status_code == 200
    assert resp.json()["total"] == 1

    forbidden = client.get("/api/v1/client/escalations/2")
    assert forbidden.status_code == 403

    forbidden_update = client.patch("/api/v1/client/escalations/2/status", json={"status": "resolved"})
    assert forbidden_update.status_code == 403


def test_admin_update_status(client_with_escalations):
    client, _ = client_with_escalations
    resp = client.patch("/api/v1/admin/escalations/1/status", json={"status": "forwarded"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "forwarded"


def test_client_update_status(client_with_escalations):
    client, _ = client_with_escalations
    resp = client.patch("/api/v1/client/escalations/1/status", json={"status": "resolved"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "resolved"


def test_invalid_status_rejected(client_with_escalations):
    client, _ = client_with_escalations
    resp = client.patch("/api/v1/admin/escalations/1/status", json={"status": "unknown"})
    assert resp.status_code == 400
