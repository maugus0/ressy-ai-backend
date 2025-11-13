"""
Script to add sample data (restaurant, menu items, FAQs).
"""
import json
import os

import mysql.connector
from dotenv import load_dotenv
from mysql.connector import Error

# Load environment variables
load_dotenv()


def get_connection():
    """Get MySQL connection."""
    try:
        connection = mysql.connector.connect(
            host=os.getenv('DB_HOST', 'localhost'),
            port=int(os.getenv('DB_PORT', 3306)),
            user=os.getenv('DB_USERNAME', 'root'),
            password=os.getenv('DB_PASSWORD', 'root'),
            database=os.getenv('DB_NAME', 'ressy')
        )
        return connection
    except Error as e:
        print(f"Error connecting to MySQL: {e}")
        raise


def add_sample_restaurant(connection):
    """Add a sample restaurant."""
    try:
        cursor = connection.cursor()

        # Check if restaurant already exists
        cursor.execute("SELECT id FROM Restaurants WHERE name = 'Sample Restaurant'")
        result = cursor.fetchone()

        if result:
            restaurant_id = result[0]
            print(f"Restaurant already exists with id: {restaurant_id}")
        else:
            query = """
                INSERT INTO Restaurants (
                    name, address, phone_number, twilio_phone_number,
                    twilio_details, deepgram_details, open_table_details,
                    forward_minutes, backward_minutes, is_credit_card_required_for_reservation
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """

            twilio_details = json.dumps({"account_sid": "sample", "auth_token": "sample"})
            deepgram_details = json.dumps({"api_key": "sample"})
            open_table_details = json.dumps({"api_key": "sample"})

            values = (
                "Ressy's Diner",
                "123 Main St, City, State 12345",
                "+1234567890",
                "+14313404949",  # This is the Twilio number to match calls
                twilio_details,
                deepgram_details,
                open_table_details,
                60,  # forward_minutes
                30,  # backward_minutes
                False
            )

            cursor.execute(query, values)
            connection.commit()
            restaurant_id = cursor.lastrowid
            print(f"Added restaurant with id: {restaurant_id}")

        cursor.close()
        return restaurant_id

    except Error as e:
        print(f"Error adding restaurant: {e}")
        raise


def add_sample_menu_items(connection, restaurant_id):
    """Add sample menu items."""
    try:
        cursor = connection.cursor()

        menu_items = [
            {
                "category": "Appetizers",
                "sub_category": "Cold",
                "item_name": "Caesar Salad",
                "item_desc": "Fresh romaine lettuce with caesar dressing, croutons, and parmesan",
                "price": 12.99,
                "avg_prep_time": 10,
                "is_available": True,
                "is_special": False
            },
            {
                "category": "Appetizers",
                "sub_category": "Hot",
                "item_name": "Buffalo Wings",
                "item_desc": "Spicy buffalo wings served with blue cheese and celery",
                "price": 14.99,
                "avg_prep_time": 15,
                "is_available": True,
                "is_special": True
            },
            {
                "category": "Main Course",
                "sub_category": "Pasta",
                "item_name": "Spaghetti Carbonara",
                "item_desc": "Classic Italian pasta with bacon, eggs, and parmesan cheese",
                "price": 18.99,
                "avg_prep_time": 20,
                "is_available": True,
                "is_special": False
            },
            {
                "category": "Main Course",
                "sub_category": "Pasta",
                "item_name": "Fettuccine Alfredo",
                "item_desc": "Creamy alfredo sauce with fettuccine pasta",
                "price": 16.99,
                "avg_prep_time": 18,
                "is_available": True,
                "is_special": False
            },
            {
                "category": "Main Course",
                "sub_category": "Pizza",
                "item_name": "Margherita Pizza",
                "item_desc": "Classic pizza with tomato sauce, mozzarella, and basil",
                "price": 15.99,
                "avg_prep_time": 15,
                "is_available": True,
                "is_special": False
            },
            {
                "category": "Main Course",
                "sub_category": "Pizza",
                "item_name": "Pepperoni Pizza",
                "item_desc": "Pizza with pepperoni and mozzarella cheese",
                "price": 17.99,
                "avg_prep_time": 15,
                "is_available": True,
                "is_special": False
            },
            {
                "category": "Main Course",
                "sub_category": "Burgers",
                "item_name": "Classic Burger",
                "item_desc": "Beef patty with lettuce, tomato, onion, and special sauce",
                "price": 13.99,
                "avg_prep_time": 12,
                "is_available": True,
                "is_special": False
            },
            {
                "category": "Desserts",
                "sub_category": None,
                "item_name": "Chocolate Cake",
                "item_desc": "Rich chocolate cake with chocolate frosting",
                "price": 8.99,
                "avg_prep_time": 5,
                "is_available": True,
                "is_special": False
            },
            {
                "category": "Desserts",
                "sub_category": None,
                "item_name": "Tiramisu",
                "item_desc": "Classic Italian dessert with coffee and mascarpone",
                "price": 9.99,
                "avg_prep_time": 5,
                "is_available": True,
                "is_special": True
            },
            {
                "category": "Beverages",
                "sub_category": "Soft Drinks",
                "item_name": "Coca Cola",
                "item_desc": None,
                "price": 2.99,
                "avg_prep_time": 2,
                "is_available": True,
                "is_special": False
            }
        ]

        query = """
            INSERT INTO Menus (
                restaurant_id, category, sub_category, item_name, item_desc,
                price, avg_prep_time, suggested_items, is_available, is_special
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """

        added_count = 0
        for item in menu_items:
            try:
                suggested_items = json.dumps([])  # Empty array for now
                values = (
                    restaurant_id,
                    item["category"],
                    item.get("sub_category"),
                    item["item_name"],
                    item.get("item_desc"),
                    item["price"],
                    item["avg_prep_time"],
                    suggested_items,
                    item["is_available"],
                    item["is_special"]
                )
                cursor.execute(query, values)
                added_count += 1
            except Error as e:
                # Skip if already exists
                if "Duplicate" not in str(e):
                    print(f"Error adding menu item {item['item_name']}: {e}")

        connection.commit()
        cursor.close()
        print(f"Added {added_count} menu items")

    except Error as e:
        print(f"Error adding menu items: {e}")
        raise


def add_sample_faqs(connection, restaurant_id):
    """Add sample FAQs."""
    try:
        cursor = connection.cursor()

        faqs = [
            {
                "question": "What are your operating hours?",
                "answer": "We are open Monday through Sunday from 11:00 AM to 10:00 PM."
            },
            {
                "question": "Do you offer delivery?",
                "answer": "No, we do not offer delivery at the moment, but you can speak with our manager for any special requests."
            },
            {
                "question": "Do you accept reservations?",
                "answer": "Yes, we accept reservations for parties of 2 or more. You can make a reservation by calling us or through our website."
            },
            {
                "question": "What payment methods do you accept?",
                "answer": "We accept cash, credit cards, and debit cards. We also accept mobile payment methods like Apple Pay and Google Pay."
            },
            {
                "question": "Do you have vegetarian options?",
                "answer": "Yes, we have several vegetarian options including our Caesar Salad, Margherita Pizza, and Fettuccine Alfredo."
            },
            {
                "question": "Is there parking available?",
                "answer": "Yes, we have free parking available in our parking lot. Street parking is also available."
            },
            {
                "question": "Do you cater events?",
                "answer": "Yes, we offer catering services for events. Please call us at least 48 hours in advance to place a catering order."
            },
            {
                "question": "Are you wheelchair accessible?",
                "answer": "Yes, our restaurant is fully wheelchair accessible with ramps and accessible restrooms."
            }
        ]

        query = """
            INSERT INTO FAQs (restaurant_id, question, answer)
            VALUES (%s, %s, %s)
        """

        added_count = 0
        for faq in faqs:
            try:
                values = (restaurant_id, faq["question"], faq["answer"])
                cursor.execute(query, values)
                added_count += 1
            except Error as e:
                # Skip if already exists
                if "Duplicate" not in str(e):
                    print(f"Error adding FAQ: {e}")

        connection.commit()
        cursor.close()
        print(f"Added {added_count} FAQs")

    except Error as e:
        print(f"Error adding FAQs: {e}")
        raise


def main():
    """Main function to add sample data."""
    print("Adding sample data...")

    connection = get_connection()

    try:
        # Add restaurant
        restaurant_id = add_sample_restaurant(connection)

        # Add menu items
        add_sample_menu_items(connection, restaurant_id)

        # Add FAQs
        add_sample_faqs(connection, restaurant_id)

        print("\nSample data added successfully!")
        print(f"Twilio Number to use for testing: +14313404949")
        print(f"Restaurant ID: {restaurant_id}")

    except Error as e:
        print(f"Error adding sample data: {e}")
    finally:
        if connection.is_connected():
            connection.close()
            print("Database connection closed")


if __name__ == "__main__":
    main()
