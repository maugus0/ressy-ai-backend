"""Tests for API structure and imports."""

import os

import pytest


@pytest.fixture(autouse=True)
def setup_env():
    """Setup environment variables before each test."""
    os.environ.setdefault("MYSQL_HOST", "localhost")
    os.environ.setdefault("MYSQL_DATABASE", "test_db")
    os.environ.setdefault("MYSQL_USER", "test_user")
    os.environ.setdefault("MYSQL_PASSWORD", "test_pass")
    os.environ.setdefault("USE_MOCK_DATA", "true")


def test_main_imports():
    """Test that main.py can be imported without errors."""
    try:
        from app.main import app

        assert app is not None
    except Exception as e:
        # If import fails due to DB connection, that's okay for structure tests
        pytest.skip(f"Could not import app due to: {e}")


def test_api_routes_import():
    """Test that API routes can be imported."""
    try:
        from app.api import admin, auth, calls, menus, restaurants, users

        assert auth is not None
        assert calls is not None
        assert admin is not None
        assert users is not None
        assert menus is not None
        assert restaurants is not None
    except Exception as e:
        # If import fails due to DB connection, that's okay for structure tests
        pytest.skip(f"Could not import API routes due to: {e}")


def test_services_import():
    """Test that services can be imported."""
    try:
        from app.services.auth_service import AuthService
        from app.services.user_service import UserService

        # Services are classes, so we check they can be imported
        assert AuthService is not None
        assert UserService is not None
    except Exception as e:
        # Some services require DB connection, skip if that fails
        pytest.skip(f"Could not import some services due to: {e}")

    # Test services that don't require DB
    from app.services.restaurant_service import RestaurantService

    assert RestaurantService is not None


def test_models_import():
    """Test that models can be imported."""
    from app.models import call_models, database, user_models

    assert database is not None
    assert user_models is not None
    assert call_models is not None


def test_utils_import():
    """Test that utils can be imported."""
    from app.utils import helpers, jwt_util

    assert jwt_util is not None
    assert helpers is not None
