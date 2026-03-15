import os
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from mysql.connector.errors import IntegrityError

os.environ.setdefault("ALLOW_DB_FAILURE", "true")
os.environ.setdefault("USE_MOCK_DATA", "true")

from app.api.client_menus import get_menu_service  # noqa: E402
from app.main import app  # noqa: E402
from app.middleware.auth_middleware import get_current_restaurant_user  # noqa: E402
from app.services.menu_service import MenuService  # noqa: E402
from tests.fake_repos import InMemoryMenuRepository, InMemoryRestaurantRepository  # noqa: E402


def _claims(restaurant_id: int, role: str = "manager") -> dict:
    return {"user_type": "restaurant", "restaurant_id": restaurant_id, "role": role, "sub": f"user-{restaurant_id}"}


@pytest.fixture
def client_with_overrides():
    restaurant_repo = InMemoryRestaurantRepository()
    restaurant_repo.add(1, "Pasta Place")
    restaurant_repo.add(2, "Burger Barn")
    menu_repo = InMemoryMenuRepository(restaurant_repo=restaurant_repo)
    service = MenuService(menu_repo=menu_repo, restaurant_repo=restaurant_repo)

    def set_claims(restaurant_id: int = 1, role: str = "manager"):
        app.dependency_overrides[get_current_restaurant_user] = lambda: _claims(restaurant_id, role)

    app.dependency_overrides[get_menu_service] = lambda: service
    set_claims()
    client = TestClient(app)
    yield client, menu_repo, set_claims
    app.dependency_overrides = {}


def test_client_menu_crud_scoped(client_with_overrides):
    client, _, _ = client_with_overrides
    create_resp = client.post(
        "/api/v1/client/menu",
        json={"item_name": "Margherita", "price": 10.5, "category": "Pizza", "sub_category": "Classic"},
    )
    assert create_resp.status_code == 201, create_resp.text
    menu_id = create_resp.json()["id"]

    list_resp = client.get("/api/v1/client/menu")
    assert list_resp.status_code == 200
    assert list_resp.json()["pagination"]["total"] == 1

    get_resp = client.get(f"/api/v1/client/menu/{menu_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["item_name"] == "Margherita"

    update_resp = client.put(f"/api/v1/client/menu/{menu_id}", json={"price": 12.0})
    assert update_resp.status_code == 200
    assert float(update_resp.json()["price"]) == 12.0


def test_client_menu_cross_restaurant_forbidden(client_with_overrides):
    client, _, set_claims = client_with_overrides
    create_resp = client.post("/api/v1/client/menu", json={"item_name": "Soup", "price": 5.0})
    menu_id = create_resp.json()["id"]

    set_claims(restaurant_id=2)
    forbidden = client.get(f"/api/v1/client/menu/{menu_id}")
    assert forbidden.status_code == 404

    toggle = client.patch(f"/api/v1/client/menu/{menu_id}/availability", json={"is_available": False})
    assert toggle.status_code == 404


def test_client_menu_bulk_availability(client_with_overrides):
    client, _, _ = client_with_overrides
    first = client.post("/api/v1/client/menu", json={"item_name": "Tea", "price": 3.0})
    second = client.post("/api/v1/client/menu", json={"item_name": "Coffee", "price": 4.0})
    ids = [first.json()["id"], second.json()["id"]]

    bulk_resp = client.patch(
        "/api/v1/client/menu/bulk-availability", json={"menu_item_ids": ids, "is_available": False}
    )
    assert bulk_resp.status_code == 200
    assert bulk_resp.json()["updated_count"] == 2

    list_resp = client.get("/api/v1/client/menu", params={"is_available": False})
    assert list_resp.status_code == 200
    assert list_resp.json()["pagination"]["total"] == 2


def test_client_menu_delete_fk_conflict_returns_409(client_with_overrides):
    """DELETE returns 409 when the menu item is referenced by existing orders (FK constraint)."""
    client, menu_repo, _ = client_with_overrides
    create_resp = client.post(
        "/api/v1/client/menu",
        json={"item_name": "Burger", "price": 14.0, "category": "Mains"},
    )
    assert create_resp.status_code == 201
    menu_id = create_resp.json()["id"]

    with patch.object(menu_repo, "delete_by_id", side_effect=IntegrityError(msg="Cannot delete", errno=1451)):
        del_resp = client.delete(f"/api/v1/client/menu/{menu_id}")

    assert del_resp.status_code == 409
    assert "referenced by existing orders" in del_resp.json()["detail"]
