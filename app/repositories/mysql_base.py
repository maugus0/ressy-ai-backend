"""
MySQL Base Repository for database operations.
This is a placeholder for MySQL operations - adapt based on your MySQL connection library.
"""

import os
from typing import Any, Dict, List

import mysql.connector
from dotenv import load_dotenv
from mysql.connector import Error

# Load environment variables from .env file
# TODO: Investigate import order - this shouldn't be needed if config.py loads first
load_dotenv()


class MySQLBaseRepository:
    """Base repository for MySQL database operations."""

    def __init__(self):
        self.connection = None
        self._connect()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def __del__(self):
        self.close()

    def _connect(self):
        """Establish MySQL connection."""
        try:
            # Close existing connection if it exists
            if self.connection:
                try:
                    if self.connection.is_connected():
                        self.connection.close()
                except (AttributeError, Error):
                    # Connection is in invalid state, ignore
                    pass
        except Exception:
            # Ignore any errors when closing old connection
            pass

        try:
            self.connection = mysql.connector.connect(
                host=os.getenv("DB_HOST", os.getenv("MYSQL_HOST", "localhost")),
                database=os.getenv("DB_NAME", os.getenv("MYSQL_DATABASE", "ressy")),
                user=os.getenv("DB_USERNAME", os.getenv("MYSQL_USER", "root")),
                password=os.getenv("DB_PASSWORD", os.getenv("MYSQL_PASSWORD", "root")),
                port=int(os.getenv("DB_PORT", os.getenv("MYSQL_PORT", 3306))),
                connection_timeout=5,  # Add timeout for faster failure in tests
            )
        except Error as e:
            error_msg = f"Error connecting to MySQL: {e}"
            print(error_msg)
            # In test mode, allow connection to fail without raising
            if os.getenv("ALLOW_DB_FAILURE", "false").lower() == "true":
                self.connection = None
                return
            raise

    def _ensure_connected(self):
        """Ensure database connection is active, reconnect if needed."""
        try:
            if not self.connection or not self.connection.is_connected():
                print("[INFO] MySQL connection closed, reconnecting...")
                self._connect()
        except (AttributeError, Error):
            # Connection object exists but is in invalid state
            print("[INFO] MySQL connection in invalid state, reconnecting...")
            self.connection = None
            self._connect()

    def _execute_query(self, query: str, params: tuple = None) -> List[Dict[str, Any]]:
        """Execute SELECT query and return results."""
        self._ensure_connected()
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
        self._ensure_connected()
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
        self._ensure_connected()
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
        try:
            if self.connection and self.connection.is_connected():
                self.connection.close()
        except (AttributeError, Error):
            # Connection is already closed or in invalid state
            pass
        finally:
            self.connection = None
