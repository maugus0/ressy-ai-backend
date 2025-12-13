import os

import pytest
from fastapi.testclient import TestClient

# Allow app import without a live MySQL instance
os.environ.setdefault("ALLOW_DB_FAILURE", "true")
os.environ.setdefault("USE_MOCK_DATA", "true")

from app.api.client_faqs import get_faq_service  # noqa: E402
from app.main import app  # noqa: E402
from app.middleware.auth_middleware import get_current_restaurant_user  # noqa: E402
from app.services.faq_service import FAQService  # noqa: E402
from tests.fake_repos import InMemoryFAQRepository, InMemoryRestaurantRepository  # noqa: E402


def _make_claims(restaurant_id: int, role: str = "manager") -> dict:
    return {"user_type": "restaurant", "restaurant_id": restaurant_id, "role": role, "sub": f"user-{restaurant_id}"}


@pytest.fixture
def client_with_overrides():
    faq_repo = InMemoryFAQRepository()
    restaurant_repo = InMemoryRestaurantRepository(faq_repo)
    restaurant_repo.add(1, "Pasta Place")
    restaurant_repo.add(2, "Burger Barn")
    service = FAQService(faq_repo=faq_repo, restaurant_repo=restaurant_repo)

    def set_claims(restaurant_id: int = 1, role: str = "manager"):
        app.dependency_overrides[get_current_restaurant_user] = lambda: _make_claims(restaurant_id, role)

    app.dependency_overrides[get_faq_service] = lambda: service
    set_claims()
    client = TestClient(app)
    yield client, faq_repo, set_claims
    app.dependency_overrides = {}


def test_create_list_get_faq_client(client_with_overrides):
    client, _, _ = client_with_overrides
    resp = client.post("/api/v1/client/faqs", json={"question": "Hours?", "answer": "9-5"})
    assert resp.status_code == 201, resp.text
    faq_id = resp.json()["id"]

    list_resp = client.get("/api/v1/client/faqs")
    assert list_resp.status_code == 200
    assert list_resp.json()["pagination"]["total"] == 1

    get_resp = client.get(f"/api/v1/client/faqs/{faq_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["question"] == "Hours?"


def test_client_faq_scoped_to_restaurant(client_with_overrides):
    client, _, set_claims = client_with_overrides
    create = client.post("/api/v1/client/faqs", json={"question": "Q1", "answer": "A1"})
    faq_id = create.json()["id"]

    # Switch to another restaurant; should not see FAQ
    set_claims(restaurant_id=2)
    forbidden = client.get(f"/api/v1/client/faqs/{faq_id}")
    assert forbidden.status_code == 404

    update = client.put(f"/api/v1/client/faqs/{faq_id}", json={"answer": "Nope"})
    assert update.status_code == 404


def test_bulk_create_client_faqs(client_with_overrides):
    client, _, _ = client_with_overrides
    resp = client.post(
        "/api/v1/client/faqs/bulk",
        json={"faqs": [{"question": "Q1", "answer": "A1"}, {"question": "Q2", "answer": "A2"}]},
    )
    assert resp.status_code == 201, resp.text
    assert len(resp.json()["items"]) == 2
