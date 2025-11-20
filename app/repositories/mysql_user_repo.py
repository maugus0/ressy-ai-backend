"""
MySQL User Repository for user operations.
"""
from app.repositories.mysql_base import MySQLBaseRepository
from typing import Dict, Optional

class MySQLUserRepository(MySQLBaseRepository):
    """Repository for user data access in MySQL."""
    
    def create_or_update_user(self, user_data: Dict) -> int:
        """
        Create or update user based on phone_number or email.
        Returns user ID.
        """
        # First, try to find existing user
        user_id = self.get_user_id_by_phone_or_email(
            user_data.get("phone_number"),
            user_data.get("email")
        )
        
        if user_id:
            # Update existing user
            query = """
                UPDATE Users
                SET name = %s,
                    email = %s,
                    address = %s,
                    is_spam = %s,
                    credit_card = %s,
                    updated_at = NOW()
                WHERE id = %s
            """
            self._execute_update(query, (
                user_data.get("name"),
                user_data.get("email"),
                user_data.get("address"),
                user_data.get("is_spam", False),
                user_data.get("credit_card"),
                user_id
            ))
            return user_id
        else:
            # Create new user
            query = """
                INSERT INTO Users (name, phone_number, email, address, is_spam, credit_card, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, NOW(), NOW())
            """
            return self._execute_insert(query, (
                user_data.get("name"),
                user_data.get("phone_number"),
                user_data.get("email"),
                user_data.get("address"),
                user_data.get("is_spam", False),
                user_data.get("credit_card")
            ))
    
    def get_user_id_by_phone_or_email(self, phone_number: Optional[str], email: Optional[str]) -> Optional[int]:
        """
        Get user ID by phone number or email.
        """
        if not phone_number and not email:
            return None
        
        query = """
            SELECT id 
            FROM Users 
            WHERE (phone_number = %s AND phone_number IS NOT NULL)
               OR (email = %s AND email IS NOT NULL)
            LIMIT 1
        """
        results = self._execute_query(query, (phone_number, email))
        return results[0]["id"] if results else None

