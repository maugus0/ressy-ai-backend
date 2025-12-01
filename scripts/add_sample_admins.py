"""
Create sample Ressy administrators and restaurant administrators for auth testing.
"""

import json
import os
import uuid

import bcrypt
import mysql.connector
from dotenv import load_dotenv
from mysql.connector import Error

# Load environment variables
load_dotenv()


def get_connection():
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


def ensure_permissions_and_role(connection, role_name: str, routes: list[str]) -> int:
    cursor = connection.cursor()
    cursor.execute("SELECT id FROM Crm_roles WHERE role = %s", (role_name,))
    row = cursor.fetchone()
    if row:
        cursor.close()
        return row[0]

    routes_json = json.dumps(routes)
    cursor.execute(
        "INSERT INTO Permissions (routes, created_at, updated_at) VALUES (%s, UTC_TIMESTAMP(), UTC_TIMESTAMP())",
        (routes_json,),
    )
    permission_id = cursor.lastrowid

    cursor.execute(
        """
        INSERT INTO Crm_roles (role, permission_id, created_at, updated_at)
        VALUES (%s, %s, UTC_TIMESTAMP(), UTC_TIMESTAMP())
        """,
        (role_name, permission_id),
    )
    role_id = cursor.lastrowid
    connection.commit()
    cursor.close()
    print(f"Created role '{role_name}' with permission_id={permission_id}")
    return role_id


def ensure_sample_restaurant(connection) -> int:
    cursor = connection.cursor()
    cursor.execute("SELECT id FROM Restaurants WHERE name = %s LIMIT 1", ("Ressy's Diner",))
    row = cursor.fetchone()
    if row:
        restaurant_id = row[0]
        cursor.close()
        return restaurant_id

    cursor.execute(
        """
        INSERT INTO Restaurants (
            name, address, phone_number, twilio_phone_number,
            twilio_details, deepgram_details, open_table_details,
            forward_minutes, backward_minutes, is_credit_card_required_for_reservation,
            created_at, updated_at
        ) VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, UTC_TIMESTAMP(), UTC_TIMESTAMP()
        )
        """,
        (
            "Ressy's Diner",
            "123 Main St, City, State",
            "+1234567890",
            "+14313404949",
            json.dumps({"account_sid": "sample", "auth_token": "sample"}),
            json.dumps({"api_key": "sample"}),
            json.dumps({"api_key": "sample"}),
            60,
            30,
            False,
        ),
    )
    restaurant_id = cursor.lastrowid
    connection.commit()
    cursor.close()
    print(f"Created sample restaurant with id={restaurant_id}")
    return restaurant_id


def _hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def ensure_admin(connection, email: str, password: str, role_id: int):
    cursor = connection.cursor()
    cursor.execute("SELECT uuid FROM Ressy_Administrator WHERE email = %s", (email,))
    row = cursor.fetchone()
    if row:
        print(f"Admin already exists with email={email}")
        cursor.close()
        return row[0]

    user_uuid = str(uuid.uuid4())
    cursor.execute(
        """
        INSERT INTO Ressy_Administrator (uuid, email, password, role_id, created_at, updated_at, last_login, last_active)
        VALUES (%s, %s, %s, %s, UTC_TIMESTAMP(), UTC_TIMESTAMP(), UTC_TIMESTAMP(), UTC_TIMESTAMP())
        """,
        (user_uuid, email, _hash_password(password), role_id),
    )
    connection.commit()
    cursor.close()
    print(f"Created admin user email={email} uuid={user_uuid}")
    return user_uuid


def ensure_restaurant_admin(connection, email: str, password: str, restaurant_id: int, role_id: int):
    cursor = connection.cursor()
    cursor.execute(
        "SELECT uuid FROM Restaurant_Administrators WHERE rest_id = %s AND email = %s",
        (restaurant_id, email),
    )
    row = cursor.fetchone()
    if row:
        print(f"Restaurant admin already exists rest_id={restaurant_id} email={email}")
        cursor.close()
        return row[0]

    user_uuid = str(uuid.uuid4())
    cursor.execute(
        """
        INSERT INTO Restaurant_Administrators (
            uuid, rest_id, email, password, role_id, created_at, updated_at, last_login, last_active
        ) VALUES (
            %s, %s, %s, %s, %s, UTC_TIMESTAMP(), UTC_TIMESTAMP(), UTC_TIMESTAMP(), UTC_TIMESTAMP()
        )
        """,
        (user_uuid, restaurant_id, email, _hash_password(password), role_id),
    )
    connection.commit()
    cursor.close()
    print(f"Created restaurant admin email={email} uuid={user_uuid} rest_id={restaurant_id}")
    return user_uuid


def main():
    connection = get_connection()
    try:
        admin_role_id = ensure_permissions_and_role(connection, "admin", ["*"])
        manager_role_id = ensure_permissions_and_role(connection, "manager", ["*"])

        restaurant_id = ensure_sample_restaurant(connection)

        admin_email = os.getenv("SAMPLE_ADMIN_EMAIL", "admin@ressy.ai")
        admin_password = os.getenv("SAMPLE_ADMIN_PASSWORD", "AdminPass!23")
        rest_admin_email = os.getenv("SAMPLE_RESTAURANT_ADMIN_EMAIL", "manager@restaurant.com")
        rest_admin_password = os.getenv("SAMPLE_RESTAURANT_ADMIN_PASSWORD", "ManagerPass!23")

        admin_uuid = ensure_admin(connection, admin_email, admin_password, admin_role_id)
        restaurant_admin_uuid = ensure_restaurant_admin(
            connection, rest_admin_email, rest_admin_password, restaurant_id, manager_role_id
        )

        print("\nSample admin users created/verified:")
        print(f"  Admin: {admin_email} / {admin_password} (uuid: {admin_uuid})")
        print(f"  Restaurant Admin: {rest_admin_email} / {rest_admin_password} (uuid: {restaurant_admin_uuid})")
        print(f"  Restaurant ID: {restaurant_id}")
    except Error as exc:
        print(f"Error creating sample admins: {exc}")
        raise
    finally:
        if connection.is_connected():
            connection.close()
            print("Database connection closed")


if __name__ == "__main__":
    main()
