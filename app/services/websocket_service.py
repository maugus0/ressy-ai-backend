import asyncio
import base64
import json
import os
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

import websockets
from fastapi import WebSocket, WebSocketDisconnect

from app.agent_fc.config import get_settings as get_fc_settings
from app.agent_fc.functions import conversation, menu, orders, reservations
from app.agent_fc.functions import catalogue as catalogue_functions, business_orders, bookings
from app.agent_fc.functions.function_context import NoArgs
from app.agent_fc.models import AgentFrame
from app.agent_fc.registry import FunctionRegistry
from app.agent_fc.responses import AgentSideEffect
from app.agent_fc.router import FunctionCallRouter
from app.agent_fc.transport import Transport
from app.config import settings
from app.repositories.mysql_user_repo import MySQLUserRepository
from app.services.call_service import CallService
from app.services.callmanager.call_filler import FillerManager
from app.services.callmanager.call_latency import log_agent_audio_start_latency, log_assistant_text_latency
from app.services.callmanager.call_state import StreamState
from app.services.deepgram_service import DeepgramService
from app.services.faq_service import FAQService
from app.services.menu_service import MenuService
from app.services.reservation_service import ReservationService
from app.services.restaurant_service import RestaurantService
from app.services.business_service import BusinessService
from app.services.catalogue_service import CatalogueService
from app.services.booking_service import BookingService
from app.services.business_faq_service import BusinessFAQService
from app.utils import prompt_loader
from app.utils.logging_config import get_logger
from app.utils.restaurant_hours import (
    DAYS_OF_WEEK,
    format_nearest_slot_label,
    format_operating_window,
    is_restaurant_open_now,
    resolve_restaurant_timezone,
)
from app.utils.business_hours import (
    is_business_open_now,
    resolve_business_timezone,
)
from app.utils.timezone import isoformat_z


@dataclass
class CallResources:
    context_payload: Dict[str, Any]
    restaurant_id: Optional[str]
    business_id: Optional[str]
    entity_type: str  # "restaurant" or "business"
    restaurant_phone: Optional[str]
    business_phone: Optional[str]
    restaurant_name: Optional[str]
    business_name: Optional[str]
    deepgram_key_terms: Optional[Any]
    think_prompt: str


class WebSocketService:
    def __init__(self):
        self.logger = get_logger(__name__)
        self.deepgram_service = DeepgramService()
        self.call_service = CallService()
        self.user_repo = MySQLUserRepository()
        self.restaurant_service = RestaurantService()
        self.business_service = BusinessService()
        self.menu_service = MenuService()
        self.catalogue_service = CatalogueService()
        self.faq_service = FAQService()
        self.business_faq_service = BusinessFAQService()
        self.reservation_service = ReservationService()
        self.booking_service = BookingService()
        self._active_twilio: set[WebSocket] = set()
        self._active_deepgram: set[Any] = set()
        self._connections_lock = asyncio.Lock()
        self._filler_manager = FillerManager()

    @staticmethod
    def _normalize_boolean(value: Any) -> bool:
        """
        Normalize a value to a boolean, handling MySQL TINYINT (0/1) and Python booleans.

        Handles:
        - True/False (Python boolean)
        - 0/1 (MySQL TINYINT)
        - None (defaults to False)
        - Other types (safely defaults to False)

        Args:
            value: The value to normalize (can be bool, int, None, or other)

        Returns:
            bool: Normalized boolean value
        """
        if isinstance(value, bool):
            return value
        if value is None:
            return False
        try:
            # Handle MySQL TINYINT (0/1) and other numeric types
            return int(value) == 1
        except (TypeError, ValueError):
            # Handle edge cases (non-numeric strings, etc.) - default to False
            return False

    def _summarize_faqs(self, faqs: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Summarize FAQs to include only question and answer."""
        return [
            {
                "question": faq.get("question"),
                "answer": faq.get("answer"),
            }
            for faq in faqs
        ]

    @staticmethod
    def _format_phone_spoken(phone: Optional[str]) -> Optional[str]:
        if not phone:
            return None
        has_plus = phone.strip().startswith("+")
        digits = [ch for ch in phone if ch.isdigit()]
        if not digits:
            return None
        digit_words = {
            "0": "zero",
            "1": "one",
            "2": "two",
            "3": "three",
            "4": "four",
            "5": "five",
            "6": "six",
            "7": "seven",
            "8": "eight",
            "9": "nine",
        }
        spoken_digits = " ".join(digit_words[d] for d in digits)
        return f"plus {spoken_digits}" if has_plus else spoken_digits

    def _get_nearest_reservation_slot(
        self,
        restaurant_id: Optional[int],
        restaurant: Dict[str, Any],
        now_utc: datetime,
        restaurant_tz,
        reservations_enabled: bool,
        forward_minutes: Optional[int],
    ) -> Optional[Dict[str, Any]]:
        if not restaurant_id or not reservations_enabled:
            return None

        try:
            window_minutes = int(forward_minutes) if forward_minutes else 0
            if window_minutes <= 0:
                window_minutes = 1440

            now_local = now_utc.astimezone(restaurant_tz)
            if now_local.tzinfo:
                now_local = now_local.replace(tzinfo=None)
            window_start = now_local
            window_end = now_local + timedelta(minutes=window_minutes)

            capacity_start = window_start.replace(tzinfo=restaurant_tz).astimezone(timezone.utc).replace(tzinfo=None)
            capacity_end = window_end.replace(tzinfo=restaurant_tz).astimezone(timezone.utc).replace(tzinfo=None)
            capacity_map_utc = self.reservation_service.get_capacity_map(
                restaurant_id=restaurant_id,
                window_start=capacity_start,
                window_end=capacity_end,
            )
            capacity_map: Dict[datetime, int] = {}
            for slot_utc, used in capacity_map_utc.items():
                slot_local = slot_utc.replace(tzinfo=timezone.utc).astimezone(restaurant_tz).replace(tzinfo=None)
                capacity_map[slot_local] = used
            nearest = self.reservation_service.find_nearest_slots(
                restaurant=restaurant,
                requested_start_local=now_local,
                party_size=5,
                window_start=window_start,
                window_end=window_end,
                capacity_map=capacity_map,
                now_utc=now_utc,
            ).get("nearest_forward_slot")
            if not nearest:
                return None
            slot_local = datetime.fromisoformat(nearest.get("datetime"))
            return {
                "nearest_slot_local": format_nearest_slot_label(
                    slot_local=slot_local,
                    now_local=now_local,
                ),
            }
        except Exception as exc:
            self.logger.warning("Failed to compute nearest reservation slot: %s", exc)
            return None

    def _build_restaurant_context(
        self, caller_phone: Optional[str] = None, restaurant_record: Optional[Dict[str, Any]] = None
    ) -> tuple[Dict[str, Any], Optional[str], Optional[str]]:
        restaurant_phone_fwd = (
            (
                restaurant_record.get("escalation_phone_number")
                if (
                    self._normalize_boolean(restaurant_record.get("forward_escalations"))
                    and restaurant_record.get("escalation_phone_number")
                )
                else restaurant_record.get("phone_number")
            )
            if restaurant_record
            else None
        )
        restaurant_id = restaurant_record.get("id") if restaurant_record else None
        if isinstance(restaurant_id, str) and restaurant_id.isdigit():
            restaurant_id = int(restaurant_id)
        restaurant = restaurant_record or {}

        # Get ALL menu items (both available and unavailable) to send to agent
        # This allows agent to inform customers when items are unavailable instead of saying "trouble checking"
        all_menu_items = self.menu_service.menu_repo.get_menus_by_restaurant(restaurant_id) if restaurant_id else []
        item_ids = [item.get("id") for item in all_menu_items if item.get("id") is not None]
        option_group_flags: Dict[int, bool] = {}
        if item_ids:
            try:
                option_group_flags = self.menu_service.menu_repo.get_items_with_option_groups(item_ids)
            except Exception as exc:
                self.logger.warning("Failed to load menu option flags restaurant_id=%s: %s", restaurant_id, exc)

        # Process items in a single pass: separate by availability and build category structures
        # This minimizes iterations for better performance
        available_items: list[dict[str, Any]] = []
        unavailable_items: list[dict[str, Any]] = []
        specials: list[dict[str, Any]] = []
        menu_by_category: Dict[str, list[dict[str, Any]]] = {}
        unavailable_by_category: Dict[str, list[dict[str, Any]]] = {}
        seen_item_ids = set()  # Track item IDs to prevent duplicates

        for item in all_menu_items:
            item_id = item.get("id")
            item_name = item.get("item_name")
            if not item_name:  # Skip items without names
                continue

            # Prevent duplicate items (shouldn't happen, but safety check)
            if item_id in seen_item_ids:
                self.logger.warning("Duplicate item_id=%s found in menu items, skipping", item_id)
                continue
            seen_item_ids.add(item_id)

            has_customizations = option_group_flags.get(item_id, False)
            item_dict = {
                "item_id": item_id,
                "name": item_name,
                "description": item.get("item_desc"),
                "price": float(item.get("price", 0)) if item.get("price") is not None else 0.0,
                "category": item.get("category"),
                "sub_category": item.get("sub_category"),
                "has_customizations": has_customizations,
                "metadata": item.get("metadata"),  # Include metadata for business-specific info (e.g., location for real estate)
            }

            # Check availability (handle both boolean and int 0/1 from MySQL)
            is_available_bool = self._normalize_boolean(item.get("is_available"))

            # Check if special (handle both boolean and int 0/1 from MySQL)
            is_special_bool = self._normalize_boolean(item.get("is_special"))

            if is_special_bool:
                specials.append(item_dict)

            # Build category structures and separate lists in one pass
            category = item.get("category") or "Uncategorized"
            item_summary = {
                "item_id": item_id,
                "name": item_name,
                "price": item_dict["price"],
                "is_special": is_special_bool,  # Mark special items in menu structure
                "has_customizations": has_customizations,
            }

            if is_available_bool:
                available_items.append(item_dict)
                if category not in menu_by_category:
                    menu_by_category[category] = []
                menu_by_category[category].append(item_summary)
            else:
                unavailable_items.append(item_dict)
                if category not in unavailable_by_category:
                    unavailable_by_category[category] = []
                unavailable_by_category[category].append(item_summary)

        # Load FAQs with error handling and summarize to include only question and answer
        faqs = []
        if restaurant_id:
            try:
                raw_faqs = self.faq_service.list_faqs(restaurant_id)
                faqs = self._summarize_faqs(raw_faqs)
            except Exception as exc:
                self.logger.warning("Failed to load FAQs for restaurant_id=%s: %s", restaurant_id, exc)
                faqs = []

        restaurant_name = restaurant.get("name")

        service_options = restaurant.get("service_options") or {}
        if not isinstance(service_options, dict):
            service_options = {}

        raw_features = restaurant.get("features") if isinstance(restaurant.get("features"), dict) else {}
        orders_enabled = (
            self._normalize_boolean(raw_features.get("orders_enabled")) if "orders_enabled" in raw_features else True
        )
        reservations_enabled = (
            self._normalize_boolean(raw_features.get("reservations_enabled"))
            if "reservations_enabled" in raw_features
            else True
        )
        faqs_enabled = (
            self._normalize_boolean(raw_features.get("faqs_enabled")) if "faqs_enabled" in raw_features else True
        )

        # SMS redirect configuration
        orders_sms_redirect = raw_features.get("orders_sms_redirect") or {}
        reservations_sms_redirect = raw_features.get("reservations_sms_redirect") or {}
        orders_sms_redirect_enabled = self._normalize_boolean(orders_sms_redirect.get("enabled"))
        reservations_sms_redirect_enabled = self._normalize_boolean(reservations_sms_redirect.get("enabled"))

        restaurant_tz, timezone_label = resolve_restaurant_timezone(restaurant)
        now_utc = datetime.now(timezone.utc)
        now_local = now_utc.astimezone(restaurant_tz)
        is_open_now = is_restaurant_open_now(restaurant, now_utc=now_utc)
        nearest_reservation_slot: Optional[Dict[str, Any]] = None
        if reservations_enabled:
            nearest_reservation_slot = self._get_nearest_reservation_slot(
                restaurant_id=restaurant_id,
                restaurant=restaurant,
                now_utc=now_utc,
                restaurant_tz=restaurant_tz,
                reservations_enabled=reservations_enabled,
                forward_minutes=restaurant.get("forward_minutes"),
            )

        # Get today's operating hours for agent context
        today_day_name = now_local.strftime("%A").lower()
        today_hours = {
            "day": today_day_name,
            "hours": format_operating_window(restaurant, today_day_name),
        }

        # Build compact weekly hours grouped by identical windows (for agent context)
        weekly_hours = []
        current_bucket = None
        for day in DAYS_OF_WEEK:
            hours_label = format_operating_window(restaurant, day)
            if current_bucket and current_bucket["hours"] == hours_label:
                current_bucket["days"].append(day)
            else:
                current_bucket = {"days": [day], "hours": hours_label}
                weekly_hours.append(current_bucket)

        # Create combined structure showing all items per category with availability status
        # This makes it easier for the agent to see both available and unavailable items together
        # Also includes special items separately for easy identification
        all_items_by_category: Dict[str, Dict[str, list[dict[str, Any]]]] = {}
        specials_by_category: Dict[str, list[dict[str, Any]]] = {}

        # Build specials by category
        for special in specials:
            category = special.get("category") or "Uncategorized"
            if category not in specials_by_category:
                specials_by_category[category] = []
            specials_by_category[category].append(
                {
                    "item_id": special.get("item_id"),
                    "name": special.get("name"),
                    "price": special.get("price"),
                    "has_customizations": special.get("has_customizations", False),
                }
            )

        # Track all special item IDs so we can avoid duplicating them in available/unavailable lists
        special_item_ids = {s.get("item_id") for s in specials if s.get("item_id") is not None}

        all_categories = (
            set(menu_by_category.keys()) | set(unavailable_by_category.keys()) | set(specials_by_category.keys())
        )

        for category in all_categories:
            # Exclude special items from available and unavailable arrays to prevent duplication
            # Special items are already included in the specials array
            available_items = [
                item for item in menu_by_category.get(category, []) if item.get("item_id") not in special_item_ids
            ]
            unavailable_items = [
                item
                for item in unavailable_by_category.get(category, [])
                if item.get("item_id") not in special_item_ids
            ]
            all_items_by_category[category] = {
                "available": available_items,
                "unavailable": unavailable_items,
                "specials": specials_by_category.get(category, []),  # Special items per category
            }

        context = {
            "restaurant_profile": {
                "id": restaurant_id,
                "name": restaurant_name,
                "cuisine": restaurant.get("cuisine_type"),
                "address": restaurant.get("full_address") or restaurant.get("address"),
                "phone": restaurant_phone_fwd,
                "phone_spoken": self._format_phone_spoken(restaurant_phone_fwd),
                "weekly_hours": weekly_hours,
                "today_hours": today_hours,
                "is_open_now": is_open_now,
                "prep_time_minutes": restaurant.get("prep_time_minutes", 20),
            },
            "service_options": {
                "dine_in": service_options.get("dine_in", True),
                "takeout": service_options.get("takeout", True),
                "delivery": service_options.get("delivery", False),
                "reservations": service_options.get("reservations", True),
            },
            "agent_capabilities": {
                "orders": {
                    "enabled": orders_enabled,
                    "sms_redirect": {
                        "enabled": orders_sms_redirect_enabled,
                        "url": orders_sms_redirect.get("redirect_url"),
                    },
                },
                "reservations": {
                    "enabled": reservations_enabled,
                    "sms_redirect": {
                        "enabled": reservations_sms_redirect_enabled,
                        "url": reservations_sms_redirect.get("redirect_url"),
                    },
                },
                "faqs": {"enabled": faqs_enabled},
            },
            "menu_by_category": all_items_by_category,
            "faqs": faqs,
            "current_time": {
                "utc_iso": isoformat_z(now_utc),
                "local_iso": now_local.isoformat(),
                "local_date": now_local.date().isoformat(),
                "timezone": timezone_label,
                "display_time": now_local.strftime("%I:%M %p").lstrip("0"),
                "display_date": now_local.strftime("%A, %B %d, %Y"),
                "day_of_week": now_local.strftime("%A").lower(),
            },
        }
        if reservations_enabled and nearest_reservation_slot:
            context["reservation_availability"] = {
                "nearest_slot": nearest_reservation_slot,
            }
        if caller_phone:
            context["caller_profile"] = {
                "caller_phone": caller_phone,
                "caller_phone_spoken": self._format_phone_spoken(caller_phone),
                "source": "inbound_call",
            }

        # Log menu context loading
        if restaurant_id:
            self.logger.info(
                "[MenuContext] Loaded for restaurant_id=%s: %d available, %d unavailable, %d specials, %d FAQs, restaurant-open: %s",
                restaurant_id,
                len(available_items),
                len(unavailable_items),
                len(specials),
                len(faqs),
                is_open_now,
            )
        return context, restaurant_id, restaurant_name

    def _build_business_context(
        self, caller_phone: Optional[str] = None, business_record: Optional[Dict[str, Any]] = None
    ) -> tuple[Dict[str, Any], Optional[str], Optional[str]]:
        """Build context for business calls (similar to restaurant context)."""
        business_phone_fwd = (
            (
                business_record.get("escalation_phone_number")
                if (
                    self._normalize_boolean(business_record.get("forward_escalations"))
                    and business_record.get("escalation_phone_number")
                )
                else business_record.get("phone_number")
            )
            if business_record
            else None
        )
        business_id = business_record.get("id") if business_record else None
        if isinstance(business_id, str) and business_id.isdigit():
            business_id = int(business_id)
        business = business_record or {}

        # Get ALL catalogue items (both available and unavailable) to send to agent
        all_catalogue_items = self.catalogue_service.catalogue_repo.get_catalogues_by_restaurant(business_id) if business_id else []
        item_ids = [item.get("id") for item in all_catalogue_items if item.get("id") is not None]
        option_group_flags: Dict[int, bool] = {}
        if item_ids:
            try:
                option_group_flags = self.catalogue_service.catalogue_repo.get_catalogue_items_with_option_groups(item_ids)
            except Exception as exc:
                self.logger.warning("Failed to load catalogue option flags business_id=%s: %s", business_id, exc)

        # Process items in a single pass: separate by availability and build category structures
        available_items: list[dict[str, Any]] = []
        unavailable_items: list[dict[str, Any]] = []
        specials: list[dict[str, Any]] = []
        menu_by_category: Dict[str, list[dict[str, Any]]] = {}
        unavailable_by_category: Dict[str, list[dict[str, Any]]] = {}
        seen_item_ids = set()

        for item in all_catalogue_items:
            item_id = item.get("id")
            item_name = item.get("item_name")
            if not item_name:
                continue

            if item_id in seen_item_ids:
                self.logger.warning("Duplicate item_id=%s found in catalogue items, skipping", item_id)
                continue
            seen_item_ids.add(item_id)

            has_customizations = option_group_flags.get(item_id, False)
            item_dict = {
                "item_id": item_id,
                "name": item_name,
                "description": item.get("item_desc"),
                "price": float(item.get("price", 0)) if item.get("price") is not None else 0.0,
                "category": item.get("category"),
                "sub_category": item.get("sub_category"),
                "has_customizations": has_customizations,
                "metadata": item.get("metadata"),  # Include metadata for business-specific info (e.g., location for real estate)
            }

            is_available_bool = self._normalize_boolean(item.get("is_available"))
            is_special_bool = self._normalize_boolean(item.get("is_special"))

            if is_special_bool:
                specials.append(item_dict)

            category = item.get("category") or "Uncategorized"
            item_summary = {
                "item_id": item_id,
                "name": item_name,
                "price": item_dict["price"],
                "is_special": is_special_bool,
                "has_customizations": has_customizations,
            }

            if is_available_bool:
                available_items.append(item_dict)
                if category not in menu_by_category:
                    menu_by_category[category] = []
                menu_by_category[category].append(item_summary)
            else:
                unavailable_items.append(item_dict)
                if category not in unavailable_by_category:
                    unavailable_by_category[category] = []
                unavailable_by_category[category].append(item_summary)

        # Load FAQs
        faqs = []
        if business_id:
            try:
                raw_faqs = self.business_faq_service.list_faqs(business_id)
                faqs = self._summarize_faqs(raw_faqs)
            except Exception as exc:
                self.logger.warning("Failed to load FAQs for business_id=%s: %s", business_id, exc)
                faqs = []

        business_name = business.get("name")

        service_options = business.get("service_options") or {}
        if not isinstance(service_options, dict):
            service_options = {}

        raw_features = business.get("features") if isinstance(business.get("features"), dict) else {}
        orders_enabled = (
            self._normalize_boolean(raw_features.get("orders_enabled")) if "orders_enabled" in raw_features else True
        )
        reservations_enabled = (
            self._normalize_boolean(raw_features.get("reservations_enabled"))
            if "reservations_enabled" in raw_features
            else True
        )
        faqs_enabled = (
            self._normalize_boolean(raw_features.get("faqs_enabled")) if "faqs_enabled" in raw_features else True
        )

        orders_sms_redirect = raw_features.get("orders_sms_redirect") or {}
        reservations_sms_redirect = raw_features.get("reservations_sms_redirect") or {}
        orders_sms_redirect_enabled = self._normalize_boolean(orders_sms_redirect.get("enabled"))
        reservations_sms_redirect_enabled = self._normalize_boolean(reservations_sms_redirect.get("enabled"))

        # Use business_hours utilities
        business_tz, timezone_label = resolve_business_timezone(business)
        now_utc = datetime.now(timezone.utc)
        now_local = now_utc.astimezone(business_tz)
        is_open_now = is_business_open_now(business, now_utc=now_utc)
        nearest_booking_slot: Optional[Dict[str, Any]] = None
        if reservations_enabled:
            # Similar logic for bookings
            nearest_booking_slot = self._get_nearest_reservation_slot(
                restaurant_id=business_id,  # Reuse same method signature
                restaurant=business,
                now_utc=now_utc,
                restaurant_tz=business_tz,
                reservations_enabled=reservations_enabled,
                forward_minutes=business.get("forward_minutes"),
            )

        today_day_name = now_local.strftime("%A").lower()
        today_hours = {
            "day": today_day_name,
            "hours": format_operating_window(business, today_day_name),
        }

        weekly_hours = []
        current_bucket = None
        for day in DAYS_OF_WEEK:
            hours_label = format_operating_window(business, day)
            if current_bucket and current_bucket["hours"] == hours_label:
                current_bucket["days"].append(day)
            else:
                current_bucket = {"days": [day], "hours": hours_label}
                weekly_hours.append(current_bucket)

        all_items_by_category: Dict[str, Dict[str, list[dict[str, Any]]]] = {}
        specials_by_category: Dict[str, list[dict[str, Any]]] = {}

        for special in specials:
            category = special.get("category") or "Uncategorized"
            if category not in specials_by_category:
                specials_by_category[category] = []
            specials_by_category[category].append({
                "item_id": special.get("item_id"),
                "name": special.get("name"),
                "price": special.get("price"),
                "has_customizations": special.get("has_customizations", False),
            })

        special_item_ids = {s.get("item_id") for s in specials if s.get("item_id") is not None}
        all_categories = (
            set(menu_by_category.keys()) | set(unavailable_by_category.keys()) | set(specials_by_category.keys())
        )

        for category in all_categories:
            available_items_cat = [
                item for item in menu_by_category.get(category, []) if item.get("item_id") not in special_item_ids
            ]
            unavailable_items_cat = [
                item for item in unavailable_by_category.get(category, [])
                if item.get("item_id") not in special_item_ids
            ]
            all_items_by_category[category] = {
                "available": available_items_cat,
                "unavailable": unavailable_items_cat,
                "specials": specials_by_category.get(category, []),
            }

        context = {
            "business_profile": {
                "id": business_id,
                "name": business_name,
                "address": business.get("address"),
                "phone": business_phone_fwd,
                "phone_spoken": self._format_phone_spoken(business_phone_fwd),
                "weekly_hours": weekly_hours,
                "today_hours": today_hours,
                "is_open_now": is_open_now,
            },
            "service_options": {
                "dine_in": service_options.get("dine_in", True),
                "takeout": service_options.get("takeout", True),
                "delivery": service_options.get("delivery", False),
                "reservations": service_options.get("reservations", True),
            },
            "agent_capabilities": {
                "orders": {
                    "enabled": orders_enabled,
                    "sms_redirect": {
                        "enabled": orders_sms_redirect_enabled,
                        "url": orders_sms_redirect.get("redirect_url"),
                    },
                },
                "reservations": {
                    "enabled": reservations_enabled,
                    "sms_redirect": {
                        "enabled": reservations_sms_redirect_enabled,
                        "url": reservations_sms_redirect.get("redirect_url"),
                    },
                },
                "faqs": {"enabled": faqs_enabled},
            },
            "menu_by_category": all_items_by_category,
            "faqs": faqs,
            "current_time": {
                "utc_iso": isoformat_z(now_utc),
                "local_iso": now_local.isoformat(),
                "local_date": now_local.date().isoformat(),
                "timezone": timezone_label,
                "display_time": now_local.strftime("%I:%M %p").lstrip("0"),
                "display_date": now_local.strftime("%A, %B %d, %Y"),
                "day_of_week": now_local.strftime("%A").lower(),
            },
        }
        if reservations_enabled and nearest_booking_slot:
            context["reservation_availability"] = {
                "nearest_slot": nearest_booking_slot,
            }
        if caller_phone:
            context["caller_profile"] = {
                "caller_phone": caller_phone,
                "caller_phone_spoken": self._format_phone_spoken(caller_phone),
                "source": "inbound_call",
            }

        if business_id:
            self.logger.info(
                "[CatalogueContext] Loaded for business_id=%s: %d available, %d unavailable, %d specials, %d FAQs, business-open: %s",
                business_id,
                len(available_items),
                len(unavailable_items),
                len(specials),
                len(faqs),
                is_open_now,
            )
        return context, business_id, business_name

    async def shutdown(self) -> None:
        """Close any remaining Twilio or Deepgram connections during app shutdown."""
        async with self._connections_lock:
            closing_tasks = []
            for ws in list(self._active_twilio):
                closing_tasks.append(self._safe_close(ws.close))
                self._active_twilio.discard(ws)
            for conn in list(self._active_deepgram):
                closing_tasks.append(self._safe_close(conn.close))
                self._active_deepgram.discard(conn)
        if closing_tasks:
            await asyncio.gather(*closing_tasks, return_exceptions=True)

    async def _safe_close(self, closer) -> None:
        try:
            result = closer()
            if asyncio.iscoroutine(result):
                await result
        except Exception as exc:
            self.logger.warning("[Shutdown] connection close failed: %s", exc)

    async def _handle_side_effects(
        self,
        side_effects: list[AgentSideEffect],
        sts_ws,
    ) -> dict[str, Optional[str] | bool]:
        """Send side effect messages (e.g., InjectAgentMessage) back to Deepgram."""

        if not side_effects:
            return {"close_requested": False, "farewell_message": None}

        close_requested = False
        last_inject_message: Optional[str] = None

        for effect in side_effects:
            try:
                if effect.delay_seconds > 0:
                    await asyncio.sleep(effect.delay_seconds)
                payload = effect.payload or {}
                effect_type = payload.get("type")
                if effect_type == "InjectAgentMessage":
                    await sts_ws.send(json.dumps(payload))
                    last_inject_message = payload.get("message") or last_inject_message
                    self.logger.info("[FX] InjectAgentMessage sent: %s", payload)
                elif effect_type == "close":
                    close_requested = True
                    self.logger.info("[FX] Close request received from agent function")
                else:
                    await sts_ws.send(json.dumps(payload))
                    self.logger.info("[FX] Side effect forwarded: %s", payload)
            except Exception as exc:
                self.logger.exception("[FX] Failed to process side effect %s: %s", effect.payload, exc)

        if not close_requested:
            last_inject_message = None
        return {"close_requested": close_requested, "farewell_message": last_inject_message}

    async def _graceful_shutdown_call(
        self,
        twilio_ws,
        sts_ws,
        shutdown_event: Optional[asyncio.Event] = None,
        audio_queue: Optional[asyncio.Queue] = None,
    ) -> None:
        """Close Deepgram and Twilio sockets after the farewell finishes."""

        if shutdown_event and not shutdown_event.is_set():
            shutdown_event.set()
        if audio_queue is not None:
            try:
                audio_queue.put_nowait(None)
            except asyncio.QueueFull:
                pass
        self.logger.info("🔚 Farewell finished, closing sockets")
        try:
            await twilio_ws.close()
        except Exception as exc:
            self.logger.warning("[Close] Failed to close Twilio websocket: %s", exc)
        try:
            await sts_ws.close()
        except Exception as exc:
            self.logger.warning("[Close] Failed to close Deepgram websocket: %s", exc)

    async def _handle_unregistered_twilio_call(
        self,
        twilio_ws,
        streamsid_queue: asyncio.Queue,
        shutdown_event: asyncio.Event,
        audio_queue: asyncio.Queue,
    ) -> None:
        """
        Handle calls to Twilio numbers not registered with any restaurant.
        Plays an error message to the caller before disconnecting.
        """
        error_message = settings.UNREGISTERED_TWILIO_MESSAGE
        self.logger.info("Playing unregistered number message: %s", error_message)

        try:
            # Wait for streamSid from Twilio start event
            try:
                streamsid = await asyncio.wait_for(streamsid_queue.get(), timeout=5.0)
            except asyncio.TimeoutError:
                self.logger.warning("Timeout waiting for Twilio streamSid, closing connection")
                return

            # Connect to Deepgram with default API key to play the message
            async with self.deepgram_service.sts_connect() as sts_ws:
                async with self._connections_lock:
                    self._active_deepgram.add(sts_ws)

                try:
                    # Build config with the error message as the greeting
                    # This ensures the error message is spoken immediately
                    config_message = {
                        "type": "Settings",
                        "audio": {
                            "input": {
                                "encoding": settings.DEEPGRAM_AUDIO_INPUT_ENCODING or "mulaw",
                                "sample_rate": settings.DEEPGRAM_AUDIO_INPUT_SAMPLE_RATE or 8000,
                            },
                            "output": {
                                "encoding": settings.DEEPGRAM_AUDIO_OUTPUT_ENCODING or "mulaw",
                                "sample_rate": settings.DEEPGRAM_AUDIO_OUTPUT_SAMPLE_RATE or 8000,
                                "container": settings.DEEPGRAM_AUDIO_OUTPUT_CONTAINER or "none",
                            },
                        },
                        "agent": {
                            "language": settings.DEEPGRAM_AGENT_LANGUAGE,
                            "listen": {
                                "provider": {
                                    "type": "deepgram",
                                    "model": settings.DEEPGRAM_LISTEN_MODEL,
                                    "endpointing": settings.DEEPGRAM_ENDPOINTING_MS,
                                    "interim_results": settings.DEEPGRAM_INTERIM_RESULTS,
                                    "utterance_end_ms": settings.DEEPGRAM_UTTERANCE_END_MS,
                                }
                            },
                            "think": {
                                "provider": {
                                    "type": settings.DEEPGRAM_THINK_PROVIDER_TYPE,
                                    "model": settings.DEEPGRAM_THINK_MODEL,
                                },
                                "prompt": "You are an automated message system. Do not respond to any user input.",
                            },
                            "speak": {
                                "provider": {
                                    "type": "deepgram",
                                    "model": settings.DEEPGRAM_SPEAK_MODEL,
                                }
                            },
                            "greeting": error_message,
                        },
                    }
                    await sts_ws.send(json.dumps(config_message))
                    self.logger.info("Sent config with error message as greeting to Deepgram")

                    # Create a stream state for audio handling
                    state = self._create_stream_state()

                    # Listen for Deepgram responses and forward audio to Twilio
                    audio_done = False
                    start_time = asyncio.get_event_loop().time()
                    timeout_seconds = 15.0  # Max time to wait for message to play

                    async for message in sts_ws:
                        elapsed = asyncio.get_event_loop().time() - start_time
                        if elapsed > timeout_seconds:
                            self.logger.warning("Timeout waiting for error message audio")
                            break

                        if isinstance(message, str):
                            decoded = json.loads(message)
                            msg_type = decoded.get("type")

                            if msg_type == "AgentAudioDone":
                                # Flush remaining audio and mark as done
                                await self._flush_audio_buffer(state, twilio_ws, streamsid)
                                audio_done = True
                                # Give time for audio to play
                                await asyncio.sleep(2.0)
                                break
                            elif msg_type == "ConversationAudio":
                                # Forward audio to Twilio
                                await self._handle_audio_payload(decoded, state, twilio_ws, streamsid)

                        elif isinstance(message, (bytes, bytearray, memoryview)):
                            await self._handle_binary_audio(message, state, twilio_ws, streamsid)

                    if not audio_done:
                        await self._flush_audio_buffer(state, twilio_ws, streamsid)

                finally:
                    async with self._connections_lock:
                        self._active_deepgram.discard(sts_ws)

        except Exception as exc:
            self.logger.exception("[ERROR] Failed to play unregistered number message: %s", exc)

        finally:
            # Signal shutdown and close connections
            shutdown_event.set()
            try:
                audio_queue.put_nowait(None)
            except asyncio.QueueFull:
                pass
            self.logger.info("Closing connection for unregistered Twilio number")

    async def _prepare_call_resources(
        self,
        restaurant_phone: Optional[str],
        caller_phone: Optional[str],
        restaurant_record: Optional[Dict[str, Any]] = None,
        business_record: Optional[Dict[str, Any]] = None,
        entity_type: str = "restaurant",
        deepgram_key_terms: Optional[Any] = None,
    ) -> CallResources:
        if entity_type == "business" and business_record:
            context_payload, business_id, business_name = await asyncio.to_thread(
                self._build_business_context,
                caller_phone,
                business_record,
            )
            # Get business_type from business_record to load appropriate prompt
            business_type = business_record.get("business_type") if isinstance(business_record, dict) else None
            think_prompt = prompt_loader.load_think_prompt(context_payload, business_type=business_type)
            return CallResources(
                context_payload=context_payload,
                restaurant_id=None,
                business_id=business_id,
                entity_type=entity_type,
                restaurant_phone=None,
                business_phone=restaurant_phone,
                restaurant_name=None,
                business_name=business_name,
                deepgram_key_terms=deepgram_key_terms,
                think_prompt=think_prompt,
            )
        else:
            context_payload, restaurant_id, restaurant_name = await asyncio.to_thread(
                self._build_restaurant_context,
                caller_phone,
                restaurant_record,
            )
            think_prompt = prompt_loader.load_think_prompt(context_payload)
            return CallResources(
                context_payload=context_payload,
                restaurant_id=restaurant_id,
                business_id=None,
                entity_type=entity_type,
                restaurant_phone=restaurant_phone,
                business_phone=None,
                restaurant_name=restaurant_name,
                business_name=None,
                deepgram_key_terms=deepgram_key_terms,
                think_prompt=think_prompt,
            )

    def _resolve_user_id(self, caller_phone: Optional[str], provided_user_id: Optional[str]) -> str:
        """
        Resolve a concrete Users.id to store on Calls.
        Uses atomic create_or_update_user to prevent duplicate user entries.
        Preference: find or create user by caller phone, then fallback to provided ID.
        """
        fallback_user_id = str(provided_user_id) if provided_user_id else None

        if caller_phone:
            try:
                # Use atomic create_or_update_user to prevent race conditions
                # This will either find existing user or create new one atomically
                user_id = self.user_repo.create_or_update_user(
                    {
                        "name": None,
                        "phone_number": caller_phone,
                        "email": None,
                        "address": None,
                        "is_spam": False,
                        "credit_card": None,
                    }
                )
                if user_id:
                    return str(user_id)
            except Exception as exc:
                self.logger.warning("Failed to resolve/create user for phone %s: %s", caller_phone, exc)

        if fallback_user_id:
            return fallback_user_id

        # No phone or provided user – use a safe sentinel to avoid breaking FK/analytics
        self.logger.warning("No caller phone or provided user_id; defaulting to user_id=0 for call logging")
        return "0"

    def _build_function_router(
        self, sts_ws, feature_flags: Optional[Dict[str, Any]] = None, entity_type: str = "restaurant"
    ) -> tuple[Transport, FunctionCallRouter]:
        feature_flags = feature_flags or {}
        orders_enabled = bool(feature_flags.get("orders_enabled", True))
        reservations_enabled = bool(feature_flags.get("reservations_enabled", True))
        faqs_enabled = bool(feature_flags.get("faqs_enabled", True))
        menu_enabled = orders_enabled or faqs_enabled
        registry = FunctionRegistry()
        
        if entity_type == "business":
            # Register business-specific functions
            if orders_enabled:
                registry.register(
                    name="create_order",
                    handler=business_orders.create_order,
                    arg_model=business_orders.CreateOrderArgs,
                )
                registry.register(
                    name="lookup_order",
                    handler=business_orders.lookup_order,
                    arg_model=NoArgs,
                )
                registry.register(
                    name="lookup_order_by_id",
                    handler=business_orders.lookup_order_by_id,
                    arg_model=business_orders.LookupOrderByIdArgs,
                )
                registry.register(
                    name="update_order_details",
                    handler=business_orders.update_order_details,
                    arg_model=business_orders.UpdateOrderDetailsArgs,
                )
                registry.register(
                    name="check_items_availability",
                    handler=business_orders.check_items_availability,
                    arg_model=business_orders.CheckItemsAvailabilityArgs,
                )
            if menu_enabled:
                registry.register(
                    name="get_menu_item_details",
                    handler=catalogue_functions.get_catalogue_item_details,
                    arg_model=catalogue_functions.GetCatalogueItemDetailsArgs,
                )
                registry.register(
                    name="get_menu_item_customizations",
                    handler=catalogue_functions.get_catalogue_item_customizations,
                    arg_model=catalogue_functions.GetCatalogueItemCustomizationsArgs,
                )
            if reservations_enabled:
                registry.register(
                    name="create_reservation",
                    handler=bookings.create_booking,
                    arg_model=bookings.CreateBookingArgs,
                )
                registry.register(
                    name="lookup_reservation",
                    handler=bookings.lookup_booking,
                    arg_model=NoArgs,
                )
                registry.register(
                    name="update_reservation",
                    handler=bookings.update_booking,
                    arg_model=bookings.UpdateBookingArgs,
                )
                registry.register(
                    name="check_reservation_availability",
                    handler=bookings.check_booking_availability,
                    arg_model=bookings.CheckAvailabilityArgs,
                )
        else:
            # Register restaurant-specific functions
            if orders_enabled:
                registry.register(
                    name="create_order",
                    handler=orders.create_order,
                    arg_model=orders.CreateOrderArgs,
                )
                registry.register(
                    name="lookup_order",
                    handler=orders.lookup_order,
                    arg_model=NoArgs,
                )
                registry.register(
                    name="lookup_order_by_id",
                    handler=orders.lookup_order_by_id,
                    arg_model=orders.LookupOrderByIdArgs,
                )
                registry.register(
                    name="update_order_details",
                    handler=orders.update_order_details,
                    arg_model=orders.UpdateOrderDetailsArgs,
                )
                registry.register(
                    name="check_items_availability",
                    handler=orders.check_items_availability,
                    arg_model=orders.CheckItemsAvailabilityArgs,
                )
            if menu_enabled:
                registry.register(
                    name="get_menu_item_details",
                    handler=menu.get_menu_item_details,
                    arg_model=menu.GetMenuItemDetailsArgs,
                )
                registry.register(
                    name="get_menu_item_customizations",
                    handler=menu.get_menu_item_customizations,
                    arg_model=menu.GetMenuItemCustomizationsArgs,
                )
            if reservations_enabled:
                registry.register(
                    name="create_reservation",
                    handler=reservations.create_reservation,
                    arg_model=reservations.CreateReservationArgs,
                )
                registry.register(
                    name="lookup_reservation",
                    handler=reservations.lookup_reservation,
                    arg_model=NoArgs,
                )
                registry.register(
                    name="update_reservation",
                    handler=reservations.update_reservation,
                    arg_model=reservations.UpdateReservationArgs,
                )
                registry.register(
                    name="check_reservation_availability",
                    handler=reservations.check_reservation_availability,
                    arg_model=reservations.CheckAvailabilityArgs,
                )
        # registry.register(
        #     name="agent_filler",
        #     handler=conversation.agent_filler,
        #     arg_model=conversation.AgentFillerArgs,
        # )
        registry.register(
            name="end_call",
            handler=conversation.end_call,
            arg_model=conversation.EndCallArgs,
        )
        registry.register(
            name="escalate_to_human",
            handler=conversation.escalate_to_human,
            arg_model=conversation.EscalateToHumanArgs,
        )

        # Register SMS redirect function if enabled for orders or reservations
        orders_sms_redirect_enabled = bool(feature_flags.get("orders_sms_redirect_enabled", False))
        reservations_sms_redirect_enabled = bool(feature_flags.get("reservations_sms_redirect_enabled", False))
        if orders_sms_redirect_enabled or reservations_sms_redirect_enabled:
            registry.register(
                name="send_sms_redirect",
                handler=conversation.send_sms_redirect,
                arg_model=conversation.SendSMSRedirectArgs,
            )

        transport = Transport(send_callable=sts_ws.send)
        router = FunctionCallRouter(
            registry=registry,
            transport=transport,
            settings=get_fc_settings(),
        )
        transport.on_message(router.handle_frame)
        return transport, router

    def _create_call_session(
        self,
        user_id: str,
        restaurant_id: Optional[str],
        twilio_sid: Optional[str],
        deepgram_session_id: Optional[str],
    ) -> Optional[str]:
        try:
            call_id = self.call_service.create_call_session(
                user_id,
                twilio_sid,
                deepgram_session_id,
                restaurant_id,
            )
            self.logger.info("📞 Call session created: %s", call_id)
            return str(call_id)
        except Exception as exc:
            self.logger.exception("[DB] create_call_session error: %s", exc)
            return None

    def _create_stream_state(self) -> StreamState:
        return StreamState()

    def _enqueue_twilio_message(
        self,
        twilio_send_queue: Optional[asyncio.Queue],
        message: str,
        *,
        is_audio: bool = False,
    ) -> bool:
        if not twilio_send_queue:
            return False
        try:
            twilio_send_queue.put_nowait(message)
            return True
        except asyncio.QueueFull:
            try:
                twilio_send_queue.get_nowait()
            except asyncio.QueueEmpty:
                # Queue drained between checks; nothing to drop.
                pass
            try:
                twilio_send_queue.put_nowait(message)
                self.logger.debug("Twilio send queue full; dropped oldest frame")
                return True
            except asyncio.QueueFull:
                if is_audio:
                    self.logger.debug("Twilio send queue full; dropping audio frame")
                else:
                    self.logger.debug("Twilio send queue full; dropping message")
                return False

    def _drain_twilio_send_queue(self, twilio_send_queue: Optional[asyncio.Queue]) -> int:
        if not twilio_send_queue:
            return 0
        drained = 0
        while True:
            try:
                twilio_send_queue.get_nowait()
                drained += 1
            except asyncio.QueueEmpty:
                break
        return drained

    def _get_twilio_chunk_interval(self) -> float:
        env_override = os.getenv("TWILIO_OUTBOUND_PACING_SECONDS")
        if env_override is not None:
            try:
                return max(float(env_override), 0.0)
            except ValueError:
                pass
        sample_rate = getattr(settings, "DEEPGRAM_AUDIO_OUTPUT_SAMPLE_RATE", None)
        encoding = (getattr(settings, "DEEPGRAM_AUDIO_OUTPUT_ENCODING", "") or "").lower()
        buffer_size = getattr(settings, "TWILIO_OUTBOUND_CHUNK_SIZE", 2 * 160)
        bytes_per_sample = 2 if "linear16" in encoding or "pcm" in encoding else 1
        if sample_rate:
            return max(buffer_size / (sample_rate * bytes_per_sample), 0.0)
        return max(getattr(settings, "TWILIO_OUTBOUND_PACING_SECONDS", 0.04), 0.0)

    async def _flush_audio_buffer(
        self,
        state: StreamState,
        twilio_ws,
        streamsid,
        twilio_send_queue: Optional[asyncio.Queue] = None,
    ) -> None:
        if not state.audio_buffer:
            return
        payload = base64.b64encode(state.audio_buffer).decode("ascii")
        msg = {"event": "media", "streamSid": streamsid, "media": {"payload": payload}}
        try:
            msg_json = json.dumps(msg)
            if twilio_send_queue:
                if not self._enqueue_twilio_message(twilio_send_queue, msg_json, is_audio=True):
                    state.audio_buffer.clear()
                    return
                state.last_agent_audio_time = asyncio.get_event_loop().time()
            else:
                await twilio_ws.send_text(msg_json)
                state.last_agent_audio_time = asyncio.get_event_loop().time()
        except Exception as exc:
            self.logger.warning("Error sending buffered audio to Twilio: %s", exc)
        state.audio_buffer.clear()

    async def _wait_for_farewell_playback(self, state: StreamState) -> None:
        """Allow buffered farewell audio to play before closing sockets."""
        grace_seconds = float(getattr(settings, "FAREWELL_PLAYBACK_GRACE_SECONDS", 3.5))
        if grace_seconds <= 0:
            return

        last_audio_time = state.last_agent_audio_time
        if last_audio_time is None:
            await asyncio.sleep(grace_seconds)
            return

        elapsed = asyncio.get_event_loop().time() - last_audio_time
        remaining = grace_seconds - elapsed
        if remaining > 0:
            await asyncio.sleep(remaining)

    async def _call_timeout_guard(
        self,
        timeout_seconds: float,
        sts_ws,
        state: StreamState,
        shutdown_event: Optional[asyncio.Event] = None,
    ) -> None:
        """Inject a timeout message after the configured duration to gracefully end the call."""
        try:
            if shutdown_event:
                try:
                    await asyncio.wait_for(shutdown_event.wait(), timeout_seconds)
                    return
                except asyncio.TimeoutError:
                    pass
            else:
                await asyncio.sleep(timeout_seconds)
        except asyncio.CancelledError:
            return

        if shutdown_event and shutdown_event.is_set():
            return
        if state.closing_after_farewell:
            return

        timeout_message = getattr(
            settings,
            "AGENT_CALL_TIMEOUT_MESSAGE",
            "I have to wrap up this call now. If you need anything else, please call back and I'll get you sorted.",
        )
        payload = {"type": "InjectAgentMessage", "message": timeout_message}
        try:
            await sts_ws.send(json.dumps(payload))
            self.logger.info("[Timeout] Injected graceful timeout message after %.0fs", timeout_seconds)
        except Exception as exc:
            self.logger.warning("[Timeout] Failed to inject timeout message: %s", exc)

        state.closing_after_farewell = True
        state.farewell_started = False
        state.farewell_expected_text = timeout_message

    async def _call_idle_guard(
        self,
        idle_seconds: float,
        sts_ws,
        state: StreamState,
        shutdown_event: Optional[asyncio.Event] = None,
        start_time: Optional[float] = None,
    ) -> None:
        """Monitor inactivity and inject a graceful wrap-up if nobody speaks for too long."""
        check_interval = min(5.0, max(1.0, idle_seconds / 4.0))
        fallback_start = start_time or time.perf_counter()
        has_fired = False

        try:
            while True:
                if shutdown_event and shutdown_event.is_set():
                    return
                if state.closing_after_farewell:
                    return

                await asyncio.sleep(check_interval)
                if shutdown_event and shutdown_event.is_set():
                    return
                if state.closing_after_farewell:
                    return

                activity_time = state.last_activity_time or fallback_start
                elapsed = time.perf_counter() - activity_time
                if elapsed < idle_seconds:
                    continue
                if has_fired:
                    continue

                idle_message = getattr(
                    settings,
                    "AGENT_IDLE_TIMEOUT_MESSAGE",
                    "I'm still here, but I'll need to wrap up this call. If you need anything else, please call back.",
                )
                payload = {"type": "InjectAgentMessage", "message": idle_message}
                try:
                    await sts_ws.send(json.dumps(payload))
                    self.logger.info("[IdleTimeout] Injected idle timeout message after %.0fs", elapsed)
                except Exception as exc:
                    self.logger.warning("[IdleTimeout] Failed to inject idle timeout message: %s", exc)

                state.closing_after_farewell = True
                state.farewell_started = False
                state.farewell_expected_text = idle_message
                has_fired = True
        except asyncio.CancelledError:
            return

    def _update_barge_in_state(self, decoded: dict[str, Any], state: StreamState) -> None:
        event_type = decoded.get("type")
        if event_type == "AgentStartedSpeaking":
            state.agent_speaking = True
            state.awaiting_tool_result = False
        elif event_type == "AgentAudioDone":
            state.agent_speaking = False
            state.barge_in_active = False
            state.awaiting_tool_result = False
        elif event_type == "UserStartedSpeaking":
            state.barge_in_active = True
            state.barge_in_start_time = time.perf_counter()
            state.barge_in_reported = False
            state.audio_buffer.clear()

    async def _handle_audio_payload(
        self,
        decoded: dict[str, Any],
        state: StreamState,
        twilio_ws,
        streamsid,
        twilio_send_queue: Optional[asyncio.Queue] = None,
    ) -> None:
        if decoded.get("type") not in {"ConversationAudio", "AgentAudioDone"}:
            return
        if state.barge_in_active:
            if not state.barge_in_reported and state.barge_in_start_time is not None:
                delta = time.perf_counter() - state.barge_in_start_time
                self.logger.debug("Barge-in suppression delay: %.3fs", delta)
                state.barge_in_reported = True
            return

        audio_payload = decoded.get("audio", "")
        if not audio_payload:
            return
        try:
            now = time.perf_counter()
            audio_bytes = base64.b64decode(audio_payload)
            state.audio_buffer.extend(audio_bytes)
            buffer_size = getattr(settings, "TWILIO_OUTBOUND_CHUNK_SIZE", 2 * 160)
            while len(state.audio_buffer) >= buffer_size:
                chunk = state.audio_buffer[:buffer_size]
                del state.audio_buffer[:buffer_size]
                payload = base64.b64encode(chunk).decode("ascii")
                msg = {"event": "media", "streamSid": streamsid, "media": {"payload": payload}}
                msg_json = json.dumps(msg)
                if twilio_send_queue:
                    if not self._enqueue_twilio_message(twilio_send_queue, msg_json, is_audio=True):
                        continue
                    state.last_agent_audio_time = asyncio.get_event_loop().time()
                else:
                    await twilio_ws.send_text(msg_json)
                    state.last_agent_audio_time = asyncio.get_event_loop().time()
                log_agent_audio_start_latency(state, now)
        except Exception as exc:
            self.logger.warning("Error processing ConversationAudio: %s", exc)

    def _track_conversation_turn(
        self, decoded: dict[str, Any], state: StreamState, now: Optional[float] = None
    ) -> None:
        if decoded.get("type") != "ConversationText":
            return
        current_time = now or time.perf_counter()
        role = decoded.get("role")
        if role == "user":
            state.last_user_text_time = current_time
            state.in_function_chain = False
            if state.barge_in_active:
                state.barge_in_active = False
        elif role == "assistant":
            state.in_function_chain = False
            state.last_assistant_text_time = current_time
            state.agent_audio_latency_logged = False
            state.last_assistant_audio_start_time = None
            state.awaiting_tool_result = False
        state.last_activity_time = current_time

    def _store_transcript_entry(self, decoded: dict[str, Any], call_id: Optional[str], state: StreamState) -> None:
        # Record only live ConversationText events to avoid duplicate transcript entries from History payloads.
        if decoded.get("type") != "ConversationText":
            return
        text = decoded.get("content")
        if not text:
            return
        role = decoded.get("role")
        state.message_seq += 1
        entry = {
            "role": role,
            "content": text,
            "timestamp": isoformat_z(datetime.now(timezone.utc)),
            "sequence": state.message_seq,
        }
        state.conversation_history.append(entry)

    async def _route_function_calls(
        self,
        decoded: dict[str, Any],
        state: StreamState,
        transport: Optional[Transport],
        sts_ws,
    ) -> None:
        if transport is None:
            return
        try:
            frame = AgentFrame.parse(decoded)
        except Exception:
            frame = None
        if not frame or frame.function_call is None:
            return

        now = time.perf_counter()
        state.awaiting_tool_result = True
        if state.in_function_chain and state.last_function_response_time:
            latency = now - state.last_function_response_time
            if settings.LATENCY_LOGS_ENABLED:
                self.logger.debug("LLM Decision Latency (chain): %.3fs", latency)
        elif state.last_user_text_time:
            latency = now - state.last_user_text_time
            if settings.LATENCY_LOGS_ENABLED:
                self.logger.debug("LLM Decision Latency (initial): %.3fs", latency)
            state.in_function_chain = True

        self._filler_manager.schedule(state, sts_ws)
        exec_start = time.perf_counter()
        try:
            router_result = await transport.emit(decoded)
        finally:
            state.awaiting_tool_result = False
            self._filler_manager.cancel(state)
        exec_ms = (time.perf_counter() - exec_start) * 1000.0
        if settings.LATENCY_LOGS_ENABLED:
            self.logger.debug("Function Execution Latency: %.2fms", exec_ms)
        state.last_function_response_time = time.perf_counter()

        if not router_result or not router_result.get("side_effects"):
            return
        effects_meta = await self._handle_side_effects(
            router_result["side_effects"],
            sts_ws,
        )
        if effects_meta.get("close_requested"):
            state.closing_after_farewell = True
            state.farewell_expected_text = effects_meta.get("farewell_message")
            state.farewell_started = state.farewell_expected_text is None
            self.logger.info("[Call] Farewell close scheduled")

    async def _maybe_finish_farewell(
        self,
        decoded: dict[str, Any],
        state: StreamState,
        twilio_ws,
        sts_ws,
        streamsid,
        shutdown_event: Optional[asyncio.Event],
        audio_queue: Optional[asyncio.Queue] = None,
        twilio_send_queue: Optional[asyncio.Queue] = None,
    ) -> bool:
        if not state.closing_after_farewell:
            return False
        event_type = decoded.get("type")
        if event_type == "AgentStartedSpeaking":
            state.farewell_started = True
        elif (
            event_type == "ConversationText"
            and decoded.get("role") == "assistant"
            and state.farewell_expected_text
            and decoded.get("content") == state.farewell_expected_text
        ):
            state.farewell_started = True
        elif event_type == "AgentAudioDone" and state.farewell_started:
            await self._flush_audio_buffer(state, twilio_ws, streamsid, twilio_send_queue)
            await self._wait_for_farewell_playback(state)
            await self._graceful_shutdown_call(twilio_ws, sts_ws, shutdown_event, audio_queue)
            state.farewell_shutdown_complete = True
            return True
        return False

    async def _handle_binary_audio(
        self,
        message: bytes | bytearray | memoryview,
        state: StreamState,
        twilio_ws,
        streamsid,
        twilio_send_queue: Optional[asyncio.Queue] = None,
    ) -> None:
        if state.barge_in_active:
            return
        now = time.perf_counter()
        try:
            state.audio_buffer.extend(message)
        except Exception as exc:
            self.logger.warning("Failed to buffer binary audio payload (%s): %s", type(message), exc)
            return
        # Keep outbound chunks small to reduce playback latency
        buffer_size = getattr(settings, "TWILIO_OUTBOUND_CHUNK_SIZE", 2 * 160)
        while len(state.audio_buffer) >= buffer_size:
            chunk = state.audio_buffer[:buffer_size]
            del state.audio_buffer[:buffer_size]
            payload = base64.b64encode(chunk).decode("ascii")
            msg = {"event": "media", "streamSid": streamsid, "media": {"payload": payload}}
            msg_json = json.dumps(msg)
            if twilio_send_queue:
                if not self._enqueue_twilio_message(twilio_send_queue, msg_json, is_audio=True):
                    continue
                state.last_agent_audio_time = asyncio.get_event_loop().time()
            else:
                await twilio_ws.send_text(msg_json)
                state.last_agent_audio_time = asyncio.get_event_loop().time()
            log_agent_audio_start_latency(state, now)

    async def handle_barge_in(
        self,
        decoded,
        twilio_ws,
        streamsid,
        last_agent_audio_time,
        agent_speaking: bool = False,
        twilio_send_queue: Optional[asyncio.Queue] = None,
    ):
        """Clear Twilio audio when the user interrupts active or recent agent speech."""
        if decoded.get("type") == "UserStartedSpeaking":
            now = asyncio.get_event_loop().time()
            threshold = float(getattr(settings, "BARGE_IN_CLEAR_SECONDS", 0.15))
            recent_audio = bool(last_agent_audio_time) and (now - last_agent_audio_time) <= threshold
            if agent_speaking or recent_audio:
                clear_msg = {"event": "clear", "streamSid": streamsid}
                msg_json = json.dumps(clear_msg)
                if twilio_send_queue:
                    drained = self._drain_twilio_send_queue(twilio_send_queue)
                    if drained:
                        self.logger.debug("Barge-in: dropped %d queued Twilio frames", drained)
                    self._enqueue_twilio_message(twilio_send_queue, msg_json)
                else:
                    await twilio_ws.send_text(msg_json)

    async def handle_text_message(
        self,
        decoded,
        twilio_ws,
        sts_ws,
        streamsid,
        last_agent_audio_time,
        agent_speaking: bool = False,
        twilio_send_queue: Optional[asyncio.Queue] = None,
    ):
        """Handle text messages and barge-in logic."""
        await self.handle_barge_in(
            decoded,
            twilio_ws,
            streamsid,
            last_agent_audio_time,
            agent_speaking,
            twilio_send_queue,
        )

    async def buffer_flusher(
        self,
        shared_buffer: bytearray,
        audio_queue: asyncio.Queue,
        shutdown_event: Optional[asyncio.Event] = None,
        buffer_lock: Optional[asyncio.Lock] = None,
    ) -> None:
        """Periodically flush partial inbound audio to keep Deepgram connection active."""
        flush_interval = getattr(settings, "TWILIO_INBOUND_FLUSH_INTERVAL", 0.15)
        try:
            while True:
                if shutdown_event and shutdown_event.is_set():
                    # Flush remaining buffered audio before exiting
                    if buffer_lock:
                        async with buffer_lock:
                            if shared_buffer:
                                await audio_queue.put(bytes(shared_buffer))
                                shared_buffer.clear()
                    elif shared_buffer:
                        await audio_queue.put(bytes(shared_buffer))
                        shared_buffer.clear()
                    break

                await asyncio.sleep(flush_interval)
                chunk = None
                if buffer_lock:
                    async with buffer_lock:
                        if not shared_buffer:
                            chunk = None
                        else:
                            chunk = bytes(shared_buffer)
                            shared_buffer.clear()
                else:
                    if not shared_buffer:
                        chunk = None
                    else:
                        chunk = bytes(shared_buffer)
                        shared_buffer.clear()
                if chunk:
                    await audio_queue.put(chunk)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            if not shutdown_event or not shutdown_event.is_set():
                self.logger.warning("buffer_flusher error: %s", exc)

    async def twilio_sender(
        self,
        twilio_ws,
        outbound_queue: asyncio.Queue,
        shutdown_event: Optional[asyncio.Event] = None,
    ) -> None:
        """Drain outbound queue and send to Twilio without blocking upstream loops."""
        chunk_interval = self._get_twilio_chunk_interval()
        next_send_time = time.monotonic()
        try:
            while True:
                if shutdown_event and shutdown_event.is_set() and outbound_queue.empty():
                    break
                try:
                    message = await asyncio.wait_for(outbound_queue.get(), timeout=0.5)
                except asyncio.TimeoutError:
                    continue
                if message is None:
                    break
                try:
                    now = time.monotonic()
                    if now < next_send_time:
                        await asyncio.sleep(next_send_time - now)
                    await twilio_ws.send_text(message)
                    now = time.monotonic()
                    next_send_time = max(next_send_time, now) + chunk_interval
                except (WebSocketDisconnect, ConnectionError):
                    self.logger.info("twilio_sender disconnected")
                    break
                except Exception as exc:
                    self.logger.warning("twilio_sender send error: %s", exc)
        except asyncio.CancelledError:
            self.logger.info("twilio_sender cancelled")
            raise

    async def sts_sender(self, sts_ws, audio_queue, shutdown_event: Optional[asyncio.Event] = None):
        """Send audio chunks to Deepgram STS."""
        try:
            while True:
                if shutdown_event and shutdown_event.is_set():
                    break
                try:
                    chunk = await asyncio.wait_for(audio_queue.get(), timeout=0.5)
                except asyncio.TimeoutError:
                    continue
                if chunk is None:
                    break
                await sts_ws.send(chunk)
        except (asyncio.CancelledError, websockets.exceptions.ConnectionClosed):
            self.logger.info("sts_sender stopped")

    async def sts_receiver(
        self,
        sts_ws,
        twilio_ws,
        streamsid_queue,
        call_id=None,
        user_id=None,
        transport: Optional[Transport] = None,
        shutdown_event: Optional[asyncio.Event] = None,
        audio_queue: Optional[asyncio.Queue] = None,
        twilio_send_queue: Optional[asyncio.Queue] = None,
        state: Optional[StreamState] = None,
    ):
        """Receive messages from Deepgram STS and forward to Twilio."""
        streamsid = await streamsid_queue.get()
        start_time = asyncio.get_event_loop().time()
        state = state or self._create_stream_state()
        deepgram_request_id_stored = False

        try:
            async for message in sts_ws:
                if isinstance(message, str):
                    decoded = json.loads(message)
                    message_type = decoded.get("type")
                    now = time.perf_counter()
                    if message_type == "Welcome" and not deepgram_request_id_stored:
                        request_id = decoded.get("request_id") or decoded.get("requestId")
                        if request_id and call_id:
                            try:
                                self.call_service.update_deepgram_request_id(call_id, request_id)
                                deepgram_request_id_stored = True
                            except Exception as exc:
                                self.logger.warning("Error storing Deepgram request_id: %s", exc)
                    if message_type == "History":
                        pass  # Don't print history entries to reduce noise
                    elif message_type == "ConversationText":
                        role = decoded.get("role", "unknown")
                        content = decoded.get("content", "")
                        self.logger.debug("[Call] %s: %s", role, content)
                    elif message_type == "Warning":
                        self.logger.warning("[Deepgram WARNING] : %s", decoded)
                        # If InjectAgentMessage was ignored because agent is speaking,
                        # mark farewell as started so we close after current speech ends
                        warning_code = decoded.get("code", "")
                        if (
                            warning_code == "INJECT_AGENT_MESSAGE_DURING_AGENT_SPEECH"
                            and state.closing_after_farewell
                            and not state.farewell_started
                        ):
                            self.logger.info("[Farewell] InjectAgentMessage ignored - will close after current speech")
                            state.farewell_started = True
                    elif message_type == "Error":
                        self.logger.error("[Deepgram ERROR] : %s", decoded)

                    if message_type == "UserStartedSpeaking":
                        state.last_user_started_speaking_time = now
                        self._filler_manager.cancel(state)
                        state.awaiting_tool_result = False
                    elif message_type == "ConversationText":
                        role = decoded.get("role")
                        self._track_conversation_turn(decoded, state, now)
                        if role == "user":
                            state.awaiting_tool_result = False
                        elif role == "assistant":
                            self._filler_manager.cancel(state)
                            log_assistant_text_latency(state, now)
                    elif message_type in {"ConversationAudio", "AgentAudioDone", "AgentStartedSpeaking"}:
                        self._filler_manager.cancel(state)

                    farewell_finished = await self._maybe_finish_farewell(
                        decoded,
                        state,
                        twilio_ws,
                        sts_ws,
                        streamsid,
                        shutdown_event,
                        audio_queue,
                        twilio_send_queue,
                    )
                    if farewell_finished:
                        break

                    self._update_barge_in_state(decoded, state)
                    await self._handle_audio_payload(decoded, state, twilio_ws, streamsid, twilio_send_queue)
                    await self.handle_text_message(
                        decoded,
                        twilio_ws,
                        sts_ws,
                        streamsid,
                        state.last_agent_audio_time,
                        state.agent_speaking,
                        twilio_send_queue,
                    )
                    await self._route_function_calls(decoded, state, transport, sts_ws)
                    self._store_transcript_entry(decoded, call_id, state)

                    if decoded.get("type") == "AgentAudioDone" and not state.closing_after_farewell:
                        await self._flush_audio_buffer(state, twilio_ws, streamsid, twilio_send_queue)
                        continue

                elif isinstance(message, (bytes, bytearray, memoryview)):
                    await self._handle_binary_audio(message, state, twilio_ws, streamsid, twilio_send_queue)
                else:
                    self.logger.warning("Dropping unexpected Deepgram payload type: %s", type(message))
                    continue

            if not state.farewell_shutdown_complete:
                await self._flush_audio_buffer(state, twilio_ws, streamsid, twilio_send_queue)
        except (websockets.exceptions.ConnectionClosed, websockets.exceptions.ConnectionClosedOK):
            self.logger.info("sts_receiver: Deepgram connection closed")
        except asyncio.CancelledError:
            self.logger.info("sts_receiver cancelled")
            raise
        finally:
            end_time = asyncio.get_event_loop().time()
            duration = int(end_time - start_time)
            self._filler_manager.cancel(state)
            try:
                if call_id:
                    self.call_service.update_call_cost(call_id, duration)
            except Exception as exc:
                self.logger.warning("Error updating call cost: %s", exc)

    async def twilio_receiver(
        self,
        twilio_ws,
        audio_queue,
        streamsid_queue,
        shutdown_event: Optional[asyncio.Event] = None,
        to_number_queue: Optional[asyncio.Queue] = None,
        from_number_queue: Optional[asyncio.Queue] = None,
        call_sid_queue: Optional[asyncio.Queue] = None,
        shared_buffer: Optional[bytearray] = None,
        buffer_lock: Optional[asyncio.Lock] = None,
    ):
        """Receive audio from Twilio and forward to Deepgram."""
        # Smaller buffer reduces turnaround latency (~0.06s chunks)
        buffer_size = getattr(settings, "TWILIO_INBOUND_BUFFER_SIZE", 3 * 160)  # bytes
        inbuffer = shared_buffer if shared_buffer is not None else bytearray()

        try:
            async for message in twilio_ws.iter_text():
                if shutdown_event and shutdown_event.is_set():
                    break
                data = json.loads(message)
                event = data.get("event")

                if event == "start":
                    streamsid = data["start"]["streamSid"]
                    await streamsid_queue.put(streamsid)
                    params = data.get("start", {}).get("customParameters", {}) or {}
                    call_sid = data.get("start", {}).get("callSid")
                    to_number = params.get("toNumber")
                    from_number = params.get("fromNumber")
                    if to_number_queue and to_number:
                        await to_number_queue.put(to_number)
                    if from_number_queue and from_number:
                        await from_number_queue.put(from_number)
                    if call_sid_queue and call_sid:
                        await call_sid_queue.put(call_sid)
                    self.logger.info("📞 Stream started: %s, to=%s, from=%s", streamsid, to_number, from_number)
                elif event == "media":
                    chunk = base64.b64decode(data["media"]["payload"])
                    if data["media"]["track"] == "inbound":
                        if buffer_lock:
                            async with buffer_lock:
                                inbuffer.extend(chunk)
                        else:
                            inbuffer.extend(chunk)
                elif event == "stop":
                    self.logger.info("🛑 Twilio stop event received - closing gracefully")
                    break

                while True:
                    if buffer_lock:
                        async with buffer_lock:
                            if len(inbuffer) < buffer_size:
                                break
                            chunk_to_send = inbuffer[:buffer_size]
                            del inbuffer[:buffer_size]
                    else:
                        if len(inbuffer) < buffer_size:
                            break
                        chunk_to_send = inbuffer[:buffer_size]
                        del inbuffer[:buffer_size]
                    await audio_queue.put(chunk_to_send)

        except (WebSocketDisconnect, ConnectionError) as exc:
            self.logger.info("Twilio receiver disconnected: %s", exc)
        except asyncio.CancelledError:
            self.logger.info("twilio_receiver cancelled")
            raise
        except Exception as e:
            if shutdown_event and shutdown_event.is_set():
                self.logger.info("Twilio receiver closed after shutdown")
            else:
                self.logger.exception("Twilio receiver error: %s", e)
        finally:
            if buffer_lock:
                async with buffer_lock:
                    if inbuffer:
                        await audio_queue.put(bytes(inbuffer))
                        inbuffer.clear()
            elif inbuffer:
                await audio_queue.put(bytes(inbuffer))
                inbuffer.clear()
            if shutdown_event and not shutdown_event.is_set():
                shutdown_event.set()
            try:
                audio_queue.put_nowait(None)
            except asyncio.QueueFull:
                # Best-effort sentinel; queue is already saturated so receiver will exit shortly.
                self.logger.warning("audio_queue full while sending shutdown sentinel")

    async def twilio_websocket_handler(
        self,
        twilio_ws: WebSocket,
        user_id: Optional[str] = None,
        restaurant_twilio_number: Optional[str] = None,
        caller_number: Optional[str] = None,
    ) -> None:
        """Main WebSocket handler for Twilio connections."""

        await twilio_ws.accept()
        async with self._connections_lock:
            self._active_twilio.add(twilio_ws)

        audio_queue: asyncio.Queue = asyncio.Queue()
        streamsid_queue: asyncio.Queue = asyncio.Queue()
        to_number_queue: asyncio.Queue = asyncio.Queue()
        from_number_queue: asyncio.Queue = asyncio.Queue()
        call_sid_queue: asyncio.Queue = asyncio.Queue()
        twilio_send_queue: asyncio.Queue = asyncio.Queue(
            maxsize=getattr(settings, "TWILIO_OUTBOUND_QUEUE_MAXSIZE", 1000)
        )
        shutdown_event = asyncio.Event()
        shared_buffer = bytearray()
        buffer_lock = asyncio.Lock()
        state = self._create_stream_state()
        call_id = None
        call_sid: Optional[str] = None
        transport: Optional[Transport] = None
        restaurant_record: Optional[Dict[str, Any]] = None
        deepgram_api_key: Optional[str] = None
        deepgram_key_terms: Optional[Any] = None
        call_timeout_task: Optional[asyncio.Task] = None
        call_idle_task: Optional[asyncio.Task] = None

        twilio_task = asyncio.create_task(
            self.twilio_receiver(
                twilio_ws,
                audio_queue,
                streamsid_queue,
                shutdown_event,
                to_number_queue,
                from_number_queue,
                call_sid_queue,
                shared_buffer,
                buffer_lock,
            )
        )
        flusher_task = asyncio.create_task(self.buffer_flusher(shared_buffer, audio_queue, shutdown_event, buffer_lock))
        twilio_send_task = asyncio.create_task(self.twilio_sender(twilio_ws, twilio_send_queue, shutdown_event))

        try:
            # Use values provided by API first; fall back to Twilio start event if missing.
            if not restaurant_twilio_number:
                try:
                    restaurant_twilio_number = await asyncio.wait_for(to_number_queue.get(), timeout=0.5)
                except asyncio.TimeoutError:
                    restaurant_twilio_number = None
            if not caller_number:
                try:
                    caller_number = await asyncio.wait_for(from_number_queue.get(), timeout=0.5)
                except asyncio.TimeoutError:
                    caller_number = None
            if not call_sid:
                try:
                    call_sid = await asyncio.wait_for(call_sid_queue.get(), timeout=0.5)
                except asyncio.TimeoutError:
                    call_sid = None

            # Try restaurant first, then business
            restaurant_record = self.restaurant_service.get_restaurant_by_twilio(restaurant_twilio_number)
            business_record = None
            entity_type = "restaurant"
            
            if not restaurant_record:
                business_record = self.business_service.get_business_by_twilio(restaurant_twilio_number)
                if business_record:
                    entity_type = "business"
                    self.logger.info("Serving call for business: %s", business_record.get("name"))
                else:
                    self.logger.error("[FATAL ERROR] No restaurant or business found with twilio number: %s", restaurant_twilio_number)
                    await self._handle_unregistered_twilio_call(twilio_ws, streamsid_queue, shutdown_event, audio_queue)
                    return
            else:
                self.logger.info("Serving call for restaurant: %s", restaurant_record.get("name"))

            entity_record = restaurant_record if entity_type == "restaurant" else business_record
            deepgram_details = entity_record.get("deepgram_details") if entity_record else None
            if isinstance(deepgram_details, str):
                try:
                    deepgram_details = json.loads(deepgram_details)
                except json.JSONDecodeError:
                    deepgram_details = None
            if isinstance(deepgram_details, dict):
                deepgram_api_key = deepgram_details.get("api_key") or deepgram_details.get("apiKey")
                deepgram_key_terms = deepgram_details.get("key_terms") or deepgram_details.get("keyTerms")
                if isinstance(deepgram_api_key, str):
                    deepgram_api_key = deepgram_api_key.strip() or None

            call_resources = await self._prepare_call_resources(
                restaurant_twilio_number, caller_number, restaurant_record, business_record, entity_type, deepgram_key_terms
            )

            try:
                async with self.deepgram_service.sts_connect(api_key=deepgram_api_key) as sts_ws:
                    async with self._connections_lock:
                        self._active_deepgram.add(sts_ws)

                    try:
                        self.logger.info("🔗 Connected to Deepgram STS")
                        raw_features = entity_record.get("features") if entity_record else {}
                        # Flatten feature_flags for function definitions and router
                        orders_sms = raw_features.get("orders_sms_redirect") or {}
                        reservations_sms = raw_features.get("reservations_sms_redirect") or {}
                        feature_flags = {
                            "orders_enabled": raw_features.get("orders_enabled", True),
                            "reservations_enabled": raw_features.get("reservations_enabled", True),
                            "faqs_enabled": raw_features.get("faqs_enabled", True),
                            "orders_sms_redirect_enabled": orders_sms.get("enabled", False),
                            "reservations_sms_redirect_enabled": reservations_sms.get("enabled", False),
                        }
                        entity_name = call_resources.restaurant_name if entity_type == "restaurant" else call_resources.business_name
                        config_message = self.deepgram_service.load_config(
                            think_prompt=call_resources.think_prompt,
                            key_terms=call_resources.deepgram_key_terms or None,
                            restaurant_name=entity_name,
                            feature_flags=feature_flags,
                        )
                        config_message_json = json.dumps(config_message)
                        await sts_ws.send(config_message_json)

                        transport, router = self._build_function_router(sts_ws, feature_flags, entity_type)
                        resolved_user_id = self._resolve_user_id(caller_number, user_id)
                        entity_id = call_resources.restaurant_id if entity_type == "restaurant" else call_resources.business_id
                        call_id = self._create_call_session(
                            resolved_user_id, entity_id, call_sid, None
                        )
                        # Build default arguments, only including customer_contact if available
                        # to avoid validation errors when caller ID is blocked/unavailable
                        default_args = {
                            "user_id": resolved_user_id,
                            "call_id": call_id,
                            "call_sid": call_sid,
                            "customization_progress_by_item": state.customization_progress_by_item,
                            "order_session_state": state.order_session_state,
                        }
                        if entity_type == "restaurant":
                            default_args["restaurant_id"] = call_resources.restaurant_id
                        else:
                            default_args["business_id"] = call_resources.business_id
                        if caller_number:
                            default_args["customer_contact"] = caller_number
                        router.set_default_arguments(default_args)

                        timeout_seconds = float(getattr(settings, "AGENT_CALL_TIMEOUT_SECONDS", 900))
                        call_timeout_task = asyncio.create_task(
                            self._call_timeout_guard(timeout_seconds, sts_ws, state, shutdown_event)
                        )
                        idle_seconds = float(getattr(settings, "AGENT_IDLE_TIMEOUT_SECONDS", 60))
                        call_idle_task = asyncio.create_task(
                            self._call_idle_guard(
                                idle_seconds,
                                sts_ws,
                                state,
                                shutdown_event,
                                start_time=time.perf_counter(),
                            )
                        )

                        sts_sender_task = asyncio.create_task(self.sts_sender(sts_ws, audio_queue, shutdown_event))
                        sts_receiver_task = asyncio.create_task(
                            self.sts_receiver(
                                sts_ws,
                                twilio_ws,
                                streamsid_queue,
                                call_id,
                                user_id,
                                transport,
                                shutdown_event,
                                audio_queue,
                                twilio_send_queue,
                                state,
                            )
                        )

                        tasks = [
                            twilio_task,
                            flusher_task,
                            sts_sender_task,
                            sts_receiver_task,
                            twilio_send_task,
                        ]
                        try:
                            done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
                            # Signal shutdown to remaining tasks and drain queues
                            shutdown_event.set()
                            try:
                                audio_queue.put_nowait(None)
                            except asyncio.QueueFull:
                                pass
                            try:
                                twilio_send_queue.put_nowait(None)
                            except asyncio.QueueFull:
                                pass
                            for task in pending:
                                task.cancel()
                            await asyncio.gather(*tasks, return_exceptions=True)
                            if call_timeout_task:
                                await asyncio.gather(call_timeout_task, return_exceptions=True)
                            if call_idle_task:
                                await asyncio.gather(call_idle_task, return_exceptions=True)
                        finally:
                            for task in tasks:
                                if not task.done():
                                    task.cancel()
                            await asyncio.gather(*tasks, return_exceptions=True)
                            if call_timeout_task:
                                if not call_timeout_task.done():
                                    call_timeout_task.cancel()
                                await asyncio.gather(call_timeout_task, return_exceptions=True)
                            if call_idle_task:
                                if not call_idle_task.done():
                                    call_idle_task.cancel()
                                await asyncio.gather(call_idle_task, return_exceptions=True)
                    finally:
                        async with self._connections_lock:
                            self._active_deepgram.discard(sts_ws)
            except websockets.exceptions.InvalidStatusCode as exc:
                if exc.status_code == 401:
                    self.logger.error(
                        "[Deepgram] Unauthorized (401). Check that DEEPGRAM_API_KEY is valid "
                        "for the restaurant or environment."
                    )
                raise
        except WebSocketDisconnect:
            self.logger.info("Client disconnected")
        except Exception as e:
            self.logger.exception("Error in twilio_websocket_handler: %s", e)
        finally:
            if shutdown_event and not shutdown_event.is_set():
                shutdown_event.set()
            try:
                audio_queue.put_nowait(None)
            except asyncio.QueueFull:
                pass
            try:
                twilio_send_queue.put_nowait(None)
            except asyncio.QueueFull:
                pass

            # Ensure background tasks are stopped
            for task in (twilio_task, flusher_task, twilio_send_task):
                if task and not task.done():
                    task.cancel()
            await asyncio.gather(twilio_task, flusher_task, twilio_send_task, return_exceptions=True)
            if call_timeout_task:
                if not call_timeout_task.done():
                    call_timeout_task.cancel()
                await asyncio.gather(call_timeout_task, return_exceptions=True)
            if call_idle_task:
                if not call_idle_task.done():
                    call_idle_task.cancel()
                await asyncio.gather(call_idle_task, return_exceptions=True)

            async with self._connections_lock:
                self._active_twilio.discard(twilio_ws)
            try:
                await twilio_ws.close()
            except Exception:
                pass

            if state.conversation_history and call_id:
                try:
                    self.call_service.save_call_transcript(call_id, state.conversation_history)
                    self.logger.info("Transcript stored to Calls.call_transcript")
                except Exception as exc:
                    self.logger.warning("Failed to store call transcript: %s", exc)

            self.logger.info("🔌 Twilio connection closed")
