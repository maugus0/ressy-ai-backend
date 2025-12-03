"""Tests for configuration."""

import os

from app.config import settings


def test_settings_has_required_attributes():
    """Test that Settings has all required attributes."""
    required_attrs = [
        "JWT_SECRET_KEY",
        "JWT_ALGORITHM",
        "JWT_PRIVATE_KEY",
        "JWT_PUBLIC_KEY",
        "JWT_ACCESS_TOKEN_EXP_SECONDS",
        "JWT_REFRESH_TOKEN_EXP_SECONDS",
        "JWT_ISSUER",
        "JWT_ADMIN_AUDIENCE",
        "JWT_CLIENT_AUDIENCE",
        "JWT_AUTH_AUDIENCE",
        "DEEPGRAM_API_KEY",
        "AWS_REGION",
    ]
    for attr in required_attrs:
        assert hasattr(settings, attr)


def test_settings_defaults():
    """Test that Settings has default values."""
    assert settings.JWT_ALGORITHM == "RS256"
    assert settings.JWT_EXPIRE_HOURS == 24
    assert settings.JWT_ACCESS_TOKEN_EXP_SECONDS == 3600
    assert settings.JWT_REFRESH_TOKEN_EXP_SECONDS == 30 * 24 * 3600
    assert settings.JWT_ISSUER == "ressy.ai/auth"
    assert settings.JWT_ADMIN_AUDIENCE == "ressy-admin-api"
    assert settings.JWT_CLIENT_AUDIENCE == "ressy-client-api"
    assert settings.JWT_AUTH_AUDIENCE == "ressy-auth"
    assert settings.AWS_REGION == os.getenv("AWS_REGION", "ca-central-1")


def test_settings_table_names():
    """Test that table names are defined."""
    assert hasattr(settings, "RESTAURANTS_TABLE")
    assert hasattr(settings, "MENUS_TABLE")
    assert hasattr(settings, "USERS_TABLE")
    assert hasattr(settings, "ORDERS_TABLE")
