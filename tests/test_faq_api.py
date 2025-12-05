import os

import pytest
from fastapi.testclient import TestClient

# Allow app import without a live MySQL instance
os.environ.setdefault("ALLOW_DB_FAILURE", "true")
os.environ.setdefault("USE_MOCK_DATA", "true")

from app.api.faqs import get_faq_service  # noqa: E402
from app.main import app  # noqa: E402
from app.middleware.auth_middleware import get_current_admin_user  # noqa: E402
from app.services.faq_service import FAQService  # noqa: E402
from tests.fake_repos import InMemoryFAQRepository, InMemoryRestaurantRepository  # noqa: E402


@pytest.fixture
def client_with_overrides():
    faq_repo = InMemoryFAQRepository()
    restaurant_repo = InMemoryRestaurantRepository(faq_repo)
    restaurant_repo.add(1, "Pasta Place")
    restaurant_repo.add(2, "Burger Barn")
    service = FAQService(faq_repo=faq_repo, restaurant_repo=restaurant_repo)

    app.dependency_overrides[get_faq_service] = lambda: service
    app.dependency_overrides[get_current_admin_user] = lambda: {"user_type": "admin"}
    client = TestClient(app)
    yield client, faq_repo
    app.dependency_overrides = {}


def test_create_and_retrieve_faq(client_with_overrides):
    client, _ = client_with_overrides
    resp = client.post(
        "/api/v1/admin/restaurants/1/faqs",
        json={"question": "What are your hours?", "answer": "We are open 9-5"},
    )
    assert resp.status_code == 201, resp.text
    faq_id = resp.json()["id"]

    get_resp = client.get(f"/api/v1/admin/faqs/{faq_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["restaurant_name"] == "Pasta Place"


def test_list_faqs_with_pagination_and_search(client_with_overrides):
    client, _ = client_with_overrides
    client.post("/api/v1/admin/restaurants/1/faqs", json={"question": "Do you have pasta?", "answer": "Yes"})
    client.post("/api/v1/admin/restaurants/1/faqs", json={"question": "Do you have burgers?", "answer": "No"})

    resp = client.get("/api/v1/admin/restaurants/1/faqs", params={"page": 1, "limit": 1, "search": "pasta"})
    body = resp.json()
    assert body["pagination"]["total"] == 1
    assert len(body["items"]) == 1


def test_update_and_delete_faq(client_with_overrides):
    client, faq_repo = client_with_overrides
    resp = client.post("/api/v1/admin/restaurants/1/faqs", json={"question": "Do you deliver?", "answer": "Yes"})
    faq_id = resp.json()["id"]

    update_resp = client.put(f"/api/v1/admin/faqs/{faq_id}", json={"answer": "Yes, within 3 miles"})
    assert update_resp.status_code == 200
    assert update_resp.json()["answer"] == "Yes, within 3 miles"

    delete_resp = client.delete(f"/api/v1/admin/faqs/{faq_id}")
    assert delete_resp.status_code == 200
    assert delete_resp.json()["message"] == "FAQ deleted"
    assert faq_repo.get_by_id(faq_id) == {}


def test_bulk_create_and_rollback_on_validation(client_with_overrides):
    client, faq_repo = client_with_overrides
    bad_resp = client.post("/api/v1/admin/restaurants/1/faqs/bulk", json={"faqs": [{"question": "Q1", "answer": ""}]})
    assert bad_resp.status_code == 400
    assert faq_repo.get_by_restaurant(1) == []

    ok_resp = client.post(
        "/api/v1/admin/restaurants/1/faqs/bulk",
        json={"faqs": [{"question": "Q1", "answer": "A1"}, {"question": "Q2", "answer": "A2"}]},
    )
    assert ok_resp.status_code == 201
    assert len(ok_resp.json()["items"]) == 2


def test_search_across_restaurants(client_with_overrides):
    client, _ = client_with_overrides
    client.post("/api/v1/admin/restaurants/1/faqs", json={"question": "How to order pizza?", "answer": "Online"})
    client.post("/api/v1/admin/restaurants/2/faqs", json={"question": "Is burger available?", "answer": "Yes"})

    resp = client.get("/api/v1/admin/faqs/search", params={"q": "pizza"})
    assert resp.status_code == 200
    assert resp.json()["pagination"]["total"] == 1
    assert resp.json()["items"][0]["restaurant_name"] == "Pasta Place"


def test_missing_restaurant_returns_404(client_with_overrides):
    client, _ = client_with_overrides
    resp = client.post("/api/v1/admin/restaurants/999/faqs", json={"question": "Q", "answer": "A"})
    assert resp.status_code == 404


def test_search_requires_query_param(client_with_overrides):
    client, _ = client_with_overrides
    resp = client.get("/api/v1/admin/faqs/search")
    assert resp.status_code == 400
