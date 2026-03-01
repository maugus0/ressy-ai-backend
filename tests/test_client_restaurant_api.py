import os

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("ALLOW_DB_FAILURE", "true")
os.environ.setdefault("USE_MOCK_DATA", "true")

from app.api.restaurants import get_restaurant_service  # noqa: E402
from app.main import app  # noqa: E402
from app.middleware.auth_middleware import get_current_restaurant_user  # noqa: E402
from app.services.restaurant_service import RestaurantService  # noqa: E402
from tests.fake_repos import InMemoryRestaurantFeaturesRepository, InMemoryRestaurantRepository  # noqa: E402


def _claims(restaurant_id: int) -> dict:
    return {
        "user_type": "restaurant",
        "restaurant_id": restaurant_id,
        "role": "manager",
        "sub": f"user-{restaurant_id}",
    }


@pytest.fixture
def client_with_overrides():
    restaurant_repo = InMemoryRestaurantRepository()
    restaurant_repo.add(1, "Pasta Place")
    restaurant_repo.add(2, "Burger Barn")
    features_repo = InMemoryRestaurantFeaturesRepository()
    service = RestaurantService(restaurant_repo=restaurant_repo, features_repo=features_repo)
    app.dependency_overrides[get_restaurant_service] = lambda: service
    app.dependency_overrides[get_current_restaurant_user] = lambda: _claims(1)
    client = TestClient(app)
    yield client, restaurant_repo
    app.dependency_overrides = {}


def test_get_and_update_own_restaurant(client_with_overrides):
    client, repo = client_with_overrides
    resp = client.get("/api/v1/client/restaurant")
    assert resp.status_code == 200
    assert resp.json()["name"] == "Pasta Place"

    update = client.put("/api/v1/client/restaurant", json={"name": "Updated Place", "forward_minutes": 15})
    assert update.status_code == 200
    assert update.json()["name"] == "Updated Place"
    # ensure repo updated
    assert repo.get_by_id(1)["forward_minutes"] == 15


def test_client_forward_escalations_requires_number(client_with_overrides):
    client, _repo = client_with_overrides
    update = client.put("/api/v1/client/restaurant", json={"forward_escalations": True})
    assert update.status_code == 400


def test_client_enable_kill_switch_requires_forwarding_ready(client_with_overrides):
    client, _repo = client_with_overrides
    resp = client.patch("/api/v1/client/restaurant/kill-switch", json={"enabled": True})
    assert resp.status_code == 400
    detail = resp.json()["detail"]
    assert "kill_switch_blockers" in detail
    assert "forward_escalations_disabled" in detail["kill_switch_blockers"]


def test_client_can_toggle_own_kill_switch(client_with_overrides):
    client, _repo = client_with_overrides

    configure = client.put(
        "/api/v1/client/restaurant",
        json={
            "forward_escalations": True,
            "escalation_phone_number": "+15550001111",
        },
    )
    assert configure.status_code == 200

    enable = client.patch("/api/v1/client/restaurant/kill-switch", json={"enabled": True})
    assert enable.status_code == 200
    enabled_payload = enable.json()
    assert enabled_payload["kill_switch_enabled"] is True
    assert enabled_payload["kill_switch_can_redirect"] is True
    assert enabled_payload["kill_switch_blockers"] == []

    disable = client.patch("/api/v1/client/restaurant/kill-switch", json={"enabled": False})
    assert disable.status_code == 200
    assert disable.json()["kill_switch_enabled"] is False


def test_client_update_rejects_invalid_forwarding_when_kill_switch_enabled(client_with_overrides):
    client, _repo = client_with_overrides
    configure = client.put(
        "/api/v1/client/restaurant",
        json={
            "forward_escalations": True,
            "escalation_phone_number": "+15550001111",
        },
    )
    assert configure.status_code == 200
    enable = client.patch("/api/v1/client/restaurant/kill-switch", json={"enabled": True})
    assert enable.status_code == 200

    bad_update = client.put("/api/v1/client/restaurant", json={"forward_escalations": False})
    assert bad_update.status_code == 400
    detail = bad_update.json()["detail"]
    assert "kill switch is enabled" in detail["message"].lower()
    assert "forward_escalations_disabled" in detail["kill_switch_blockers"]


def test_client_kill_switch_toggle_emits_event_on_state_change(client_with_overrides, monkeypatch):
    client, _repo = client_with_overrides
    captured = []

    async def _mock_emit(**kwargs):
        captured.append(kwargs)

    monkeypatch.setattr("app.api.client_restaurant.emit_kill_switch_toggled", _mock_emit)

    configure = client.put(
        "/api/v1/client/restaurant",
        json={
            "forward_escalations": True,
            "escalation_phone_number": "+15550009994",
        },
    )
    assert configure.status_code == 200

    enable = client.patch("/api/v1/client/restaurant/kill-switch", json={"enabled": True})
    assert enable.status_code == 200
    assert len(captured) == 1
    event = captured[0]
    assert event["restaurant_id"] == 1
    assert event["enabled"] is True
    assert event["previous_enabled"] is False
    assert event["actor_type"] == "restaurant"
    assert event["source"] == "client_dashboard"
