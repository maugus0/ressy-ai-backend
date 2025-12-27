"""Tests for Client Analytics API endpoints."""

import os
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("ALLOW_DB_FAILURE", "true")
os.environ.setdefault("USE_MOCK_DATA", "true")

from app.api.client_analytics import get_analytics_service  # noqa: E402
from app.main import app  # noqa: E402
from app.middleware.auth_middleware import get_current_restaurant_user  # noqa: E402
from app.services.client_analytics_service import ClientAnalyticsService  # noqa: E402
from tests.fake_repos import (  # noqa: E402
    InMemoryCallRepository,
    InMemoryFAQRepository,
    InMemoryMenuRepository,
    InMemoryOrderRepository,
    InMemoryReservationRepository,
    InMemoryRestaurantRepository,
    InMemoryUserRepository,
)


def _claims(restaurant_id: int, role: str = "manager") -> dict:
    return {
        "user_type": "restaurant",
        "restaurant_id": restaurant_id,
        "role": role,
        "sub": f"user-{restaurant_id}",
    }


class FakeAnalyticsService(ClientAnalyticsService):
    """Override service with in-memory repositories for testing."""

    def __init__(
        self,
        call_repo: InMemoryCallRepository,
        order_repo: InMemoryOrderRepository,
        reservation_repo: InMemoryReservationRepository,
        menu_repo: InMemoryMenuRepository,
        faq_repo: InMemoryFAQRepository,
        user_repo: InMemoryUserRepository,
    ):
        # Don't call super().__init__() - we're replacing all repos
        # Store repos as instance variables for factory methods to return
        self._call_repo = call_repo
        self._order_repo = order_repo
        self._reservation_repo = reservation_repo
        self._menu_repo = menu_repo
        self._faq_repo = faq_repo
        self._user_repo = user_repo

    # Override factory methods to return in-memory repositories
    def _get_call_repo(self):
        return self._call_repo

    def _get_order_repo(self):
        return self._order_repo

    def _get_reservation_repo(self):
        return self._reservation_repo

    def _get_menu_repo(self):
        return self._menu_repo

    def _get_faq_repo(self):
        return self._faq_repo

    def _get_user_repo(self):
        return self._user_repo

    # Add properties for backward compatibility with tests that access repos directly
    @property
    def call_repo(self):
        return self._call_repo

    @property
    def order_repo(self):
        return self._order_repo

    @property
    def reservation_repo(self):
        return self._reservation_repo

    @property
    def menu_repo(self):
        return self._menu_repo

    @property
    def faq_repo(self):
        return self._faq_repo

    @property
    def user_repo(self):
        return self._user_repo


@pytest.fixture
def client_with_overrides():
    """Set up test client with mocked dependencies."""
    # Create in-memory repositories
    restaurant_repo = InMemoryRestaurantRepository()
    restaurant_repo.add(1, "Test Restaurant")
    restaurant_repo.add(2, "Other Restaurant")

    call_repo = InMemoryCallRepository()
    order_repo = InMemoryOrderRepository()
    reservation_repo = InMemoryReservationRepository()
    menu_repo = InMemoryMenuRepository(restaurant_repo=restaurant_repo)
    faq_repo = InMemoryFAQRepository()
    user_repo = InMemoryUserRepository()

    # Add some test data for restaurant 1
    # Calls
    call_repo._calls[1] = {
        "id": 1,
        "restaurant_id": 1,
        "caller_phone": "+1234567890",
        "call_status": "completed",
        "call_duration": 120,
        "started_at": datetime.now(timezone.utc),
    }
    call_repo._calls[2] = {
        "id": 2,
        "restaurant_id": 1,
        "caller_phone": "+0987654321",
        "call_status": "completed",
        "call_duration": 60,
        "started_at": datetime.now(timezone.utc),
    }

    # Orders
    order_repo.add_order(1, "completed", 50.0, "John Doe")
    order_repo.add_order(1, "completed", 75.0, "Jane Smith")
    order_repo.add_order(1, "pending", 25.0, "Bob Wilson")

    # Reservations
    reservation_repo.add_reservation(1, "confirmed", 4, "Alice Johnson")
    reservation_repo.add_reservation(1, "pending", 2, "Charlie Brown")

    # Menu items
    menu_repo.create_menu(1, {"item_name": "Burger", "price": 15.0, "category": "Main", "is_available": True})
    menu_repo.create_menu(1, {"item_name": "Fries", "price": 5.0, "category": "Sides", "is_available": True})
    menu_repo.create_menu(
        1, {"item_name": "Seasonal Salad", "price": 12.0, "category": "Main", "is_available": True, "is_special": True}
    )

    # FAQs
    faq_repo.create(1, {"question": "What are your hours?", "answer": "9 AM - 10 PM"})
    faq_repo.create(1, {"question": "Do you accept reservations?", "answer": "Yes!"})

    # Users
    user_repo.add_user(1, "Customer 1", "+1111111111")
    user_repo.add_user(1, "Customer 2", "+2222222222")

    # Create fake service
    service = FakeAnalyticsService(
        call_repo=call_repo,
        order_repo=order_repo,
        reservation_repo=reservation_repo,
        menu_repo=menu_repo,
        faq_repo=faq_repo,
        user_repo=user_repo,
    )

    def set_claims(restaurant_id: int = 1, role: str = "manager"):
        app.dependency_overrides[get_current_restaurant_user] = lambda: _claims(restaurant_id, role)

    app.dependency_overrides[get_analytics_service] = lambda: service
    set_claims()
    client = TestClient(app)
    yield client, service, set_claims
    app.dependency_overrides = {}


def test_get_restaurant_analytics(client_with_overrides):
    """Test comprehensive restaurant analytics endpoint."""
    client, _, _ = client_with_overrides

    response = client.get("/api/v1/client/analytics")
    assert response.status_code == 200

    data = response.json()

    # Check call statistics
    assert data["total_calls"] == 2
    assert "calls_today" in data
    assert data["average_call_duration"] == 90.0  # (120 + 60) / 2

    # Check order statistics
    assert data["total_orders"] == 3
    assert data["total_revenue"] == 125.0  # 50 + 75 (completed only)
    assert data["pending_orders_count"] == 1

    # Check reservation statistics
    assert data["total_reservations"] == 2
    assert data["confirmed_reservations"] == 1
    assert data["pending_reservations"] == 1

    # Check menu statistics
    assert data["total_menu_items"] == 3
    assert data["available_menu_items"] == 3
    assert data["special_items"] == 1
    assert set(data["menu_categories"]) == {"Main", "Sides"}

    # Check FAQ statistics
    assert data["total_faqs"] == 2

    # Check customer statistics
    assert data["total_customers"] == 2

    # Check activity data
    assert "recent_activity" in data
    assert "todays_schedule" in data
    assert "pending_orders" in data


def test_get_call_analytics(client_with_overrides):
    """Test call analytics endpoint."""
    client, _, _ = client_with_overrides

    response = client.get("/api/v1/client/analytics/calls")
    assert response.status_code == 200

    data = response.json()
    assert data["total_calls"] == 2
    assert data["average_call_duration"] == 90.0
    assert "status_breakdown" in data
    assert data["status_breakdown"]["completed"] == 2


def test_get_reservation_analytics(client_with_overrides):
    """Test reservation analytics endpoint."""
    client, _, _ = client_with_overrides

    response = client.get("/api/v1/client/analytics/reservations")
    assert response.status_code == 200

    data = response.json()
    assert data["total_reservations"] == 2
    assert data["confirmed_reservations"] == 1
    assert data["pending_reservations"] == 1
    assert data["cancelled_reservations"] == 0


def test_get_order_analytics(client_with_overrides):
    """Test order analytics endpoint."""
    client, _, _ = client_with_overrides

    response = client.get("/api/v1/client/analytics/orders")
    assert response.status_code == 200

    data = response.json()
    assert data["total_orders"] == 3
    assert data["total_revenue"] == 125.0
    assert data["pending_orders"] == 1
    assert data["completed_orders"] == 2


def test_get_menu_analytics(client_with_overrides):
    """Test menu analytics endpoint."""
    client, _, _ = client_with_overrides

    response = client.get("/api/v1/client/analytics/menu")
    assert response.status_code == 200

    data = response.json()
    assert data["total_menu_items"] == 3
    assert data["available_menu_items"] == 3
    assert data["unavailable_menu_items"] == 0
    assert data["special_items"] == 1
    assert data["category_count"] == 2
    assert set(data["categories"]) == {"Main", "Sides"}


def test_analytics_scoped_to_restaurant(client_with_overrides):
    """Test that analytics are scoped to the authenticated restaurant."""
    client, service, set_claims = client_with_overrides

    # Add data for restaurant 2
    service.order_repo.add_order(2, "completed", 100.0, "Restaurant 2 Customer")

    # Get analytics for restaurant 1
    response = client.get("/api/v1/client/analytics")
    assert response.status_code == 200
    data = response.json()
    assert data["total_orders"] == 3  # Only restaurant 1 orders

    # Switch to restaurant 2
    set_claims(restaurant_id=2)
    response = client.get("/api/v1/client/analytics")
    assert response.status_code == 200
    data = response.json()
    assert data["total_orders"] == 1  # Only restaurant 2 orders
    assert data["total_revenue"] == 100.0


def test_analytics_with_empty_data(client_with_overrides):
    """Test analytics with no data returns zeros."""
    client, _, set_claims = client_with_overrides

    # Switch to restaurant with no data
    set_claims(restaurant_id=2)

    response = client.get("/api/v1/client/analytics")
    assert response.status_code == 200

    data = response.json()
    assert data["total_calls"] == 0
    assert data["total_orders"] == 0
    assert data["total_reservations"] == 0
    assert data["total_menu_items"] == 0
    assert data["total_faqs"] == 0
    assert data["total_customers"] == 0
    assert data["recent_activity"] == []
    assert data["todays_schedule"] == []
    assert data["pending_orders"] == []


def test_pending_orders_response_format(client_with_overrides):
    """Test pending orders response format."""
    client, _, _ = client_with_overrides

    response = client.get("/api/v1/client/analytics")
    assert response.status_code == 200

    data = response.json()
    pending_orders = data["pending_orders"]

    assert len(pending_orders) == 1
    order = pending_orders[0]
    assert "id" in order
    assert "order_number" in order
    assert "customer_name" in order
    assert "total" in order
    assert "status" in order
    assert order["status"] == "pending"


def test_recent_activity_includes_multiple_types(client_with_overrides):
    """Test recent activity includes calls, reservations, and orders."""
    client, _, _ = client_with_overrides

    response = client.get("/api/v1/client/analytics")
    assert response.status_code == 200

    data = response.json()
    recent_activity = data["recent_activity"]

    # Should have activities of different types
    types = {activity["type"] for activity in recent_activity}
    assert "call" in types
    assert "order" in types
    assert "reservation" in types
