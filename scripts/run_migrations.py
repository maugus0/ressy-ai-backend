"""
Script to run MySQL migrations.
"""
import os
import sys
from pathlib import Path

import mysql.connector
from dotenv import load_dotenv
from mysql.connector import Error

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.utils.logging_config import get_logger, setup_logging

setup_logging()
logger = get_logger(__name__)

# Load environment variables
load_dotenv()


def get_connection():
    """Get MySQL connection."""
    try:
        connection = mysql.connector.connect(
            host=os.getenv('DB_HOST', 'localhost'),
            port=int(os.getenv('DB_PORT', 3306)),
            user=os.getenv('DB_USERNAME', 'root'),
            password=os.getenv('DB_PASSWORD', 'root')
        )
        return connection
    except Error as e:
        logger.error("Error connecting to MySQL: %s", e)
        raise


def create_database(connection, db_name):
    """Create database if it doesn't exist."""
    try:
        cursor = connection.cursor()
        cursor.execute(f"CREATE DATABASE IF NOT EXISTS {db_name}")
        logger.info("Database '%s' ready", db_name)
        cursor.close()
    except Error as e:
        logger.error("Error creating database: %s", e)
        raise


def run_migration_file(connection, file_path):
    """Run a single migration file."""
    try:
        cursor = connection.cursor()

        with open(file_path, 'r', encoding='utf-8') as f:
            sql_content = f.read()

        # Remove comments and split by semicolon
        lines = []
        for line in sql_content.split('\n'):
            # Remove full-line comments
            if line.strip().startswith('--'):
                continue
            # Remove inline comments (simple approach)
            if '--' in line:
                line = line[:line.index('--')]
            lines.append(line)

        # Join and split by semicolon
        cleaned_content = '\n'.join(lines)
        statements = [s.strip() for s in cleaned_content.split(';') if s.strip()]

        for statement in statements:
            if statement:
                try:
                    cursor.execute(statement)
                    connection.commit()
                except Error as e:
                    # Some errors are expected (like IF NOT EXISTS, or DROP INDEX when index missing)
                    error_msg = str(e).lower()
                    err_code = getattr(e, "errno", None)
                    skip_warning = (
                        "already exists" in error_msg
                        or "duplicate" in error_msg
                        or err_code == 1091  # Can't DROP; check that column/key exists
                        or "check that column/key exists" in error_msg
                    )
                    if not skip_warning:
                        logger.warning("Warning in %s: %s", file_path.name, e)
                        logger.warning("Statement: %s...", statement[:100])

        cursor.close()
        logger.info("Ran migration: %s", file_path.name)
        return True
    except Error as e:
        logger.error("Error running migration %s: %s", file_path.name, e)
        return False
    except Exception as e:
        logger.exception("Unexpected error in %s: %s", file_path.name, e)
        return False


def main():
    """Main function to run all migrations."""
    db_name = os.getenv('DB_NAME', 'ressy')
    migrations_dir = Path(__file__).parent.parent / 'migrations'

    logger.info("Starting migrations for database: %s", db_name)

    # Get connection (without database)
    connection = get_connection()

    try:
        # Create database
        create_database(connection, db_name)

        # Connect to the database
        connection.database = db_name

        # Get all migration files sorted
        migration_files = sorted([f for f in migrations_dir.glob('*.sql') if f.name.startswith('0')])

        logger.info("Found %s migration files", len(migration_files))

        # Run each migration
        for migration_file in migration_files:
            run_migration_file(connection, migration_file)

        logger.info("All migrations completed successfully!")

    except Error as e:
        logger.error("Migration error: %s", e)
    finally:
        if connection.is_connected():
            connection.close()
            logger.info("Database connection closed")


if __name__ == "__main__":
    main()
