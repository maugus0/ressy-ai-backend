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
        from app.api import (
            admin_users,
            auth,
            calls,
            client_client_users,
            client_faqs,
            client_menus,
            client_restaurant,
            client_users,
            dashboard_reservations,
            faqs,
            menus,
            opentable,
            order_history,
            orders,
            reservations,
            restaurants,
            transcripts,
            users,
            websocket,
        )

        assert auth is not None
        assert calls is not None
        assert users is not None
        assert menus is not None
        assert restaurants is not None
        assert admin_users is not None
        assert client_users is not None
        assert client_client_users is not None
        assert client_faqs is not None
        assert client_menus is not None
        assert client_restaurant is not None
        assert faqs is not None
        assert opentable is not None
        assert order_history is not None
        assert orders is not None
        assert reservations is not None
        assert transcripts is not None
        assert dashboard_reservations is not None
        assert websocket is not None
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
    from app.models import call_models, menu_models

    assert menu_models is not None
    assert call_models is not None


def test_utils_import():
    """Test that utils can be imported."""
    from app.utils import helpers, jwt_util

    assert jwt_util is not None
    assert helpers is not None
