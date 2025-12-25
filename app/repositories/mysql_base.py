"""
MySQL Base Repository for database operations.

This module provides a base class for all MySQL repositories with connection pooling.
Connections are borrowed from a shared pool for each operation, improving performance
under high load by avoiding the overhead of creating new connections per request.
"""

import os
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from mysql.connector import Error
from mysql.connector.pooling import PooledMySQLConnection

from app.repositories.db_pool import get_db_pool

# Load environment variables from .env file
load_dotenv()


class MySQLBaseRepository:
    """
    Base repository for MySQL database operations with connection pooling.
    
    This class manages database connections using a shared connection pool.
    Connections are borrowed from the pool for each operation and returned
    automatically, significantly improving performance for high-volume API calls.
    
    Thread Safety:
        This class is thread-safe. Each method borrows its own connection
        from the pool and returns it when done.
    """

    def __init__(self):
        """
        Initialize the repository.
        
        Note: Unlike the previous implementation, this no longer creates a
        dedicated connection. Instead, connections are borrowed from the
        shared pool as needed.
        """
        self._pool = get_db_pool()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        # No cleanup needed - connections are managed by the pool
        pass
    
    def __del__(self):
        # No cleanup needed - connections are managed by the pool
        pass

    def _get_connection(self) -> Optional[PooledMySQLConnection]:
        """
        Get a connection from the pool.
        
        Returns:
            A pooled MySQL connection, or None if unavailable.
            
        Note:
            The caller MUST return the connection using _return_connection() when done.
        """
        return self._pool.get_connection()
    
    def _return_connection(self, connection: Optional[PooledMySQLConnection]) -> None:
        """
        Return a connection to the pool with logging.
        
        Args:
            connection: The pooled connection to return
        """
        if connection:
            self._pool.return_connection(connection)

    def _execute_query(self, query: str, params: tuple = None) -> List[Dict[str, Any]]:
        """
        Execute SELECT query and return results.
        
        Borrows a connection from the pool, executes the query, and returns
        the connection to the pool when done.
        """
        connection = None
        cursor = None
        try:
            connection = self._get_connection()
            if connection is None:
                if os.getenv("ALLOW_DB_FAILURE", "false").lower() == "true":
                    return []
                raise RuntimeError("Database connection unavailable")
            
            cursor = connection.cursor(dictionary=True)
            cursor.execute(query, params)
            results = cursor.fetchall()
            return results
        except Error as e:
            print(f"Error executing query: {e}")
            raise
        finally:
            if cursor:
                try:
                    cursor.close()
                except Exception:
                    pass
            self._return_connection(connection)

    def _execute_insert(self, query: str, params: tuple = None) -> int:
        """
        Execute INSERT query and return last insert ID.
        
        Borrows a connection from the pool, executes the insert with commit,
        and returns the connection to the pool when done.
        """
        connection = None
        cursor = None
        try:
            connection = self._get_connection()
            if connection is None:
                if os.getenv("ALLOW_DB_FAILURE", "false").lower() == "true":
                    return 0
                raise RuntimeError("Database connection unavailable")
            
            cursor = connection.cursor()
            cursor.execute(query, params)
            connection.commit()
            last_id = cursor.lastrowid
            return last_id
        except Error as e:
            if connection:
                try:
                    connection.rollback()
                except Exception:
                    pass
            print(f"Error executing insert: {e}")
            raise
        finally:
            if cursor:
                try:
                    cursor.close()
                except Exception:
                    pass
            self._return_connection(connection)

    def _execute_update(self, query: str, params: tuple = None) -> int:
        """
        Execute UPDATE/DELETE query and return affected rows.
        
        Borrows a connection from the pool, executes the update with commit,
        and returns the connection to the pool when done.
        """
        connection = None
        cursor = None
        try:
            connection = self._get_connection()
            if connection is None:
                if os.getenv("ALLOW_DB_FAILURE", "false").lower() == "true":
                    return 0
                raise RuntimeError("Database connection unavailable")
            
            cursor = connection.cursor()
            cursor.execute(query, params)
            connection.commit()
            affected = cursor.rowcount
            return affected
        except Error as e:
            if connection:
                try:
                    connection.rollback()
                except Exception:
                    pass
            print(f"Error executing update: {e}")
            raise
        finally:
            if cursor:
                try:
                    cursor.close()
                except Exception:
                    pass
            self._return_connection(connection)

    def _execute_many(self, query: str, params_list: list) -> int:
        """
        Execute a query with multiple parameter sets (bulk insert/update).
        
        Borrows a connection from the pool, executes the bulk operation with commit,
        and returns the connection to the pool when done.
        
        Args:
            query: SQL query with parameter placeholders
            params_list: List of tuples, each containing parameters for one execution
            
        Returns:
            The lastrowid from the bulk operation (first inserted ID for auto-increment)
        """
        connection = None
        cursor = None
        try:
            connection = self._get_connection()
            if connection is None:
                if os.getenv("ALLOW_DB_FAILURE", "false").lower() == "true":
                    return 0
                raise RuntimeError("Database connection unavailable")
            
            cursor = connection.cursor()
            cursor.executemany(query, params_list)
            connection.commit()
            return cursor.lastrowid
        except Error as e:
            if connection:
                try:
                    connection.rollback()
                except Exception:
                    pass
            print(f"Error executing bulk operation: {e}")
            raise
        finally:
            if cursor:
                try:
                    cursor.close()
                except Exception:
                    pass
            self._return_connection(connection)

    def _execute_transaction(self, operations: list) -> list:
        """
        Execute multiple operations in a single transaction.
        
        Borrows a connection from the pool, executes all operations within
        a single transaction, commits on success or rolls back on failure,
        and returns the connection to the pool when done.
        
        Args:
            operations: List of tuples (query, params) to execute in order
            
        Returns:
            List of lastrowid for each operation
        """
        connection = None
        cursor = None
        results = []
        try:
            connection = self._get_connection()
            if connection is None:
                if os.getenv("ALLOW_DB_FAILURE", "false").lower() == "true":
                    return []
                raise RuntimeError("Database connection unavailable")
            
            cursor = connection.cursor()
            for query, params in operations:
                cursor.execute(query, params)
                results.append(cursor.lastrowid)
            
            connection.commit()
            return results
        except Error as e:
            if connection:
                try:
                    connection.rollback()
                except Exception:
                    pass
            print(f"Error executing transaction: {e}")
            raise
        finally:
            if cursor:
                try:
                    cursor.close()
                except Exception:
                    pass
            self._return_connection(connection)

    def close(self):
        """
        No-op for backward compatibility.
        
        Previously closed the dedicated connection. With connection pooling,
        this is no longer needed as connections are returned to the pool
        after each operation.
        """
        pass
