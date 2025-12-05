import pytest
from fastapi import HTTPException

from app.services.faq_service import FAQService
from tests.fake_repos import InMemoryFAQRepository, InMemoryRestaurantRepository


def _build_service() -> tuple[FAQService, InMemoryFAQRepository, InMemoryRestaurantRepository]:
    faq_repo = InMemoryFAQRepository()
    restaurant_repo = InMemoryRestaurantRepository(faq_repo)
    restaurant_repo.add(1, "Pasta Place")
    restaurant_repo.add(2, "Burger Barn")
    service = FAQService(faq_repo=faq_repo, restaurant_repo=restaurant_repo)
    return service, faq_repo, restaurant_repo


def test_create_and_get_faq_includes_restaurant_name():
    service, _, _ = _build_service()
    created = service.create_faq(1, {"question": "What are your hours?", "answer": "We are open daily."})
    fetched = service.get_faq(created["id"])
    assert fetched["question"] == "What are your hours?"
    assert fetched["restaurant_name"] == "Pasta Place"


def test_update_faq_changes_content():
    service, _, _ = _build_service()
    created = service.create_faq(1, {"question": "Do you deliver?", "answer": "Yes"})
    updated = service.update_faq(created["id"], {"answer": "Yes, within 5 miles."})
    assert updated["answer"] == "Yes, within 5 miles."


def test_bulk_create_rollback_on_error():
    service, faq_repo, _ = _build_service()
    with pytest.raises(HTTPException) as exc_info:
        service.bulk_create_faqs(1, [{"question": "Q1", "answer": ""}])
    assert exc_info.value.status_code == 400
    assert faq_repo.get_by_restaurant(1) == []


def test_search_all_faqs_uses_fulltext_like_matching():
    service, _, _ = _build_service()
    service.create_faq(1, {"question": "How to order pizza?", "answer": "Use the app"})
    service.create_faq(2, {"question": "Do you serve burgers?", "answer": "Yes, all day"})

    result = service.search_all("pizza", page=1, limit=10)
    assert result["pagination"]["total"] == 1
    assert result["items"][0]["restaurant_id"] == 1
    assert result["items"][0]["restaurant_name"] == "Pasta Place"


def test_cascade_delete_removes_faqs_for_restaurant():
    service, faq_repo, restaurant_repo = _build_service()
    service.create_faq(1, {"question": "Any vegan options?", "answer": "Yes"})
    assert len(faq_repo.get_by_restaurant(1)) == 1

    restaurant_repo.delete(1)
    assert faq_repo.get_by_restaurant(1) == []


def test_list_faqs_paginated_with_search():
    service, _, _ = _build_service()
    service.create_faq(1, {"question": "Do you have pasta?", "answer": "Yes"})
    service.create_faq(1, {"question": "Do you have burgers?", "answer": "No"})

    result = service.list_faqs_paginated(1, page=1, limit=1, search="pasta")
    assert result["pagination"]["total"] == 1
    assert len(result["items"]) == 1
