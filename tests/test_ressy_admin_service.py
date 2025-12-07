import pytest
from fastapi import HTTPException

from app.services.ressy_admin_service import RessyAdministratorService
from tests.fake_repos import InMemoryRessyAdminRepository


def _build_service():
    repo = InMemoryRessyAdminRepository()
    repo.add_role(1, "superadmin", ["/dash", "/users"])
    repo.add_role(2, "ops", ["/ops:view"])
    RessyAdministratorService._password_reset_buckets.clear()
    service = RessyAdministratorService(admin_repo=repo)
    return service, repo


def test_create_and_get_admin_includes_role_and_permissions():
    service, repo = _build_service()
    created = service.create_admin_user("admin@test.com", "StrongPass1", 1)
    assert created["role"] == "superadmin"
    assert created["permissions"] == ["/dash", "/users"]

    fetched = service.get_admin_user(created["uuid"])
    assert fetched["email"] == "admin@test.com"
    assert fetched["role_id"] == 1


def test_duplicate_email_rejected():
    service, repo = _build_service()
    service.create_admin_user("admin@test.com", "StrongPass1", 1)
    with pytest.raises(HTTPException) as exc_info:
        service.create_admin_user("admin@test.com", "StrongPass1", 1)
    assert exc_info.value.status_code == 400
    assert repo.count_admin_users() == 1


def test_update_email_and_role():
    service, _ = _build_service()
    created = service.create_admin_user("ops@test.com", "StrongPass1", 2)
    updated = service.update_admin_user(created["uuid"], {"email": "updated@test.com", "role_id": 1})
    assert updated["email"] == "updated@test.com"
    assert updated["role_id"] == 1


def test_delete_prevents_last_admin_and_revokes_sessions():
    service, repo = _build_service()
    created = service.create_admin_user("solo@test.com", "StrongPass1", 1)
    with pytest.raises(HTTPException) as exc_info:
        service.delete_admin_user(created["uuid"])
    assert exc_info.value.status_code == 400

    service.create_admin_user("other@test.com", "StrongPass1", 1)
    resp = service.delete_admin_user(created["uuid"])
    assert resp["message"] == "User deleted"
    assert created["uuid"] in repo.revoked_sessions
    assert repo.count_admin_users() == 1


def test_reset_password_applies_rate_limit_and_revokes_sessions():
    service, repo = _build_service()
    created = service.create_admin_user("reset@test.com", "StrongPass1", 1)

    resp = service.reset_admin_user_password(created["uuid"], "Another1A")
    assert resp["message"] == "Password reset successful"
    assert created["uuid"] in repo.revoked_sessions

    with pytest.raises(HTTPException) as exc_info:
        for _ in range(service.PASSWORD_RESET_MAX_ATTEMPTS):
            service.reset_admin_user_password(created["uuid"], "Another1A")
    assert exc_info.value.status_code == 429


def test_bulk_create_validates_and_succeeds():
    service, repo = _build_service()
    with pytest.raises(HTTPException):
        service.bulk_create_admin_users(
            [
                {"email": "dup@test.com", "password": "StrongPass1", "role_id": 1},
                {"email": "dup@test.com", "password": "StrongPass1", "role_id": 1},
            ]
        )
    assert repo.count_admin_users() == 0

    created = service.bulk_create_admin_users(
        [
            {"email": "a@test.com", "password": "StrongPass1", "role_id": 1},
            {"email": "b@test.com", "password": "StrongPass1", "role_id": 2},
        ]
    )
    assert len(created) == 2
    assert repo.count_admin_users() == 2


def test_list_filters_by_role():
    service, _ = _build_service()
    service.create_admin_user("a@test.com", "StrongPass1", 1)
    service.create_admin_user("b@test.com", "StrongPass1", 2)

    result = service.list_admin_users(page=1, limit=10, role_id=2)
    assert result["pagination"]["total"] == 1
    assert result["items"][0]["role_id"] == 2
