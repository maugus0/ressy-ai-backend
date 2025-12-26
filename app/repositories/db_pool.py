"""
MySQL Connection Pool Manager.

This module provides a singleton connection pool for efficient database connections.
Instead of creating a new connection for each API request, connections are borrowed
from and returned to a shared pool, significantly improving performance under load.
"""

import os
import threading
import time
from contextlib import contextmanager
from typing import Optional

from dotenv import load_dotenv
from mysql.connector import Error
from mysql.connector.pooling import MySQLConnectionPool, PooledMySQLConnection

from app.utils.logging_config import get_logger

# Load environment variables
load_dotenv()

logger = get_logger(__name__)


def _should_log_connections() -> bool:
    """Check if connection logging is enabled via environment variable."""
    return os.getenv("DB_POOL_LOG_CONNECTIONS", "false").lower() in ("true", "1", "yes")


class DatabasePool:
    """
    Singleton connection pool manager for MySQL.

    Thread-safe implementation that provides a shared pool of database connections.
    Connections are borrowed from the pool and automatically returned when done.

    Enable connection logging for testing by setting:
        DB_POOL_LOG_CONNECTIONS=true
    """

    _instance: Optional["DatabasePool"] = None
    _lock: threading.Lock = threading.Lock()
    _pool: Optional[MySQLConnectionPool] = None
    _initialized: bool = False

    # Connection tracking for logging
    _active_connections: int = 0
    _total_connections_served: int = 0
    _connections_lock: threading.Lock = threading.Lock()

    def __new__(cls) -> "DatabasePool":
        if cls._instance is None:
            with cls._lock:
                # Double-checked locking pattern
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        # Only initialize once
        if DatabasePool._initialized:
            return

        with DatabasePool._lock:
            if DatabasePool._initialized:
                return

            self._create_pool()
            DatabasePool._initialized = True

    def _get_pool_config(self) -> dict:
        """Get database configuration from environment variables."""
        return {
            "host": os.getenv("DB_HOST", os.getenv("MYSQL_HOST", "localhost")),
            "database": os.getenv("DB_NAME", os.getenv("MYSQL_DATABASE", "ressy")),
            "user": os.getenv("DB_USERNAME", os.getenv("MYSQL_USER", "root")),
            "password": os.getenv("DB_PASSWORD", os.getenv("MYSQL_PASSWORD", "root")),
            "port": int(os.getenv("DB_PORT", os.getenv("MYSQL_PORT", 3306))),
            "connection_timeout": int(os.getenv("DB_CONNECTION_TIMEOUT", 20)),
            "autocommit": False,
        }

    def _create_pool(self) -> None:
        """Create the connection pool."""
        try:
            config = self._get_pool_config()
            pool_size = int(os.getenv("DB_POOL_SIZE", 10))
            pool_name = os.getenv("DB_POOL_NAME", "ressy_pool")

            self._pool = MySQLConnectionPool(
                pool_name=pool_name, pool_size=pool_size, pool_reset_session=True, **config
            )
            logger.info("Created connection pool '%s' with size %d", pool_name, pool_size)
            if _should_log_connections():
                logger.info("Connection logging ENABLED (DB_POOL_LOG_CONNECTIONS=true)")
        except Error as e:
            logger.error("Error creating connection pool: %s", e)
            # In test mode, allow pool creation to fail without raising
            if os.getenv("ALLOW_DB_FAILURE", "false").lower() == "true":
                self._pool = None
                return
            raise

    def _log_connection_borrowed(self, conn_id: int) -> None:
        """Log when a connection is borrowed from the pool."""
        if not _should_log_connections():
            return

        with self._connections_lock:
            DatabasePool._active_connections += 1
            DatabasePool._total_connections_served += 1
            active = DatabasePool._active_connections
            total = DatabasePool._total_connections_served

        thread_id = threading.current_thread().ident
        pool_size = self._pool.pool_size if self._pool else 0
        logger.debug(
            "BORROW conn_id=%d thread=%s active=%d/%d total_served=%d",
            conn_id,
            thread_id,
            active,
            pool_size,
            total,
        )

    def _log_connection_returned(self, conn_id: int, duration_ms: float) -> None:
        """Log when a connection is returned to the pool."""
        if not _should_log_connections():
            return

        with self._connections_lock:
            DatabasePool._active_connections = max(0, DatabasePool._active_connections - 1)
            active = DatabasePool._active_connections

        thread_id = threading.current_thread().ident
        pool_size = self._pool.pool_size if self._pool else 0
        logger.debug(
            "RETURN conn_id=%d thread=%s active=%d/%d held_for=%.1fms",
            conn_id,
            thread_id,
            active,
            pool_size,
            duration_ms,
        )

    def get_connection(self) -> Optional[PooledMySQLConnection]:
        """
        Get a connection from the pool.

        Returns:
            A pooled MySQL connection, or None if pool is unavailable.

        Note:
            The caller is responsible for returning the connection by calling
            connection.close() when done. This doesn't close the underlying
            connection - it returns it to the pool.
        """
        if self._pool is None:
            if os.getenv("ALLOW_DB_FAILURE", "false").lower() == "true":
                return None
            raise RuntimeError("Database pool not initialized")

        try:
            connection = self._pool.get_connection()

            # Log and wrap connection for tracking
            if _should_log_connections() and connection:
                conn_id = id(connection)
                self._log_connection_borrowed(conn_id)
                # Store metadata for return logging
                connection._pool_borrow_time = time.time()
                connection._pool_conn_id = conn_id

            return connection
        except Error as e:
            logger.error("Error getting connection from pool: %s", e)
            if os.getenv("ALLOW_DB_FAILURE", "false").lower() == "true":
                return None
            raise

    def return_connection(self, connection: PooledMySQLConnection) -> None:
        """
        Return a connection to the pool with logging.

        This is called internally - users should just call connection.close()
        which returns the connection to the pool.
        """
        if connection is None:
            return

        # Log return if tracking is enabled
        if _should_log_connections():
            conn_id = getattr(connection, "_pool_conn_id", id(connection))
            borrow_time = getattr(connection, "_pool_borrow_time", None)
            duration_ms = (time.time() - borrow_time) * 1000 if borrow_time else 0
            self._log_connection_returned(conn_id, duration_ms)

        try:
            connection.close()  # Returns to pool
        except Exception as e:
            # Log but don't raise - we're in cleanup and the connection
            # may already be in an invalid state
            logger.warning("Error returning connection to pool: %s", e)

    @contextmanager
    def connection(self):
        """
        Context manager for safely borrowing and returning connections.

        Usage:
            with pool.connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT ...")

        The connection is automatically returned to the pool when the
        context exits, even if an exception occurs.
        """
        conn = self.get_connection()
        try:
            yield conn
        finally:
            if conn:
                self.return_connection(conn)

    def close_pool(self) -> None:
        """
        Close all connections in the pool.

        Call this during application shutdown to cleanly release all connections.
        """
        # Note: mysql-connector-python's MySQLConnectionPool doesn't have a
        # built-in close_all method. The pool will be garbage collected.
        # We mark as uninitialized so a new pool can be created if needed.
        with DatabasePool._lock:
            if _should_log_connections():
                logger.info(
                    "Closing pool. Stats: total_served=%d",
                    DatabasePool._total_connections_served,
                )
            self._pool = None
            DatabasePool._initialized = False
            DatabasePool._active_connections = 0
            logger.info("Connection pool closed")

    @property
    def is_available(self) -> bool:
        """Check if the pool is available and ready for connections."""
        return self._pool is not None

    def get_pool_stats(self) -> dict:
        """
        Get pool statistics for monitoring.

        Returns:
            Dictionary with pool configuration and status.
        """
        if self._pool is None:
            return {
                "available": False,
                "pool_name": None,
                "pool_size": 0,
                "active_connections": 0,
                "total_connections_served": 0,
            }

        with self._connections_lock:
            active = DatabasePool._active_connections
            total = DatabasePool._total_connections_served

        return {
            "available": True,
            "pool_name": self._pool.pool_name,
            "pool_size": self._pool.pool_size,
            "active_connections": active,
            "total_connections_served": total,
        }


# Global pool instance (lazy initialization)
_db_pool: Optional[DatabasePool] = None


def get_db_pool() -> DatabasePool:
    """
    Get the global database pool instance.

    This function provides lazy initialization of the pool singleton.
    The pool is created on first access.

    Returns:
        The global DatabasePool instance.
    """
    global _db_pool
    if _db_pool is None:
        _db_pool = DatabasePool()
    return _db_pool


def close_db_pool() -> None:
    """
    Close the global database pool.

    Call this during application shutdown to cleanly release all connections.
    """
    global _db_pool
    if _db_pool is not None:
        _db_pool.close_pool()
        _db_pool = None
