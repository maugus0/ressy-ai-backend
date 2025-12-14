from __future__ import annotations

import copy
import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple


class InMemoryRestaurantRepository:
    """Lightweight in-memory restaurant repo used for tests."""

    def __init__(self, faq_repo: "InMemoryFAQRepository | None" = None):
        self._restaurants: Dict[int, Dict[str, Any]] = {}
        self._counter = 0
        self._faq_repo = faq_repo
        self._stats: Dict[int, Dict[str, Any]] = {}

    def add(self, restaurant_id: int, name: str = "Test Restaurant") -> Dict[str, Any]:
        restaurant = {
            "id": restaurant_id,
            "name": name,
            "address": None,
            "phone_number": None,
            "twilio_phone_number": None,
            "twilio_details": None,
            "deepgram_details": None,
            "open_table_details": None,
            "forward_minutes": 0,
            "backward_minutes": 0,
            "is_credit_card_required_for_reservation": False,
            "opening_time": "09:00:00",
            "closing_time": "22:00:00",
            "created_at": None,
            "updated_at": None,
        }
        self._restaurants[restaurant_id] = restaurant
        self._counter = max(self._counter, restaurant_id)
        return restaurant

    def create(self, data: Dict[str, Any]) -> int:
        self._counter += 1
        restaurant_id = self._counter
        restaurant = {
            "id": restaurant_id,
            "name": data.get("name"),
            "address": data.get("address"),
            "phone_number": data.get("phone_number"),
            "twilio_phone_number": data.get("twilio_phone_number"),
            "twilio_details": data.get("twilio_details"),
            "deepgram_details": data.get("deepgram_details"),
            "open_table_details": data.get("open_table_details"),
            "forward_minutes": data.get("forward_minutes", 0),
            "backward_minutes": data.get("backward_minutes", 0),
            "is_credit_card_required_for_reservation": data.get("is_credit_card_required_for_reservation", False),
            "opening_time": data.get("opening_time", "09:00:00"),
            "closing_time": data.get("closing_time", "22:00:00"),
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        }
        self._restaurants[restaurant_id] = restaurant
        return restaurant_id

    def get_by_id(self, restaurant_id: int) -> Dict[str, Any]:
        return copy.deepcopy(self._restaurants.get(restaurant_id, {}))

    def get_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        for restaurant in self._restaurants.values():
            if restaurant.get("name") == name:
                return copy.deepcopy(restaurant)
        return None

    def get_by_phone(self, phone_number: str) -> Optional[Dict[str, Any]]:
        for restaurant in self._restaurants.values():
            if restaurant.get("phone_number") == phone_number:
                return copy.deepcopy(restaurant)
        return None

    def get_by_twilio_number(self, twilio_phone_number: str) -> Optional[Dict[str, Any]]:
        for restaurant in self._restaurants.values():
            if restaurant.get("twilio_phone_number") == twilio_phone_number:
                return copy.deepcopy(restaurant)
        return None

    def get_all(
        self,
        page: int = 1,
        limit: int = 20,
        search: Optional[str] = None,
        is_credit_card_required: Optional[bool] = None,
    ) -> Tuple[List[Dict[str, Any]], int]:
        restaurants = list(self._restaurants.values())
        if search:
            restaurants = [r for r in restaurants if search.lower() in r["name"].lower()]
        if is_credit_card_required is not None:
            restaurants = [
                r for r in restaurants if r.get("is_credit_card_required_for_reservation") == is_credit_card_required
            ]
        restaurants.sort(key=lambda r: r["id"], reverse=True)
        total = len(restaurants)
        start = (page - 1) * limit
        end = start + limit
        return [copy.deepcopy(r) for r in restaurants[start:end]], total

    def update(self, restaurant_id: int, data: Dict[str, Any]) -> bool:
        restaurant = self._restaurants.get(restaurant_id)
        if not restaurant:
            return False
        restaurant.update(data)
        restaurant["updated_at"] = datetime.now(timezone.utc)
        self._restaurants[restaurant_id] = restaurant
        return True

    def delete(self, restaurant_id: int) -> int:
        removed = self._restaurants.pop(restaurant_id, None)
        if removed and self._faq_repo:
            self._faq_repo.delete_by_restaurant(restaurant_id)
        return 1 if removed else 0

    def get_statistics(self, restaurant_id: int) -> Dict[str, Any]:
        return copy.deepcopy(self._stats.get(restaurant_id, {}))


class InMemoryCallRepository:
    """In-memory call repository for API/service tests."""

    def __init__(self, calls: Optional[List[Dict[str, Any]]] = None):
        self._calls: Dict[int, Dict[str, Any]] = {}
        for call in calls or []:
            cid = int(call.get("id"))
            self._calls[cid] = copy.deepcopy(call)

    def list_calls(
        self,
        restaurant_id: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        status: Optional[str] = None,
        duration_min: Optional[int] = None,
        duration_max: Optional[int] = None,
        caller_phone: Optional[str] = None,
        page: int = 1,
        limit: int = 20,
        sort_by: str = "created_at",
        sort_order: str = "desc",
        search_term: Optional[str] = None,
    ) -> Tuple[List[Dict[str, Any]], int]:
        calls = list(self._calls.values())
        if restaurant_id is not None:
            calls = [c for c in calls if str(c.get("restaurant_id")) == str(restaurant_id)]
        if status:
            calls = [c for c in calls if c.get("call_status") == status]
        if duration_min is not None:
            calls = [c for c in calls if (c.get("call_duration") or 0) >= duration_min]
        if duration_max is not None:
            calls = [c for c in calls if (c.get("call_duration") or 0) <= duration_max]
        if caller_phone:
            calls = [c for c in calls if caller_phone in str(c.get("caller_phone", ""))]
        if search_term:
            filtered: List[Dict[str, Any]] = []
            for c in calls:
                transcript = c.get("call_transcript")
                if transcript:
                    try:
                        payload = json.loads(transcript)
                        conversation = payload.get("conversation", [])
                    except (json.JSONDecodeError, TypeError):
                        conversation = []
                    if any(search_term.lower() in (entry.get("content", "").lower()) for entry in conversation):
                        filtered.append(c)
                        continue
                if search_term.lower() in str(c.get("caller_phone", "")).lower():
                    filtered.append(c)
            calls = filtered

        total = len(calls)
        start = (page - 1) * limit
        end = start + limit
        rows = []
        for c in calls[start:end]:
            row = copy.deepcopy(c)
            row["has_transcript"] = bool(row.get("call_transcript"))
            rows.append(row)
        return rows, total

    def get_call_by_id(self, call_id: int) -> Optional[Dict[str, Any]]:
        call = self._calls.get(int(call_id))
        if not call:
            return None
        row = copy.deepcopy(call)
        row["restaurant_name"] = call.get("restaurant_name")
        return row

    def update_call_transcript(self, call_id: int, conversation: List[Dict[str, Any]]) -> None:
        call = self._calls.get(int(call_id))
        if call is None:
            return
        call["call_transcript"] = json.dumps({"conversation": conversation})

    def delete_call(self, call_id: int) -> int:
        removed = self._calls.pop(int(call_id), None)
        return 1 if removed else 0

    def delete_call_transcript(self, call_id: int) -> int:
        call = self._calls.get(int(call_id))
        if not call:
            return 0
        call["call_transcript"] = None
        return 1

    def get_call_analytics(
        self,
        restaurant_id: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
    ) -> Dict[str, Any]:
        calls = list(self._calls.values())
        if restaurant_id is not None:
            calls = [c for c in calls if str(c.get("restaurant_id")) == str(restaurant_id)]
        total_calls = len(calls)
        total_duration = sum(c.get("call_duration", 0) or 0 for c in calls)
        avg_duration = total_duration / total_calls if total_calls else 0
        status_breakdown: Dict[str, int] = {}
        for c in calls:
            status = c.get("call_status") or "unknown"
            status_breakdown[status] = status_breakdown.get(status, 0) + 1
        return {
            "total_calls": total_calls,
            "average_call_duration": avg_duration,
            "total_duration": total_duration,
            "status_breakdown": status_breakdown,
            "time_of_day_distribution": [],
            "top_restaurants": [],
            "calls_by_day_of_week": [],
        }


class InMemoryFAQRepository:
    """In-memory FAQ repository with basic search and pagination for tests."""

    def __init__(self):
        self._faqs: Dict[int, Dict[str, Any]] = {}
        self._by_restaurant: Dict[int, List[Dict[str, Any]]] = {}
        self._counter = 0

    def _now(self):
        return datetime.now(timezone.utc)

    def _clone(self, item: Dict[str, Any]) -> Dict[str, Any]:
        return copy.deepcopy(item)

    def get_by_restaurant(self, restaurant_id: int, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        faqs = sorted(self._by_restaurant.get(restaurant_id, []), key=lambda x: x["created_at"], reverse=True)
        if limit is not None:
            faqs = faqs[:limit]
        return [self._clone(faq) for faq in faqs]

    def get_by_restaurant_and_question(
        self, restaurant_id: int, question: str, exclude_id: Optional[int] = None
    ) -> Optional[Dict[str, Any]]:
        faqs = self._by_restaurant.get(restaurant_id, [])
        for faq in faqs:
            if faq["question"].lower() == question.lower() and (exclude_id is None or faq["id"] != exclude_id):
                return self._clone(faq)
        return None

    def get_paginated_by_restaurant(
        self, restaurant_id: int, page: int, limit: int, search: Optional[str]
    ) -> Tuple[List[Dict[str, Any]], int]:
        faqs = self.get_by_restaurant(restaurant_id)
        if search:
            query = search.lower()
            faqs = [f for f in faqs if query in f["question"].lower() or query in f["answer"].lower()]
        total = len(faqs)
        start = (page - 1) * limit
        end = start + limit
        return faqs[start:end], total

    def search_all(self, search: str, page: int, limit: int) -> Tuple[List[Dict[str, Any]], int]:
        query = search.lower()
        faqs = [self._clone(faq) for faq in sorted(self._faqs.values(), key=lambda x: x["created_at"], reverse=True)]
        faqs = [f for f in faqs if query in f["question"].lower() or query in f["answer"].lower()]
        total = len(faqs)
        start = (page - 1) * limit
        end = start + limit
        return faqs[start:end], total

    def get_by_id(self, faq_id: int) -> Dict[str, Any]:
        return self._clone(self._faqs.get(faq_id, {}))

    def get_by_id_scoped(self, faq_id: int, restaurant_id: int) -> Dict[str, Any]:
        faq = self._faqs.get(faq_id)
        if not faq or faq.get("restaurant_id") != restaurant_id:
            return {}
        return self._clone(faq)

    def create(self, restaurant_id: int, data: Dict[str, Any]) -> Dict[str, Any]:
        self._counter += 1
        now = self._now()
        faq = {
            "id": self._counter,
            "restaurant_id": restaurant_id,
            "question": data.get("question"),
            "answer": data.get("answer"),
            "created_at": now,
            "updated_at": now,
        }
        self._faqs[faq["id"]] = faq
        self._by_restaurant.setdefault(restaurant_id, []).append(faq)
        return self._clone(faq)

    def bulk_create(self, restaurant_id: int, faqs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        staged = []
        for data in faqs:
            self._counter += 1
            now = self._now()
            faq = {
                "id": self._counter,
                "restaurant_id": restaurant_id,
                "question": data.get("question"),
                "answer": data.get("answer"),
                "created_at": now,
                "updated_at": now,
            }
            staged.append(faq)

        # Commit staged
        for faq in staged:
            self._faqs[faq["id"]] = faq
            self._by_restaurant.setdefault(restaurant_id, []).append(faq)

        return [self._clone(faq) for faq in sorted(staged, key=lambda x: x["created_at"], reverse=True)]

    def update(self, faq_id: int, data: Dict[str, Any]) -> Dict[str, Any]:
        faq = self._faqs.get(faq_id)
        if not faq:
            return {}
        faq.update(data)
        faq["updated_at"] = self._now()
        return self._clone(faq)

    def update_scoped(self, faq_id: int, restaurant_id: int, data: Dict[str, Any]) -> Dict[str, Any]:
        faq = self._faqs.get(faq_id)
        if not faq or faq.get("restaurant_id") != restaurant_id:
            return {}
        return self.update(faq_id, data)

    def delete(self, faq_id: int) -> int:
        faq = self._faqs.pop(faq_id, None)
        if not faq:
            return 0
        restaurant_id = faq["restaurant_id"]
        self._by_restaurant[restaurant_id] = [
            f for f in self._by_restaurant.get(restaurant_id, []) if f["id"] != faq_id
        ]
        return 1

    def delete_scoped(self, faq_id: int, restaurant_id: int) -> int:
        faq = self._faqs.get(faq_id)
        if not faq or faq.get("restaurant_id") != restaurant_id:
            return 0
        return self.delete(faq_id)

    def delete_by_restaurant(self, restaurant_id: int) -> int:
        faqs = self._by_restaurant.pop(restaurant_id, [])
        for faq in faqs:
            self._faqs.pop(faq["id"], None)
        return len(faqs)


class InMemoryMenuRepository:
    """In-memory menu repository used for client/admin menu tests."""

    def __init__(self, restaurant_repo: InMemoryRestaurantRepository | None = None):
        self._menus: Dict[int, Dict[str, Any]] = {}
        self._counter = 0
        self.restaurant_repo = restaurant_repo

    def _now(self):
        return datetime.now(timezone.utc)

    def _clone(self, item: Dict[str, Any]) -> Dict[str, Any]:
        return copy.deepcopy(item)

    def create_menu(self, restaurant_id: int, data: Dict[str, Any]) -> int:
        self._counter += 1
        menu_id = self._counter
        record = {
            "id": menu_id,
            "restaurant_id": restaurant_id,
            "category": data.get("category"),
            "sub_category": data.get("sub_category"),
            "item_name": data.get("item_name"),
            "item_desc": data.get("item_desc"),
            "price": data.get("price", 0.0),
            "avg_prep_time": data.get("avg_prep_time"),
            "suggested_items": list(data.get("suggested_items") or []),
            "is_available": True if data.get("is_available") is None else data.get("is_available"),
            "is_special": False if data.get("is_special") is None else data.get("is_special"),
            "created_at": self._now(),
            "updated_at": self._now(),
        }
        # Enrich with restaurant name for convenience
        if self.restaurant_repo:
            restaurant = self.restaurant_repo.get_by_id(restaurant_id)
            record["restaurant_name"] = restaurant.get("name") if restaurant else None
        self._menus[menu_id] = record
        return menu_id

    def get_by_id(self, menu_id: int) -> Optional[Dict[str, Any]]:
        return self._clone(self._menus.get(menu_id, {}))

    def get_menu_by_id(self, restaurant_id: int, menu_id: int) -> Dict[str, Any]:
        item = self._menus.get(menu_id)
        if not item or item.get("restaurant_id") != restaurant_id:
            return {}
        return self._clone(item)

    def item_name_exists(self, restaurant_id: int, item_name: str, exclude_menu_id: Optional[int] = None) -> bool:
        for menu in self._menus.values():
            if menu.get("restaurant_id") != restaurant_id:
                continue
            if exclude_menu_id and menu.get("id") == exclude_menu_id:
                continue
            if (menu.get("item_name") or "").strip().lower() == (item_name or "").strip().lower():
                return True
        return False

    def validate_suggested_items(self, menu_item_ids: List[int]) -> bool:
        return all(item_id in self._menus for item_id in menu_item_ids)

    def validate_suggested_items_belong_to_restaurant(self, menu_item_ids: List[int], restaurant_id: int) -> bool:
        return all(self._menus.get(item_id, {}).get("restaurant_id") == restaurant_id for item_id in menu_item_ids)

    def get_paginated_by_restaurant(
        self,
        restaurant_id: int,
        page: int = 1,
        limit: int = 50,
        category: Optional[str] = None,
        sub_category: Optional[str] = None,
        is_available: Optional[bool] = None,
        is_special: Optional[bool] = None,
        search: Optional[str] = None,
    ) -> Tuple[List[Dict], int]:
        items = [self._clone(m) for m in self._menus.values() if m.get("restaurant_id") == restaurant_id]
        if category is not None:
            items = [i for i in items if i.get("category") == category]
        if sub_category is not None:
            items = [i for i in items if i.get("sub_category") == sub_category]
        if is_available is not None:
            items = [i for i in items if i.get("is_available") == is_available]
        if is_special is not None:
            items = [i for i in items if i.get("is_special") == is_special]
        if search:
            query = search.lower()
            items = [i for i in items if query in (i.get("item_name") or "").lower()]
        items.sort(key=lambda i: i["id"])
        total = len(items)
        start = (page - 1) * limit
        end = start + limit
        return items[start:end], total

    def update_by_id(self, menu_id: int, data: Dict[str, Any]) -> int:
        item = self._menus.get(menu_id)
        if not item:
            return 0
        for key, value in data.items():
            item[key] = value
        item["updated_at"] = self._now()
        self._menus[menu_id] = item
        return 1

    def update_menu(self, restaurant_id: int, menu_id: int, data: Dict[str, Any]) -> int:
        item = self._menus.get(menu_id)
        if not item or item.get("restaurant_id") != restaurant_id:
            return 0
        return self.update_by_id(menu_id, data)

    def delete_by_id(self, menu_id: int) -> int:
        removed = self._menus.pop(menu_id, None)
        return 1 if removed else 0

    def delete_menu(self, restaurant_id: int, menu_id: int) -> int:
        item = self._menus.get(menu_id)
        if not item or item.get("restaurant_id") != restaurant_id:
            return 0
        return self.delete_by_id(menu_id)

    def items_exist(self, menu_item_ids: List[int]) -> bool:
        return all(item_id in self._menus for item_id in menu_item_ids)

    def verify_items_belong_to_restaurant(self, menu_item_ids: List[int], restaurant_id: int) -> bool:
        return all(self._menus.get(item_id, {}).get("restaurant_id") == restaurant_id for item_id in menu_item_ids)

    def bulk_update_availability(self, restaurant_id: int, menu_item_ids: List[int], is_available: bool) -> int:
        updated = 0
        for item_id in menu_item_ids:
            item = self._menus.get(item_id)
            if item and item.get("restaurant_id") == restaurant_id:
                item["is_available"] = is_available
                item["updated_at"] = self._now()
                updated += 1
        return updated

    def get_menu_categories(self, restaurant_id: int) -> Dict[str, List[str]]:
        categories: Dict[str, List[str]] = {}
        for item in self._menus.values():
            if item.get("restaurant_id") != restaurant_id:
                continue
            category = item.get("category")
            sub = item.get("sub_category")
            if not category:
                continue
            categories.setdefault(category, [])
            if sub and sub not in categories[category]:
                categories[category].append(sub)
        return categories


class InMemoryRestaurantAdminRepository:
    """In-memory repository for restaurant client users used in tests."""

    def __init__(self, restaurant_repo: InMemoryRestaurantRepository):
        self.restaurant_repo = restaurant_repo
        self._admins: Dict[str, Dict[str, Any]] = {}
        self._roles: Dict[int, Dict[str, Any]] = {}
        self.revoked_sessions: list[str] = []

    def add_role(self, role_id: int, role: str, permissions: list[str]):
        self._roles[role_id] = {"id": role_id, "role": role, "permissions": permissions}

    def _now(self):
        return datetime.now(timezone.utc)

    def _clone(self, item: Dict[str, Any]) -> Dict[str, Any]:
        return copy.deepcopy(item)

    def _enrich(self, admin: Dict[str, Any]) -> Dict[str, Any]:
        if not admin:
            return {}
        restaurant = self.restaurant_repo.get_by_id(admin["restaurant_id"])
        admin["restaurant_name"] = restaurant.get("name") if restaurant else None
        role = self._roles.get(admin["role_id"])
        if role:
            admin["role_name"] = role.get("role")
            admin["permissions"] = list(role.get("permissions", []))
        else:
            admin["permissions"] = []
        return admin

    # ---- Role lookup ----
    def get_role_with_permissions(self, role_id: int) -> Optional[Dict[str, Any]]:
        role = self._roles.get(role_id)
        return self._clone(role) if role else None

    # ---- CRUD helpers ----
    def get_client_user_by_restaurant_and_email(self, restaurant_id: int, email: str) -> Optional[Dict[str, Any]]:
        for admin in self._admins.values():
            if admin["restaurant_id"] == restaurant_id and admin["email"] == email:
                return self._clone(admin)
        return None

    def get_client_user_by_uuid(self, admin_uuid: str) -> Optional[Dict[str, Any]]:
        admin = self._admins.get(admin_uuid)
        if not admin:
            return None
        return self._clone(self._enrich(copy.deepcopy(admin)))

    def create_client_user(
        self, admin_uuid: str, restaurant_id: int, email: str, password_hash: str, role_id: int
    ) -> Dict[str, Any]:
        record = {
            "uuid": admin_uuid,
            "restaurant_id": restaurant_id,
            "email": email,
            "password": password_hash,
            "role_id": role_id,
            "created_at": self._now(),
            "updated_at": self._now(),
            "last_login": None,
            "last_active": None,
        }
        self._admins[admin_uuid] = record
        return self.get_client_user_by_uuid(admin_uuid) or {}

    def bulk_create_client_users(self, restaurant_id: int, admins: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        created = []
        for admin in admins:
            created.append(
                self.create_client_user(
                    admin["uuid"], restaurant_id, admin["email"], admin["password"], admin["role_id"]
                )
            )
        return created

    def update_client_user(self, admin_uuid: str, fields: Dict[str, Any]) -> Dict[str, Any]:
        admin = self._admins.get(admin_uuid)
        if not admin:
            return {}
        admin.update(fields)
        admin["updated_at"] = self._now()
        self._admins[admin_uuid] = admin
        return self.get_client_user_by_uuid(admin_uuid) or {}

    def update_client_user_password(self, admin_uuid: str, password_hash: str) -> int:
        admin = self._admins.get(admin_uuid)
        if not admin:
            return 0
        admin["password"] = password_hash
        admin["updated_at"] = self._now()
        return 1

    def update_client_user_role(self, admin_uuid: str, role_id: int) -> int:
        admin = self._admins.get(admin_uuid)
        if not admin:
            return 0
        admin["role_id"] = role_id
        admin["updated_at"] = self._now()
        return 1

    def delete_client_user(self, admin_uuid: str) -> int:
        return 1 if self._admins.pop(admin_uuid, None) else 0

    def count_client_users_by_restaurant(self, restaurant_id: int) -> int:
        return len([a for a in self._admins.values() if a.get("restaurant_id") == restaurant_id])

    def list_client_users_by_restaurant(self, restaurant_id: int, page: int, limit: int, role_id: Optional[int]):
        filtered = [
            self._enrich(copy.deepcopy(a)) for a in self._admins.values() if a["restaurant_id"] == restaurant_id
        ]
        if role_id is not None:
            filtered = [a for a in filtered if a.get("role_id") == role_id]
        filtered.sort(key=lambda a: a["created_at"], reverse=True)
        total = len(filtered)
        start = (page - 1) * limit
        end = start + limit
        return filtered[start:end], total

    def revoke_sessions_for_user(self, user_uuid: str) -> int:
        self.revoked_sessions.append(user_uuid)
        return 1


class InMemoryRessyAdminRepository:
    """In-memory repository for Ressy admin users used in tests."""

    def __init__(self):
        self._admins: Dict[str, Dict[str, Any]] = {}
        self._roles: Dict[int, Dict[str, Any]] = {}
        self.revoked_sessions: list[str] = []

    def add_role(self, role_id: int, role: str, permissions: list[str]):
        self._roles[role_id] = {"id": role_id, "role": role, "permissions": permissions}

    def _now(self):
        return datetime.now(timezone.utc)

    def _clone(self, item: Dict[str, Any]) -> Dict[str, Any]:
        return copy.deepcopy(item)

    def _enrich(self, admin: Dict[str, Any]) -> Dict[str, Any]:
        if not admin:
            return {}
        role = self._roles.get(admin["role_id"])
        if role:
            admin["role_name"] = role.get("role")
            admin["permissions"] = list(role.get("permissions", []))
        else:
            admin["permissions"] = []
        return admin

    def get_role_with_permissions(self, role_id: int) -> Optional[Dict[str, Any]]:
        role = self._roles.get(role_id)
        return self._clone(role) if role else None

    def get_admin_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        for admin in self._admins.values():
            if admin["email"] == email:
                return self._clone(admin)
        return None

    def get_admin_by_uuid(self, admin_uuid: str) -> Optional[Dict[str, Any]]:
        admin = self._admins.get(admin_uuid)
        if not admin:
            return None
        return self._clone(self._enrich(copy.deepcopy(admin)))

    def create_admin_user(self, admin_uuid: str, email: str, password_hash: str, role_id: int) -> Dict[str, Any]:
        record = {
            "uuid": admin_uuid,
            "email": email,
            "password": password_hash,
            "role_id": role_id,
            "created_at": self._now(),
            "updated_at": self._now(),
            "last_login": None,
            "last_active": None,
        }
        self._admins[admin_uuid] = record
        return self.get_admin_by_uuid(admin_uuid) or {}

    def bulk_create_admin_users(self, admins: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        created = []
        for admin in admins:
            created.append(self.create_admin_user(admin["uuid"], admin["email"], admin["password"], admin["role_id"]))
        return created

    def update_admin_user(self, admin_uuid: str, fields: Dict[str, Any]) -> Dict[str, Any]:
        admin = self._admins.get(admin_uuid)
        if not admin:
            return {}
        admin.update(fields)
        admin["updated_at"] = self._now()
        self._admins[admin_uuid] = admin
        return self.get_admin_by_uuid(admin_uuid) or {}

    def update_admin_user_password(self, admin_uuid: str, password_hash: str) -> int:
        admin = self._admins.get(admin_uuid)
        if not admin:
            return 0
        admin["password"] = password_hash
        admin["updated_at"] = self._now()
        return 1

    def update_admin_user_role(self, admin_uuid: str, role_id: int) -> int:
        admin = self._admins.get(admin_uuid)
        if not admin:
            return 0
        admin["role_id"] = role_id
        admin["updated_at"] = self._now()
        return 1

    def delete_admin_user(self, admin_uuid: str) -> int:
        return 1 if self._admins.pop(admin_uuid, None) else 0

    def count_admin_users(self) -> int:
        return len(self._admins)

    def list_admin_users(self, page: int, limit: int, role_id: Optional[int]):
        filtered = [self._enrich(copy.deepcopy(a)) for a in self._admins.values()]
        if role_id is not None:
            filtered = [a for a in filtered if a.get("role_id") == role_id]
        filtered.sort(key=lambda a: a["created_at"], reverse=True)
        total = len(filtered)
        start = (page - 1) * limit
        end = start + limit
        return filtered[start:end], total

    def revoke_sessions_for_user(self, user_uuid: str) -> int:
        self.revoked_sessions.append(user_uuid)
        return 1
