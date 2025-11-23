"""
MySQL FAQ Repository for fetching restaurant FAQs.
"""

from typing import Any, Dict, List

from app.repositories.mysql_base import MySQLBaseRepository


class MySQLFAQRepository(MySQLBaseRepository):
    """Repository for FAQ data access in MySQL."""

    def get_by_restaurant(self, restaurant_id: int) -> List[Dict]:
        """
        Get all FAQs for a restaurant.
        """
        query = """
            SELECT
                id,
                restaurant_id,
                question,
                answer,
                created_at,
                updated_at
            FROM FAQs
            WHERE restaurant_id = %s
            ORDER BY id
        """
        return self._execute_query(query, (restaurant_id,))

    def create(self, restaurant_id: int, data: Dict[str, Any]) -> int:
        query = """
            INSERT INTO FAQs (restaurant_id, question, answer, created_at, updated_at)
            VALUES (%s, %s, %s, NOW(), NOW())
        """
        return self._execute_insert(query, (restaurant_id, data.get("question"), data.get("answer")))

    def update(self, restaurant_id: int, faq_id: int, data: Dict[str, Any]) -> int:
        fields = []
        params = []
        for key in ["question", "answer"]:
            if key in data:
                fields.append(f"{key} = %s")
                params.append(data[key])
        if not fields:
            return 0
        fields.append("updated_at = NOW()")
        params.extend([restaurant_id, faq_id])
        query = f"UPDATE FAQs SET {', '.join(fields)} WHERE restaurant_id = %s AND id = %s"
        return self._execute_update(query, tuple(params))

    def delete(self, restaurant_id: int, faq_id: int) -> int:
        return self._execute_update("DELETE FROM FAQs WHERE restaurant_id = %s AND id = %s", (restaurant_id, faq_id))
