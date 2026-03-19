from typing import Any, Dict, List, Optional, Tuple

from fastapi import HTTPException, status

from app.repositories.mysql_business_faq_repo import MySQLBusinessFAQRepository
from app.repositories.mysql_business_repo import MySQLBusinessRepository


class BusinessFAQService:
    def __init__(
        self,
        business_faq_repo: Optional[MySQLBusinessFAQRepository] = None,
        business_repo: Optional[MySQLBusinessRepository] = None,
    ):
        self.business_faq_repo = business_faq_repo or MySQLBusinessFAQRepository()
        self.business_repo = business_repo or MySQLBusinessRepository()

    def _validate_business(self, business_id: int) -> Dict[str, Any]:
        business = self.business_repo.get_by_id(business_id)
        if not business:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Restaurant not found")
        return business

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

    def _ensure_unique_question(self, business_id: int, question: str, exclude_id: Optional[int] = None):
        existing = self.business_faq_repo.get_by_business_and_question(business_id, question, exclude_id=exclude_id)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="An FAQ with the same question already exists for this business",
            )

    def _validate_pagination(self, page: int, limit: int) -> Tuple[int, int]:
        if page < 1 or limit < 1:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="page and limit must be positive")
        return page, limit

    def _enrich_with_business_name(
        self, item: Dict[str, Any], cache: Optional[Dict[int, Optional[str]]] = None
    ) -> Dict[str, Any]:
        """Populate business_name if missing, caching lookups within a batch."""
        if not item:
            return item
        business_id = item.get("business_id")
        if item.get("business_name") or business_id is None:
            return item
        try:
            business_id_int = int(business_id)
        except (TypeError, ValueError):
            return item

        cache = cache if cache is not None else {}
        if business_id_int not in cache:
            business = self.business_repo.get_by_id(business_id_int)
            cache[business_id_int] = business.get("name") if business else None
        business_name = cache.get(business_id_int)
        if business_name:
            item["business_name"] = business_name
        return item

    def create_faq(self, business_id: int, data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new FAQ."""
        business = self._validate_business(business_id)
        question = self._validate_question_answer(data.get("question"), "question")
        answer = self._validate_question_answer(data.get("answer"), "answer")
        self._ensure_unique_question(business_id, question)
        created = self.business_faq_repo.create(business_id, {"question": question, "answer": answer})
        if not created:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to create FAQ")
        if business:
            self._enrich_with_business_name(created, {business_id: business.get("name")})
        return created

    def list_faqs(self, business_id: int, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """List Business_FAQs for a business (used by internal consumers)."""
        self._validate_business(business_id)
        # Repo already returns business_name via JOIN; no enrichment needed here.
        return self.business_faq_repo.get_by_business(business_id, limit=limit)

    def list_faqs_paginated(self, business_id: int, page: int, limit: int, search: Optional[str]) -> Dict[str, Any]:
        """List Business_FAQs for a business with pagination and optional search."""
        self._validate_business(business_id)
        page, limit = self._validate_pagination(page, limit)
        search_term = (search or "").strip() or None
        items, total = self.business_faq_repo.get_paginated_by_business(business_id, page, limit, search_term)
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
        """Get FAQ by ID including business name."""
        faq = self.business_faq_repo.get_by_id(faq_id)
        if not faq:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="FAQ not found")
        self._enrich_with_business_name(faq)
        return faq

    def get_faq_for_business(self, business_id: int, faq_id: int) -> Dict[str, Any]:
        """Get FAQ by ID scoped to a business."""
        faq = self.business_faq_repo.get_by_id_scoped(faq_id, business_id)
        if not faq:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="FAQ not found")
        self._enrich_with_business_name(faq, {business_id: faq.get("business_name")})
        return faq

    def update_faq(self, faq_id: int, data: Dict[str, Any]) -> Dict[str, Any]:
        """Update an existing FAQ."""
        if not data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="At least one field (question or answer) is required"
            )
        current = self.business_faq_repo.get_by_id(faq_id)
        if not current:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="FAQ not found")
        update_fields: Dict[str, str] = {}
        if "question" in data:
            question = self._validate_question_answer(data.get("question"), "question")
            self._ensure_unique_question(int(current["business_id"]), question, exclude_id=faq_id)
            update_fields["question"] = question
        if "answer" in data:
            update_fields["answer"] = self._validate_question_answer(data.get("answer"), "answer")
        if not update_fields:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="At least one field (question or answer) is required"
            )
        updated = self.business_faq_repo.update(faq_id, update_fields)
        if not updated:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="FAQ not found")
        self._enrich_with_business_name(updated)
        return updated

    def update_faq_for_business(self, business_id: int, faq_id: int, data: Dict[str, Any]) -> Dict[str, Any]:
        """Update FAQ scoped to a business."""
        if not data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="At least one field (question or answer) is required"
            )
        current = self.business_faq_repo.get_by_id_scoped(faq_id, business_id)
        if not current:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="FAQ not found")

        update_fields: Dict[str, str] = {}
        if "question" in data:
            question = self._validate_question_answer(data.get("question"), "question")
            self._ensure_unique_question(business_id, question, exclude_id=faq_id)
            update_fields["question"] = question
        if "answer" in data:
            update_fields["answer"] = self._validate_question_answer(data.get("answer"), "answer")
        if not update_fields:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="At least one field (question or answer) is required"
            )

        updated = self.business_faq_repo.update_scoped(faq_id, business_id, update_fields)
        if not updated:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="FAQ not found")
        self._enrich_with_business_name(updated, {business_id: current.get("business_name")})
        return updated

    def delete_faq(self, faq_id: int) -> Dict[str, str]:
        """Delete an FAQ."""
        deleted = self.business_faq_repo.delete(faq_id)
        if not deleted:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="FAQ not found")
        return {"message": "FAQ deleted"}

    def delete_faq_for_business(self, business_id: int, faq_id: int) -> Dict[str, str]:
        """Delete an FAQ scoped to a business."""
        deleted = self.business_faq_repo.delete_scoped(faq_id, business_id)
        if not deleted:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="FAQ not found")
        return {"message": "FAQ deleted"}

    def bulk_create_faqs(self, business_id: int, faqs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Bulk create Business_FAQs inside a single transaction."""
        self._validate_business(business_id)
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
                    detail="Duplicate question found in payload for this business",
                )
            seen_questions.add(key)
            self._ensure_unique_question(business_id, question)
            clean_faqs.append({"question": question, "answer": answer})
        try:
            created = self.business_faq_repo.bulk_create(business_id, clean_faqs)
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to bulk create Business_FAQs: {exc}",
            ) from exc
        if not created:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to bulk create Business_FAQs")
        return created

    def search_all(self, search: str, page: int, limit: int) -> Dict[str, Any]:
        """Search Business_FAQs across all businesss."""
        search_term = (search or "").strip()
        if not search_term:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="search query is required")
        page, limit = self._validate_pagination(page, limit)
        items, total = self.business_faq_repo.search_all(search_term, page, limit)
        business_cache: Dict[int, Optional[str]] = {}
        for item in items:
            # Repo may already return business_name; enrichment remains as a fallback for search path
            self._enrich_with_business_name(item, business_cache)
        return {
            "items": items,
            "pagination": {
                "page": page,
                "limit": limit,
                "total": total,
                "pages": (total + limit - 1) // limit if limit else 0,
            },
        }
