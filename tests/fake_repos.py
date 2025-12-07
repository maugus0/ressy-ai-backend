from __future__ import annotations

import copy
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple


class InMemoryRestaurantRepository:
    """Lightweight in-memory restaurant repo used for tests."""

    def __init__(self, faq_repo: "InMemoryFAQRepository | None" = None):
        self._restaurants: Dict[int, Dict[str, Any]] = {}
        self._faq_repo = faq_repo

    def add(self, restaurant_id: int, name: str = "Test Restaurant") -> Dict[str, Any]:
        restaurant = {"id": restaurant_id, "name": name}
        self._restaurants[restaurant_id] = restaurant
        return restaurant

    def get_by_id(self, restaurant_id: int) -> Dict[str, Any]:
        return copy.deepcopy(self._restaurants.get(restaurant_id, {}))

    def delete(self, restaurant_id: int) -> int:
        removed = self._restaurants.pop(restaurant_id, None)
        if removed and self._faq_repo:
            self._faq_repo.delete_by_restaurant(restaurant_id)
        return 1 if removed else 0


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

    def delete(self, faq_id: int) -> int:
        faq = self._faqs.pop(faq_id, None)
        if not faq:
            return 0
        restaurant_id = faq["restaurant_id"]
        self._by_restaurant[restaurant_id] = [
            f for f in self._by_restaurant.get(restaurant_id, []) if f["id"] != faq_id
        ]
        return 1

    def delete_by_restaurant(self, restaurant_id: int) -> int:
        faqs = self._by_restaurant.pop(restaurant_id, [])
        for faq in faqs:
            self._faqs.pop(faq["id"], None)
        return len(faqs)


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
