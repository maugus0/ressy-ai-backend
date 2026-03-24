import os
import json
import mysql.connector
from dotenv import load_dotenv

load_dotenv()

try:
    connection = mysql.connector.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", 3306)),
        user=os.getenv("DB_USERNAME", "root"),
        password=os.getenv("DB_PASSWORD", "root"),
        database=os.getenv("DB_NAME", "ressy"),
    )
    cursor = connection.cursor()

    # Update default_order_options from TAKEOUT to PICKUP
    new_options = json.dumps({"dining_option": "PICKUP"})
    cursor.execute(
        "UPDATE POS_Integrations SET default_order_options = %s WHERE default_order_options LIKE %s",
        (new_options, "%TAKEOUT%"),
    )
    connection.commit()
    print(f"Updated {cursor.rowcount} integration(s)")

    # Show updated integrations
    cursor.execute("SELECT id, restaurant_id, pos_type, default_order_options FROM POS_Integrations")
    results = cursor.fetchall()
    print("\nUpdated integrations:")
    for r in results:
        print(f"  ID: {r[0]}, Restaurant: {r[1]}, Type: {r[2]}, Options: {r[3]}")

except mysql.connector.Error as err:
    print(f"Error: {err}")
finally:
    if "cursor" in locals() and cursor:
        cursor.close()
    if "connection" in locals() and connection.is_connected():
        connection.close()
