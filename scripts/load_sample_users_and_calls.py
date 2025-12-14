"""
Load sample users and calls from JSON dumps into MySQL.

Reads `scripts/sample_users.json` and `scripts/sample_calls.json` and upserts rows
into the Users and Calls tables using environment-driven DB credentials.
"""

import json
import os
from pathlib import Path
from typing import Any, Iterable, Optional

import mysql.connector
from dotenv import load_dotenv
from mysql.connector import Error

# Load environment variables from .env if present
load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
USERS_PATH = BASE_DIR / "sample_users.json"
CALLS_PATH = BASE_DIR / "sample_calls.json"


def get_connection():
    """Create a MySQL connection from environment variables."""
    try:
        return mysql.connector.connect(
            host=os.getenv("DB_HOST", "localhost"),
            port=int(os.getenv("DB_PORT", 3306)),
            user=os.getenv("DB_USERNAME", "root"),
            password=os.getenv("DB_PASSWORD", "root"),
            database=os.getenv("DB_NAME", "ressy"),
        )
    except Error as exc:
        print(f"Error connecting to MySQL: {exc}")
        raise


def _normalize_blank(value: Optional[str]) -> Optional[str]:
    """Return None for blank strings to avoid unique/constraint issues."""
    if value is None:
        return None
    value = str(value).strip()
    return value or None


def load_json(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(f"Sample data file not found: {path}")
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def upsert_users(connection, users: Iterable[dict[str, Any]]) -> int:
    """Insert or update users based on primary key/unique constraints."""
    cursor = connection.cursor()
    query = """
        INSERT INTO Users (id, name, phone_number, email, address, is_spam, credit_card, created_at, updated_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
            name = VALUES(name),
            phone_number = VALUES(phone_number),
            email = VALUES(email),
            address = VALUES(address),
            is_spam = VALUES(is_spam),
            credit_card = VALUES(credit_card),
            created_at = VALUES(created_at),
            updated_at = VALUES(updated_at)
    """
    count = 0
    for user in users:
        payload = (
            user.get("id"),
            _normalize_blank(user.get("name")),
            _normalize_blank(user.get("phone_number")),
            _normalize_blank(user.get("email")),
            _normalize_blank(user.get("address")),
            bool(user.get("is_spam", False)),
            _normalize_blank(user.get("credit_card")),
            user.get("created_at"),
            user.get("updated_at"),
        )
        cursor.execute(query, payload)
        count += 1
    connection.commit()
    cursor.close()
    return count


def upsert_calls(connection, calls: Iterable[dict[str, Any]]) -> int:
    """Insert or update calls based on primary key."""
    cursor = connection.cursor()
    query = """
        INSERT INTO Calls (
            id, user_id, restaurant_id, twilio_call_sid, deepgram_request_id,
            call_status, call_direction, call_duration, cost,
            started_at, ended_at, created_at, updated_at, call_transcript
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
            user_id = VALUES(user_id),
            restaurant_id = VALUES(restaurant_id),
            twilio_call_sid = VALUES(twilio_call_sid),
            deepgram_request_id = VALUES(deepgram_request_id),
            call_status = VALUES(call_status),
            call_direction = VALUES(call_direction),
            call_duration = VALUES(call_duration),
            cost = VALUES(cost),
            started_at = VALUES(started_at),
            ended_at = VALUES(ended_at),
            created_at = VALUES(created_at),
            updated_at = VALUES(updated_at),
            call_transcript = VALUES(call_transcript)
    """
    count = 0
    for call in calls:
        payload = (
            call.get("id"),
            call.get("user_id"),
            _normalize_blank(call.get("restaurant_id")),
            call.get("twilio_call_sid"),
            call.get("deepgram_request_id"),
            call.get("call_status"),
            call.get("call_direction"),
            call.get("call_duration"),
            call.get("cost"),
            call.get("started_at"),
            call.get("ended_at"),
            call.get("created_at"),
            call.get("updated_at"),
            _normalize_blank(call.get("call_transcript")),
        )
        cursor.execute(query, payload)
        count += 1
    connection.commit()
    cursor.close()
    return count


def main() -> None:
    connection = get_connection()
    try:
        users = load_json(USERS_PATH)
        calls = load_json(CALLS_PATH)

        user_count = upsert_users(connection, users)
        call_count = upsert_calls(connection, calls)

        print(f"Upserted {user_count} users from {USERS_PATH.name}")
        print(f"Upserted {call_count} calls from {CALLS_PATH.name}")
    finally:
        if connection and connection.is_connected():
            connection.close()


if __name__ == "__main__":
    main()
