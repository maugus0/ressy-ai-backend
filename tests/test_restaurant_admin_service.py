import pytest
from fastapi import HTTPException

from app.services.restaurant_admin_service import RestaurantAdministratorService
from tests.fake_repos import InMemoryRestaurantAdminRepository, InMemoryRestaurantRepository


def _build_service():
    restaurant_repo = InMemoryRestaurantRepository()
    restaurant_repo.add(1, "Pasta Place")
    restaurant_repo.add(2, "Burger Barn")
    admin_repo = InMemoryRestaurantAdminRepository(restaurant_repo)
    admin_repo.add_role(1, "manager", ["/dash", "/orders"])
    admin_repo.add_role(2, "staff", ["/orders:view"])
    RestaurantAdministratorService._password_reset_buckets.clear()
    service = RestaurantAdministratorService(admin_repo=admin_repo, restaurant_repo=restaurant_repo)
    return service, admin_repo, restaurant_repo


def test_create_and_get_user_includes_role_and_permissions():
    service, repo, _ = _build_service()
    created = service.create_client_user(1, "manager@test.com", "StrongPass1", 1)
    assert created["role"] == "manager"
    assert created["permissions"] == ["/dash", "/orders"]

    fetched = service.get_client_user(1, created["uuid"])
    assert fetched["restaurant_name"] == "Pasta Place"
    assert fetched["email"] == "manager@test.com"


def test_duplicate_email_rejected_per_restaurant():
    service, repo, _ = _build_service()
    service.create_client_user(1, "manager@test.com", "StrongPass1", 1)
    with pytest.raises(HTTPException) as exc_info:
        service.create_client_user(1, "manager@test.com", "StrongPass1", 1)
    assert exc_info.value.status_code == 400
    assert repo.count_client_users_by_restaurant(1) == 1


def test_update_email_and_role():
    service, _, _ = _build_service()
    created = service.create_client_user(1, "a@test.com", "StrongPass1", 1)
    updated = service.update_client_user(1, created["uuid"], {"email": "b@test.com", "role_id": 2})
    assert updated["email"] == "b@test.com"
    assert updated["role_id"] == 2


def test_delete_prevents_last_user():
    service, _, _ = _build_service()
    created = service.create_client_user(1, "only@test.com", "StrongPass1", 1)
    with pytest.raises(HTTPException) as exc_info:
        service.delete_client_user(1, created["uuid"])
    assert exc_info.value.status_code == 400

    # Add another admin and delete one should succeed
    service.create_client_user(1, "second@test.com", "StrongPass1", 1)
    resp = service.delete_client_user(1, created["uuid"])
    assert resp["message"] == "User deleted"


def test_reset_password_applies_rate_limit_and_revokes_sessions():
    service, repo, _ = _build_service()
    created = service.create_client_user(1, "reset@test.com", "StrongPass1", 1)

    resp = service.reset_client_user_password(1, created["uuid"], "NewStrong2")
    assert resp["message"] == "Password reset successful"
    assert created["uuid"] in repo.revoked_sessions

    with pytest.raises(HTTPException) as exc_info:
        for _ in range(service.PASSWORD_RESET_MAX_ATTEMPTS):
            service.reset_client_user_password(1, created["uuid"], "AnotherPass3")
    assert exc_info.value.status_code == 429


def test_bulk_create_validates_and_rolls_back_on_error():
    service, repo, _ = _build_service()
    with pytest.raises(HTTPException):
        service.bulk_create_client_users(
            1,
            [
                {"email": "dup@test.com", "password": "StrongPass1", "role_id": 1},
                {"email": "dup@test.com", "password": "StrongPass1", "role_id": 1},
            ],
        )
    assert repo.count_client_users_by_restaurant(1) == 0

    created = service.bulk_create_client_users(
        1,
        [
            {"email": "a@test.com", "password": "StrongPass1", "role_id": 1},
            {"email": "b@test.com", "password": "StrongPass1", "role_id": 2},
        ],
    )
    assert len(created) == 2


def test_list_by_restaurant_filters_by_role():
    service, _, _ = _build_service()
    service.create_client_user(1, "a@test.com", "StrongPass1", 1)
    service.create_client_user(1, "b@test.com", "StrongPass1", 2)

    result = service.list_client_users_for_restaurant(1, page=1, limit=10, role_id=2)
    assert result["pagination"]["total"] == 1
    assert result["items"][0]["role_id"] == 2


def test_cascade_delete_restaurant_blocks_list():
    service, restaurant_admin_repo, restaurant_repo = _build_service()
    service.create_client_user(1, "c@test.com", "StrongPass1", 1)
    restaurant_repo.delete(1)
    with pytest.raises(HTTPException) as exc_info:
        service.list_client_users_for_restaurant(1, page=1, limit=10, role_id=None)
    assert exc_info.value.status_code == 404
