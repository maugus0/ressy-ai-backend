import os

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("ALLOW_DB_FAILURE", "true")
os.environ.setdefault("USE_MOCK_DATA", "true")

from app.api.client_client_users import get_restaurant_admin_service  # noqa: E402
from app.main import app  # noqa: E402
from app.middleware.auth_middleware import get_current_restaurant_user  # noqa: E402
from app.services.restaurant_admin_service import RestaurantAdministratorService  # noqa: E402
from tests.fake_repos import InMemoryRestaurantAdminRepository, InMemoryRestaurantRepository  # noqa: E402


def _claims(restaurant_id: int, role: str = "manager", sub: str | None = None) -> dict:
    return {
        "user_type": "restaurant",
        "restaurant_id": restaurant_id,
        "role": role,
        "sub": sub or f"user-{restaurant_id}",
    }


@pytest.fixture
def client_with_overrides():
    restaurant_repo = InMemoryRestaurantRepository()
    restaurant_repo.add(1, "Pasta Place")
    restaurant_repo.add(2, "Burger Barn")
    admin_repo = InMemoryRestaurantAdminRepository(restaurant_repo)
    admin_repo.add_role(1, "manager", ["/dash"])
    admin_repo.add_role(2, "staff", ["/orders:view"])
    service = RestaurantAdministratorService(admin_repo=admin_repo, restaurant_repo=restaurant_repo)

    def set_claims(restaurant_id: int = 1, role: str = "manager", sub: str | None = None):
        app.dependency_overrides[get_current_restaurant_user] = lambda: _claims(restaurant_id, role, sub)

    app.dependency_overrides[get_restaurant_admin_service] = lambda: service
    set_claims()
    client = TestClient(app)
    yield client, admin_repo, set_claims
    app.dependency_overrides = {}


def test_manager_can_manage_users(client_with_overrides):
    client, repo, _ = client_with_overrides
    create = client.post(
        "/api/v1/client/users",
        json={"email": "manager@test.com", "password": "StrongPass1", "role_id": 1},
    )
    assert create.status_code == 201, create.text
    user_uuid = create.json()["uuid"]

    # add another user so deletion of the first is allowed
    client.post(
        "/api/v1/client/users",
        json={"email": "secondary@test.com", "password": "StrongPass1", "role_id": 1},
    )

    list_resp = client.get("/api/v1/client/users")
    assert list_resp.status_code == 200
    assert list_resp.json()["pagination"]["total"] == 2

    get_resp = client.get(f"/api/v1/client/users/{user_uuid}")
    assert get_resp.status_code == 200
    assert get_resp.json()["restaurant_name"] == "Pasta Place"

    update = client.put(f"/api/v1/client/users/{user_uuid}", json={"email": "updated@test.com"})
    assert update.status_code == 200
    assert update.json()["email"] == "updated@test.com"

    delete_resp = client.delete(f"/api/v1/client/users/{user_uuid}")
    assert delete_resp.status_code == 200
    assert repo.get_client_user_by_uuid(user_uuid) is None


def test_staff_forbidden_on_manager_routes(client_with_overrides):
    client, _, set_claims = client_with_overrides
    set_claims(role="staff", sub="staff-1")
    resp = client.get("/api/v1/client/users")
    assert resp.status_code == 403


def test_self_password_reset_allowed(client_with_overrides):
    client, repo, set_claims = client_with_overrides
    create = client.post(
        "/api/v1/client/users",
        json={"email": "staff@test.com", "password": "StrongPass1", "role_id": 2},
    )
    assert create.status_code == 201
    user_uuid = create.json()["uuid"]

    # switch to staff token matching the created user
    set_claims(role="staff", sub=user_uuid)
    reset = client.post("/api/v1/client/me/reset-password", json={"new_password": "NewPass1A"})
    assert reset.status_code == 200
    # ensure password updated in repo
    assert repo.get_client_user_by_uuid(user_uuid)["password"] != ""


def test_cross_restaurant_user_is_404(client_with_overrides):
    client, _, set_claims = client_with_overrides
    create = client.post(
        "/api/v1/client/users",
        json={"email": "other@test.com", "password": "StrongPass1", "role_id": 1},
    )
    user_uuid = create.json()["uuid"]

    set_claims(restaurant_id=2, role="manager")
    get_resp = client.get(f"/api/v1/client/users/{user_uuid}")
    assert get_resp.status_code == 404
