"""
Script to run MySQL migrations with ledger-based tracking.
"""

import argparse
import hashlib
import os
import re
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional

import mysql.connector
from dotenv import load_dotenv
from mysql.connector import Error

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.utils.logging_config import get_logger, setup_logging

setup_logging()
logger = get_logger(__name__)

load_dotenv()

SCHEMA_MIGRATIONS_TABLE = "Schema_Migrations"
MIGRATION_FILENAME_PATTERN = re.compile(r"^\d+_.+\.sql$")
DB_IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z0-9_]+$")
MIGRATION_LOCK_NAME = "ressy_schema_migrations"
RECOVERABLE_SCHEMA_ERROR_CODES = {1050, 1060, 1061, 1091}


class MigrationError(RuntimeError):
    """Raised when migration execution should stop."""


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(description="Run tracked MySQL migrations.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show applied, pending, and checksum-mismatch migrations without changing the database.",
    )
    parser.add_argument(
        "--baseline-through",
        metavar="FILENAME",
        help="Mark migrations up to and including the specified filename as applied without executing them.",
    )
    args = parser.parse_args(argv)
    if args.dry_run and args.baseline_through:
        parser.error("--dry-run and --baseline-through cannot be used together")
    return args


def get_connection():
    """Get MySQL connection."""
    try:
        return mysql.connector.connect(
            host=os.getenv("DB_HOST", os.getenv("MYSQL_HOST", "localhost")),
            port=int(os.getenv("DB_PORT", os.getenv("MYSQL_PORT", 3306))),
            user=os.getenv("DB_USERNAME", os.getenv("MYSQL_USER", "root")),
            password=os.getenv("DB_PASSWORD", os.getenv("MYSQL_PASSWORD", "root")),
        )
    except Error as exc:
        logger.error("Error connecting to MySQL: %s", exc)
        raise


def validate_database_name(db_name: str) -> str:
    """Validate database identifier before interpolating it into SQL."""
    if not DB_IDENTIFIER_PATTERN.match(db_name):
        raise MigrationError("Invalid database name. Only letters, numbers, and underscores are allowed.")
    return db_name


def create_database(connection, db_name: str) -> None:
    """Create database if it doesn't exist."""
    cursor = None
    try:
        validated_db_name = validate_database_name(db_name)
        cursor = connection.cursor()
        cursor.execute(f"CREATE DATABASE IF NOT EXISTS `{validated_db_name}`")
        logger.info("Database '%s' ready", validated_db_name)
    except Error as exc:
        logger.error("Error creating database: %s", exc)
        raise
    finally:
        if cursor:
            cursor.close()


def ensure_schema_migrations_table(connection) -> None:
    """Ensure the migration ledger table exists."""
    query = f"""
        CREATE TABLE IF NOT EXISTS {SCHEMA_MIGRATIONS_TABLE} (
            id INT AUTO_INCREMENT PRIMARY KEY,
            filename VARCHAR(255) NOT NULL UNIQUE,
            checksum CHAR(64) NOT NULL,
            execution_time_ms INT NULL,
            applied_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """
    cursor = None
    try:
        cursor = connection.cursor()
        cursor.execute(query)
        connection.commit()
    except Error as exc:
        logger.error("Failed to ensure %s table exists: %s", SCHEMA_MIGRATIONS_TABLE, exc)
        raise
    finally:
        if cursor:
            cursor.close()


def acquire_migration_lock(connection, timeout_seconds: int = 30) -> None:
    """Acquire a MySQL advisory lock for migration planning/execution."""
    cursor = None
    try:
        cursor = connection.cursor()
        cursor.execute("SELECT GET_LOCK(%s, %s)", (MIGRATION_LOCK_NAME, timeout_seconds))
        row = cursor.fetchone()
        lock_acquired = int(row[0]) if row and row[0] is not None else 0
        if lock_acquired != 1:
            raise MigrationError("Could not acquire migration lock. Another migration process may be running.")
    except Error as exc:
        logger.error("Failed to acquire migration lock: %s", exc)
        raise
    finally:
        if cursor:
            cursor.close()


def release_migration_lock(connection) -> None:
    """Release the MySQL advisory lock if held."""
    cursor = None
    try:
        cursor = connection.cursor()
        cursor.execute("SELECT RELEASE_LOCK(%s)", (MIGRATION_LOCK_NAME,))
    except Error as exc:
        logger.warning("Failed to release migration lock: %s", exc)
    finally:
        if cursor:
            cursor.close()


def get_migration_files(migrations_dir: Path) -> List[Path]:
    """Return migration files sorted by filename."""
    return sorted(
        [file_path for file_path in migrations_dir.glob("*.sql") if MIGRATION_FILENAME_PATTERN.match(file_path.name)]
    )


def calculate_checksum(file_path: Path) -> str:
    """Calculate a stable SHA-256 checksum for a migration file."""
    return hashlib.sha256(file_path.read_bytes()).hexdigest()


def get_applied_migrations(connection) -> Dict[str, str]:
    """Return applied migration filenames mapped to their recorded checksums."""
    query = f"SELECT filename, checksum FROM {SCHEMA_MIGRATIONS_TABLE} ORDER BY filename ASC"
    cursor = None
    try:
        cursor = connection.cursor(dictionary=True)
        cursor.execute(query)
        rows = cursor.fetchall()
        return {str(row["filename"]): str(row["checksum"]) for row in rows}
    except Error as exc:
        logger.error("Failed to load applied migrations: %s", exc)
        raise
    finally:
        if cursor:
            cursor.close()


def record_applied_migration(connection, filename: str, checksum: str, execution_time_ms: Optional[int]) -> None:
    """Insert a migration ledger row."""
    query = f"""
        INSERT INTO {SCHEMA_MIGRATIONS_TABLE} (filename, checksum, execution_time_ms)
        VALUES (%s, %s, %s)
    """
    cursor = None
    try:
        cursor = connection.cursor()
        cursor.execute(query, (filename, checksum, execution_time_ms))
        connection.commit()
    except Error as exc:
        logger.error("Failed to record migration %s: %s", filename, exc)
        raise
    finally:
        if cursor:
            cursor.close()


def split_sql_statements(sql_content: str) -> List[str]:
    """Remove simple SQL comments and split by semicolon."""
    lines: List[str] = []
    for line in sql_content.split("\n"):
        stripped = line.strip()
        if stripped.startswith("--"):
            continue
        if "--" in line:
            line = line[: line.index("--")]
        lines.append(line)
    cleaned_content = "\n".join(lines)
    return [statement.strip() for statement in cleaned_content.split(";") if statement.strip()]


def is_recoverable_schema_error(exc: Error) -> bool:
    """Return True only for known schema-replay errors that are safe to skip."""
    err_code = getattr(exc, "errno", None)
    if err_code in RECOVERABLE_SCHEMA_ERROR_CODES:
        return True

    error_msg = str(exc).lower()
    return "check that column/key exists" in error_msg


def run_migration_file(connection, file_path: Path) -> int:
    """Run a single migration file and return execution time in milliseconds."""
    cursor = None
    try:
        statements = split_sql_statements(file_path.read_text(encoding="utf-8"))
        cursor = connection.cursor()
        started_at = time.time()
        for statement in statements:
            try:
                cursor.execute(statement)
                connection.commit()
            except Error as exc:
                try:
                    connection.rollback()
                except Exception:  # pragma: no cover - defensive
                    pass
                if is_recoverable_schema_error(exc):
                    logger.warning(
                        "Recoverable migration warning in %s: %s",
                        file_path.name,
                        exc,
                    )
                    continue
                raise
        duration_ms = int((time.time() - started_at) * 1000)
        logger.info("Applied migration: %s", file_path.name)
        return duration_ms
    except Error as exc:
        logger.error("Error running migration %s: %s", file_path.name, exc)
        raise MigrationError(f"Migration failed for {file_path.name}: {exc}") from exc
    except Exception as exc:  # pragma: no cover - defensive
        logger.exception("Unexpected error in %s: %s", file_path.name, exc)
        raise MigrationError(f"Unexpected migration error in {file_path.name}: {exc}") from exc
    finally:
        if cursor:
            cursor.close()


def classify_migrations(migration_files: List[Path], applied_migrations: Dict[str, str]) -> Dict[str, List[str]]:
    """Classify migrations into applied, pending, and checksum mismatches."""
    applied: List[str] = []
    pending: List[str] = []
    mismatched: List[str] = []
    for file_path in migration_files:
        checksum = calculate_checksum(file_path)
        recorded_checksum = applied_migrations.get(file_path.name)
        if recorded_checksum is None:
            pending.append(file_path.name)
            continue
        if recorded_checksum != checksum:
            mismatched.append(file_path.name)
            continue
        applied.append(file_path.name)
    return {"applied": applied, "pending": pending, "mismatched": mismatched}


def resolve_baseline_target(migration_files: List[Path], target_filename: str) -> int:
    """Resolve the exact migration index for baseline-through."""
    for index, file_path in enumerate(migration_files):
        if file_path.name == target_filename:
            return index
    raise MigrationError(f"Baseline target '{target_filename}' not found in migrations directory")


def log_migration_plan(plan: Dict[str, List[str]]) -> None:
    """Log the current migration plan."""
    logger.info("Applied migrations: %s", len(plan["applied"]))
    for filename in plan["applied"]:
        logger.info("  [APPLIED] %s", filename)

    logger.info("Pending migrations: %s", len(plan["pending"]))
    for filename in plan["pending"]:
        logger.info("  [PENDING] %s", filename)

    logger.info("Checksum mismatches: %s", len(plan["mismatched"]))
    for filename in plan["mismatched"]:
        logger.error("  [MISMATCH] %s", filename)


def baseline_through(
    connection, migration_files: List[Path], applied_migrations: Dict[str, str], target_filename: str
) -> None:
    """Mark migrations up to and including target_filename as applied without executing them."""
    cutoff_index = resolve_baseline_target(migration_files, target_filename)
    for file_path in migration_files[: cutoff_index + 1]:
        checksum = calculate_checksum(file_path)
        recorded_checksum = applied_migrations.get(file_path.name)
        if recorded_checksum is not None:
            if recorded_checksum != checksum:
                raise MigrationError(
                    f"Checksum mismatch for already-recorded migration {file_path.name}; baseline cannot continue"
                )
            logger.info("Skipping already-recorded migration during baseline: %s", file_path.name)
            continue
        record_applied_migration(connection, file_path.name, checksum, execution_time_ms=None)
        logger.info("Baselined migration: %s", file_path.name)


def apply_pending_migrations(connection, migration_files: List[Path], applied_migrations: Dict[str, str]) -> None:
    """Apply only pending migrations, failing on checksum drift."""
    for file_path in migration_files:
        checksum = calculate_checksum(file_path)
        recorded_checksum = applied_migrations.get(file_path.name)
        if recorded_checksum is not None:
            if recorded_checksum != checksum:
                raise MigrationError(
                    f"Checksum mismatch for already-applied migration {file_path.name}. "
                    "Historical migration files must not be modified."
                )
            logger.info("Skipping already-applied migration: %s", file_path.name)
            continue

        execution_time_ms = run_migration_file(connection, file_path)
        record_applied_migration(connection, file_path.name, checksum, execution_time_ms)


def main(argv: Optional[List[str]] = None) -> int:
    """Run tracked migrations or operator modes."""
    args = parse_args(argv)
    db_name = os.getenv("DB_NAME", os.getenv("MYSQL_DATABASE", "ressy"))
    migrations_dir = ROOT_DIR / "migrations"
    logger.info("Starting migrations for database: %s", db_name)

    connection = None
    try:
        connection = get_connection()
        create_database(connection, db_name)
        connection.database = db_name
        ensure_schema_migrations_table(connection)
        acquire_migration_lock(connection)

        migration_files = get_migration_files(migrations_dir)
        logger.info("Found %s migration files", len(migration_files))

        applied_migrations = get_applied_migrations(connection)
        plan = classify_migrations(migration_files, applied_migrations)

        if plan["mismatched"]:
            log_migration_plan(plan)
            raise MigrationError("Checksum mismatches detected. Resolve them before continuing.")

        if args.dry_run:
            log_migration_plan(plan)
            logger.info("Dry-run complete. No database changes made.")
            return 0

        if args.baseline_through:
            baseline_through(connection, migration_files, applied_migrations, args.baseline_through)
            logger.info("Baseline-through complete up to %s", args.baseline_through)
            return 0

        apply_pending_migrations(connection, migration_files, applied_migrations)
        logger.info("All pending migrations completed successfully!")
        return 0
    except (Error, MigrationError) as exc:
        logger.error("Migration error: %s", exc)
        return 1
    finally:
        if connection is not None and connection.is_connected():
            release_migration_lock(connection)
            connection.close()
            logger.info("Database connection closed")


if __name__ == "__main__":
    raise SystemExit(main())
