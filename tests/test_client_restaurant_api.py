import os

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("ALLOW_DB_FAILURE", "true")
os.environ.setdefault("USE_MOCK_DATA", "true")

from app.api.restaurants import get_restaurant_service  # noqa: E402
from app.main import app  # noqa: E402
from app.middleware.auth_middleware import get_current_restaurant_user  # noqa: E402
from app.services.restaurant_service import RestaurantService  # noqa: E402
from tests.fake_repos import InMemoryRestaurantRepository  # noqa: E402


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
    service = RestaurantService(restaurant_repo=restaurant_repo)
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
