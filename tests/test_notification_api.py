"""
API tests for persistent notification endpoints.

Tests cover:
- Dashboard endpoints (restaurant-scoped):
  - GET /api/v1/dashboard/notifications
  - GET /api/v1/dashboard/notifications/unread-count
  - GET /api/v1/dashboard/notifications/{notification_id}
  - PATCH /api/v1/dashboard/notifications/{notification_id}/read
  - PATCH /api/v1/dashboard/notifications/read-all

- Admin endpoints (system-wide):
  - GET /api/v1/admin/notifications
  - GET /api/v1/admin/notifications/{notification_id}

- Service layer: build_notification_title, build_notification_message
"""

import os
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("ALLOW_DB_FAILURE", "true")
os.environ.setdefault("USE_MOCK_DATA", "true")

from app.api import admin_notifications, dashboard_notifications  # noqa: E402
from app.main import app  # noqa: E402
from app.middleware.auth_middleware import get_current_admin_user  # noqa: E402
from app.services.notification_persistence_service import NotificationPersistenceService  # noqa: E402

# ══════════════════════════════════════════════════════════
# FIXTURES
# ══════════════════════════════════════════════════════════


@pytest.fixture
def test_client():
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def mock_client_user():
    """Mock authenticated client user with restaurant_id."""
    return {
        "user_id": 1,
        "role": "client",
        "restaurant_id": 100,
        "email": "test@restaurant.com",
        "user_type": "restaurant",
        "sub": "user-100",
    }


@pytest.fixture
def mock_admin_user():
    """Mock authenticated admin user."""
    return {
        "user_id": 99,
        "role": "admin",
        "email": "admin@ressy.ai",
        "user_type": "admin",
        "sub": "admin-99",
    }


@pytest.fixture
def sample_notification():
    """Sample notification row as returned from DB."""
    return {
        "id": 1,
        "restaurant_id": 100,
        "type": "order",
        "subtype": "new_order",
        "title": "New Order #5 — John",
        "message": "John placed a new order for $25.00. Status: pending.",
        "data": {"order_id": 5, "customer_name": "John", "total_amount": 25.0, "status": "pending"},
        "entity_id": 5,
        "is_read": False,
        "read_at": None,
        "created_at": "2026-02-11T10:00:00Z",
        "updated_at": "2026-02-11T10:00:00Z",
    }


@pytest.fixture
def sample_notification_read():
    """Sample notification that has been read."""
    return {
        "id": 2,
        "restaurant_id": 100,
        "type": "reservation",
        "subtype": "new_reservation",
        "title": "New Reservation — Alice, Party of 4",
        "message": "Alice booked a table for 4 on Feb 15, 2026 at 7:00 PM. Confirmation: RES-ABC123.",
        "data": {"reservation_id": 10, "name": "Alice", "party_size": 4},
        "entity_id": 10,
        "is_read": True,
        "read_at": "2026-02-11T12:00:00Z",
        "created_at": "2026-02-11T09:00:00Z",
        "updated_at": "2026-02-11T12:00:00Z",
    }


@pytest.fixture
def sample_escalation_notification():
    """Sample escalation notification."""
    return {
        "id": 3,
        "restaurant_id": 100,
        "type": "escalation",
        "subtype": "user_requested",
        "title": "Escalation — Customer Requested Human",
        "message": "Customer wants to speak with manager. Caller: +1234567890. Urgency: standard.",
        "data": {
            "reason": "Customer wants to speak with manager",
            "caller_phone": "+1234567890",
            "urgency": "standard",
        },
        "entity_id": 50,
        "is_read": False,
        "read_at": None,
        "created_at": "2026-02-11T11:00:00Z",
        "updated_at": "2026-02-11T11:00:00Z",
    }


AUTH_HEADER_CLIENT = {"Authorization": "Bearer test-dashboard-client"}
AUTH_HEADER_ADMIN = {"Authorization": "Bearer test-dashboard-admin"}


def _fake_validate_token(token, audiences):
    if token == "test-dashboard-client":
        return {"user_id": 1, "role": "client", "restaurant_id": 100, "user_type": "restaurant", "sub": "user-100"}
    if token == "test-dashboard-admin":
        return {"user_id": 99, "role": "admin", "user_type": "admin", "sub": "admin-99"}
    raise Exception("Invalid token")


@pytest.fixture
def dashboard_client(test_client, mock_client_user, sample_notification):
    """Test client with dashboard auth and mocked notification service."""
    mock_svc = MagicMock()
    mock_svc.get_notifications.return_value = ([sample_notification], 1)
    mock_svc.get_unread_count.return_value = 1
    mock_svc.get_notification_by_id.return_value = sample_notification
    mock_svc.mark_as_read.return_value = {**sample_notification, "is_read": True, "read_at": "2026-02-11T12:00:00Z"}
    mock_svc.mark_all_as_read.return_value = 1

    app.dependency_overrides[dashboard_notifications.get_notification_service] = lambda: mock_svc
    with patch("app.middleware.auth_middleware._validate_access_token", side_effect=_fake_validate_token):
        yield test_client, mock_svc
    app.dependency_overrides.pop(dashboard_notifications.get_notification_service, None)


@pytest.fixture
def admin_client(test_client, mock_admin_user, sample_notification):
    """Test client with admin auth and mocked notification service."""
    mock_svc = MagicMock()
    mock_svc.get_notifications.return_value = ([sample_notification], 1)
    mock_svc.get_unread_count.return_value = 1
    mock_svc.get_notification_by_id.return_value = sample_notification

    app.dependency_overrides[get_current_admin_user] = lambda: mock_admin_user
    app.dependency_overrides[admin_notifications.get_notification_service] = lambda: mock_svc
    yield test_client, mock_svc
    app.dependency_overrides.pop(get_current_admin_user, None)
    app.dependency_overrides.pop(admin_notifications.get_notification_service, None)


# ══════════════════════════════════════════════════════════
# DASHBOARD ENDPOINT TESTS
# ══════════════════════════════════════════════════════════


class TestDashboardNotificationsList:
    """Tests for GET /api/v1/dashboard/notifications"""

    def test_list_notifications_success(self, dashboard_client, sample_notification):
        """List notifications returns paginated results with unread count."""
        client, mock_svc = dashboard_client
        response = client.get("/api/v1/dashboard/notifications", headers=AUTH_HEADER_CLIENT)
        assert response.status_code == 200
        data = response.json()
        assert "notifications" in data
        assert data["total"] == 1
        assert data["unread_count"] == 1
        assert len(data["notifications"]) == 1
        assert data["notifications"][0]["id"] == sample_notification["id"]
        assert data["notifications"][0]["title"] == sample_notification["title"]

    def test_list_notifications_filter_by_type(self, dashboard_client):
        """Filter notifications by type (order, reservation, escalation)."""
        client, mock_svc = dashboard_client
        mock_svc.get_notifications.return_value = ([], 0)
        response = client.get(
            "/api/v1/dashboard/notifications",
            params={"type": "order"},
            headers=AUTH_HEADER_CLIENT,
        )
        assert response.status_code == 200
        mock_svc.get_notifications.assert_called_once()
        call_kw = mock_svc.get_notifications.call_args[1]
        assert call_kw["type"] == "order"
        assert call_kw["restaurant_id"] == 100

    def test_list_notifications_filter_by_read_status(self, dashboard_client):
        """Filter notifications by is_read status."""
        client, mock_svc = dashboard_client
        mock_svc.get_notifications.return_value = ([], 0)
        response = client.get(
            "/api/v1/dashboard/notifications",
            params={"is_read": False},
            headers=AUTH_HEADER_CLIENT,
        )
        assert response.status_code == 200
        call_kw = mock_svc.get_notifications.call_args[1]
        assert call_kw["is_read"] is False

    def test_list_notifications_pagination(self, dashboard_client):
        """Pagination with limit and offset works correctly."""
        client, mock_svc = dashboard_client
        response = client.get(
            "/api/v1/dashboard/notifications",
            params={"limit": 10, "offset": 5},
            headers=AUTH_HEADER_CLIENT,
        )
        assert response.status_code == 200
        call_kw = mock_svc.get_notifications.call_args[1]
        assert call_kw["limit"] == 10
        assert call_kw["offset"] == 5
        assert response.json()["limit"] == 10
        assert response.json()["offset"] == 5

    def test_list_notifications_unauthorized(self, test_client):
        """Returns 401 without auth token."""
        response = test_client.get("/api/v1/dashboard/notifications")
        assert response.status_code == 403  # HTTPBearer returns 403 when no credentials

    def test_list_notifications_no_restaurant(self, test_client, sample_notification):
        """Returns 403 for user without restaurant_id."""

        def _validate_no_restaurant(token, audiences):
            if token == "no-restaurant":
                return {"user_id": 1, "role": "client", "user_type": "restaurant", "restaurant_id": None}
            raise Exception("Invalid token")

        mock_svc = MagicMock()
        mock_svc.get_notifications.return_value = ([], 0)
        mock_svc.get_unread_count.return_value = 0
        app.dependency_overrides[dashboard_notifications.get_notification_service] = lambda: mock_svc
        with patch("app.middleware.auth_middleware._validate_access_token", side_effect=_validate_no_restaurant):
            response = test_client.get(
                "/api/v1/dashboard/notifications",
                headers={"Authorization": "Bearer no-restaurant"},
            )
        app.dependency_overrides.pop(dashboard_notifications.get_notification_service, None)
        assert response.status_code == 403
        assert "Restaurant" in response.json().get("detail", "")


class TestDashboardUnreadCount:
    """Tests for GET /api/v1/dashboard/notifications/unread-count"""

    def test_unread_count_success(self, dashboard_client):
        """Returns correct unread count for restaurant."""
        client, mock_svc = dashboard_client
        mock_svc.get_unread_count.return_value = 3
        response = client.get("/api/v1/dashboard/notifications/unread-count", headers=AUTH_HEADER_CLIENT)
        assert response.status_code == 200
        assert response.json()["unread_count"] == 3

    def test_unread_count_zero(self, dashboard_client):
        """Returns zero when no unread notifications."""
        client, mock_svc = dashboard_client
        mock_svc.get_unread_count.return_value = 0
        response = client.get("/api/v1/dashboard/notifications/unread-count", headers=AUTH_HEADER_CLIENT)
        assert response.status_code == 200
        assert response.json()["unread_count"] == 0

    def test_unread_count_unauthorized(self, test_client):
        """Returns 401 without auth token."""
        response = test_client.get("/api/v1/dashboard/notifications/unread-count")
        assert response.status_code == 403


class TestDashboardGetNotification:
    """Tests for GET /api/v1/dashboard/notifications/{notification_id}"""

    def test_get_notification_success(self, dashboard_client, sample_notification):
        """Get single notification by ID."""
        client, mock_svc = dashboard_client
        response = client.get("/api/v1/dashboard/notifications/1", headers=AUTH_HEADER_CLIENT)
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == 1
        assert data["title"] == sample_notification["title"]

    def test_get_notification_not_found(self, dashboard_client):
        """Returns 404 for non-existent notification."""
        client, mock_svc = dashboard_client
        mock_svc.get_notification_by_id.return_value = None
        response = client.get("/api/v1/dashboard/notifications/99999", headers=AUTH_HEADER_CLIENT)
        assert response.status_code == 404
        assert response.json()["detail"] == "Notification not found"

    def test_get_notification_wrong_restaurant(self, dashboard_client):
        """Returns 404 when notification belongs to different restaurant."""
        client, mock_svc = dashboard_client
        mock_svc.get_notification_by_id.return_value = {
            "id": 1,
            "restaurant_id": 999,
            "type": "order",
            "subtype": "new_order",
        }
        response = client.get("/api/v1/dashboard/notifications/1", headers=AUTH_HEADER_CLIENT)
        assert response.status_code == 404
        assert response.json()["detail"] == "Notification not found"

    def test_get_notification_unauthorized(self, test_client):
        """Returns 401 without auth token."""
        response = test_client.get("/api/v1/dashboard/notifications/1")
        assert response.status_code == 403


class TestDashboardMarkAsRead:
    """Tests for PATCH /api/v1/dashboard/notifications/{notification_id}/read"""

    def test_mark_as_read_success(self, dashboard_client, sample_notification):
        """Mark notification as read updates is_read and read_at."""
        client, mock_svc = dashboard_client
        updated = {**sample_notification, "is_read": True, "read_at": "2026-02-11T12:00:00Z"}
        mock_svc.mark_as_read.return_value = updated
        response = client.patch("/api/v1/dashboard/notifications/1/read", headers=AUTH_HEADER_CLIENT)
        assert response.status_code == 200
        assert response.json()["is_read"] is True
        assert response.json()["read_at"] is not None

    def test_mark_as_read_already_read(self, dashboard_client, sample_notification_read):
        """Marking already-read notification is idempotent (preserves original read_at)."""
        client, mock_svc = dashboard_client
        mock_svc.get_notification_by_id.return_value = sample_notification_read
        mock_svc.mark_as_read.return_value = sample_notification_read
        response = client.patch("/api/v1/dashboard/notifications/2/read", headers=AUTH_HEADER_CLIENT)
        assert response.status_code == 200
        assert response.json()["read_at"] == "2026-02-11T12:00:00Z"

    def test_mark_as_read_not_found(self, dashboard_client):
        """Returns 404 for non-existent notification."""
        client, mock_svc = dashboard_client
        mock_svc.get_notification_by_id.return_value = None
        response = client.patch("/api/v1/dashboard/notifications/99999/read", headers=AUTH_HEADER_CLIENT)
        assert response.status_code == 404

    def test_mark_as_read_wrong_restaurant(self, dashboard_client):
        """Returns 404 when notification belongs to different restaurant."""
        client, mock_svc = dashboard_client
        mock_svc.get_notification_by_id.return_value = {"id": 1, "restaurant_id": 999}
        response = client.patch("/api/v1/dashboard/notifications/1/read", headers=AUTH_HEADER_CLIENT)
        assert response.status_code == 404

    def test_mark_as_read_unauthorized(self, test_client):
        """Returns 401 without auth token."""
        response = test_client.patch("/api/v1/dashboard/notifications/1/read")
        assert response.status_code == 403


class TestDashboardMarkAllAsRead:
    """Tests for PATCH /api/v1/dashboard/notifications/read-all"""

    def test_mark_all_read_success(self, dashboard_client):
        """Mark all notifications as read returns updated count."""
        client, mock_svc = dashboard_client
        mock_svc.mark_all_as_read.return_value = 5
        response = client.patch("/api/v1/dashboard/notifications/read-all", headers=AUTH_HEADER_CLIENT)
        assert response.status_code == 200
        assert response.json()["updated_count"] == 5

    def test_mark_all_read_with_type_filter(self, dashboard_client):
        """Mark all with type filter only affects matching notifications."""
        client, mock_svc = dashboard_client
        mock_svc.mark_all_as_read.return_value = 2
        response = client.patch(
            "/api/v1/dashboard/notifications/read-all",
            params={"type": "order"},
            headers=AUTH_HEADER_CLIENT,
        )
        assert response.status_code == 200
        mock_svc.mark_all_as_read.assert_called_once_with(100, type="order")

    def test_mark_all_read_none_unread(self, dashboard_client):
        """Returns updated_count=0 when no unread notifications."""
        client, mock_svc = dashboard_client
        mock_svc.mark_all_as_read.return_value = 0
        response = client.patch("/api/v1/dashboard/notifications/read-all", headers=AUTH_HEADER_CLIENT)
        assert response.status_code == 200
        assert response.json()["updated_count"] == 0

    def test_mark_all_read_unauthorized(self, test_client):
        """Returns 401 without auth token."""
        response = test_client.patch("/api/v1/dashboard/notifications/read-all")
        assert response.status_code == 403


# ══════════════════════════════════════════════════════════
# ADMIN ENDPOINT TESTS
# ══════════════════════════════════════════════════════════


class TestAdminNotificationsList:
    """Tests for GET /api/v1/admin/notifications"""

    def test_list_all_notifications(self, admin_client, sample_notification):
        """Admin can list notifications across all restaurants."""
        client, mock_svc = admin_client
        response = client.get("/api/v1/admin/notifications")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert len(data["notifications"]) == 1
        mock_svc.get_notifications.assert_called_once()
        call_kw = mock_svc.get_notifications.call_args[1]
        assert call_kw["restaurant_id"] is None
        assert call_kw["exclude_bulk_system_kill_switch_toggled"] is True

    def test_list_notifications_filter_by_restaurant(self, admin_client):
        """Filter by specific restaurant_id."""
        client, mock_svc = admin_client
        mock_svc.get_notifications.return_value = ([], 0)
        mock_svc.get_unread_count.return_value = 0
        response = client.get("/api/v1/admin/notifications", params={"restaurant_id": 100})
        assert response.status_code == 200
        call_kw = mock_svc.get_notifications.call_args[1]
        assert call_kw["restaurant_id"] == 100

    def test_list_notifications_filter_by_type(self, admin_client):
        """Filter by notification type."""
        client, mock_svc = admin_client
        response = client.get("/api/v1/admin/notifications", params={"type": "escalation"})
        assert response.status_code == 200
        call_kw = mock_svc.get_notifications.call_args[1]
        assert call_kw["type"] == "escalation"

    def test_list_notifications_filter_by_read_status(self, admin_client):
        """Filter by is_read status."""
        client, mock_svc = admin_client
        response = client.get("/api/v1/admin/notifications", params={"is_read": True})
        assert response.status_code == 200
        call_kw = mock_svc.get_notifications.call_args[1]
        assert call_kw["is_read"] is True

    def test_list_notifications_pagination(self, admin_client):
        """Pagination works correctly."""
        client, mock_svc = admin_client
        response = client.get("/api/v1/admin/notifications", params={"limit": 20, "offset": 10})
        assert response.status_code == 200
        call_kw = mock_svc.get_notifications.call_args[1]
        assert call_kw["limit"] == 20
        assert call_kw["offset"] == 10

    def test_list_notifications_unauthorized(self, test_client):
        """Returns 401 without auth token."""
        response = test_client.get("/api/v1/admin/notifications")
        assert response.status_code == 403

    def test_list_notifications_forbidden_for_client(self, dashboard_client):
        """Returns 403 for non-admin users (client token on admin endpoint)."""
        client, _ = dashboard_client
        response = client.get("/api/v1/admin/notifications", headers=AUTH_HEADER_CLIENT)
        assert response.status_code == 403


class TestAdminGetNotification:
    """Tests for GET /api/v1/admin/notifications/{notification_id}"""

    def test_get_notification_success(self, admin_client, sample_notification):
        """Admin can get any notification by ID."""
        client, mock_svc = admin_client
        response = client.get("/api/v1/admin/notifications/1")
        assert response.status_code == 200
        assert response.json()["id"] == 1
        assert response.json()["title"] == sample_notification["title"]

    def test_get_notification_not_found(self, admin_client):
        """Returns 404 for non-existent notification."""
        client, mock_svc = admin_client
        mock_svc.get_notification_by_id.return_value = None
        response = client.get("/api/v1/admin/notifications/99999")
        assert response.status_code == 404
        assert response.json()["detail"] == "Notification not found"

    def test_get_notification_unauthorized(self, test_client):
        """Returns 401 without auth token."""
        response = test_client.get("/api/v1/admin/notifications/1")
        assert response.status_code == 403

    def test_get_notification_forbidden_for_client(self, dashboard_client):
        """Returns 403 for non-admin users."""
        client, _ = dashboard_client
        response = client.get("/api/v1/admin/notifications/1", headers=AUTH_HEADER_CLIENT)
        assert response.status_code == 403


# ══════════════════════════════════════════════════════════
# NOTIFICATION PERSISTENCE SERVICE TESTS
# ══════════════════════════════════════════════════════════


class TestNotificationTitleBuilder:
    """Tests for NotificationPersistenceService.build_notification_title"""

    def test_order_new_order_with_name(self):
        """New order title includes customer name."""
        title = NotificationPersistenceService.build_notification_title(
            "order",
            "new_order",
            {"order_id": 5, "customer_name": "John"},
        )
        assert title == "New Order #5 — John"

    def test_order_new_order_without_name(self):
        """New order title without customer name."""
        title = NotificationPersistenceService.build_notification_title(
            "order",
            "new_order",
            {"order_id": 5},
        )
        assert title == "New Order #5"

    def test_order_updated_confirmed(self):
        """Order confirmed title."""
        title = NotificationPersistenceService.build_notification_title(
            "order",
            "order_updated",
            {"order_id": 5, "status": "confirmed"},
        )
        assert title == "Order #5 Confirmed"

    def test_order_updated_preparing(self):
        """Order preparing title."""
        title = NotificationPersistenceService.build_notification_title(
            "order",
            "order_updated",
            {"order_id": 5, "status": "preparing"},
        )
        assert title == "Order #5 Being Prepared"

    def test_order_updated_ready(self):
        """Order ready title."""
        title = NotificationPersistenceService.build_notification_title(
            "order",
            "order_updated",
            {"order_id": 5, "status": "ready"},
        )
        assert title == "Order #5 Ready for Pickup"

    def test_order_updated_completed(self):
        """Order completed title."""
        title = NotificationPersistenceService.build_notification_title(
            "order",
            "order_updated",
            {"order_id": 5, "status": "completed"},
        )
        assert title == "Order #5 Completed"

    def test_order_updated_cancelled(self):
        """Order cancelled title."""
        title = NotificationPersistenceService.build_notification_title(
            "order",
            "order_updated",
            {"order_id": 5, "status": "cancelled"},
        )
        assert title == "Order #5 Cancelled"

    def test_order_cancelled(self):
        """Order cancelled subtype title."""
        title = NotificationPersistenceService.build_notification_title(
            "order",
            "order_cancelled",
            {"order_id": 5},
        )
        assert title == "Order #5 Cancelled"

    def test_reservation_new_with_name_and_party(self):
        """New reservation title with name and party size."""
        title = NotificationPersistenceService.build_notification_title(
            "reservation",
            "new_reservation",
            {"reservation_id": 10, "name": "Alice", "party_size": 4},
        )
        assert title == "New Reservation — Alice, Party of 4"

    def test_reservation_new_without_name(self):
        """New reservation title without name."""
        title = NotificationPersistenceService.build_notification_title(
            "reservation",
            "new_reservation",
            {"reservation_id": 10},
        )
        assert title == "New Reservation #10"

    def test_reservation_updated_confirmed(self):
        """Reservation confirmed title."""
        title = NotificationPersistenceService.build_notification_title(
            "reservation",
            "reservation_updated",
            {"reservation_id": 10, "name": "Alice", "status": "confirmed"},
        )
        assert title == "Reservation Confirmed — Alice"

    def test_reservation_updated_cancelled(self):
        """Reservation cancelled title."""
        title = NotificationPersistenceService.build_notification_title(
            "reservation",
            "reservation_updated",
            {"reservation_id": 10, "name": "Alice", "status": "cancelled"},
        )
        assert title == "Reservation Cancelled — Alice"

    def test_reservation_updated_no_show(self):
        """Reservation no-show title."""
        title = NotificationPersistenceService.build_notification_title(
            "reservation",
            "reservation_updated",
            {"reservation_id": 10, "name": "Alice", "status": "no_show"},
        )
        assert title == "Reservation No-Show — Alice"

    def test_escalation_user_requested(self):
        """Escalation user requested title."""
        title = NotificationPersistenceService.build_notification_title(
            "escalation",
            "user_requested",
            {"reason": "test"},
        )
        assert title == "Escalation — Customer Requested Human"

    def test_escalation_internal_server_error(self):
        """Escalation server error title."""
        title = NotificationPersistenceService.build_notification_title(
            "escalation",
            "internal_server_error",
            {"reason": "test"},
        )
        assert title == "⚠ Escalation — System Error During Call"

    def test_escalation_suspected_spam(self):
        """Escalation suspected spam title."""
        title = NotificationPersistenceService.build_notification_title(
            "escalation",
            "suspected_spam",
            {"reason": "test"},
        )
        assert title == "Escalation — Suspected Spam Call"

    def test_escalation_sms_redirect_failed(self):
        """Escalation SMS redirect failed title."""
        title = NotificationPersistenceService.build_notification_title(
            "escalation",
            "sms_redirect_failed",
            {"reason": "timeout"},
        )
        assert title == "Escalation — SMS Redirect Failed"

    def test_escalation_kill_switch_redirected(self):
        """Escalation kill switch redirected title."""
        title = NotificationPersistenceService.build_notification_title(
            "escalation",
            "kill_switch_redirected",
            {"reason": "kill switch"},
        )
        assert title == "Escalation — Kill Switch Redirected"

    def test_system_kill_switch_toggled(self):
        """System kill switch toggled title."""
        enabled = NotificationPersistenceService.build_notification_title(
            "system",
            "kill_switch_toggled",
            {"enabled": True},
        )
        disabled = NotificationPersistenceService.build_notification_title(
            "system",
            "kill_switch_toggled",
            {"enabled": False},
        )
        assert enabled == "System — Kill Switch Enabled"
        assert disabled == "System — Kill Switch Disabled"

    def test_system_kill_switch_bulk_updated(self):
        """System kill switch bulk title."""
        enabled = NotificationPersistenceService.build_notification_title(
            "system",
            "kill_switch_bulk_updated",
            {"enabled": True},
        )
        disabled = NotificationPersistenceService.build_notification_title(
            "system",
            "kill_switch_bulk_updated",
            {"enabled": False},
        )
        assert enabled == "System — Kill Switch Bulk Enabled"
        assert disabled == "System — Kill Switch Bulk Disabled"


class TestNotificationMessageBuilder:
    """Tests for NotificationPersistenceService.build_notification_message"""

    def test_order_new_order_full_data(self):
        """New order message with all data."""
        message = NotificationPersistenceService.build_notification_message(
            "order",
            "new_order",
            {"order_id": 5, "customer_name": "John", "total_amount": 25.0, "status": "pending"},
        )
        assert message == "John placed a new order for $25.00. Status: pending."

    def test_order_new_order_minimal_data(self):
        """New order message with minimal data."""
        message = NotificationPersistenceService.build_notification_message(
            "order",
            "new_order",
            {"order_id": 5, "status": "pending"},
        )
        assert message == "New order #5 received. Status: pending."

    def test_order_updated_confirmed(self):
        """Order confirmed message."""
        message = NotificationPersistenceService.build_notification_message(
            "order",
            "order_updated",
            {"order_id": 5, "status": "confirmed"},
        )
        assert message == "Order #5 has been confirmed and is queued for preparation."

    def test_escalation_user_requested(self):
        """Escalation user requested message."""
        message = NotificationPersistenceService.build_notification_message(
            "escalation",
            "user_requested",
            {"reason": "Customer wants manager", "caller_phone": "+1234567890", "urgency": "standard"},
        )
        assert "Customer wants manager" in message
        assert "+1234567890" in message
        assert "standard" in message

    def test_escalation_sms_redirect_failed(self):
        """Escalation SMS redirect failed message."""
        message = NotificationPersistenceService.build_notification_message(
            "escalation",
            "sms_redirect_failed",
            {"redirect_type": "orders", "caller_phone": "+1234567890", "reason": "twilio timeout"},
        )
        assert "Could not send SMS redirect for orders." in message
        assert "+1234567890" in message
        assert "twilio timeout" in message

    def test_escalation_kill_switch_redirected(self):
        """Escalation kill switch redirected message."""
        message = NotificationPersistenceService.build_notification_message(
            "escalation",
            "kill_switch_redirected",
            {"caller_phone": "+1234567890", "reason": "dependency outage"},
        )
        assert "kill switch is enabled" in message
        assert "+1234567890" in message
        assert "dependency outage" in message

    def test_system_kill_switch_toggled(self):
        """System kill switch toggled message."""
        message = NotificationPersistenceService.build_notification_message(
            "system",
            "kill_switch_toggled",
            {"enabled": True, "actor_type": "admin", "actor_email": "ops@example.com"},
        )
        assert "enabled" in message
        assert "ops@example.com" in message

    def test_system_kill_switch_bulk_updated(self):
        """System kill switch bulk message."""
        message = NotificationPersistenceService.build_notification_message(
            "system",
            "kill_switch_bulk_updated",
            {"enabled": False, "updated_count": 7, "targeted_count": 10, "skipped_count": 3, "actor_type": "admin"},
        )
        assert "disabled" in message
        assert "7/10" in message
        assert "skipped 3" in message


class TestNotificationPersistenceValidation:
    """Validation tests for NotificationPersistenceService.create_notification."""

    def test_null_restaurant_id_rejected_for_non_system_type(self):
        repo = MagicMock()
        svc = NotificationPersistenceService(repo=repo)
        row = svc.create_notification(
            restaurant_id=None,
            type="order",
            subtype="new_order",
            data={"order_id": 5},
            entity_id=5,
        )
        assert row == {}
        repo.create_notification.assert_not_called()

    def test_null_restaurant_id_allowed_for_system_type(self):
        repo = MagicMock()
        repo.create_notification.return_value = {"id": 99, "restaurant_id": None, "type": "system"}
        svc = NotificationPersistenceService(repo=repo)
        row = svc.create_notification(
            restaurant_id=None,
            type="system",
            subtype="kill_switch_bulk_updated",
            data={"updated_count": 1},
            entity_id=None,
        )
        assert row.get("id") == 99
        repo.create_notification.assert_called_once()

    def test_bulk_system_kill_switch_toggled_persists_rows(self):
        repo = MagicMock()
        repo.create_notifications_bulk.return_value = 2
        svc = NotificationPersistenceService(repo=repo)

        count = svc.create_system_kill_switch_toggled_bulk(
            [
                {"restaurant_id": 10, "data": {"enabled": True, "actor_type": "admin"}},
                {"restaurant_id": 11, "data": {"enabled": False, "actor_type": "admin"}},
            ]
        )

        assert count == 2
        repo.create_notifications_bulk.assert_called_once()
        rows = repo.create_notifications_bulk.call_args[0][0]
        assert len(rows) == 2
        assert rows[0]["restaurant_id"] == 10
        assert rows[0]["type"] == "system"
        assert rows[0]["subtype"] == "kill_switch_toggled"
        assert rows[1]["restaurant_id"] == 11
