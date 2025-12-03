"""
MySQL OpenTable API Log Repository for logging OpenTable API calls.
"""
from app.repositories.mysql_base import MySQLBaseRepository
from typing import Dict, Optional
import json


class MySQLOpenTableLogRepository(MySQLBaseRepository):
    """Repository for OpenTable API log data access in MySQL."""
    
    def create_log(
        self,
        restaurant_id: int,
        endpoint: str,
        method: str,
        request_payload: Optional[Dict] = None,
        response_payload: Optional[Dict] = None,
        status_code: Optional[int] = None,
        error_message: Optional[str] = None
    ) -> int:
        """
        Create an OpenTable API log entry.
        
        Args:
            restaurant_id: Restaurant ID
            endpoint: API endpoint
            method: HTTP method (GET, POST, PUT, etc.)
            request_payload: Request payload as dictionary
            response_payload: Response payload as dictionary
            status_code: HTTP status code
            error_message: Error message if any
        
        Returns:
            Log ID
        """
        query = """
            INSERT INTO OpenTable_API_Logs (
                restaurant_id,
                endpoint,
                method,
                request_payload,
                response_payload,
                status_code,
                error_message,
                created_at,
                updated_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
        """
        
        request_json = json.dumps(request_payload) if request_payload else None
        response_json = json.dumps(response_payload) if response_payload else None
        
        return self._execute_insert(query, (
            restaurant_id,
            endpoint,
            method,
            request_json,
            response_json,
            status_code,
            error_message
        ))
    
    def get_logs_by_restaurant(
        self,
        restaurant_id: int,
        limit: int = 100,
        offset: int = 0
    ) -> list:
        """
        Get OpenTable API logs for a restaurant.
        
        Args:
            restaurant_id: Restaurant ID
            limit: Maximum number of logs to return
            offset: Offset for pagination
        
        Returns:
            List of log dictionaries
        """
        query = """
            SELECT 
                id,
                restaurant_id,
                endpoint,
                method,
                request_payload,
                response_payload,
                status_code,
                error_message,
                created_at,
                updated_at
            FROM OpenTable_API_Logs
            WHERE restaurant_id = %s
            ORDER BY created_at DESC
            LIMIT %s OFFSET %s
        """
        return self._execute_query(query, (restaurant_id, limit, offset))
    
    def get_log_by_id(self, log_id: int) -> Optional[Dict]:
        """
        Get a specific log entry by ID.
        
        Args:
            log_id: Log ID
        
        Returns:
            Log dictionary or None
        """
        query = """
            SELECT 
                id,
                restaurant_id,
                endpoint,
                method,
                request_payload,
                response_payload,
                status_code,
                error_message,
                created_at,
                updated_at
            FROM OpenTable_API_Logs
            WHERE id = %s
            LIMIT 1
        """
        results = self._execute_query(query, (log_id,))
        return results[0] if results else None


