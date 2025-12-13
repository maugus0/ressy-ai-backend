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
from tests.fake_repos import InMemoryRestaurantRepository  # noqa: E402


@pytest.fixture
def client_with_overrides():
    restaurant_repo = InMemoryRestaurantRepository()
    service = RestaurantService(restaurant_repo=restaurant_repo)
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
            "opening_time": "10:00:00",
            "closing_time": "23:30:00",
            "forward_minutes": 30,
        },
    )
    assert resp.status_code == 201, resp.text
    created = resp.json()
    assert created["opening_time"] == "10:00:00"
    assert created["closing_time"] == "23:30:00"

    get_resp = client.get(f"/api/v1/restaurants/{created['id']}")
    assert get_resp.status_code == 200
    assert get_resp.json()["name"] == "Evening Eats"


def test_list_includes_default_hours(client_with_overrides):
    client = client_with_overrides
    client.post("/api/v1/restaurants/", json={"name": "Default Hours"})

    list_resp = client.get("/api/v1/restaurants/")
    assert list_resp.status_code == 200
    body = list_resp.json()
    assert body["items"][0]["opening_time"] == "09:00:00"
    assert body["items"][0]["closing_time"] == "22:00:00"


def test_update_restaurant_hours(client_with_overrides):
    client = client_with_overrides
    create_resp = client.post("/api/v1/restaurants/", json={"name": "Update Hours"})
    rid = create_resp.json()["id"]

    update_resp = client.put(
        f"/api/v1/restaurants/{rid}", json={"opening_time": "08:00:00", "closing_time": "20:00:00"}
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["opening_time"] == "08:00:00"
    assert update_resp.json()["closing_time"] == "20:00:00"


def test_invalid_hours_rejected(client_with_overrides):
    client = client_with_overrides
    resp = client.post("/api/v1/restaurants/", json={"name": "Bad", "opening_time": "25:00:00"})
    assert resp.status_code == 400


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
