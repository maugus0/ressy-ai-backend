"""Tests for configuration."""

import os

from app.config import settings


def test_settings_has_required_attributes():
    """Test that Settings has all required attributes."""
    assert hasattr(settings, "JWT_SECRET_KEY")
    assert hasattr(settings, "JWT_ALGORITHM")
    assert hasattr(settings, "DEEPGRAM_API_KEY")
    assert hasattr(settings, "AWS_REGION")


def test_settings_defaults():
    """Test that Settings has default values."""
    assert settings.JWT_ALGORITHM == "HS256"
    assert settings.JWT_EXPIRE_HOURS == 24
    assert settings.AWS_REGION == os.getenv("AWS_REGION", "ca-central-1")


def test_settings_table_names():
    """Test that table names are defined."""
    assert hasattr(settings, "RESTAURANTS_TABLE")
    assert hasattr(settings, "MENUS_TABLE")
    assert hasattr(settings, "USERS_TABLE")
    assert hasattr(settings, "ORDERS_TABLE")
