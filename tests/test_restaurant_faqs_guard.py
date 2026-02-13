"""
API tests for faqs_enabled guard: FAQ Agent Capability cannot be disabled.

Business rule: faqs_enabled must always be true. Both admin and client
restaurant update endpoints reject requests that set faqs_enabled=false.
"""

import os

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("ALLOW_DB_FAILURE", "true")
os.environ.setdefault("USE_MOCK_DATA", "true")

from app.api.restaurants import get_restaurant_service  # noqa: E402
from app.main import app  # noqa: E402
from app.middleware.auth_middleware import get_current_admin_user, get_current_restaurant_user  # noqa: E402
from app.services.restaurant_service import RestaurantService  # noqa: E402
from tests.fake_repos import InMemoryRestaurantFeaturesRepository, InMemoryRestaurantRepository  # noqa: E402

FAQ_DISABLED_MESSAGE = "FAQ Agent Capability cannot be disabled."


def _client_claims(restaurant_id: int) -> dict:
    return {
        "user_type": "restaurant",
        "restaurant_id": restaurant_id,
        "role": "manager",
        "sub": f"user-{restaurant_id}",
    }


@pytest.fixture
def admin_client():
    """Test client with admin auth and in-memory restaurant service."""
    restaurant_repo = InMemoryRestaurantRepository()
    restaurant_repo.add(1, "Test Restaurant")
    features_repo = InMemoryRestaurantFeaturesRepository()
    features_repo.create_defaults(1)
    service = RestaurantService(restaurant_repo=restaurant_repo, features_repo=features_repo)
    app.dependency_overrides[get_restaurant_service] = lambda: service
    app.dependency_overrides[get_current_admin_user] = lambda: {"user_type": "admin"}
    client = TestClient(app)
    yield client
    app.dependency_overrides = {}


@pytest.fixture
def client_restaurant_client():
    """Test client with client (restaurant) auth and in-memory restaurant service."""
    restaurant_repo = InMemoryRestaurantRepository()
    restaurant_repo.add(1, "Pasta Place")
    features_repo = InMemoryRestaurantFeaturesRepository()
    features_repo.create_defaults(1)
    service = RestaurantService(restaurant_repo=restaurant_repo, features_repo=features_repo)
    app.dependency_overrides[get_restaurant_service] = lambda: service
    app.dependency_overrides[get_current_restaurant_user] = lambda: _client_claims(1)
    client = TestClient(app)
    yield client
    app.dependency_overrides = {}


def test_admin_cannot_disable_faqs(admin_client):
    """Admin PUT with faqs_enabled=false returns 400 and exact error message; restaurant is not updated."""
    client = admin_client
    resp = client.put(
        "/api/v1/restaurants/1",
        json={"features": {"faqs_enabled": False}},
    )
    assert resp.status_code == 400
    data = resp.json()
    assert data.get("detail") == FAQ_DISABLED_MESSAGE
    # Restaurant features should be unchanged (still true)
    get_resp = client.get("/api/v1/restaurants/1")
    assert get_resp.status_code == 200
    assert get_resp.json().get("features", {}).get("faqs_enabled") is True


def test_admin_cannot_disable_faqs_with_other_flags(admin_client):
    """Admin PUT with multiple feature flags including faqs_enabled=false returns 400."""
    client = admin_client
    resp = client.put(
        "/api/v1/restaurants/1",
        json={
            "features": {
                "orders_enabled": True,
                "reservations_enabled": False,
                "faqs_enabled": False,
            },
        },
    )
    assert resp.status_code == 400
    assert resp.json().get("detail") == FAQ_DISABLED_MESSAGE


def test_client_cannot_disable_faqs(client_restaurant_client):
    """Client PUT with faqs_enabled=false returns 400 and exact error message; restaurant is not updated."""
    client = client_restaurant_client
    resp = client.put(
        "/api/v1/client/restaurant",
        json={"features": {"faqs_enabled": False}},
    )
    assert resp.status_code == 400
    data = resp.json()
    assert data.get("detail") == FAQ_DISABLED_MESSAGE
    get_resp = client.get("/api/v1/client/restaurant")
    assert get_resp.status_code == 200
    assert get_resp.json().get("features", {}).get("faqs_enabled") is True


def test_update_allowed_when_faqs_true(admin_client, client_restaurant_client):
    """PUT with faqs_enabled=true is allowed (200) on both admin and client routes."""
    admin = admin_client
    resp_admin = admin.put(
        "/api/v1/restaurants/1",
        json={"features": {"faqs_enabled": True}},
    )
    assert resp_admin.status_code == 200
    assert resp_admin.json().get("features", {}).get("faqs_enabled") is True

    client = client_restaurant_client
    resp_client = client.put(
        "/api/v1/client/restaurant",
        json={"features": {"faqs_enabled": True, "orders_enabled": False}},
    )
    assert resp_client.status_code == 200
    assert resp_client.json().get("features", {}).get("faqs_enabled") is True


def test_update_allowed_when_features_omitted(admin_client, client_restaurant_client):
    """PUT without features key is allowed (200); existing faqs_enabled unchanged."""
    admin = admin_client
    resp_admin = admin.put(
        "/api/v1/restaurants/1",
        json={"name": "Updated Name Only"},
    )
    assert resp_admin.status_code == 200
    assert resp_admin.json().get("features", {}).get("faqs_enabled") is True

    client = client_restaurant_client
    resp_client = client.put(
        "/api/v1/client/restaurant",
        json={"forward_minutes": 20},
    )
    assert resp_client.status_code == 200
    assert resp_client.json().get("features", {}).get("faqs_enabled") is True


def test_update_allowed_when_faqs_omitted_in_features(admin_client):
    """PUT with features but faqs_enabled omitted (other flags only) is allowed."""
    client = admin_client
    resp = client.put(
        "/api/v1/restaurants/1",
        json={"features": {"orders_enabled": False, "reservations_enabled": True}},
    )
    assert resp.status_code == 200
    assert resp.json().get("features", {}).get("faqs_enabled") is True
