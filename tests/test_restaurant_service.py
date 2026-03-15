import pytest
from fastapi import HTTPException

from app.config import settings
from app.services.restaurant_service import RestaurantService
from tests.fake_repos import InMemoryRestaurantFeaturesRepository, InMemoryRestaurantRepository


def _build_service():
    repo = InMemoryRestaurantRepository()
    features_repo = InMemoryRestaurantFeaturesRepository()
    service = RestaurantService(restaurant_repo=repo, features_repo=features_repo)
    return service, repo


def test_create_restaurant_with_defaults():
    service, _ = _build_service()
    restaurant = service.create_restaurant({"name": "Pasta Place"})
    assert restaurant["name"] == "Pasta Place"
    assert restaurant["operating_hours"]["monday"]["open"] == "09:00:00"
    assert restaurant["operating_hours"]["monday"]["close"] == "22:00:00"


def test_create_restaurant_with_custom_hours():
    service, _ = _build_service()
    restaurant = service.create_restaurant(
        {
            "name": "Late Night",
            "operating_hours": {
                "monday": {"open": "10:30:00", "close": "23:45:00", "is_closed": False},
                "tuesday": {"open": "10:30:00", "close": "23:45:00", "is_closed": False},
                "wednesday": {"open": "10:30:00", "close": "23:45:00", "is_closed": False},
                "thursday": {"open": "10:30:00", "close": "23:45:00", "is_closed": False},
                "friday": {"open": "10:30:00", "close": "23:45:00", "is_closed": False},
                "saturday": {"open": "10:30:00", "close": "23:45:00", "is_closed": False},
                "sunday": {"open": "10:30:00", "close": "23:45:00", "is_closed": False},
            },
        }
    )
    assert restaurant["operating_hours"]["monday"]["open"] == "10:30:00"
    assert restaurant["operating_hours"]["monday"]["close"] == "23:45:00"


def test_create_restaurant_invalid_time_rejected():
    service, _ = _build_service()
    with pytest.raises(HTTPException):
        service.create_restaurant(
            {
                "name": "Bad Time",
                "operating_hours": {
                    "monday": {"open": "25:00:00", "close": "22:00:00", "is_closed": False},
                },
            }
        )


def test_update_restaurant_times():
    service, repo = _build_service()
    rid = repo.create({"name": "Update Me"})
    updated = service.update_restaurant(
        rid,
        {
            "operating_hours": {
                "monday": {"open": "08:00:00", "close": "21:00:00", "is_closed": False},
            }
        },
    )
    assert updated["operating_hours"]["monday"]["open"] == "08:00:00"
    assert updated["operating_hours"]["monday"]["close"] == "21:00:00"


def test_duplicate_name_rejected():
    service, _ = _build_service()
    service.create_restaurant({"name": "Unique"})
    with pytest.raises(HTTPException):
        service.create_restaurant({"name": "Unique"})


def test_duplicate_twilio_rejected():
    service, _ = _build_service()
    service.create_restaurant({"name": "First", "twilio_phone_number": "+10000000001"})
    with pytest.raises(HTTPException):
        service.create_restaurant({"name": "Second", "twilio_phone_number": "+10000000001"})


def test_update_duplicate_name_rejected():
    service, repo = _build_service()
    service.create_restaurant({"name": "First"})
    second_id = service.create_restaurant({"name": "Second"})["id"]
    with pytest.raises(HTTPException):
        service.update_restaurant(second_id, {"name": "First"})


def test_update_duplicate_twilio_rejected():
    service, repo = _build_service()
    service.create_restaurant({"name": "First", "twilio_phone_number": "+10000000001"})
    second_id = service.create_restaurant({"name": "Second", "twilio_phone_number": "+10000000002"})["id"]
    with pytest.raises(HTTPException):
        service.update_restaurant(second_id, {"twilio_phone_number": "+10000000001"})


def test_create_restaurant_rejects_non_e164_escalation_number():
    service, _ = _build_service()
    with pytest.raises(HTTPException) as exc_info:
        service.create_restaurant(
            {
                "name": "Escalation Format Test",
                "forward_escalations": True,
                "escalation_phone_number": "(415) 555-1234",
            }
        )
    assert exc_info.value.status_code == 400
    assert "E.164" in str(exc_info.value.detail)


def test_create_restaurant_allows_feature_disable_without_forwarding():
    service, _ = _build_service()
    restaurant = service.create_restaurant({"name": "No Orders", "features": {"orders_enabled": False}})
    assert restaurant["features"]["orders_enabled"] is False


def test_update_restaurant_allows_feature_disable_without_forwarding():
    service, _ = _build_service()
    restaurant = service.create_restaurant({"name": "Selective"})
    updated = service.update_restaurant(restaurant["id"], {"features": {"reservations_enabled": False}})
    assert updated["features"]["reservations_enabled"] is False


def test_normalize_timezone_defaults_to_setting():
    service, _ = _build_service()
    assert service._normalize_timezone(None) == settings.RESTAURANT_TIMEZONE
    assert service._normalize_timezone("   ") == settings.RESTAURANT_TIMEZONE


def test_normalize_timezone_accepts_valid():
    service, _ = _build_service()
    assert service._normalize_timezone("UTC") == "UTC"


def test_normalize_timezone_rejects_invalid():
    service, _ = _build_service()
    with pytest.raises(HTTPException):
        service._normalize_timezone("Not/A_Timezone")


class TestSMSRedirectValidation:
    """Tests for SMS redirect business rule validation."""

    def test_orders_sms_redirect_requires_orders_disabled(self):
        """Orders SMS redirect requires orders_enabled=False."""
        features = {
            "orders_enabled": True,
            "orders_sms_redirect": {
                "enabled": True,
                "redirect_url": "https://order.example.com",
            },
        }
        with pytest.raises(HTTPException) as exc_info:
            RestaurantService.validate_sms_redirect_rules(features)
        assert exc_info.value.status_code == 400
        assert "Orders" in exc_info.value.detail

    def test_orders_sms_redirect_requires_url(self):
        """Orders SMS redirect requires a redirect URL."""
        features = {
            "orders_enabled": False,
            "orders_sms_redirect": {
                "enabled": True,
                "redirect_url": None,
            },
        }
        with pytest.raises(HTTPException) as exc_info:
            RestaurantService.validate_sms_redirect_rules(features)
        assert exc_info.value.status_code == 400
        assert "URL" in exc_info.value.detail

    def test_reservations_sms_redirect_requires_reservations_disabled(self):
        """Reservations SMS redirect requires reservations_enabled=False."""
        features = {
            "reservations_enabled": True,
            "reservations_sms_redirect": {
                "enabled": True,
                "redirect_url": "https://book.example.com",
            },
        }
        with pytest.raises(HTTPException) as exc_info:
            RestaurantService.validate_sms_redirect_rules(features)
        assert exc_info.value.status_code == 400
        assert "Reservations" in exc_info.value.detail

    def test_reservations_sms_redirect_requires_url(self):
        """Reservations SMS redirect requires a redirect URL."""
        features = {
            "reservations_enabled": False,
            "reservations_sms_redirect": {
                "enabled": True,
                "redirect_url": None,
            },
        }
        with pytest.raises(HTTPException) as exc_info:
            RestaurantService.validate_sms_redirect_rules(features)
        assert exc_info.value.status_code == 400
        assert "URL" in exc_info.value.detail

    def test_valid_orders_sms_redirect_passes(self):
        """Valid orders SMS redirect configuration passes validation."""
        features = {
            "orders_enabled": False,
            "orders_sms_redirect": {
                "enabled": True,
                "redirect_url": "https://order.example.com",
            },
        }
        # Should not raise
        RestaurantService.validate_sms_redirect_rules(features)

    def test_valid_reservations_sms_redirect_passes(self):
        """Valid reservations SMS redirect configuration passes validation."""
        features = {
            "reservations_enabled": False,
            "reservations_sms_redirect": {
                "enabled": True,
                "redirect_url": "https://book.example.com",
            },
        }
        # Should not raise
        RestaurantService.validate_sms_redirect_rules(features)

    def test_disabled_sms_redirect_skips_validation(self):
        """Disabled SMS redirect skips URL validation."""
        features = {
            "orders_enabled": True,
            "orders_sms_redirect": {
                "enabled": False,
                "redirect_url": None,
            },
        }
        # Should not raise - SMS redirect is disabled
        RestaurantService.validate_sms_redirect_rules(features)


class TestEscalationModeValidation:
    """Tests for _validate_escalation_mode."""

    def test_none_defaults_to_always(self):
        assert RestaurantService._validate_escalation_mode(None) == "always"

    def test_always_accepted(self):
        assert RestaurantService._validate_escalation_mode("always") == "always"

    def test_open_hours_only_accepted(self):
        assert RestaurantService._validate_escalation_mode("open_hours_only") == "open_hours_only"

    def test_whitespace_stripped(self):
        assert RestaurantService._validate_escalation_mode("  open_hours_only  ") == "open_hours_only"

    def test_case_insensitive(self):
        assert RestaurantService._validate_escalation_mode("ALWAYS") == "always"
        assert RestaurantService._validate_escalation_mode("Open_Hours_Only") == "open_hours_only"

    def test_invalid_mode_rejected(self):
        with pytest.raises(HTTPException) as exc_info:
            RestaurantService._validate_escalation_mode("never")
        assert exc_info.value.status_code == 400
        assert "escalation_mode" in exc_info.value.detail

    def test_create_restaurant_defaults_escalation_mode(self):
        service, _ = _build_service()
        restaurant = service.create_restaurant({"name": "No Escalation Mode"})
        assert restaurant.get("escalation_mode", "always") == "always"

    def test_create_restaurant_with_open_hours_only(self):
        service, _ = _build_service()
        restaurant = service.create_restaurant({"name": "Open Hours", "escalation_mode": "open_hours_only"})
        assert restaurant.get("escalation_mode") == "open_hours_only"
