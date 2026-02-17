"""Comprehensive tests for SMS notification system.

Tests cover:
- Message template building (all statuses, brand voice, Ressy signature)
- NotificationService send flows (success, failure, edge cases)
- TwilioClient (validation, error handling)
- PII masking utility (phone and email)
- Repository operations (mocked)
"""

from unittest.mock import Mock

import pytest

from app.integrations.twilio_client import MessageResult
from app.services.notification_service import SMS_SIGNATURE, NotificationService

# ============================================================================
# PII Masking Tests
# ============================================================================


class TestPIIMasking:
    """Tests for PII masking utilities."""

    @pytest.mark.parametrize(
        "phone,expected",
        [
            ("+14155551234", "********1234"),
            ("5551234567", "******4567"),
            ("1234", "1234"),
            ("123", "123"),
            ("", ""),
            (None, "None"),
            ("  +14155551234  ", "********1234"),  # with whitespace (stripped first)
        ],
    )
    def test_mask_phone_number(self, phone, expected):
        """Test phone number masking with various inputs."""
        from app.utils.pii_masking import mask_phone_number

        assert mask_phone_number(phone) == expected

    @pytest.mark.parametrize(
        "email,expected",
        [
            ("john.doe@example.com", "j******e@example.com"),  # 8 char local -> 6 asterisks
            ("ab@test.com", "a*@test.com"),
            ("a@test.com", "a*@test.com"),
            (None, "None"),
            ("", ""),
            ("invalid", "invalid"),
        ],
    )
    def test_mask_email(self, email, expected):
        """Test email masking with various inputs."""
        from app.utils.pii_masking import mask_email

        assert mask_email(email) == expected


# ============================================================================
# Phone Validation Tests
# ============================================================================


class TestPhoneValidation:
    """Tests for phone number validation."""

    @pytest.mark.parametrize(
        "phone",
        [
            "+14155551234",
            "+442071234567",
            "+8613812345678",
            "+61412345678",
        ],
    )
    def test_valid_e164_numbers(self, phone):
        """Test valid E.164 format phone numbers."""
        from app.integrations.twilio_client import _validate_phone_number

        is_valid, error = _validate_phone_number(phone)
        assert is_valid is True
        assert error == ""

    @pytest.mark.parametrize(
        "phone",
        [
            "4155551234",  # 10 digits, US without country code
            "14155551234",  # 11 digits
            "004155551234",  # 12 digits
        ],
    )
    def test_valid_digit_only_numbers(self, phone):
        """Test valid phone numbers with just digits."""
        from app.integrations.twilio_client import _validate_phone_number

        is_valid, error = _validate_phone_number(phone)
        assert is_valid is True

    @pytest.mark.parametrize(
        "phone",
        [
            "",
            "123",
            "abc",
        ],
    )
    def test_invalid_numbers(self, phone):
        """Test invalid phone numbers."""
        from app.integrations.twilio_client import _validate_phone_number

        is_valid, error = _validate_phone_number(phone)
        assert is_valid is False


# ============================================================================
# Order Message Template Tests
# ============================================================================


class TestOrderMessageTemplates:
    """Tests for order status message templates."""

    def setup_method(self):
        self.service = NotificationService(
            notification_repo=Mock(),
            twilio_client=Mock(),
        )

    @pytest.mark.parametrize(
        "status",
        ["pending", "confirmed", "preparing", "ready", "completed", "cancelled"],
    )
    def test_all_statuses_have_messages(self, status):
        """Verify all order statuses produce non-empty messages."""
        message = self.service._build_order_status_message(
            order_id=123,
            new_status=status,
            restaurant_name="Test Restaurant",
        )
        assert message
        assert "123" in message or "#123" in message
        assert "Test Restaurant" in message

    @pytest.mark.parametrize(
        "status",
        ["pending", "confirmed", "preparing", "ready", "completed", "cancelled"],
    )
    def test_all_messages_have_ressy_signature(self, status):
        """Verify all order messages include RessyAI signature."""
        message = self.service._build_order_status_message(
            order_id=123,
            new_status=status,
            restaurant_name="Test Restaurant",
        )
        assert "RessyAI" in message
        assert message.endswith(SMS_SIGNATURE)

    def test_cancelled_message_is_empathetic(self):
        """Verify cancelled message has warm, understanding tone."""
        message = self.service._build_order_status_message(
            order_id=123,
            new_status="cancelled",
            restaurant_name="Test Restaurant",
        )
        # Should contain empathetic language
        assert any(word in message.lower() for word in ["sorry", "understand", "get it", "happens"])
        # Should invite them back
        assert any(word in message.lower() for word in ["again", "welcome", "ready"])

    def test_confirmed_message_is_positive(self):
        """Verify confirmed message has positive, excited tone."""
        message = self.service._build_order_status_message(
            order_id=123,
            new_status="confirmed",
            restaurant_name="Test Restaurant",
        )
        assert any(word in message.lower() for word in ["awesome", "excited", "delicious"])

    def test_unknown_status_fallback(self):
        """Test that unknown statuses get a reasonable fallback message."""
        message = self.service._build_order_status_message(
            order_id=123,
            new_status="unknown_status_xyz",
            restaurant_name="Test Restaurant",
        )
        assert "123" in message
        assert "unknown_status_xyz" in message
        assert "RessyAI" in message  # Still has signature


# ============================================================================
# Reservation Message Template Tests
# ============================================================================


class TestReservationMessageTemplates:
    """Tests for reservation status message templates."""

    def setup_method(self):
        self.service = NotificationService(
            notification_repo=Mock(),
            twilio_client=Mock(),
        )

    @pytest.mark.parametrize(
        "status",
        ["pending", "confirmed", "seated", "completed", "cancelled", "no_show"],
    )
    def test_all_statuses_have_messages(self, status):
        """Verify all reservation statuses produce non-empty messages."""
        message = self.service._build_reservation_status_message(
            reservation_id=456,
            new_status=status,
            restaurant_name="Fine Dining",
            confirmation_number="ABC123",
        )
        assert message
        assert "Fine Dining" in message

    @pytest.mark.parametrize(
        "status",
        ["pending", "confirmed", "seated", "completed", "cancelled", "no_show"],
    )
    def test_all_messages_have_ressy_signature(self, status):
        """Verify all reservation messages include RessyAI signature."""
        message = self.service._build_reservation_status_message(
            reservation_id=456,
            new_status=status,
            restaurant_name="Fine Dining",
        )
        assert "RessyAI" in message
        assert message.endswith(SMS_SIGNATURE)

    def test_uses_confirmation_number_when_provided(self):
        """Verify confirmation number is used instead of reservation ID."""
        message = self.service._build_reservation_status_message(
            reservation_id=456,
            new_status="confirmed",
            restaurant_name="Test",
            confirmation_number="ABC123",
        )
        assert "ABC123" in message
        assert "#456" not in message

    def test_uses_reservation_id_when_no_confirmation(self):
        """Verify reservation ID is used when no confirmation number."""
        message = self.service._build_reservation_status_message(
            reservation_id=456,
            new_status="confirmed",
            restaurant_name="Test",
            confirmation_number=None,
        )
        assert "#456" in message

    def test_no_show_message_is_caring(self):
        """Verify no-show message is caring, not accusatory."""
        message = self.service._build_reservation_status_message(
            reservation_id=456,
            new_status="no_show",
            restaurant_name="Test Restaurant",
        )
        # Should express "We missed you" (not "you missed")
        assert "missed you" in message.lower()
        # Should be caring
        assert any(word in message.lower() for word in ["care", "welcome", "love"])
        # Should invite back
        assert any(word in message.lower() for word in ["again", "sometime", "always"])

    def test_cancelled_message_is_understanding(self):
        """Verify cancelled message is understanding and inviting."""
        message = self.service._build_reservation_status_message(
            reservation_id=456,
            new_status="cancelled",
            restaurant_name="Test Restaurant",
        )
        assert any(word in message.lower() for word in ["understand", "okay", "get it"])
        assert any(word in message.lower() for word in ["welcome", "ready", "again"])


# ============================================================================
# NotificationService Flow Tests
# ============================================================================


class TestNotificationServiceFlows:
    """Tests for notification sending flows."""

    def setup_method(self):
        self.mock_repo = Mock()
        self.mock_twilio = Mock()
        self.service = NotificationService(
            notification_repo=self.mock_repo,
            twilio_client=self.mock_twilio,
        )

    @pytest.mark.asyncio
    async def test_send_order_notification_no_phone_skips(self):
        """Verify notification is skipped when no phone number."""
        result = await self.service.send_order_notification(
            restaurant_id=1,
            order_id=123,
            new_status="confirmed",
            recipient_phone="",
            restaurant_name="Test",
            restaurant_twilio_number="+15551234567",
        )
        assert result is None
        self.mock_repo.create_log.assert_not_called()
        self.mock_twilio.send_sms.assert_not_called()

    @pytest.mark.asyncio
    async def test_send_order_notification_no_twilio_number_skips(self):
        """Verify notification is skipped when restaurant has no Twilio number."""
        result = await self.service.send_order_notification(
            restaurant_id=1,
            order_id=123,
            new_status="confirmed",
            recipient_phone="+15559876543",
            restaurant_name="Test",
            restaurant_twilio_number="",
        )
        assert result is None
        self.mock_repo.create_log.assert_not_called()

    @pytest.mark.asyncio
    async def test_send_order_notification_success_flow(self):
        """Test complete successful notification flow."""
        self.mock_repo.create_log.return_value = 42
        self.mock_twilio.send_sms.return_value = MessageResult(
            success=True,
            message_sid="SM123abc",
        )

        result = await self.service.send_order_notification(
            restaurant_id=1,
            order_id=123,
            new_status="confirmed",
            recipient_phone="+15559876543",
            restaurant_name="Test Restaurant",
            restaurant_twilio_number="+15551234567",
        )

        assert result == 42
        self.mock_repo.create_log.assert_called_once()
        self.mock_twilio.send_sms.assert_called_once()
        self.mock_repo.update_status.assert_called_with(
            log_id=42,
            status="sent",
            twilio_message_sid="SM123abc",
        )

    @pytest.mark.asyncio
    async def test_send_order_notification_failure_updates_status(self):
        """Test that failed sends update status and increment retry."""
        self.mock_repo.create_log.return_value = 42
        self.mock_twilio.send_sms.return_value = MessageResult(
            success=False,
            error_message="Invalid phone number",
        )

        result = await self.service.send_order_notification(
            restaurant_id=1,
            order_id=123,
            new_status="confirmed",
            recipient_phone="+15559876543",
            restaurant_name="Test Restaurant",
            restaurant_twilio_number="+15551234567",
        )

        assert result == 42
        self.mock_repo.update_status.assert_called_with(
            log_id=42,
            status="failed",
            error_message="Invalid phone number",
        )
        self.mock_repo.increment_retry_count.assert_called_with(42)

    @pytest.mark.asyncio
    async def test_send_reservation_notification_success(self):
        """Test successful reservation notification flow."""
        self.mock_repo.create_log.return_value = 99
        self.mock_twilio.send_sms.return_value = MessageResult(
            success=True,
            message_sid="SM456def",
        )

        result = await self.service.send_reservation_notification(
            restaurant_id=1,
            reservation_id=456,
            new_status="confirmed",
            recipient_phone="+15559876543",
            restaurant_name="Fine Dining",
            restaurant_twilio_number="+15551234567",
            confirmation_number="RES-ABC123",
        )

        assert result == 99
        self.mock_repo.create_log.assert_called_once()
        self.mock_twilio.send_sms.assert_called_once()
        # Verify the message contains the confirmation number
        call_args = self.mock_twilio.send_sms.call_args
        assert "RES-ABC123" in call_args.kwargs["body"]
        assert "RessyAI" in call_args.kwargs["body"]


# ============================================================================
# TwilioClient Tests (Legacy compatibility)
# ============================================================================


class TestTwilioClient:
    """Tests for TwilioClient."""

    def test_phone_validation_valid_e164(self):
        """Test valid E.164 phone numbers."""
        from app.integrations.twilio_client import _validate_phone_number

        assert _validate_phone_number("+14155551234")[0] is True
        assert _validate_phone_number("+442071234567")[0] is True

    def test_phone_validation_invalid(self):
        """Test invalid phone numbers."""
        from app.integrations.twilio_client import _validate_phone_number

        assert _validate_phone_number("")[0] is False
        assert _validate_phone_number("123")[0] is False


# ============================================================================
# Word Boundary Truncation Tests
# ============================================================================


class TestWordBoundaryTruncation:
    """Tests for word boundary truncation."""

    def test_truncate_at_word_boundary(self):
        """Verify truncation happens at word boundary."""
        from app.integrations.twilio_client import _truncate_at_word_boundary

        text = "This is a test message with multiple words"
        truncated = _truncate_at_word_boundary(text, 25)

        assert len(truncated) <= 25
        assert not truncated.endswith(" ")  # Should not end with space

    def test_truncate_short_text_unchanged(self):
        """Verify short text is not modified."""
        from app.integrations.twilio_client import _truncate_at_word_boundary

        text = "Short"
        truncated = _truncate_at_word_boundary(text, 100)
        assert truncated == text

    def test_truncate_exact_length(self):
        """Verify text at exact max length is unchanged."""
        from app.integrations.twilio_client import _truncate_at_word_boundary

        text = "Exactly 10"
        truncated = _truncate_at_word_boundary(text, 10)
        assert truncated == text


# ============================================================================
# Thread-Safe Singleton Tests
# ============================================================================


class TestThreadSafeSingletons:
    """Tests for thread-safe singleton initialization."""

    def test_get_twilio_client_returns_same_instance(self):
        """Verify singleton returns same instance."""
        from app.services.notification_service import _get_twilio_client

        client1 = _get_twilio_client()
        client2 = _get_twilio_client()
        assert client1 is client2

    def test_thread_lock_exists(self):
        """Verify thread lock is used for singleton initialization."""
        import threading

        from app.services import notification_service

        assert hasattr(notification_service, "_init_lock")
        assert isinstance(notification_service._init_lock, type(threading.Lock()))


# ============================================================================
# Status Validation Tests
# ============================================================================


class TestStatusValidation:
    """Tests for status validation in message builders."""

    def setup_method(self):
        self.service = NotificationService(
            notification_repo=Mock(),
            twilio_client=Mock(),
        )

    def test_unknown_order_status_uses_fallback(self):
        """Verify unknown status uses fallback message."""
        message = self.service._build_order_status_message(
            order_id=123,
            new_status="unknown_weird_status",
            restaurant_name="Test Restaurant",
        )

        assert message  # Should not be empty
        assert "unknown_weird_status" in message  # Fallback includes status
        assert "RessyAI" in message

    def test_unknown_reservation_status_uses_fallback(self):
        """Verify unknown status uses fallback message."""
        message = self.service._build_reservation_status_message(
            reservation_id=456,
            new_status="weird_status",
            restaurant_name="Test Restaurant",
        )

        assert message
        assert "weird_status" in message
        assert "RessyAI" in message


# ============================================================================
# Additional Error Handling Tests
# ============================================================================


class TestTwilioClientErrorMessages:
    """Tests for specific Twilio error messages."""

    def test_send_sms_returns_specific_error_for_missing_credentials(self):
        """Verify error message is specific when credentials are missing."""
        from app.integrations.twilio_client import TwilioClient

        client = TwilioClient()
        client.client = None  # Simulate missing credentials

        result = client.send_sms(
            to="+15551234567",
            body="Test",
            from_number="+15559876543",
        )

        assert result.success is False
        assert "not configured" in result.error_message.lower() or "TWILIO" in result.error_message
