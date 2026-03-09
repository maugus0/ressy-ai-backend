import os

import pytest
from fastapi.testclient import TestClient

# Allow app import without a live MySQL instance
os.environ.setdefault("ALLOW_DB_FAILURE", "true")
os.environ.setdefault("USE_MOCK_DATA", "true")

from app.api.restaurants import get_restaurant_service  # noqa: E402
from app.main import app  # noqa: E402
from app.middleware.auth_middleware import get_current_admin_user  # noqa: E402
from app.services.restaurant_service import RestaurantService  # noqa: E402
from tests.fake_repos import InMemoryRestaurantFeaturesRepository, InMemoryRestaurantRepository  # noqa: E402


@pytest.fixture
def client_with_overrides():
    restaurant_repo = InMemoryRestaurantRepository()
    features_repo = InMemoryRestaurantFeaturesRepository()
    service = RestaurantService(restaurant_repo=restaurant_repo, features_repo=features_repo)
    app.dependency_overrides[get_restaurant_service] = lambda: service
    app.dependency_overrides[get_current_admin_user] = lambda: {"user_type": "admin"}
    client = TestClient(app)
    yield client
    app.dependency_overrides = {}


def test_create_and_get_restaurant_with_hours(client_with_overrides):
    client = client_with_overrides
    resp = client.post(
        "/api/v1/restaurants/",
        json={
            "name": "Evening Eats",
            "operating_hours": {
                "monday": {"open": "10:00:00", "close": "23:30:00", "is_closed": False},
                "tuesday": {"open": "10:00:00", "close": "23:30:00", "is_closed": False},
                "wednesday": {"open": "10:00:00", "close": "23:30:00", "is_closed": False},
                "thursday": {"open": "10:00:00", "close": "23:30:00", "is_closed": False},
                "friday": {"open": "10:00:00", "close": "23:30:00", "is_closed": False},
                "saturday": {"open": "10:00:00", "close": "23:30:00", "is_closed": False},
                "sunday": {"open": "10:00:00", "close": "23:30:00", "is_closed": False},
            },
            "forward_minutes": 30,
        },
    )
    assert resp.status_code == 201, resp.text
    created = resp.json()
    assert created["operating_hours"]["monday"]["open"] == "10:00:00"
    assert created["operating_hours"]["monday"]["close"] == "23:30:00"

    get_resp = client.get(f"/api/v1/restaurants/{created['id']}")
    assert get_resp.status_code == 200
    assert get_resp.json()["name"] == "Evening Eats"


def test_list_includes_default_hours(client_with_overrides):
    client = client_with_overrides
    client.post("/api/v1/restaurants/", json={"name": "Default Hours"})

    list_resp = client.get("/api/v1/restaurants/")
    assert list_resp.status_code == 200
    body = list_resp.json()
    assert body["items"][0]["operating_hours"]["monday"]["open"] == "09:00:00"
    assert body["items"][0]["operating_hours"]["monday"]["close"] == "22:00:00"


def test_update_restaurant_hours(client_with_overrides):
    client = client_with_overrides
    create_resp = client.post("/api/v1/restaurants/", json={"name": "Update Hours"})
    rid = create_resp.json()["id"]

    update_resp = client.put(
        f"/api/v1/restaurants/{rid}",
        json={
            "operating_hours": {
                "monday": {"open": "08:00:00", "close": "20:00:00", "is_closed": False},
            }
        },
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["operating_hours"]["monday"]["open"] == "08:00:00"
    assert update_resp.json()["operating_hours"]["monday"]["close"] == "20:00:00"


def test_forward_escalations_requires_number_on_update(client_with_overrides):
    client = client_with_overrides
    create_resp = client.post("/api/v1/restaurants/", json={"name": "Escalation Update"})
    rid = create_resp.json()["id"]

    update_resp = client.put(f"/api/v1/restaurants/{rid}", json={"forward_escalations": True})
    assert update_resp.status_code == 400


def test_invalid_hours_rejected(client_with_overrides):
    client = client_with_overrides
    resp = client.post(
        "/api/v1/restaurants/",
        json={
            "name": "Bad",
            "operating_hours": {
                "monday": {"open": "25:00:00", "close": "22:00:00", "is_closed": False},
            },
        },
    )
    # Invalid time format should be rejected - 422 (Pydantic) or 400 (service layer)
    assert resp.status_code in (400, 422)


def test_duplicate_name_rejected(client_with_overrides):
    client = client_with_overrides
    first = client.post("/api/v1/restaurants/", json={"name": "Dup"})
    assert first.status_code == 201
    second = client.post("/api/v1/restaurants/", json={"name": "Dup"})
    assert second.status_code == 400


def test_duplicate_twilio_rejected(client_with_overrides):
    client = client_with_overrides
    first = client.post("/api/v1/restaurants/", json={"name": "One", "twilio_phone_number": "+12223334444"})
    assert first.status_code == 201
    dup = client.post("/api/v1/restaurants/", json={"name": "Two", "twilio_phone_number": "+12223334444"})
    assert dup.status_code == 400


def test_forward_escalations_requires_number_on_create(client_with_overrides):
    client = client_with_overrides
    resp = client.post("/api/v1/restaurants/", json={"name": "Escalations", "forward_escalations": True})
    assert resp.status_code == 400


def test_create_restaurant_rejects_non_e164_escalation_number(client_with_overrides):
    client = client_with_overrides
    resp = client.post(
        "/api/v1/restaurants/",
        json={
            "name": "Bad Escalation Number",
            "forward_escalations": True,
            "escalation_phone_number": "(415) 555-1234",
        },
    )
    assert resp.status_code == 400
    assert "E.164" in resp.json()["detail"]


def test_admin_enable_kill_switch_requires_forwarding_readiness(client_with_overrides):
    client = client_with_overrides
    create = client.post("/api/v1/restaurants/", json={"name": "Kill Switch Invalid"})
    rid = create.json()["id"]

    toggle = client.patch(f"/api/v1/restaurants/{rid}/kill-switch", json={"enabled": True})
    assert toggle.status_code == 400
    detail = toggle.json()["detail"]
    assert detail["message"].startswith("Cannot enable kill switch")
    assert "forward_escalations_disabled" in detail["kill_switch_blockers"]
    assert "escalation_phone_number_missing" in detail["kill_switch_blockers"]


def test_admin_can_toggle_restaurant_kill_switch(client_with_overrides):
    client = client_with_overrides
    create = client.post(
        "/api/v1/restaurants/",
        json={
            "name": "Kill Switch Ready",
            "forward_escalations": True,
            "escalation_phone_number": "+15550001111",
        },
    )
    rid = create.json()["id"]

    enable = client.patch(f"/api/v1/restaurants/{rid}/kill-switch", json={"enabled": True})
    assert enable.status_code == 200
    enabled_payload = enable.json()
    assert enabled_payload["kill_switch_enabled"] is True
    assert enabled_payload["kill_switch_can_redirect"] is True
    assert enabled_payload["kill_switch_blockers"] == []

    disable = client.patch(f"/api/v1/restaurants/{rid}/kill-switch", json={"enabled": False})
    assert disable.status_code == 200
    assert disable.json()["kill_switch_enabled"] is False


def test_admin_bulk_enable_kill_switch_skips_invalid_restaurants(client_with_overrides):
    client = client_with_overrides
    ready_resp = client.post(
        "/api/v1/restaurants/",
        json={
            "name": "Bulk Ready",
            "forward_escalations": True,
            "escalation_phone_number": "+15550002222",
        },
    )
    invalid_resp = client.post("/api/v1/restaurants/", json={"name": "Bulk Invalid"})
    ready_id = ready_resp.json()["id"]
    invalid_id = invalid_resp.json()["id"]

    bulk_enable = client.patch("/api/v1/restaurants/kill-switch/all", json={"enabled": True})
    assert bulk_enable.status_code == 200
    body = bulk_enable.json()
    assert body["enabled"] is True
    assert body["targeted_count"] == 2
    assert body["eligible_count"] == 1
    assert body["updated_count"] == 1
    assert body["skipped_count"] == 1
    assert body["skipped"][0]["restaurant_id"] == invalid_id
    assert "forward_escalations_disabled" in body["skipped"][0]["kill_switch_blockers"]

    ready = client.get(f"/api/v1/restaurants/{ready_id}")
    invalid = client.get(f"/api/v1/restaurants/{invalid_id}")
    assert ready.json()["kill_switch_enabled"] is True
    assert invalid.json()["kill_switch_enabled"] is False


def test_admin_update_rejects_invalid_forwarding_when_kill_switch_enabled(client_with_overrides):
    client = client_with_overrides
    created = client.post(
        "/api/v1/restaurants/",
        json={
            "name": "Kill Switch Drift Guard",
            "forward_escalations": True,
            "escalation_phone_number": "+15550003333",
        },
    )
    rid = created.json()["id"]
    enable = client.patch(f"/api/v1/restaurants/{rid}/kill-switch", json={"enabled": True})
    assert enable.status_code == 200

    bad_update = client.put(f"/api/v1/restaurants/{rid}", json={"forward_escalations": False})
    assert bad_update.status_code == 400
    detail = bad_update.json()["detail"]
    assert "kill switch is enabled" in detail["message"].lower()
    assert "forward_escalations_disabled" in detail["kill_switch_blockers"]


def test_admin_kill_switch_toggle_emits_event_on_state_change(client_with_overrides, monkeypatch):
    client = client_with_overrides
    captured = []

    async def _mock_emit(**kwargs):
        captured.append(kwargs)

    monkeypatch.setattr("app.api.restaurants.emit_kill_switch_toggled", _mock_emit)

    create = client.post(
        "/api/v1/restaurants/",
        json={
            "name": "Emit Toggle",
            "forward_escalations": True,
            "escalation_phone_number": "+15550009991",
        },
    )
    rid = create.json()["id"]

    enable = client.patch(f"/api/v1/restaurants/{rid}/kill-switch", json={"enabled": True})
    assert enable.status_code == 200
    assert len(captured) == 1
    event = captured[0]
    assert event["restaurant_id"] == rid
    assert event["enabled"] is True
    assert event["previous_enabled"] is False
    assert event["actor_type"] == "admin"
    assert event["source"] == "admin_dashboard"

    noop = client.patch(f"/api/v1/restaurants/{rid}/kill-switch", json={"enabled": True})
    assert noop.status_code == 200
    assert len(captured) == 1


def test_admin_bulk_kill_switch_emits_only_for_changed_restaurants(client_with_overrides, monkeypatch):
    client = client_with_overrides
    bulk_events = []
    summaries = []

    async def _mock_bulk(**kwargs):
        bulk_events.append(kwargs)

    async def _mock_summary(**kwargs):
        summaries.append(kwargs)

    monkeypatch.setattr("app.api.restaurants.emit_kill_switch_toggled_bulk_for_restaurants", _mock_bulk)
    monkeypatch.setattr("app.api.restaurants.emit_kill_switch_bulk_summary", _mock_summary)

    first = client.post(
        "/api/v1/restaurants/",
        json={
            "name": "Bulk Emit A",
            "forward_escalations": True,
            "escalation_phone_number": "+15550009992",
        },
    )
    second = client.post(
        "/api/v1/restaurants/",
        json={
            "name": "Bulk Emit B",
            "forward_escalations": True,
            "escalation_phone_number": "+15550009993",
        },
    )
    first_id = first.json()["id"]
    second_id = second.json()["id"]

    pre_enable = client.patch(f"/api/v1/restaurants/{first_id}/kill-switch", json={"enabled": True})
    assert pre_enable.status_code == 200
    bulk_events.clear()

    bulk_enable = client.patch("/api/v1/restaurants/kill-switch/all", json={"enabled": True})
    assert bulk_enable.status_code == 200
    assert bulk_enable.json()["updated_count"] == 1
    assert len(bulk_events) == 1
    assert bulk_events[0]["enabled"] is True
    assert bulk_events[0]["include_admin_sse"] is False
    assert len(bulk_events[0]["changed_restaurants"]) == 1
    assert bulk_events[0]["changed_restaurants"][0]["restaurant_id"] == second_id
    assert bulk_events[0]["changed_restaurants"][0]["previous_enabled"] is False
    assert len(summaries) == 1
    assert summaries[0]["enabled"] is True
    assert summaries[0]["updated_count"] == 1


def test_admin_bulk_kill_switch_emits_summary_even_when_no_updates(client_with_overrides, monkeypatch):
    client = client_with_overrides
    summaries = []
    bulk_events = []

    async def _mock_summary(**kwargs):
        summaries.append(kwargs)

    async def _mock_bulk(**kwargs):
        bulk_events.append(kwargs)

    monkeypatch.setattr("app.api.restaurants.emit_kill_switch_bulk_summary", _mock_summary)
    monkeypatch.setattr("app.api.restaurants.emit_kill_switch_toggled_bulk_for_restaurants", _mock_bulk)

    client.post("/api/v1/restaurants/", json={"name": "Invalid A"})
    client.post("/api/v1/restaurants/", json={"name": "Invalid B"})

    bulk_enable = client.patch("/api/v1/restaurants/kill-switch/all", json={"enabled": True})
    assert bulk_enable.status_code == 200
    assert bulk_enable.json()["updated_count"] == 0
    assert bulk_events == []
    assert len(summaries) == 1
    assert summaries[0]["enabled"] is True
    assert summaries[0]["updated_count"] == 0
