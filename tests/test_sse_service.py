"""
Tests for SSE (Server-Sent Events) Service.

Tests cover:
- SSEJSONEncoder serialization of non-JSON-native types (datetime, date, time, Decimal, Enum)
- SSEEvent serialization with various data types
"""

import json
from datetime import date, datetime, time, timezone
from decimal import Decimal
from enum import Enum

import pytest

from app.services.sse_service import SSEEvent, SSEEventType, SSEJSONEncoder


class TestSSEJSONEncoder:
    """Test the custom JSON encoder for SSE events."""

    def test_datetime_serialization(self):
        """Test that datetime objects are serialized to ISO format strings."""
        dt = datetime(2025, 12, 20, 15, 30, 45, 123456, tzinfo=timezone.utc)
        result = json.dumps({"timestamp": dt}, cls=SSEJSONEncoder)
        data = json.loads(result)
        assert data["timestamp"] == "2025-12-20T15:30:45.123456Z"
        assert isinstance(data["timestamp"], str)

    def test_date_serialization(self):
        """Test that date objects are serialized to ISO format strings."""
        d = date(2025, 12, 20)
        result = json.dumps({"date": d}, cls=SSEJSONEncoder)
        data = json.loads(result)
        assert data["date"] == "2025-12-20"
        assert isinstance(data["date"], str)

    def test_time_serialization(self):
        """Test that time objects are serialized to ISO format strings."""
        t = time(15, 30, 45, 123456)
        result = json.dumps({"time": t}, cls=SSEJSONEncoder)
        data = json.loads(result)
        assert data["time"] == "15:30:45.123456"
        assert isinstance(data["time"], str)

    def test_decimal_serialization(self):
        """Test that Decimal objects are serialized to float."""
        dec = Decimal("123.456789")
        result = json.dumps({"amount": dec}, cls=SSEJSONEncoder)
        data = json.loads(result)
        assert data["amount"] == 123.456789
        assert isinstance(data["amount"], float)

    def test_enum_serialization(self):
        """Test that Enum objects are serialized to their values."""

        class TestEnum(Enum):
            VALUE1 = "value1"
            VALUE2 = "value2"

        result = json.dumps({"status": TestEnum.VALUE1}, cls=SSEJSONEncoder)
        data = json.loads(result)
        assert data["status"] == "value1"
        assert isinstance(data["status"], str)

    def test_sse_event_type_enum_serialization(self):
        """Test that SSEEventType enum is serialized correctly."""
        result = json.dumps({"event_type": SSEEventType.ORDER}, cls=SSEJSONEncoder)
        data = json.loads(result)
        assert data["event_type"] == "order"
        assert isinstance(data["event_type"], str)

    def test_mixed_types_serialization(self):
        """Test serialization of mixed types in a single object."""
        dt = datetime(2025, 12, 20, 15, 30, 45, tzinfo=timezone.utc)
        d = date(2025, 12, 20)
        t = time(15, 30, 45)
        dec = Decimal("99.99")

        class StatusEnum(Enum):
            ACTIVE = "active"

        obj = {
            "timestamp": dt,
            "date": d,
            "time": t,
            "price": dec,
            "status": StatusEnum.ACTIVE,
            "regular_string": "test",
            "regular_int": 42,
            "regular_float": 3.14,
        }

        result = json.dumps(obj, cls=SSEJSONEncoder)
        data = json.loads(result)

        assert data["timestamp"] == "2025-12-20T15:30:45Z"
        assert data["date"] == "2025-12-20"
        assert data["time"] == "15:30:45"
        assert data["price"] == 99.99
        assert data["status"] == "active"
        assert data["regular_string"] == "test"
        assert data["regular_int"] == 42
        assert data["regular_float"] == 3.14

    def test_nested_datetime_serialization(self):
        """Test that datetime objects in nested structures are serialized correctly."""
        dt = datetime(2025, 12, 20, 15, 30, 45, tzinfo=timezone.utc)
        obj = {
            "order": {
                "id": 123,
                "created_at": dt,
                "items": [
                    {"name": "Item 1", "timestamp": dt},
                    {"name": "Item 2", "timestamp": dt},
                ],
            }
        }

        result = json.dumps(obj, cls=SSEJSONEncoder)
        data = json.loads(result)

        assert data["order"]["created_at"] == "2025-12-20T15:30:45Z"
        assert data["order"]["items"][0]["timestamp"] == "2025-12-20T15:30:45Z"
        assert data["order"]["items"][1]["timestamp"] == "2025-12-20T15:30:45Z"

    def test_regular_json_types_unchanged(self):
        """Test that regular JSON-serializable types work as expected."""
        obj = {
            "string": "test",
            "int": 42,
            "float": 3.14,
            "bool": True,
            "none": None,
            "list": [1, 2, 3],
            "dict": {"key": "value"},
        }

        result = json.dumps(obj, cls=SSEJSONEncoder)
        data = json.loads(result)

        assert data["string"] == "test"
        assert data["int"] == 42
        assert data["float"] == 3.14
        assert data["bool"] is True
        assert data["none"] is None
        assert data["list"] == [1, 2, 3]
        assert data["dict"] == {"key": "value"}

    def test_unsupported_type_raises_error(self):
        """Test that unsupported types raise TypeError."""
        obj = {"unsupported": object()}

        with pytest.raises(TypeError):
            json.dumps(obj, cls=SSEJSONEncoder)


class TestSSEEventSerialization:
    """Test SSEEvent serialization with various data types."""

    def test_sse_event_with_datetime_in_data(self):
        """Test that SSEEvent correctly serializes datetime objects in data field."""
        dt = datetime(2025, 12, 20, 15, 30, 45, tzinfo=timezone.utc)
        event = SSEEvent(
            event_type=SSEEventType.RESERVATION,
            subtype="reservation_updated",
            restaurant_id=1,
            data={
                "reservation_id": 123,
                "date_time": dt,
                "status": "confirmed",
            },
        )

        sse_format = event.to_sse_format()
        # Extract the data portion
        lines = sse_format.strip().split("\n")
        data_line = [line for line in lines if line.startswith("data: ")][0]
        json_data = json.loads(data_line[6:])  # Remove "data: " prefix

        assert json_data["data"]["date_time"] == "2025-12-20T15:30:45Z"
        assert isinstance(json_data["data"]["date_time"], str)

    def test_sse_event_with_mixed_types_in_data(self):
        """Test that SSEEvent correctly serializes mixed types in data field."""
        dt = datetime(2025, 12, 20, 15, 30, 45, tzinfo=timezone.utc)
        d = date(2025, 12, 20)
        dec = Decimal("99.99")

        class StatusEnum(Enum):
            ACTIVE = "active"

        event = SSEEvent(
            event_type=SSEEventType.ORDER,
            subtype="order_updated",
            restaurant_id=2,
            data={
                "order_id": 456,
                "created_at": dt,
                "date": d,
                "total_amount": dec,
                "status": StatusEnum.ACTIVE,
                "customer_name": "John Doe",
            },
        )

        sse_format = event.to_sse_format()
        lines = sse_format.strip().split("\n")
        data_line = [line for line in lines if line.startswith("data: ")][0]
        json_data = json.loads(data_line[6:])

        assert json_data["data"]["created_at"] == "2025-12-20T15:30:45Z"
        assert json_data["data"]["date"] == "2025-12-20"
        assert json_data["data"]["total_amount"] == 99.99
        assert json_data["data"]["status"] == "active"
        assert json_data["data"]["customer_name"] == "John Doe"

    def test_sse_event_format_structure(self):
        """Test that SSEEvent produces correctly formatted SSE output."""
        event = SSEEvent(
            event_type=SSEEventType.ORDER,
            subtype="new_order",
            restaurant_id=1,
            data={"order_id": 123, "status": "pending"},
        )

        sse_format = event.to_sse_format()

        # Should have id, event, and data lines
        assert f"id: {event.id}" in sse_format
        assert "event: order" in sse_format
        assert "data: " in sse_format
        assert sse_format.endswith("\n\n")  # SSE format ends with double newline
