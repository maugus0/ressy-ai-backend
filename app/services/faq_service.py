from typing import Any, Dict, List, Optional, Tuple

from fastapi import HTTPException, status

from app.repositories.mysql_faq_repo import MySQLFAQRepository
from app.repositories.mysql_restaurant_repo import MySQLRestaurantRepository


class FAQService:
    def __init__(
        self,
        faq_repo: Optional[MySQLFAQRepository] = None,
        restaurant_repo: Optional[MySQLRestaurantRepository] = None,
    ):
        self.faq_repo = faq_repo or MySQLFAQRepository()
        self.restaurant_repo = restaurant_repo or MySQLRestaurantRepository()

    def _validate_restaurant(self, restaurant_id: int) -> Dict[str, Any]:
        restaurant = self.restaurant_repo.get_by_id(restaurant_id)
        if not restaurant:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Restaurant not found")
        return restaurant

    def _validate_question_answer(self, value: Optional[str], field: str) -> str:
        if value is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"{field} is required")
        cleaned = str(value).strip()
        if not cleaned:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"{field} cannot be empty")
        return cleaned

    def _normalize_question_key(self, question: str) -> str:
        """Normalize a question string for duplicate detection."""
        return self._validate_question_answer(question, "question").lower()

    def _ensure_unique_question(self, restaurant_id: int, question: str, exclude_id: Optional[int] = None):
        existing = self.faq_repo.get_by_restaurant_and_question(restaurant_id, question, exclude_id=exclude_id)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="An FAQ with the same question already exists for this restaurant",
            )

    def _validate_pagination(self, page: int, limit: int) -> Tuple[int, int]:
        if page < 1 or limit < 1:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="page and limit must be positive")
        return page, limit

    def _enrich_with_restaurant_name(
        self, item: Dict[str, Any], cache: Optional[Dict[int, Optional[str]]] = None
    ) -> Dict[str, Any]:
        """Populate restaurant_name if missing, caching lookups within a batch."""
        if not item:
            return item
        restaurant_id = item.get("restaurant_id")
        if item.get("restaurant_name") or restaurant_id is None:
            return item
        try:
            restaurant_id_int = int(restaurant_id)
        except (TypeError, ValueError):
            return item

        cache = cache if cache is not None else {}
        if restaurant_id_int not in cache:
            restaurant = self.restaurant_repo.get_by_id(restaurant_id_int)
            cache[restaurant_id_int] = restaurant.get("name") if restaurant else None
        restaurant_name = cache.get(restaurant_id_int)
        if restaurant_name:
            item["restaurant_name"] = restaurant_name
        return item

    def create_faq(self, restaurant_id: int, data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new FAQ."""
        restaurant = self._validate_restaurant(restaurant_id)
        question = self._validate_question_answer(data.get("question"), "question")
        answer = self._validate_question_answer(data.get("answer"), "answer")
        self._ensure_unique_question(restaurant_id, question)
        created = self.faq_repo.create(restaurant_id, {"question": question, "answer": answer})
        if not created:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to create FAQ")
        if restaurant:
            self._enrich_with_restaurant_name(created, {restaurant_id: restaurant.get("name")})
        return created

    def list_faqs(self, restaurant_id: int, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """List FAQs for a restaurant (used by internal consumers)."""
        self._validate_restaurant(restaurant_id)
        # Repo already returns restaurant_name via JOIN; no enrichment needed here.
        return self.faq_repo.get_by_restaurant(restaurant_id, limit=limit)

    def list_faqs_paginated(self, restaurant_id: int, page: int, limit: int, search: Optional[str]) -> Dict[str, Any]:
        """List FAQs for a restaurant with pagination and optional search."""
        self._validate_restaurant(restaurant_id)
        page, limit = self._validate_pagination(page, limit)
        search_term = (search or "").strip() or None
        items, total = self.faq_repo.get_paginated_by_restaurant(restaurant_id, page, limit, search_term)
        return {
            "items": items,
            "pagination": {
                "page": page,
                "limit": limit,
                "total": total,
                "pages": (total + limit - 1) // limit if limit else 0,
            },
        }

    def get_faq(self, faq_id: int) -> Dict[str, Any]:
        """Get FAQ by ID including restaurant name."""
        faq = self.faq_repo.get_by_id(faq_id)
        if not faq:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="FAQ not found")
        self._enrich_with_restaurant_name(faq)
        return faq

    def update_faq(self, faq_id: int, data: Dict[str, Any]) -> Dict[str, Any]:
        """Update an existing FAQ."""
        if not data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="At least one field (question or answer) is required"
            )
        current = self.faq_repo.get_by_id(faq_id)
        if not current:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="FAQ not found")
        update_fields: Dict[str, str] = {}
        if "question" in data:
            question = self._validate_question_answer(data.get("question"), "question")
            self._ensure_unique_question(int(current["restaurant_id"]), question, exclude_id=faq_id)
            update_fields["question"] = question
        if "answer" in data:
            update_fields["answer"] = self._validate_question_answer(data.get("answer"), "answer")
        if not update_fields:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="At least one field (question or answer) is required"
            )
        updated = self.faq_repo.update(faq_id, update_fields)
        if not updated:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="FAQ not found")
        self._enrich_with_restaurant_name(updated)
        return updated

    def delete_faq(self, faq_id: int) -> Dict[str, str]:
        """Delete an FAQ."""
        deleted = self.faq_repo.delete(faq_id)
        if not deleted:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="FAQ not found")
        return {"message": "FAQ deleted"}

    def bulk_create_faqs(self, restaurant_id: int, faqs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Bulk create FAQs inside a single transaction."""
        self._validate_restaurant(restaurant_id)
        if not faqs:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="faqs list cannot be empty")
        clean_faqs: List[Dict[str, str]] = []
        seen_questions: set[str] = set()
        for faq in faqs:
            question = self._validate_question_answer(faq.get("question"), "question")
            answer = self._validate_question_answer(faq.get("answer"), "answer")
            key = self._normalize_question_key(question)
            if key in seen_questions:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Duplicate question found in payload for this restaurant",
                )
            seen_questions.add(key)
            self._ensure_unique_question(restaurant_id, question)
            clean_faqs.append({"question": question, "answer": answer})
        try:
            created = self.faq_repo.bulk_create(restaurant_id, clean_faqs)
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to bulk create FAQs: {exc}",
            ) from exc
        if not created:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to bulk create FAQs")
        return created

    def search_all(self, search: str, page: int, limit: int) -> Dict[str, Any]:
        """Search FAQs across all restaurants."""
        search_term = (search or "").strip()
        if not search_term:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="search query is required")
        page, limit = self._validate_pagination(page, limit)
        items, total = self.faq_repo.search_all(search_term, page, limit)
        restaurant_cache: Dict[int, Optional[str]] = {}
        for item in items:
            # Repo may already return restaurant_name; enrichment remains as a fallback for search path
            self._enrich_with_restaurant_name(item, restaurant_cache)
        return {
            "items": items,
            "pagination": {
                "page": page,
                "limit": limit,
                "total": total,
                "pages": (total + limit - 1) // limit if limit else 0,
            },
        }
