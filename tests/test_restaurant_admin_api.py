import os

import pytest
from fastapi.testclient import TestClient

# Ensure DB calls are mocked/ignored for tests
os.environ.setdefault("ALLOW_DB_FAILURE", "true")
os.environ.setdefault("USE_MOCK_DATA", "true")

from app.api.client_users import get_restaurant_admin_service  # noqa: E402
from app.main import app  # noqa: E402
from app.middleware.auth_middleware import get_current_admin_user  # noqa: E402
from app.services.restaurant_admin_service import RestaurantAdministratorService  # noqa: E402
from tests.fake_repos import (  # noqa: E402
    InMemoryRestaurantAdminRepository,
    InMemoryRestaurantRepository,
)


@pytest.fixture
def client_with_overrides():
    restaurant_repo = InMemoryRestaurantRepository()
    restaurant_repo.add(1, "Pasta Place")
    restaurant_repo.add(2, "Burger Barn")
    admin_repo = InMemoryRestaurantAdminRepository(restaurant_repo)
    admin_repo.add_role(1, "manager", ["/dash"])
    admin_repo.add_role(2, "staff", ["/orders:view"])
    service = RestaurantAdministratorService(admin_repo=admin_repo, restaurant_repo=restaurant_repo)

    app.dependency_overrides[get_restaurant_admin_service] = lambda: service
    app.dependency_overrides[get_current_admin_user] = lambda: {"user_type": "admin"}
    client = TestClient(app)
    yield client, service, admin_repo
    app.dependency_overrides = {}


def test_create_and_get_admin(client_with_overrides):
    client, service, repo = client_with_overrides
    resp = client.post(
        "/api/v1/admin/restaurants/1/client-users",
        json={"email": "manager@test.com", "password": "StrongPass1", "role_id": 1},
    )
    assert resp.status_code == 201, resp.text
    created = resp.json()
    assert created["role"] == "manager"

    get_resp = client.get(f"/api/v1/admin/restaurants/1/client-users/{created['uuid']}")
    assert get_resp.status_code == 200
    assert get_resp.json()["restaurant_name"] == "Pasta Place"


def test_list_and_update_admin(client_with_overrides):
    client, _, _ = client_with_overrides
    client.post(
        "/api/v1/admin/restaurants/1/client-users",
        json={"email": "staff@test.com", "password": "StrongPass1", "role_id": 2},
    )

    list_resp = client.get("/api/v1/admin/restaurants/1/client-users", params={"page": 1, "limit": 10})
    assert list_resp.status_code == 200
    assert list_resp.json()["pagination"]["total"] == 1

    admin_uuid = list_resp.json()["items"][0]["uuid"]
    update_resp = client.put(
        f"/api/v1/admin/restaurants/1/client-users/{admin_uuid}",
        json={"email": "updated@test.com"},
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["email"] == "updated@test.com"


def test_bulk_create_and_filters(client_with_overrides):
    client, _, _ = client_with_overrides
    resp = client.post(
        "/api/v1/admin/restaurants/1/client-users/bulk",
        json={
            "users": [
                {"email": "a@test.com", "password": "StrongPass1", "role_id": 1},
                {"email": "b@test.com", "password": "StrongPass1", "role_id": 2},
            ]
        },
    )
    assert resp.status_code == 201, resp.text
    assert len(resp.json()["items"]) == 2

    list_resp = client.get("/api/v1/admin/restaurants/1/client-users", params={"role_id": 2})
    assert list_resp.status_code == 200
    assert list_resp.json()["pagination"]["total"] == 1


def test_reset_password_endpoint(client_with_overrides):
    client, _, _ = client_with_overrides
    create_resp = client.post(
        "/api/v1/admin/restaurants/1/client-users",
        json={"email": "reset@test.com", "password": "StrongPass1", "role_id": 1},
    )
    admin_uuid = create_resp.json()["uuid"]

    reset_resp = client.post(
        f"/api/v1/admin/restaurants/1/client-users/{admin_uuid}/reset-password",
        json={"new_password": "Another1A"},
    )
    assert reset_resp.status_code == 200
    assert reset_resp.json()["message"] == "Password reset successful"
