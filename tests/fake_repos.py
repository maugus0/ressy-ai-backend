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
