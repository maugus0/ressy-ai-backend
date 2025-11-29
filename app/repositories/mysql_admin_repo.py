"""
MySQL Admin Repository for Ressy Administrator operations.
"""
from app.repositories.mysql_base import MySQLBaseRepository
from typing import Dict, Optional, List
import json

class MySQLAdminRepository(MySQLBaseRepository):
    """Repository for Ressy Administrator data access in MySQL."""
    
    def get_by_email(self, email: str) -> Optional[Dict]:
        """
        Get administrator by email.
        """
        query = """
            SELECT 
                ra.uuid,
                ra.email,
                ra.password,
                ra.role_id,
                cr.role,
                cr.permission_id,
                p.routes,
                ra.created_at,
                ra.updated_at
            FROM Ressy_Administrator ra
            INNER JOIN Crm_roles cr ON ra.role_id = cr.id
            INNER JOIN Permissions p ON cr.permission_id = p.id
            WHERE ra.email = %s
            LIMIT 1
        """
        results = self._execute_query(query, (email,))
        if results:
            result = results[0]
            # Parse JSON routes
            if result.get('routes'):
                result['routes'] = json.loads(result['routes']) if isinstance(result['routes'], str) else result['routes']
            return result
        return None
    
    def get_by_uuid(self, uuid: str) -> Optional[Dict]:
        """
        Get administrator by UUID.
        """
        query = """
            SELECT 
                ra.uuid,
                ra.email,
                ra.password,
                ra.role_id,
                cr.role,
                cr.permission_id,
                p.routes,
                ra.created_at,
                ra.updated_at
            FROM Ressy_Administrator ra
            INNER JOIN Crm_roles cr ON ra.role_id = cr.id
            INNER JOIN Permissions p ON cr.permission_id = p.id
            WHERE ra.uuid = %s
            LIMIT 1
        """
        results = self._execute_query(query, (uuid,))
        if results:
            result = results[0]
            # Parse JSON routes
            if result.get('routes'):
                result['routes'] = json.loads(result['routes']) if isinstance(result['routes'], str) else result['routes']
            return result
        return None
    
    def get_role_by_name(self, role_name: str) -> Optional[Dict]:
        """
        Get role by name.
        """
        query = """
            SELECT 
                cr.id,
                cr.role,
                cr.permission_id,
                p.routes,
                cr.created_at,
                cr.updated_at
            FROM Crm_roles cr
            INNER JOIN Permissions p ON cr.permission_id = p.id
            WHERE cr.role = %s
            LIMIT 1
        """
        results = self._execute_query(query, (role_name,))
        if results:
            result = results[0]
            # Parse JSON routes
            if result.get('routes'):
                result['routes'] = json.loads(result['routes']) if isinstance(result['routes'], str) else result['routes']
            return result
        return None

