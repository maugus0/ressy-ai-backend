"""
MySQL Business FAQ Repository for fetching and managing business Business_FAQs.
"""

from typing import Any, Dict, List, Optional, Tuple

from app.repositories.mysql_base import MySQLBaseRepository


class MySQLBusinessFAQRepository(MySQLBaseRepository):
    """Repository for Business FAQ data access in MySQL."""

    def get_by_business_and_question(
        self, business_id: int, question: str, exclude_id: Optional[int] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Get a single FAQ by business/question (case-insensitive), optionally excluding an ID.
        """
        query = """
            SELECT
                f.id,
                f.business_id,
                f.question,
                f.answer,
                f.created_at,
                f.updated_at
            FROM Business_FAQs f
            WHERE f.business_id = %s AND LOWER(f.question) = LOWER(%s)
        """
        params: List[Any] = [business_id, question]
        if exclude_id is not None:
            query += " AND f.id <> %s"
            params.append(exclude_id)
        query += " LIMIT 1"
        results = self._execute_query(query, tuple(params))
        return results[0] if results else None

    def get_by_business(self, business_id: int, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Get Business_FAQs for a business, optionally limited.
        """
        query = """
            SELECT
                f.id,
                f.business_id,
                r.name AS business_name,
                f.question,
                f.answer,
                f.created_at,
                f.updated_at
            FROM Business_FAQs f
            LEFT JOIN Businesses r ON r.id = f.business_id
            WHERE f.business_id = %s
            ORDER BY f.created_at DESC
        """
        params: Tuple[Any, ...] = (business_id,)
        if limit:
            query += " LIMIT %s"
            params = (business_id, limit)
        return self._execute_query(query, params)

    def get_paginated_by_business(
        self, business_id: int, page: int, limit: int, search: Optional[str]
    ) -> Tuple[List[Dict[str, Any]], int]:
        """
        Get paginated Business_FAQs for a business with optional FULLTEXT search.
        """
        offset = (page - 1) * limit
        filters = ["f.business_id = %s"]
        params: List[Any] = [business_id]

        if search:
            filters.append("MATCH(f.question, f.answer) AGAINST (%s IN NATURAL LANGUAGE MODE)")
            params.append(search)

        where_clause = " AND ".join(filters)
        count_query = f"SELECT COUNT(*) as total FROM Business_FAQs f WHERE {where_clause}"
        total_rows = self._execute_query(count_query, tuple(params))
        total = total_rows[0]["total"] if total_rows else 0

        data_query = f"""
            SELECT
                f.id,
                f.business_id,
                r.name AS business_name,
                f.question,
                f.answer,
                f.created_at,
                f.updated_at
            FROM Business_FAQs f
            LEFT JOIN Businesses r ON r.id = f.business_id
            WHERE {where_clause}
            ORDER BY f.created_at DESC
            LIMIT %s OFFSET %s
        """
        items = self._execute_query(data_query, tuple(params + [limit, offset]))
        return items, int(total)

    def search_all(self, search: str, page: int, limit: int) -> Tuple[List[Dict[str, Any]], int]:
        """
        Search Business_FAQs across all businesss using FULLTEXT.
        """
        offset = (page - 1) * limit
        base_params: List[Any] = [search]

        count_query = """
            SELECT COUNT(*) as total
            FROM Business_FAQs f
            WHERE MATCH(f.question, f.answer) AGAINST (%s IN NATURAL LANGUAGE MODE)
        """
        total_rows = self._execute_query(count_query, tuple(base_params))
        total = total_rows[0]["total"] if total_rows else 0

        data_query = """
            SELECT
                f.id,
                f.business_id,
                r.name AS business_name,
                f.question,
                f.answer,
                f.created_at,
                f.updated_at
            FROM Business_FAQs f
            LEFT JOIN Businesses r ON r.id = f.business_id
            WHERE MATCH(f.question, f.answer) AGAINST (%s IN NATURAL LANGUAGE MODE)
            ORDER BY f.created_at DESC
            LIMIT %s OFFSET %s
        """
        items = self._execute_query(data_query, tuple(base_params + [limit, offset]))
        return items, int(total)

    def get_by_id(self, faq_id: int) -> Dict[str, Any]:
        query = """
            SELECT
                f.id,
                f.business_id,
                r.name AS business_name,
                f.question,
                f.answer,
                f.created_at,
                f.updated_at
            FROM Business_FAQs f
            LEFT JOIN Businesses r ON r.id = f.business_id
            WHERE f.id = %s
            LIMIT 1
        """
        results = self._execute_query(query, (faq_id,))
        return results[0] if results else {}

    def get_by_id_scoped(self, faq_id: int, business_id: int) -> Dict[str, Any]:
        """
        Get FAQ by ID limited to a specific business.
        """
        query = """
            SELECT
                f.id,
                f.business_id,
                r.name AS business_name,
                f.question,
                f.answer,
                f.created_at,
                f.updated_at
            FROM Business_FAQs f
            LEFT JOIN Businesses r ON r.id = f.business_id
            WHERE f.id = %s AND f.business_id = %s
            LIMIT 1
        """
        results = self._execute_query(query, (faq_id, business_id))
        return results[0] if results else {}

    def create(self, business_id: int, data: Dict[str, Any]) -> Dict[str, Any]:
        query = """
            INSERT INTO Business_FAQs (business_id, question, answer, created_at, updated_at)
            VALUES (%s, %s, %s, NOW(), NOW())
        """
        new_id = self._execute_insert(query, (business_id, data.get("question"), data.get("answer")))
        return self.get_by_id(int(new_id)) if new_id else {}

    def bulk_create(self, business_id: int, faqs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Bulk insert Business_FAQs in a single transaction.
        """
        if not faqs:
            return []

        insert_query = """
            INSERT INTO Business_FAQs (business_id, question, answer, created_at, updated_at)
            VALUES (%s, %s, %s, NOW(), NOW())
        """
        params = [(business_id, faq.get("question"), faq.get("answer")) for faq in faqs]

        try:
            first_id = self._execute_many(insert_query, params)
        except Exception as err:
            raise RuntimeError(f"Bulk insert Business_FAQs failed: {err}") from err

        if not first_id:
            return []

        last_id = first_id + len(faqs) - 1
        fetch_query = """
            SELECT
                f.id,
                f.business_id,
                f.question,
                f.answer,
                f.created_at,
                f.updated_at
            FROM Business_FAQs f
            WHERE f.business_id = %s AND f.id BETWEEN %s AND %s
            ORDER BY f.id DESC
        """
        return self._execute_query(fetch_query, (business_id, first_id, last_id))

    def update(self, faq_id: int, data: Dict[str, Any]) -> Dict[str, Any]:
        fields = []
        params = []
        for key in ["question", "answer"]:
            if key in data:
                fields.append(f"{key} = %s")
                params.append(data[key])
        if not fields:
            return {}
        fields.append("updated_at = NOW()")
        params.append(faq_id)
        query = f"UPDATE Business_FAQs SET {', '.join(fields)} WHERE id = %s"
        affected = self._execute_update(query, tuple(params))
        if affected == 0:
            return {}
        return self.get_by_id(faq_id)

    def update_scoped(self, faq_id: int, business_id: int, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update FAQ ensuring it belongs to the business.
        """
        fields = []
        params = []
        for key in ["question", "answer"]:
            if key in data:
                fields.append(f"{key} = %s")
                params.append(data[key])
        if not fields:
            return {}
        fields.append("updated_at = NOW()")
        params.extend([faq_id, business_id])
        query = f"UPDATE Business_FAQs SET {', '.join(fields)} WHERE id = %s AND business_id = %s"
        affected = self._execute_update(query, tuple(params))
        if affected == 0:
            return {}
        return self.get_by_id_scoped(faq_id, business_id)

    def delete(self, faq_id: int) -> int:
        return self._execute_update("DELETE FROM Business_FAQs WHERE id = %s", (faq_id,))

    def delete_scoped(self, faq_id: int, business_id: int) -> int:
        """
        Delete FAQ ensuring it belongs to the business.
        """
        return self._execute_update("DELETE FROM Business_FAQs WHERE id = %s AND business_id = %s", (faq_id, business_id))

    def delete_by_business(self, business_id: int) -> int:
        return self._execute_update("DELETE FROM Business_FAQs WHERE business_id = %s", (business_id,))
