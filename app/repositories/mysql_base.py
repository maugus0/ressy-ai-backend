"""
MySQL Base Repository for database operations.
This is a placeholder for MySQL operations - adapt based on your MySQL connection library.
"""
from typing import Dict, List, Any, Optional
import mysql.connector
from mysql.connector import Error
from app.config import settings
import os

class MySQLBaseRepository:
    """Base repository for MySQL database operations."""
    
    def __init__(self):
        self.connection = None
        self._connect()
    
    def _connect(self):
        """Establish MySQL connection."""
        try:
            self.connection = mysql.connector.connect(
                host=os.getenv('DB_HOST', os.getenv('MYSQL_HOST', 'localhost')),
                database=os.getenv('DB_NAME', os.getenv('MYSQL_DATABASE', 'ressy')),
                user=os.getenv('DB_USERNAME', os.getenv('MYSQL_USER', 'root')),
                password=os.getenv('DB_PASSWORD', os.getenv('MYSQL_PASSWORD', 'root')),
                port=int(os.getenv('DB_PORT', os.getenv('MYSQL_PORT', 3306)))
            )
        except Error as e:
            print(f"Error connecting to MySQL: {e}")
            raise
    
    def _execute_query(self, query: str, params: tuple = None) -> List[Dict[str, Any]]:
        """Execute SELECT query and return results."""
        try:
            cursor = self.connection.cursor(dictionary=True)
            cursor.execute(query, params)
            results = cursor.fetchall()
            cursor.close()
            return results
        except Error as e:
            print(f"Error executing query: {e}")
            raise
    
    def _execute_insert(self, query: str, params: tuple = None) -> int:
        """Execute INSERT query and return last insert ID."""
        try:
            cursor = self.connection.cursor()
            cursor.execute(query, params)
            self.connection.commit()
            last_id = cursor.lastrowid
            cursor.close()
            return last_id
        except Error as e:
            self.connection.rollback()
            print(f"Error executing insert: {e}")
            raise
    
    def _execute_update(self, query: str, params: tuple = None) -> int:
        """Execute UPDATE query and return affected rows."""
        try:
            cursor = self.connection.cursor()
            cursor.execute(query, params)
            self.connection.commit()
            affected = cursor.rowcount
            cursor.close()
            return affected
        except Error as e:
            self.connection.rollback()
            print(f"Error executing update: {e}")
            raise
    
    def close(self):
        """Close database connection."""
        if self.connection and self.connection.is_connected():
            self.connection.close()

