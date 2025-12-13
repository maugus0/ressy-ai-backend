import pytest
from fastapi import HTTPException

from app.services.restaurant_service import RestaurantService
from tests.fake_repos import InMemoryRestaurantRepository


def _build_service():
    repo = InMemoryRestaurantRepository()
    service = RestaurantService(restaurant_repo=repo)
    return service, repo


def test_create_restaurant_with_defaults():
    service, _ = _build_service()
    restaurant = service.create_restaurant({"name": "Pasta Place"})
    assert restaurant["name"] == "Pasta Place"
    assert restaurant["opening_time"] == "09:00:00"
    assert restaurant["closing_time"] == "22:00:00"


def test_create_restaurant_with_custom_hours():
    service, _ = _build_service()
    restaurant = service.create_restaurant(
        {"name": "Late Night", "opening_time": "10:30:00", "closing_time": "23:45:00"}
    )
    assert restaurant["opening_time"] == "10:30:00"
    assert restaurant["closing_time"] == "23:45:00"


def test_create_restaurant_invalid_time_rejected():
    service, _ = _build_service()
    with pytest.raises(HTTPException):
        service.create_restaurant({"name": "Bad Time", "opening_time": "25:00:00"})


def test_update_restaurant_times():
    service, repo = _build_service()
    rid = repo.create({"name": "Update Me"})
    updated = service.update_restaurant(rid, {"opening_time": "08:00:00", "closing_time": "21:00:00"})
    assert updated["opening_time"] == "08:00:00"
    assert updated["closing_time"] == "21:00:00"


def test_duplicate_name_rejected():
    service, _ = _build_service()
    service.create_restaurant({"name": "Unique"})
    with pytest.raises(HTTPException):
        service.create_restaurant({"name": "Unique"})


def test_duplicate_twilio_rejected():
    service, _ = _build_service()
    service.create_restaurant({"name": "First", "twilio_phone_number": "+1000"})
    with pytest.raises(HTTPException):
        service.create_restaurant({"name": "Second", "twilio_phone_number": "+1000"})


def test_update_duplicate_name_rejected():
    service, repo = _build_service()
    service.create_restaurant({"name": "First"})["id"]
    second_id = service.create_restaurant({"name": "Second"})["id"]
    with pytest.raises(HTTPException):
        service.update_restaurant(second_id, {"name": "First"})
