"""Static in-memory data used when USE_MOCK_DATA flag is enabled."""

from __future__ import annotations

import copy
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict


def now_iso() -> str:
    return datetime.utcnow().isoformat()


def next_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


MOCK_DATA: Dict[str, Any] = {
    "restaurants": {},
    "menus": {},
    "specials": {},
    "faqs": {},
    "orders": {},
    "order_history": {},
    "reservations": {},
    "calls": {},
    "transcripts": {},
    "users": {},
    "blocklist": set(),
}


def _seed_restaurant() -> None:
    restaurant_id = "mock-restaurant-1"
    MOCK_DATA["restaurants"][restaurant_id] = {
        "restaurant_id": restaurant_id,
        "name": "House of Dosa",
        "cuisine_type": "South Indian",
        "full_address": "123 Mockingbird Lane, Test City",
        "phone_number": "+14313404949",
        "prep_time_minutes": 20,
        "max_party_size": 10,
        "reservation_slot_minutes": 30,
        "reservations_per_slot": 3,
        "service_options": {
            "dine_in": True,
            "takeout": True,
            "delivery": False,
            "reservations": True,
        },
        "hours": {
            "Mon-Thu": "11:00 AM - 9:00 PM",
            "Fri-Sat": "11:00 AM - 10:00 PM",
            "Sun": "12:00 PM - 8:00 PM",
        },
    }

    menu_id = "menu-main"
    MOCK_DATA["menus"][restaurant_id] = [
        {
            "restaurant_id": restaurant_id,
            "menu_id": menu_id,
            "name": "Main Menu",
            "items": [
                {
                    "menu_item_id": "item-1",
                    "name": "Heritage Dosa",
                    "description": "Crispy dosa with traditional chutneys",
                    "price": 12.0,
                    "is_available": True,
                },
                {
                    "menu_item_id": "item-2",
                    "name": "Spiced Paneer Wrap",
                    "description": "Paneer, pickled onions, mint chutney",
                    "price": 14.5,
                    "is_available": True,
                },
            ],
        },
    ]

    MOCK_DATA["specials"][restaurant_id] = [
        {
            "special_id": "special-1",
            "restaurant_id": restaurant_id,
            "name": "Mango Lassi Mocktail",
            "description": "House-made yogurt, mango puree, mint",
            "price": 6.5,
            "is_available": True
        },
    ]

    MOCK_DATA["faqs"][restaurant_id] = [
        {
            "restaurant_id": restaurant_id,
            "faq_id": "faq-1",
            "question": "Do you offer gluten-free options?",
            "answer": "Yes, several dosas can be made gluten-free."
        },
    ]

    order_id = "order-1"
    MOCK_DATA["orders"][order_id] = {
        "order_id": order_id,
        "restaurant_id": restaurant_id,
        "customer_name": "Sam Sample",
        "customer_contact": "+15551231234",
        "items": [
            {"name": "Heritage Dosa", "quantity": 1},
        ],
        "status": "ready",
        "created_at": now_iso(),
    }
    MOCK_DATA["order_history"][order_id] = [
        {"order_id": order_id, "status": "created", "timestamp": now_iso()},
    ]

    reservation_id = "reservation-1"
    MOCK_DATA["reservations"][reservation_id] = {
        "reservation_id": reservation_id,
        "restaurant_id": restaurant_id,
        "reservation_datetime": (datetime.utcnow() + timedelta(hours=4)).isoformat(),
        "party_size": 4,
        "customer_name": "Asjad",
        "customer_contact": "+919650786718",
    }

    call_id = "call-1"
    MOCK_DATA["calls"][call_id] = {
        "call_id": call_id,
        "CALL_METADATA": "dummy",
        "user_id": "demo-user",
        "restaurant_id": restaurant_id,
        "call_status": "completed",
        "started_at": now_iso(),
        "call_duration": 60,
        "cost": 0.05,
    }
    MOCK_DATA["transcripts"][call_id] = [
        {
            "call_id": call_id,
            "message_sequence": 1,
            "speaker": "user",
            "message": "Hi, I'd like to place an order.",
            "timestamp": now_iso(),
        }
    ]

    user_id = "user-1"
    MOCK_DATA["users"][user_id] = {
        "user_id": user_id,
        "restaurant_id": restaurant_id,
        "email": "owner@example.com",
        "role": "admin",
        "permissions": ["calls:read", "orders:manage"],
        "status": "active",
        "created_at": now_iso(),
    }

    MOCK_DATA["blocklist"] = {"+15559999999"}


_seed_restaurant()


def clone(value: Any) -> Any:
    return copy.deepcopy(value)
