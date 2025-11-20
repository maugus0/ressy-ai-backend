"""
Script to seed pilot restaurant data (4 restaurants with menus).
This script adds restaurants and their menu items to the database.
"""
import mysql.connector
from mysql.connector import Error
import os
from dotenv import load_dotenv
import json

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

def add_restaurant(connection, restaurant_data):
    """Add a restaurant and return its ID."""
    try:
        cursor = connection.cursor()
        
        # Check if restaurant already exists
        cursor.execute("SELECT id FROM Restaurants WHERE name = %s", (restaurant_data['name'],))
        result = cursor.fetchone()
        
        if result:
            restaurant_id = result[0]
            print(f"[OK] Restaurant '{restaurant_data['name']}' already exists with id: {restaurant_id}")
            cursor.close()
            return restaurant_id
        
        query = """
            INSERT INTO Restaurants (
                name, address, phone_number, twilio_phone_number,
                twilio_details, deepgram_details, open_table_details,
                forward_minutes, backward_minutes, is_credit_card_required_for_reservation
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        
        twilio_details = json.dumps({})
        deepgram_details = json.dumps({})
        open_table_details = json.dumps({})
        
        values = (
            restaurant_data['name'],
            restaurant_data['address'],
            restaurant_data['phone_number'],
            restaurant_data.get('twilio_phone_number', restaurant_data['phone_number']),
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
        print(f"[OK] Added restaurant '{restaurant_data['name']}' with id: {restaurant_id}")
        
        cursor.close()
        return restaurant_id
        
    except Error as e:
        print(f"[ERROR] Error adding restaurant {restaurant_data['name']}: {e}")
        raise

def add_menu_items(connection, restaurant_id, menu_items):
    """Add menu items for a restaurant."""
    try:
        cursor = connection.cursor()
        
        query = """
            INSERT INTO Menus (
                restaurant_id, category, sub_category, item_name, item_desc,
                price, avg_prep_time, suggested_items, is_available, is_special
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        
        added_count = 0
        skipped_count = 0
        
        for item in menu_items:
            try:
                # Check if item already exists
                cursor.execute(
                    "SELECT id FROM Menus WHERE restaurant_id = %s AND item_name = %s",
                    (restaurant_id, item['item_name'])
                )
                if cursor.fetchone():
                    skipped_count += 1
                    continue
                
                suggested_items = json.dumps(item.get('suggested_items', []))
                values = (
                    restaurant_id,
                    item.get('category'),
                    item.get('sub_category'),
                    item['item_name'],
                    item.get('item_desc'),
                    item['price'],
                    item.get('avg_prep_time', 15),
                    suggested_items,
                    item.get('is_available', True),
                    item.get('is_special', False)
                )
                cursor.execute(query, values)
                added_count += 1
            except Error as e:
                if "Duplicate" not in str(e):
                    print(f"  [ERROR] Error adding menu item '{item['item_name']}': {e}")
        
        connection.commit()
        cursor.close()
        print(f"  [OK] Added {added_count} menu items (skipped {skipped_count} duplicates)")
        
    except Error as e:
        print(f"[ERROR] Error adding menu items: {e}")
        raise

# Restaurant 1: Amici Italian Grill & Lounge
amici_menu = [
    # Antipasti
    {"category": "Antipasti", "item_name": "Bruschetta", "price": 10.50, "avg_prep_time": 10},
    {"category": "Antipasti", "item_name": "Mozzarella Carrozza", "price": 12.95, "item_desc": "Deep fried cheese with dip", "avg_prep_time": 12},
    {"category": "Antipasti", "item_name": "Gamberi", "price": 15.75, "item_desc": "Prawns in sambuca or garlic and butter sauce", "avg_prep_time": 15},
    {"category": "Antipasti", "item_name": "Calamari", "price": 16.95, "avg_prep_time": 12},
    {"category": "Antipasti", "item_name": "Zucchini Sticks", "price": 13.50, "item_desc": "With tzatziki sauce", "avg_prep_time": 10},
    {"category": "Antipasti", "item_name": "Chicken Wings", "price": 24.50, "avg_prep_time": 18},
    {"category": "Antipasti", "item_name": "Salsicce", "price": 22.95, "item_desc": "Italian sausage sautéed in spicy tomato sauce", "avg_prep_time": 15},
    {"category": "Antipasti", "item_name": "Meatballs Marinara", "price": 14.50, "avg_prep_time": 12},
    {"category": "Antipasti", "item_name": "Dry Ribs", "price": 17.50, "item_desc": "A mound of yummy pork ribs", "avg_prep_time": 20},
    {"category": "Antipasti", "item_name": "Amici Bruschetta", "price": 14.95, "item_desc": "Pizza sticks with bruschetta", "avg_prep_time": 10},
    {"category": "Antipasti", "item_name": "Cozze De La Casa", "price": 17.50, "item_desc": "Mussels in garlic tomato broth", "avg_prep_time": 15},
    
    # Pizza
    {"category": "Pizza", "sub_category": "Handcrafted Pizzas", "item_name": "Di Mare", "price": 19.99, "item_desc": "Crab, shrimp, scallops & fresh tomatoes", "avg_prep_time": 18},
    {"category": "Pizza", "sub_category": "Handcrafted Pizzas", "item_name": "Authentic Italian", "price": 16.49, "item_desc": "Topped with sausage, capicollo & jalapeño", "avg_prep_time": 15},
    {"category": "Pizza", "sub_category": "Handcrafted Pizzas", "item_name": "Chicken Jambalaya", "price": 16.99, "item_desc": "Chicken, Italian sausage, onion, garlic, green & red peppers", "avg_prep_time": 16},
    {"category": "Pizza", "sub_category": "Handcrafted Pizzas", "item_name": "Vegetarian", "price": 16.49, "item_desc": "Zucchini, spinach, onion, olives, tomato, mushrooms & peppers", "avg_prep_time": 15},
    {"category": "Pizza", "sub_category": "Handcrafted Pizzas", "item_name": "Barbecued Chicken", "price": 16.49, "item_desc": "Chicken, BBQ sauce, onions", "avg_prep_time": 15},
    {"category": "Pizza", "sub_category": "Handcrafted Pizzas", "item_name": "South of the Border", "price": 16.49, "item_desc": "Beef, beans, hot peppers, salsa, taco chips & cheddar", "avg_prep_time": 16},
    {"category": "Pizza", "sub_category": "Handcrafted Pizzas", "item_name": "Peppered Chicken", "price": 16.49, "item_desc": "Onion, tomatoes, peppered chicken", "avg_prep_time": 15},
    {"category": "Pizza", "sub_category": "Handcrafted Pizzas", "item_name": "Thai Chicken", "price": 16.49, "item_desc": "With pineapple", "avg_prep_time": 15},
    {"category": "Pizza", "sub_category": "Handcrafted Pizzas", "item_name": "All Meat", "price": 18.99, "item_desc": "Capicollo, pepperoni, sausage, bacon, beef", "avg_prep_time": 17},
    
    # Soups & Salads
    {"category": "Zuppa e Insalate", "sub_category": "Soups", "item_name": "House Minestrone", "price": 8.50, "avg_prep_time": 8},
    {"category": "Zuppa e Insalate", "sub_category": "Soups", "item_name": "Stracciatella", "price": 8.50, "item_desc": "Chicken broth with Parmesan and egg drop", "avg_prep_time": 8},
    {"category": "Zuppa e Insalate", "sub_category": "Soups", "item_name": "Zuppa del Giorno", "price": 9.50, "item_desc": "Soup of the day", "avg_prep_time": 8},
    {"category": "Zuppa e Insalate", "sub_category": "Salads", "item_name": "Caesar Salad (Traditional)", "price": 12.50, "item_desc": "Crisp romaine lettuce tossed with house-made Caesar dressing, topped with croutons and shaved Parmesan", "avg_prep_time": 8},
    {"category": "Zuppa e Insalate", "sub_category": "Salads", "item_name": "Caesar Salad (Starter)", "price": 7.50, "item_desc": "Smaller Caesar salad with croutons and Parmesan", "avg_prep_time": 6},
    {"category": "Zuppa e Insalate", "sub_category": "Salads", "item_name": "Pomodoro - Onion Salad", "price": 14.50, "item_desc": "Tomato, basil, olive oil, balsamic vinegar & onion", "avg_prep_time": 7},
    {"category": "Zuppa e Insalate", "sub_category": "Salads", "item_name": "Mista (House Mixed Salad)", "price": 11.50, "avg_prep_time": 7},
    {"category": "Zuppa e Insalate", "sub_category": "Salads", "item_name": "Spinach Salad", "price": 16.50, "avg_prep_time": 8},
    
    # Amici Favourites
    {"category": "Amici Favourites", "item_name": "Ribs", "price": 29.95, "item_desc": "Smothered in BBQ sauce", "avg_prep_time": 25},
    {"category": "Amici Favourites", "item_name": "Meat Combo Platter", "price": 29.95, "item_desc": "Chicken, ribs & sausage platter", "avg_prep_time": 25},
    
    # Chicken & Seafood Mains
    {"category": "Pollo & Pesce", "item_name": "Pollo Parmigiana", "price": 24.50, "item_desc": "Breaded chicken topped with mozzarella in tangy tomato sauce", "avg_prep_time": 20},
    {"category": "Pollo & Pesce", "item_name": "Pollo Cordon Bleu", "price": 28.95, "item_desc": "Chicken stuffed with ham & Swiss cheese in a herb cream sauce", "avg_prep_time": 22},
    {"category": "Pollo & Pesce", "item_name": "Pollo Griglia", "price": 26.50, "item_desc": "Marinated & grilled chicken breast", "avg_prep_time": 18},
    {"category": "Pollo & Pesce", "item_name": "Pollo Limone", "price": 27.50, "item_desc": "Chicken in a lemon butter sauce", "avg_prep_time": 20},
    {"category": "Pollo & Pesce", "item_name": "Salmon Fillet", "price": 27.50, "item_desc": "Grilled salmon fillet (choice of baked potato, pasta of the day, or rice)", "avg_prep_time": 18},
    {"category": "Pollo & Pesce", "item_name": "Cozze Marinara", "price": 25.50, "item_desc": "Mussels in garlic tomato broth (served with side)", "avg_prep_time": 15},
    {"category": "Pollo & Pesce", "item_name": "Calamari", "price": 25.50, "item_desc": "Fried calamari (served with choice of side)", "avg_prep_time": 12},
    {"category": "Pollo & Pesce", "item_name": "Prawns-Scallops-Crab", "price": 31.50, "item_desc": "Seafood trio in Newberg gratiné béchamel, topped with cheese", "avg_prep_time": 20},
    {"category": "Pollo & Pesce", "item_name": "Seafood Combo", "price": 34.50, "item_desc": "Mussels, calamari & prawns platter", "avg_prep_time": 22},
    {"category": "Pollo & Pesce", "item_name": "Boscaiola", "price": 32.50, "item_desc": "Wild mushroom medley in demi-glace sauce (with chicken)", "avg_prep_time": 20},
    {"category": "Pollo & Pesce", "item_name": "Prawns Provinciale", "price": 35.50, "item_desc": "Prawns in fresh tomato, garlic butter & white wine sauce", "avg_prep_time": 18},
    
    # Pasta (sample - adding key items)
    {"category": "Pasta", "item_name": "Spaghetti & Meat Sauce", "price": 19.95, "avg_prep_time": 15},
    {"category": "Pasta", "item_name": "Tortellini Panna", "price": 22.95, "item_desc": "Veal tortellini in a Parmesan cream sauce", "avg_prep_time": 16},
    {"category": "Pasta", "item_name": "Spaghetti Pomodoro", "price": 18.50, "item_desc": "Spaghetti in a fresh tomato & basil sauce", "avg_prep_time": 14},
    {"category": "Pasta", "item_name": "Penne Quattro Formaggio", "price": 24.50, "item_desc": "Penne with Parmesan, mozzarella, provolone & gorgonzola cheese sauce", "avg_prep_time": 16},
    {"category": "Pasta", "item_name": "Penne Vodka", "price": 22.95, "item_desc": "Penne with spinach, bacon & creamy vodka-tomato sauce", "avg_prep_time": 16},
    {"category": "Pasta", "item_name": "Fettuccine Alfredo", "price": 22.50, "item_desc": "Fettuccine with ham, mushroom & green onions in cream sauce", "avg_prep_time": 15},
    {"category": "Pasta", "item_name": "Fettuccine Primavera Peppercorn", "price": 22.50, "item_desc": "Garden vegetables in a rose cream sauce", "avg_prep_time": 15},
    {"category": "Pasta", "item_name": "Spaghetti Carbonara", "price": 21.95, "item_desc": "Bacon, onion, cracked pepper & egg yolk in a rich cream sauce", "avg_prep_time": 16},
    {"category": "Pasta", "item_name": "Linguine Pescatore", "price": 26.00, "item_desc": "Linguine with prawns, scallops, clams, calamari & mussels (red or white sauce)", "avg_prep_time": 18},
    {"category": "Pasta", "item_name": "Linguine Di Mare", "price": 25.50, "item_desc": "Linguine with shrimp & scallops in a cream sauce", "avg_prep_time": 17},
    {"category": "Pasta", "item_name": "Penne Arrabbiata", "price": 22.25, "item_desc": "Penne in a very spicy jalapeño-tomato sauce", "avg_prep_time": 15},
    {"category": "Pasta", "item_name": "Linguine Amici", "price": 24.95, "item_desc": "Linguine with clams and chicken in a cream sauce", "avg_prep_time": 17},
    {"category": "Pasta", "item_name": "Seafood Stracci", "price": 24.95, "item_desc": "Seafood crêpe melt (assorted seafood in crepe with sauce)", "avg_prep_time": 18},
    {"category": "Pasta", "item_name": "Penne Salsicce", "price": 22.95, "item_desc": "Penne with Italian sausage & onions in spicy tomato sauce", "avg_prep_time": 16},
    {"category": "Pasta", "item_name": "Lasagna with Meat Sauce", "price": 22.50, "avg_prep_time": 20},
    {"category": "Pasta", "item_name": "Penne Amatriciana", "price": 22.95, "item_desc": "Penne with onions, garlic, bacon in tomato sauce", "avg_prep_time": 16},
    {"category": "Pasta", "item_name": "Penne Jambalaya", "price": 24.95, "item_desc": "Penne with sausage, chicken, peppers in spicy tomato sauce", "avg_prep_time": 17},
    {"category": "Pasta", "item_name": "Black Pepper Chicken Fettuccine", "price": 24.50, "item_desc": "Fettuccine with chicken and mixed peppers in a rosé sauce", "avg_prep_time": 17},
    {"category": "Pasta", "item_name": "Chicken Fettuccine Al Panna", "price": 24.95, "item_desc": "Fettuccine with chicken in Parmesan cream sauce", "avg_prep_time": 16},
    {"category": "Pasta", "item_name": "Gnocchi Bolognese", "price": 22.50, "item_desc": "Potato gnocchi with meat sauce", "avg_prep_time": 18},
    {"category": "Pasta", "item_name": "Gnocchi Pomodoro", "price": 21.50, "item_desc": "Potato gnocchi with tomato sauce", "avg_prep_time": 17},
    {"category": "Pasta", "item_name": "Ravioli Basilico", "price": 22.50, "item_desc": "Cheese ravioli in a tomato basil sauce", "avg_prep_time": 16},
    {"category": "Pasta", "item_name": "Smoked Salmon Tortellini", "price": 24.50, "item_desc": "Veal tortellini in a smoked salmon & fresh basil cream sauce", "avg_prep_time": 18},
    {"category": "Pasta", "item_name": "Fettuccine Gigi", "price": 22.95, "item_desc": "Fettuccine with peppers, mushrooms, peas & ham in a spicy rosé sauce", "avg_prep_time": 16},
    {"category": "Pasta", "item_name": "Smoked Salmon Capellini", "price": 24.50, "item_desc": "Angel-hair pasta with smoked salmon, sun-dried tomatoes & white wine sauce", "avg_prep_time": 17},
    {"category": "Pasta", "item_name": "Cannelloni", "price": 22.50, "item_desc": "Pasta tubes stuffed with meat, baked with tomato sauce and béchamel", "avg_prep_time": 20},
    {"category": "Pasta", "item_name": "Manicotti", "price": 23.50, "item_desc": "Crepes stuffed with ricotta & spinach, baked in béchamel sauce", "avg_prep_time": 20},
    {"category": "Pasta", "item_name": "Tortellini Papalina", "price": 23.95, "item_desc": "Veal tortellini with bacon, green onions & mushrooms in a garlic cream sauce", "avg_prep_time": 17},
    {"category": "Pasta", "item_name": "Penne Calabrese", "price": 22.50, "item_desc": "Penne with sun-dried tomatoes, green onions, Italian sausage in a light tomato–white wine sauce", "avg_prep_time": 16},
    {"category": "Pasta", "item_name": "Linguine Vongole", "price": 24.95, "item_desc": "Linguine with clams (choice of white wine or tomato clam sauce)", "avg_prep_time": 17},
    {"category": "Pasta", "item_name": "Ravioli Toscana", "price": 22.50, "item_desc": "Cheese ravioli in a rosé meat sauce", "avg_prep_time": 16},
    
    # Risotto
    {"category": "Risotto", "item_name": "Risotto Funghi", "price": 22.50, "item_desc": "Creamy Italian rice with a wild mushroom medley", "avg_prep_time": 18},
    {"category": "Risotto", "item_name": "Italian Sausage Risotto", "price": 23.50, "item_desc": "Risotto with garlic, onion, tomato and Italian sausage", "avg_prep_time": 19},
    {"category": "Risotto", "item_name": "Risotto Primavera", "price": 25.75, "item_desc": "Risotto with fresh garden vegetable medley", "avg_prep_time": 18},
    {"category": "Risotto", "item_name": "Risotto Pescatore", "price": 25.95, "item_desc": "Risotto with prawns, scallops, clams, calamari & mussels", "avg_prep_time": 20},
    
    # Steaks
    {"category": "Alberta Beef", "sub_category": "Steaks", "item_name": "New York Steak (8 oz)", "price": 36.50, "avg_prep_time": 20},
    {"category": "Alberta Beef", "sub_category": "Steaks", "item_name": "New York Peppercorn (8 oz)", "price": 38.95, "avg_prep_time": 22},
    
    # Sandwiches
    {"category": "Sandwiches", "item_name": "NY Steak Sandwich (6 oz)", "price": 27.50, "item_desc": "Open-faced steak sandwich with garlic toast", "avg_prep_time": 15},
    {"category": "Sandwiches", "item_name": "Grilled Chicken Sandwich", "price": 20.95, "avg_prep_time": 12},
    {"category": "Sandwiches", "item_name": "Italian Club", "price": 19.95, "avg_prep_time": 10},
    {"category": "Sandwiches", "item_name": "Meatball Sub", "price": 19.95, "item_desc": "Baked with mozzarella cheese", "avg_prep_time": 12},
    {"category": "Sandwiches", "item_name": "Hamburger (8 oz) with Cheese", "price": 19.95, "avg_prep_time": 12},
    {"category": "Sandwiches", "item_name": "Grilled Salmon Sandwich", "price": 21.50, "avg_prep_time": 14},
    {"category": "Sandwiches", "item_name": "Italian Sausage Sandwich", "price": 19.95, "item_desc": "Italian sausage with mozzarella, onion & tomato on a bun", "avg_prep_time": 12},
    
    # Veal Entrées
    {"category": "Veal Entrées", "item_name": "Piccata", "price": 27.50, "item_desc": "Veal scaloppini in lemon sauce", "avg_prep_time": 18},
    {"category": "Veal Entrées", "item_name": "Involtini", "price": 31.50, "item_desc": "Veal rolls stuffed with shrimp & herbs in a white wine cream sauce", "avg_prep_time": 22},
    {"category": "Veal Entrées", "item_name": "Bolognese (Veal)", "price": 29.95, "item_desc": "Breaded veal topped with ham & mozzarella, finished in tomato sauce", "avg_prep_time": 20},
    {"category": "Veal Entrées", "item_name": "Parmigiana (Veal)", "price": 24.95, "item_desc": "Breaded veal topped with mozzarella in tangy tomato sauce", "avg_prep_time": 18},
    {"category": "Veal Entrées", "item_name": "Scalloppini Montenara", "price": 29.50, "item_desc": "Veal in a creamy wild mushroom brandy sauce", "avg_prep_time": 20},
    {"category": "Veal Entrées", "item_name": "Veal Cordon Bleu", "price": 29.95, "item_desc": "Veal stuffed with ham & Swiss cheese in herb sauce", "avg_prep_time": 22},
    {"category": "Veal Entrées", "item_name": "Veal Gorgonzola", "price": 29.95, "item_desc": "Veal medallions in a gorgonzola cream sauce", "avg_prep_time": 20},
    {"category": "Veal Entrées", "item_name": "Grilled Veal Sandwich", "price": 25.50, "item_desc": "Grilled veal on focaccia with lettuce, tomato & aioli", "avg_prep_time": 15},
    {"category": "Veal Entrées", "item_name": "Marsala", "price": 27.50, "item_desc": "Veal scaloppini in marsala wine sauce", "avg_prep_time": 18},
    
    # Sides & Add-Ons
    {"category": "Sides & Add-Ons", "item_name": "Baked Potato", "price": 6.50, "avg_prep_time": 15},
    {"category": "Sides & Add-Ons", "item_name": "Fries", "price": 7.50, "avg_prep_time": 8},
    {"category": "Sides & Add-Ons", "item_name": "Vegetables", "price": 7.50, "avg_prep_time": 10},
    {"category": "Sides & Add-Ons", "item_name": "Olive Oil & Balsamic Vinegar", "price": 2.25, "avg_prep_time": 2},
    {"category": "Sides & Add-Ons", "item_name": "Dressings", "price": 1.25, "item_desc": "Choice of Italian, Ranch, Blue Cheese, etc.", "avg_prep_time": 1},
    {"category": "Sides & Add-Ons", "item_name": "Sour Cream", "price": 1.25, "avg_prep_time": 1},
    {"category": "Sides & Add-Ons", "item_name": "Salsa", "price": 1.25, "avg_prep_time": 1},
    {"category": "Sides & Add-Ons", "item_name": "Prawns (3 pcs)", "price": 5.95, "avg_prep_time": 8},
    {"category": "Sides & Add-Ons", "item_name": "Sausage", "price": 5.95, "avg_prep_time": 8},
    {"category": "Sides & Add-Ons", "item_name": "Meatballs", "price": 7.50, "avg_prep_time": 10},
    {"category": "Sides & Add-Ons", "item_name": "Extra Sauce", "price": 5.95, "avg_prep_time": 2},
    {"category": "Sides & Add-Ons", "item_name": "Mushrooms", "price": 5.95, "avg_prep_time": 8},
    {"category": "Sides & Add-Ons", "item_name": "Chicken", "price": 7.50, "avg_prep_time": 12},
    {"category": "Sides & Add-Ons", "item_name": "Gravy", "price": 4.50, "avg_prep_time": 2},
    
    # Build Your Own Pizza
    {"category": "Build Your Own Pizza", "item_name": "Build Your Own Pizza (8\")", "price": 14.50, "avg_prep_time": 15},
    {"category": "Build Your Own Pizza", "item_name": "Build Your Own Pizza (10\")", "price": 18.25, "avg_prep_time": 16},
    {"category": "Build Your Own Pizza", "item_name": "Build Your Own Pizza (12\")", "price": 23.50, "avg_prep_time": 18},
    {"category": "Build Your Own Pizza", "item_name": "Panzerotti (Pizza Pocket)", "price": 16.50, "avg_prep_time": 14},
]

# Restaurant 2: Biryani Lounge Restaurant and Bar
biryani_menu = [
    # Appetizers & Street Food
    {"category": "Appetizers & Street Food", "item_name": "Chilli Prawns", "price": 19.00, "avg_prep_time": 15},
    {"category": "Appetizers & Street Food", "item_name": "Fish Pakoras", "price": 15.00, "avg_prep_time": 12},
    {"category": "Appetizers & Street Food", "item_name": "Honey Garlic Chicken", "price": 17.00, "avg_prep_time": 14},
    {"category": "Appetizers & Street Food", "item_name": "Paneer Tikka", "price": 18.00, "avg_prep_time": 12},
    {"category": "Appetizers & Street Food", "item_name": "Pav Bhaji", "price": 17.00, "avg_prep_time": 10},
    {"category": "Appetizers & Street Food", "item_name": "Samosa Chaat", "price": 15.00, "avg_prep_time": 8},
    {"category": "Appetizers & Street Food", "item_name": "Samosas (2 pcs)", "price": 9.00, "avg_prep_time": 6},
    {"category": "Appetizers & Street Food", "item_name": "Sev Puri", "price": 13.00, "avg_prep_time": 7},
    {"category": "Appetizers & Street Food", "item_name": "Spring Rolls (8 pcs)", "price": 15.00, "avg_prep_time": 10},
    {"category": "Appetizers & Street Food", "item_name": "Street Style Chicken Tikka", "price": 19.00, "avg_prep_time": 14},
    {"category": "Appetizers & Street Food", "item_name": "Sweet Chilli Cauliflower", "price": 15.00, "avg_prep_time": 10},
    {"category": "Appetizers & Street Food", "item_name": "Tandoori Chicken", "price": 20.00, "avg_prep_time": 18},
    {"category": "Appetizers & Street Food", "item_name": "Tandoori Soya Chaap", "price": 17.00, "avg_prep_time": 12},
    {"category": "Appetizers & Street Food", "item_name": "Vada Pav", "price": 14.00, "avg_prep_time": 8},
    {"category": "Appetizers & Street Food", "item_name": "Veggie Pakoras", "price": 11.00, "avg_prep_time": 10},
    {"category": "Appetizers & Street Food", "item_name": "Amritsari Kulcha and Chana", "price": 18.00, "avg_prep_time": 12},
    {"category": "Appetizers & Street Food", "item_name": "Dahi Sev Puri", "price": 13.00, "avg_prep_time": 7},
    {"category": "Appetizers & Street Food", "item_name": "Kasundi Fish Tikka", "price": 22.00, "avg_prep_time": 15},
    
    # Traditional Curries & Mains
    {"category": "Classics", "item_name": "Aloo Gobhi", "price": 18.00, "avg_prep_time": 15},
    {"category": "Classics", "item_name": "Butter Chicken", "price": 18.00, "avg_prep_time": 18},
    {"category": "Classics", "item_name": "Chana Masala", "price": 17.00, "avg_prep_time": 14},
    {"category": "Classics", "item_name": "Chicken Korma", "price": 17.95, "avg_prep_time": 18},
    {"category": "Classics", "item_name": "Chicken Tikka Masala", "price": 19.00, "avg_prep_time": 18},
    {"category": "Classics", "item_name": "Chicken Vindaloo", "price": 18.00, "avg_prep_time": 16},
    {"category": "Classics", "item_name": "Classic Chicken Curry", "price": 18.00, "avg_prep_time": 17},
    {"category": "Classics", "item_name": "Classic Goat Curry", "price": 20.00, "avg_prep_time": 20},
    {"category": "Classics", "item_name": "Classic Lamb Curry", "price": 21.00, "avg_prep_time": 20},
    {"category": "Classics", "item_name": "Daal Makhani", "price": 17.00, "avg_prep_time": 15},
    {"category": "Classics", "item_name": "Lamb Korma", "price": 17.95, "avg_prep_time": 18},
    {"category": "Classics", "item_name": "Lamb Rogan Josh", "price": 21.00, "avg_prep_time": 20},
    {"category": "Classics", "item_name": "Lamb Vindaloo", "price": 20.00, "avg_prep_time": 18},
    {"category": "Classics", "item_name": "Malai Kofta", "price": 18.00, "avg_prep_time": 16},
    {"category": "Classics", "item_name": "Paneer Tikka Masala", "price": 18.00, "avg_prep_time": 16},
    {"category": "Classics", "item_name": "Malabar Fish Curry", "price": 21.00, "avg_prep_time": 17},
    {"category": "Classics", "item_name": "Malabar Prawn Curry", "price": 21.00, "avg_prep_time": 17},
    {"category": "Classics", "item_name": "Malai Palak Paneer", "price": 18.00, "avg_prep_time": 15},
    {"category": "Classics", "item_name": "Saagwala Chicken", "price": 18.00, "avg_prep_time": 17},
    {"category": "Classics", "item_name": "Saagwala Goat", "price": 20.00, "avg_prep_time": 19},
    {"category": "Classics", "item_name": "Saagwala Lamb", "price": 21.00, "avg_prep_time": 19},
    
    # House Specialties
    {"category": "Biryani Special", "item_name": "Baingan Bharta", "price": 17.00, "avg_prep_time": 15},
    {"category": "Biryani Special", "item_name": "Coconut Chicken Curry", "price": 19.00, "avg_prep_time": 18},
    {"category": "Biryani Special", "item_name": "Coconut Prawn Curry", "price": 22.00, "avg_prep_time": 17},
    {"category": "Biryani Special", "item_name": "Chicken Kolahpuri", "price": 19.00, "avg_prep_time": 18},
    {"category": "Biryani Special", "item_name": "Coconut Lamb Curry", "price": 20.00, "avg_prep_time": 19},
    {"category": "Biryani Special", "item_name": "Goat Bhuna", "price": 21.00, "avg_prep_time": 20},
    {"category": "Biryani Special", "item_name": "Imli Wali Daal", "price": 18.00, "avg_prep_time": 15},
    {"category": "Biryani Special", "item_name": "Kadhai Soya", "price": 18.00, "avg_prep_time": 14},
    {"category": "Biryani Special", "item_name": "Kashmiri Goat Korma", "price": 21.00, "avg_prep_time": 20},
    {"category": "Biryani Special", "item_name": "Keema Kofta", "price": 21.00, "avg_prep_time": 18},
    {"category": "Biryani Special", "item_name": "Paneer Angara", "price": 19.00, "avg_prep_time": 16},
    {"category": "Biryani Special", "item_name": "Vegetable Kolahpuri", "price": 18.00, "avg_prep_time": 16},
    
    # Rice & Biryanis
    {"category": "Rice & Biryanis", "item_name": "Boneless Chicken Biryani", "price": 20.00, "avg_prep_time": 25},
    {"category": "Rice & Biryanis", "item_name": "Goat Biryani", "price": 21.00, "avg_prep_time": 25},
    {"category": "Rice & Biryanis", "item_name": "Jeera Basmati Rice", "price": 7.00, "avg_prep_time": 12},
    {"category": "Rice & Biryanis", "item_name": "Lamb Biryani", "price": 23.00, "avg_prep_time": 25},
    {"category": "Rice & Biryanis", "item_name": "Prawn Biryani", "price": 23.00, "avg_prep_time": 25},
    {"category": "Rice & Biryanis", "item_name": "Tandoori Chicken Biryani", "price": 23.00, "avg_prep_time": 25},
    {"category": "Rice & Biryanis", "item_name": "Vegetable Biryani", "price": 19.00, "avg_prep_time": 22},
    {"category": "Rice & Biryanis", "item_name": "Egg Biryani", "price": 19.00, "avg_prep_time": 20},
    {"category": "Rice & Biryanis", "item_name": "Navratan Pulao", "price": 16.00, "avg_prep_time": 18},
    
    # Breads
    {"category": "Breads", "item_name": "Bhatura", "price": 5.50, "avg_prep_time": 8},
    {"category": "Breads", "item_name": "Garlic Naan", "price": 6.50, "avg_prep_time": 6},
    {"category": "Breads", "item_name": "Kulcha", "price": 7.00, "avg_prep_time": 7},
    {"category": "Breads", "item_name": "Plain Naan", "price": 5.50, "avg_prep_time": 5},
    {"category": "Breads", "item_name": "Butter Naan", "price": 6.50, "avg_prep_time": 6},
    {"category": "Breads", "item_name": "Potato Parantha", "price": 7.00, "avg_prep_time": 8},
    {"category": "Breads", "item_name": "Cauliflower Parantha", "price": 7.00, "avg_prep_time": 8},
    {"category": "Breads", "item_name": "Green Chilli Parantha", "price": 7.00, "avg_prep_time": 8},
    {"category": "Breads", "item_name": "Onion Parantha", "price": 7.00, "avg_prep_time": 8},
    {"category": "Breads", "item_name": "Paneer Parantha", "price": 7.00, "avg_prep_time": 8},
    {"category": "Breads", "item_name": "Puri", "price": 5.50, "avg_prep_time": 6},
    {"category": "Breads", "item_name": "Tandoori Roti", "price": 5.00, "avg_prep_time": 5},
    {"category": "Breads", "item_name": "Tava Roti", "price": 5.00, "avg_prep_time": 5},
    
    # Sides
    {"category": "Sides", "item_name": "Cucumber Raita", "price": 7.00, "avg_prep_time": 3},
    {"category": "Sides", "item_name": "Indian Salad", "price": 7.00, "avg_prep_time": 5},
    {"category": "Sides", "item_name": "Mango Chutney", "price": 7.00, "avg_prep_time": 2},
    {"category": "Sides", "item_name": "Mint Chutney", "price": 7.00, "avg_prep_time": 2},
    {"category": "Sides", "item_name": "Mixed Pickles", "price": 7.00, "avg_prep_time": 2},
    {"category": "Sides", "item_name": "Papadum (2 pcs)", "price": 5.50, "avg_prep_time": 4},
    {"category": "Sides", "item_name": "Tamarind Chutney", "price": 7.00, "avg_prep_time": 2},
    
    # Dessert
    {"category": "Dessert", "item_name": "Gajar Ka Halwa", "price": 10.00, "avg_prep_time": 5},
    {"category": "Dessert", "item_name": "Gulab Jamun with Rabdi", "price": 10.00, "avg_prep_time": 5},
    {"category": "Dessert", "item_name": "Rasmalai", "price": 9.00, "avg_prep_time": 5},
    {"category": "Dessert", "item_name": "Anjeer Ki Kheer", "price": 10.00, "avg_prep_time": 5},
    
    # Non-Alcoholic Beverages
    {"category": "Non-Alcoholic Beverages", "item_name": "Pop Cans", "price": 3.50, "item_desc": "Assorted soft drinks", "avg_prep_time": 1},
    {"category": "Non-Alcoholic Beverages", "item_name": "Heineken Zero", "price": 8.00, "item_desc": "Non-alcoholic beer", "avg_prep_time": 1},
    
    # Specialty Beverages
    {"category": "Non-Alcoholic Drinks", "item_name": "Mango Lassi", "price": 8.00, "avg_prep_time": 3},
    {"category": "Non-Alcoholic Drinks", "item_name": "Beeryani's Lime Mojito", "price": 8.00, "avg_prep_time": 4},
    {"category": "Non-Alcoholic Drinks", "item_name": "Beeryani's Mango Mojito", "price": 8.00, "avg_prep_time": 4},
    {"category": "Non-Alcoholic Drinks", "item_name": "Jeera Lassi", "price": 7.00, "item_desc": "Cumin-spiced yogurt drink", "avg_prep_time": 3},
    {"category": "Non-Alcoholic Drinks", "item_name": "Lychee Mule", "price": 8.00, "avg_prep_time": 4},
    {"category": "Non-Alcoholic Drinks", "item_name": "Masala Lemonade", "price": 7.50, "item_desc": "Spiced lemonade", "avg_prep_time": 3},
    {"category": "Non-Alcoholic Drinks", "item_name": "Moonshine", "price": 8.00, "item_desc": "Non-alcoholic cocktail", "avg_prep_time": 4},
]

# Restaurant 3: Coco Rico Cafe
coco_rico_menu = [
    # Brunch Menu
    {"category": "Brunch", "item_name": "Spinach Tomato Benedict", "price": 16.00, "avg_prep_time": 15},
    {"category": "Brunch", "item_name": "Ham & Cheese Omelette", "price": 16.50, "avg_prep_time": 12},
    {"category": "Brunch", "item_name": "Smoked Salmon Panini", "price": 20.50, "avg_prep_time": 10},
    {"category": "Brunch", "item_name": "Grilled Ham & Cheese Sandwich", "price": 20.00, "avg_prep_time": 10},
    {"category": "Brunch", "item_name": "Canadian Benedict", "price": 17.50, "avg_prep_time": 15},
    {"category": "Brunch", "item_name": "Garden Fresh Omelette", "price": 16.00, "avg_prep_time": 12},
    {"category": "Brunch", "item_name": "Belgian Waffles", "price": 17.50, "avg_prep_time": 12},
    {"category": "Brunch", "item_name": "Smoked Salmon Omelette", "price": 20.00, "avg_prep_time": 12},
    {"category": "Brunch", "item_name": "Robson St. Breakfast Special", "price": 15.00, "avg_prep_time": 10},
    {"category": "Brunch", "item_name": "BELT Sandwich (Bacon, Egg, Lettuce, Tomato)", "price": 19.50, "avg_prep_time": 10},
    {"category": "Brunch", "item_name": "Bacon & Cheese Omelette", "price": 17.75, "avg_prep_time": 12},
    {"category": "Brunch", "item_name": "Smoked Salmon Benedict", "price": 20.00, "avg_prep_time": 15},
    {"category": "Brunch", "item_name": "Cinnamon French Toast", "price": 17.50, "avg_prep_time": 12},
    {"category": "Brunch", "item_name": "Brunch Burger", "price": 22.00, "avg_prep_time": 15},
    {"category": "Brunch", "item_name": "Coco Rico Benedict", "price": 18.75, "avg_prep_time": 15},
    {"category": "Brunch", "item_name": "Buttermilk Pancakes", "price": 17.00, "avg_prep_time": 12},
    
    # Dinner Menu - Tapas & Appetizers
    {"category": "Tapas & Appetizers", "item_name": "Fish & Chips", "price": 20.00, "avg_prep_time": 15},
    {"category": "Tapas & Appetizers", "item_name": "Spicy Meatballs", "price": 17.50, "avg_prep_time": 12},
    {"category": "Tapas & Appetizers", "item_name": "Side of Fries", "price": 7.00, "avg_prep_time": 8},
    {"category": "Tapas & Appetizers", "item_name": "Chicken Strips with Fries", "price": 18.50, "avg_prep_time": 12},
    {"category": "Tapas & Appetizers", "item_name": "Poutine", "price": 13.50, "avg_prep_time": 10},
    {"category": "Tapas & Appetizers", "item_name": "Chilli Chicken", "price": 17.00, "avg_prep_time": 12},
    {"category": "Tapas & Appetizers", "item_name": "Chicken Wings", "price": 15.50, "avg_prep_time": 15},
    {"category": "Tapas & Appetizers", "item_name": "Crispy Yam Fries", "price": 13.00, "avg_prep_time": 10},
    {"category": "Tapas & Appetizers", "item_name": "Three Cheese Nachos", "price": 18.50, "avg_prep_time": 10},
    {"category": "Tapas & Appetizers", "item_name": "Cauliflower Bites", "price": 15.50, "avg_prep_time": 10},
    {"category": "Tapas & Appetizers", "item_name": "Fish Tacos", "price": 19.50, "avg_prep_time": 12},
    {"category": "Tapas & Appetizers", "item_name": "Sliders", "price": 20.50, "avg_prep_time": 12},
    {"category": "Tapas & Appetizers", "item_name": "Calamari", "price": 21.50, "avg_prep_time": 12},
    {"category": "Tapas & Appetizers", "item_name": "Chicken Tikka Skewer", "price": 21.00, "avg_prep_time": 15},
    {"category": "Tapas & Appetizers", "item_name": "Baked Garlic and Cheese Prawns", "price": 19.50, "avg_prep_time": 15},
    {"category": "Tapas & Appetizers", "item_name": "Hummus", "price": 11.00, "avg_prep_time": 5},
    {"category": "Tapas & Appetizers", "item_name": "Drunken Mussels and Chorizo", "price": 19.50, "avg_prep_time": 15},
    
    # Salads & Soup
    {"category": "Salads & Soup", "item_name": "Citrus Caesar Salad", "price": 12.00, "avg_prep_time": 8},
    {"category": "Salads & Soup", "item_name": "Maple Salmon Salad", "price": 23.00, "avg_prep_time": 15},
    {"category": "Salads & Soup", "item_name": "Quinoa and Spinach Salad", "price": 18.00, "avg_prep_time": 10},
    {"category": "Salads & Soup", "item_name": "Soup of the Day", "price": 8.00, "avg_prep_time": 8},
    
    # Rice Bowls
    {"category": "Rice Bowls", "item_name": "Beef Stroganoff Rice Bowl", "price": 25.75, "avg_prep_time": 18},
    {"category": "Rice Bowls", "item_name": "Butter Chicken Curry Rice Bowl", "price": 17.00, "avg_prep_time": 15},
    {"category": "Rice Bowls", "item_name": "Madras Chicken Curry Rice Bowl", "price": 25.50, "avg_prep_time": 18},
    {"category": "Rice Bowls", "item_name": "Chicken Teriyaki Rice Bowl", "price": 17.00, "avg_prep_time": 15},
    
    # Pastas & Pizzas
    {"category": "Pastas & Pizzas", "item_name": "Garden Fresh Vegetable Pasta", "price": 18.50, "avg_prep_time": 15},
    {"category": "Pastas & Pizzas", "item_name": "Creamy Pesto Chicken Penne", "price": 20.50, "avg_prep_time": 16},
    {"category": "Pastas & Pizzas", "item_name": "Spicy Prawns Spaghettini", "price": 22.00, "avg_prep_time": 16},
    {"category": "Pastas & Pizzas", "item_name": "Spaghetti Carbonara", "price": 20.50, "avg_prep_time": 16},
    {"category": "Pastas & Pizzas", "item_name": "Chicken and Chorizo Penne", "price": 22.00, "avg_prep_time": 17},
    {"category": "Pastas & Pizzas", "item_name": "Spinach & Feta Pizza", "price": 19.00, "avg_prep_time": 15},
    {"category": "Pastas & Pizzas", "item_name": "BBQ Pulled Pork Pizza", "price": 20.25, "avg_prep_time": 16},
    {"category": "Pastas & Pizzas", "item_name": "Hawaiian Pizza", "price": 19.75, "avg_prep_time": 15},
    {"category": "Pastas & Pizzas", "item_name": "Coco Pizza (house special pizza)", "price": 21.00, "avg_prep_time": 16},
    
    # Sandwiches & Burgers
    {"category": "Sandwiches & Burgers", "item_name": "Avocado & Brie Club Sandwich", "price": 20.00, "avg_prep_time": 10},
    {"category": "Sandwiches & Burgers", "item_name": "Pulled Pork Panini", "price": 19.50, "avg_prep_time": 10},
    {"category": "Sandwiches & Burgers", "item_name": "Roasted Beef Dip", "price": 19.50, "avg_prep_time": 12},
    {"category": "Sandwiches & Burgers", "item_name": "Classic Beef Burger", "price": 20.50, "avg_prep_time": 12},
    {"category": "Sandwiches & Burgers", "item_name": "Avocado Chicken Burger", "price": 20.50, "avg_prep_time": 12},
    {"category": "Sandwiches & Burgers", "item_name": "Beyond Meat Burger", "price": 20.00, "avg_prep_time": 12},
    {"category": "Sandwiches & Burgers", "item_name": "Swiss Mushroom Melt Burger", "price": 20.25, "avg_prep_time": 12},
    {"category": "Sandwiches & Burgers", "item_name": "Chicken Burger", "price": 19.50, "avg_prep_time": 12},
    
    # Desserts
    {"category": "Desserts", "item_name": "Brownie with Ice Cream", "price": 10.00, "avg_prep_time": 5},
    
    # Breakfast Specials (Weekday Mornings)
    {"category": "Breakfast Specials", "item_name": "Canadian Benedict (Weekday Special)", "price": 13.25, "avg_prep_time": 15},
    {"category": "Breakfast Specials", "item_name": "Robson Street Breakfast Special (Weekday Special)", "price": 10.75, "avg_prep_time": 10},
    {"category": "Breakfast Specials", "item_name": "Canadian Ham & Cheese Omelette (Weekday Special)", "price": 13.75, "avg_prep_time": 12},
    
    # Non-Alcoholic Beverages
    {"category": "Non-Alcoholic Beverages", "item_name": "Apple Juice", "price": 4.50, "avg_prep_time": 1},
    {"category": "Non-Alcoholic Beverages", "item_name": "Orange Juice", "price": 4.50, "avg_prep_time": 1},
    {"category": "Non-Alcoholic Beverages", "item_name": "Ginger Ale", "price": 4.00, "avg_prep_time": 1},
    {"category": "Non-Alcoholic Beverages", "item_name": "Coca-Cola", "price": 4.00, "avg_prep_time": 1},
    {"category": "Non-Alcoholic Beverages", "item_name": "Diet Coke", "price": 4.00, "avg_prep_time": 1},
    {"category": "Non-Alcoholic Beverages", "item_name": "Sprite", "price": 4.00, "avg_prep_time": 1},
    {"category": "Non-Alcoholic Beverages", "item_name": "Crush (Orange Soda)", "price": 4.00, "avg_prep_time": 1},
    {"category": "Non-Alcoholic Beverages", "item_name": "Perrier (Sparkling Water)", "price": 4.75, "avg_prep_time": 1},
    {"category": "Non-Alcoholic Beverages", "item_name": "Dasani Bottled Water", "price": 4.00, "avg_prep_time": 1},
    {"category": "Non-Alcoholic Beverages", "item_name": "Iced Tea", "price": 5.00, "avg_prep_time": 2},
    {"category": "Non-Alcoholic Beverages", "item_name": "Lemonade", "price": 5.00, "avg_prep_time": 2},
    {"category": "Non-Alcoholic Beverages", "item_name": "Red Bull", "price": 5.25, "avg_prep_time": 1},
    {"category": "Non-Alcoholic Beverages", "item_name": "Tea", "price": 3.50, "avg_prep_time": 3},
    {"category": "Non-Alcoholic Beverages", "item_name": "Regular Coffee", "price": 3.50, "avg_prep_time": 3},
    {"category": "Non-Alcoholic Beverages", "item_name": "Americano", "price": 5.00, "avg_prep_time": 3},
    {"category": "Non-Alcoholic Beverages", "item_name": "Latte", "price": 5.50, "avg_prep_time": 4},
    {"category": "Non-Alcoholic Beverages", "item_name": "Mocha", "price": 5.00, "avg_prep_time": 4},
    {"category": "Non-Alcoholic Beverages", "item_name": "Cappuccino", "price": 5.25, "avg_prep_time": 4},
    {"category": "Non-Alcoholic Beverages", "item_name": "Espresso", "price": 5.00, "avg_prep_time": 2},
    {"category": "Non-Alcoholic Beverages", "item_name": "Hot Chocolate", "price": 5.25, "avg_prep_time": 3},
    
    # Alcoholic Beverages
    {"category": "Alcoholic Beverages", "item_name": "Mimosa", "price": 10.00, "avg_prep_time": 3},
    {"category": "Alcoholic Beverages", "item_name": "Caesar (classic Canadian cocktail)", "price": 13.00, "avg_prep_time": 4},
    {"category": "Alcoholic Beverages", "item_name": "Bloody Mary", "price": 13.00, "avg_prep_time": 4},
]

# Restaurant 4: House of Dosas
house_of_dosas_menu = [
    # Appetizers - Starters
    {"category": "Appetizers", "sub_category": "Starters", "item_name": "Cauliflower Fry", "price": 14.00, "item_desc": "Golden-fried cauliflower florets with a crispy crunch and a hint of spice", "avg_prep_time": 12},
    {"category": "Appetizers", "sub_category": "Starters", "item_name": "Paneer 65", "price": 15.00, "item_desc": "A vibrant blend of spices coating tender bites of paneer", "avg_prep_time": 12},
    {"category": "Appetizers", "sub_category": "Starters", "item_name": "Chicken 65", "price": 12.00, "item_desc": "A vibrant blend of spices coating tender bites of chicken", "avg_prep_time": 12},
    {"category": "Appetizers", "sub_category": "Starters", "item_name": "Prawn 65", "price": 16.00, "item_desc": "A vibrant blend of spices coating tender bites of prawn", "avg_prep_time": 12},
    {"category": "Appetizers", "sub_category": "Starters", "item_name": "Vegetable Pakora", "price": 11.00, "item_desc": "Crispy golden fritters with a hint of spice", "avg_prep_time": 10},
    {"category": "Appetizers", "sub_category": "Starters", "item_name": "Fish Pakora", "price": 15.00, "item_desc": "Crispy golden fritters with a hint of spice", "avg_prep_time": 12},
    {"category": "Appetizers", "sub_category": "Starters", "item_name": "Chicken Tikka", "price": 20.00, "item_desc": "Tender marinated chicken grilled with aromatic spices, served sizzling", "avg_prep_time": 18},
    {"category": "Appetizers", "sub_category": "Starters", "item_name": "Spicy Butter Prawns", "price": 17.00, "item_desc": "Juicy prawns sautéed in a spiced butter sauce", "avg_prep_time": 12},
    {"category": "Appetizers", "sub_category": "Starters", "item_name": "HOD Spicy Chicken", "price": 14.00, "item_desc": "Succulent chicken tossed in a bold, peppery spice mix", "avg_prep_time": 12},
    {"category": "Appetizers", "sub_category": "Starters", "item_name": "Mutton Varuval", "price": 17.00, "item_desc": "Hearty spiced mutton stir-fry with aromatic deep spices", "avg_prep_time": 18},
    {"category": "Appetizers", "sub_category": "Starters", "item_name": "Pepper Beef", "price": 17.00, "item_desc": "Tender beef infused with fiery peppercorn seasoning", "avg_prep_time": 15},
    {"category": "Appetizers", "sub_category": "Starters", "item_name": "Kingfish Tava Fry", "price": 18.00, "item_desc": "Slice of king mackerel marinated in a zesty blend of South Indian herbs and spices, pan-fried", "avg_prep_time": 15},
    
    # Appetizers - Indo-Chinese
    {"category": "Appetizers", "sub_category": "Indo-Chinese", "item_name": "Chilli Paneer", "price": 16.00, "item_desc": "Indo-Chinese style stir-fry with bell peppers, onions and chilies in a savory soy-chilli sauce", "avg_prep_time": 12},
    {"category": "Appetizers", "sub_category": "Indo-Chinese", "item_name": "Chilli Cauliflower", "price": 14.00, "item_desc": "Indo-Chinese style stir-fry with bell peppers, onions and chilies in a savory soy-chilli sauce", "avg_prep_time": 12},
    {"category": "Appetizers", "sub_category": "Indo-Chinese", "item_name": "Chilli Chicken", "price": 14.00, "item_desc": "Indo-Chinese style stir-fry with bell peppers, onions and chilies in a savory soy-chilli sauce", "avg_prep_time": 12},
    {"category": "Appetizers", "sub_category": "Indo-Chinese", "item_name": "Chilli Fish", "price": 15.00, "item_desc": "Indo-Chinese style stir-fry with bell peppers, onions and chilies in a savory soy-chilli sauce", "avg_prep_time": 12},
    {"category": "Appetizers", "sub_category": "Indo-Chinese", "item_name": "Chilli Shrimp", "price": 17.00, "item_desc": "Indo-Chinese style stir-fry with bell peppers, onions and chilies in a savory soy-chilli sauce", "avg_prep_time": 12},
    {"category": "Appetizers", "sub_category": "Indo-Chinese", "item_name": "Vegetable Noodles", "price": 15.00, "item_desc": "Wok-tossed noodles with vegetables. Choice of Hakka or Szechuan style", "avg_prep_time": 12},
    {"category": "Appetizers", "sub_category": "Indo-Chinese", "item_name": "Egg Noodles", "price": 15.00, "item_desc": "Wok-tossed noodles with egg. Choice of Hakka or Szechuan style", "avg_prep_time": 12},
    {"category": "Appetizers", "sub_category": "Indo-Chinese", "item_name": "Chicken Noodles", "price": 16.00, "item_desc": "Wok-tossed noodles with chicken. Choice of Hakka or Szechuan style", "avg_prep_time": 12},
    {"category": "Appetizers", "sub_category": "Indo-Chinese", "item_name": "Shrimp Noodles", "price": 18.00, "item_desc": "Wok-tossed noodles with shrimp. Choice of Hakka or Szechuan style", "avg_prep_time": 12},
    {"category": "Appetizers", "sub_category": "Indo-Chinese", "item_name": "Vegetable Fried Rice", "price": 15.00, "item_desc": "Fried rice with vegetables, seasoned with soy and spices. Choice of Hakka or Szechuan style", "avg_prep_time": 12},
    {"category": "Appetizers", "sub_category": "Indo-Chinese", "item_name": "Egg Fried Rice", "price": 15.00, "item_desc": "Fried rice with egg, seasoned with soy and spices. Choice of Hakka or Szechuan style", "avg_prep_time": 12},
    {"category": "Appetizers", "sub_category": "Indo-Chinese", "item_name": "Chicken Fried Rice", "price": 16.00, "item_desc": "Fried rice with chicken, seasoned with soy and spices. Choice of Hakka or Szechuan style", "avg_prep_time": 12},
    {"category": "Appetizers", "sub_category": "Indo-Chinese", "item_name": "Shrimp Fried Rice", "price": 18.00, "item_desc": "Fried rice with shrimp, seasoned with soy and spices. Choice of Hakka or Szechuan style", "avg_prep_time": 12},
    
    # Appetizers - Soups
    {"category": "Appetizers", "sub_category": "Soups", "item_name": "Rasam", "price": 5.00, "item_desc": "A tangy South Indian tomato-tamarind broth with warming spices", "avg_prep_time": 8},
    
    # Dosa - Plain Varieties
    {"category": "Dosa", "item_name": "Plain Dosa", "price": 10.00, "item_desc": "Crispy crêpe made from fermented rice & lentil batter, served with coconut chutney, tomato chutney, and sambar", "avg_prep_time": 10},
    {"category": "Dosa", "item_name": "Onion Dosa", "price": 12.00, "item_desc": "Dosa spread with onion", "avg_prep_time": 11},
    {"category": "Dosa", "item_name": "Mysore Dosa", "price": 12.00, "item_desc": "Dosa spread with spicy Mysore chutney", "avg_prep_time": 11},
    {"category": "Dosa", "item_name": "Podi Dosa", "price": 14.00, "item_desc": "Dosa spread with podi powder", "avg_prep_time": 11},
    {"category": "Dosa", "item_name": "Ghee Roast Dosa", "price": 14.00, "item_desc": "Dosa brushed with ghee", "avg_prep_time": 11},
    
    # Dosa - Masala Varieties
    {"category": "Dosa", "item_name": "Masala Dosa", "price": 12.00, "item_desc": "Classic crispy dosa filled with spiced potato masala", "avg_prep_time": 12},
    {"category": "Dosa", "item_name": "Onion Masala Dosa", "price": 13.00, "item_desc": "Dosa filled with spiced potato masala and onions", "avg_prep_time": 12},
    {"category": "Dosa", "item_name": "Podi Masala Dosa", "price": 13.00, "item_desc": "Dosa filled with spiced potato masala and podi spice", "avg_prep_time": 12},
    {"category": "Dosa", "item_name": "Ghee Roast Masala Dosa", "price": 16.00, "item_desc": "Dosa filled with spiced potato masala and brushed with ghee", "avg_prep_time": 12},
    {"category": "Dosa", "item_name": "Mysore Masala Dosa", "price": 15.00, "item_desc": "A dosa spread with fiery Mysore chutney (made of chilies and lentils) and filled with spiced mashed potatoes. Available crispy or soft", "avg_prep_time": 13},
    {"category": "Dosa", "item_name": "Paneer Masala Dosa", "price": 16.00, "item_desc": "Dosa filled with spiced cottage cheese (paneer) and savory potato masala", "avg_prep_time": 13},
    {"category": "Dosa", "item_name": "Mixed Vegetable Dosa", "price": 15.00, "item_desc": "A golden dosa filled with a medley of sautéed vegetables seasoned with aromatic spices", "avg_prep_time": 13},
    {"category": "Dosa", "item_name": "Cauliflower Dosa", "price": 15.00, "item_desc": "Thin, crispy dosa stuffed with spiced cauliflower florets", "avg_prep_time": 13},
    {"category": "Dosa", "item_name": "Pav Bhaji Dosa", "price": 15.00, "item_desc": "A fusion dosa filled with Mumbai-style spicy mixed vegetable bhaji", "avg_prep_time": 13},
    {"category": "Dosa", "item_name": "Eggplant Dosa", "price": 15.00, "item_desc": "Dosa filled with roasted eggplant masala, offering a smoky, spiced flavor", "avg_prep_time": 13},
    {"category": "Dosa", "item_name": "Mushroom Dosa", "price": 15.00, "item_desc": "Crispy dosa packed with savory sautéed mushrooms and fragrant spices", "avg_prep_time": 13},
    {"category": "Dosa", "item_name": "Palak Paneer Dosa", "price": 16.00, "item_desc": "Dosa filled with vibrant spiced spinach (palak) and paneer", "avg_prep_time": 13},
    {"category": "Dosa", "item_name": "Palak Chicken Dosa", "price": 15.00, "item_desc": "Dosa filled with vibrant spiced spinach (palak) and chicken", "avg_prep_time": 13},
    {"category": "Dosa", "item_name": "Palak Lamb Dosa", "price": 16.00, "item_desc": "Dosa filled with vibrant spiced spinach (palak) and lamb", "avg_prep_time": 13},
    {"category": "Dosa", "item_name": "Palak Beef Dosa", "price": 16.00, "item_desc": "Dosa filled with vibrant spiced spinach (palak) and beef", "avg_prep_time": 13},
    {"category": "Dosa", "item_name": "Palak Shrimp Dosa", "price": 17.00, "item_desc": "Dosa filled with vibrant spiced spinach (palak) and shrimp", "avg_prep_time": 13},
    {"category": "Dosa", "item_name": "Set Dosa", "price": 15.00, "item_desc": "A set of three soft, fluffy dosas (thicker, pancake-style) served together", "avg_prep_time": 12},
    {"category": "Dosa", "item_name": "Egg Masala Dosa", "price": 12.00, "item_desc": "Dosa filled with spiced egg scramble", "avg_prep_time": 12},
    {"category": "Dosa", "item_name": "Chicken Masala Dosa", "price": 15.00, "item_desc": "Dosa filled with savory chicken masala", "avg_prep_time": 13},
    {"category": "Dosa", "item_name": "Lamb Masala Dosa", "price": 16.00, "item_desc": "Dosa filled with spiced lamb curry", "avg_prep_time": 13},
    {"category": "Dosa", "item_name": "Beef Masala Dosa", "price": 16.00, "item_desc": "Dosa filled with spiced beef curry", "avg_prep_time": 13},
    {"category": "Dosa", "item_name": "Fish Masala Dosa", "price": 16.00, "item_desc": "Dosa stuffed with flavorful fish curry masala", "avg_prep_time": 13},
    {"category": "Dosa", "item_name": "Shrimp Masala Dosa", "price": 17.00, "item_desc": "Dosa filled with seasoned shrimp masala", "avg_prep_time": 13},
    {"category": "Dosa", "item_name": "Chicken Chettinad Dosa", "price": 16.00, "item_desc": "Dosa filled with chicken cooked Chettinad-style – a fiery blend of roasted spices, curry leaves, and coconut", "avg_prep_time": 14},
    {"category": "Dosa", "item_name": "Lamb Chettinad Dosa", "price": 17.00, "item_desc": "Dosa filled with lamb cooked Chettinad-style – a fiery blend of roasted spices, curry leaves, and coconut", "avg_prep_time": 14},
    {"category": "Dosa", "item_name": "Beef Chettinad Dosa", "price": 17.00, "item_desc": "Dosa filled with beef cooked Chettinad-style – a fiery blend of roasted spices, curry leaves, and coconut", "avg_prep_time": 14},
    {"category": "Dosa", "item_name": "Shrimp Chettinad Dosa", "price": 17.00, "item_desc": "Dosa filled with shrimp cooked Chettinad-style – a fiery blend of roasted spices, curry leaves, and coconut", "avg_prep_time": 14},
    {"category": "Dosa", "item_name": "Chicken Pepper Dosa", "price": 16.00, "item_desc": "Dosa filled with chicken prepared with cracked black pepper, garlic, and spices for a bold kick", "avg_prep_time": 13},
    {"category": "Dosa", "item_name": "Lamb Pepper Dosa", "price": 17.00, "item_desc": "Dosa filled with lamb prepared with cracked black pepper, garlic, and spices for a bold kick", "avg_prep_time": 13},
    {"category": "Dosa", "item_name": "Beef Pepper Dosa", "price": 17.00, "item_desc": "Dosa filled with beef prepared with cracked black pepper, garlic, and spices for a bold kick", "avg_prep_time": 13},
    {"category": "Dosa", "item_name": "Shrimp Pepper Dosa", "price": 17.00, "item_desc": "Dosa filled with shrimp prepared with cracked black pepper, garlic, and spices for a bold kick", "avg_prep_time": 13},
    {"category": "Dosa", "item_name": "Paneer Butter Dosa", "price": 16.00, "item_desc": "Dosa filled with paneer simmered in a rich, creamy butter curry (makhani) sauce", "avg_prep_time": 13},
    {"category": "Dosa", "item_name": "Chicken Butter Dosa", "price": 17.00, "item_desc": "Dosa filled with chicken simmered in a rich, creamy butter curry (makhani) sauce", "avg_prep_time": 13},
    {"category": "Dosa", "item_name": "Lamb Butter Dosa", "price": 18.00, "item_desc": "Dosa filled with lamb simmered in a rich, creamy butter curry (makhani) sauce", "avg_prep_time": 13},
    {"category": "Dosa", "item_name": "Shrimp Butter Dosa", "price": 17.00, "item_desc": "Dosa filled with shrimp simmered in a rich, creamy butter curry (makhani) sauce", "avg_prep_time": 13},
    
    # Uthappam
    {"category": "Uthappam", "item_name": "Onion Chilli Uthappam", "price": 14.00, "item_desc": "A savory rice-lentil pancake topped with caramelized onions and green chilies", "avg_prep_time": 12},
    {"category": "Uthappam", "item_name": "Mixed Vegetables Uthappam", "price": 14.00, "item_desc": "Soft thick dosa topped with a colorful mix of diced vegetables", "avg_prep_time": 12},
    {"category": "Uthappam", "item_name": "401 Uthappam", "price": 14.00, "item_desc": "Uthappam topped with onions, tomatoes, paneer, green chilies, and sweet peppers", "avg_prep_time": 12},
    {"category": "Uthappam", "item_name": "Paneer Uthappam", "price": 17.00, "item_desc": "Thick dosa cooked with spiced paneer on top for added richness", "avg_prep_time": 13},
    
    # Curries
    {"category": "Curries", "item_name": "Vegetable Korma", "price": 17.00, "item_desc": "A creamy, mildly spiced coconut-milk curry with mixed vegetables. Served with two sides: your first choice of rice or plain dosa, and second choice of parotta, plain/garlic naan, rice or another plain dosa", "avg_prep_time": 18},
    {"category": "Curries", "item_name": "Chicken Korma", "price": 18.00, "item_desc": "A creamy, mildly spiced coconut-milk curry with tender chicken. Served with two sides: your first choice of rice or plain dosa, and second choice of parotta, plain/garlic naan, rice or another plain dosa", "avg_prep_time": 18},
    {"category": "Curries", "item_name": "Paneer Butter Masala", "price": 20.00, "item_desc": "Soft paneer cubes in a rich, buttery tomato gravy. Served with two sides", "avg_prep_time": 16},
    {"category": "Curries", "item_name": "Kadai Paneer", "price": 20.00, "item_desc": "Paneer stir-fried with bell peppers and onions in a bold spiced gravy. Served with two sides", "avg_prep_time": 16},
    {"category": "Curries", "item_name": "Dal Makhani", "price": 18.00, "item_desc": "Slow-cooked creamy black lentils in a buttery spiced sauce. Served with two sides", "avg_prep_time": 20},
    {"category": "Curries", "item_name": "Goat Curry", "price": 19.00, "item_desc": "Goat slow-cooked in a traditional South Indian curry sauce with coconut and spices. Served with two sides", "avg_prep_time": 25},
    {"category": "Curries", "item_name": "Chicken Curry", "price": 15.00, "item_desc": "Chicken slow-cooked in a traditional South Indian curry sauce with coconut and spices. Served with two sides", "avg_prep_time": 20},
    {"category": "Curries", "item_name": "Lamb Curry", "price": 20.00, "item_desc": "Lamb slow-cooked in a traditional South Indian curry sauce with coconut and spices. Served with two sides", "avg_prep_time": 25},
    {"category": "Curries", "item_name": "Beef Curry", "price": 20.00, "item_desc": "Beef slow-cooked in a traditional South Indian curry sauce with coconut and spices. Served with two sides", "avg_prep_time": 25},
    {"category": "Curries", "item_name": "Eggplant Masala", "price": 18.00, "item_desc": "Sautéed eggplant in a rich, tangy spiced tomato gravy. Served with two sides", "avg_prep_time": 15},
    {"category": "Curries", "item_name": "Beef Masala", "price": 21.00, "item_desc": "Slow-cooked beef in a flavorful tomato-based curry sauce. Served with two sides", "avg_prep_time": 25},
    {"category": "Curries", "item_name": "Vendakkai Masala", "price": 18.00, "item_desc": "Tender okra simmered in a spiced onion-tomato masala. Served with two sides", "avg_prep_time": 15},
    {"category": "Curries", "item_name": "Palak Paneer", "price": 20.00, "item_desc": "Spinach curry blended with spices and paneer. Served with two sides", "avg_prep_time": 16},
    {"category": "Curries", "item_name": "Palak Chicken", "price": 18.00, "item_desc": "Spinach curry blended with spices and chicken. Served with two sides", "avg_prep_time": 18},
    {"category": "Curries", "item_name": "Palak Lamb", "price": 21.00, "item_desc": "Spinach curry blended with spices and lamb. Served with two sides", "avg_prep_time": 20},
    {"category": "Curries", "item_name": "Chicken Sukka", "price": 20.00, "item_desc": "Dry-style roast of chicken with toasted spices and curry leaves. Served with two sides", "avg_prep_time": 18},
    {"category": "Curries", "item_name": "Lamb Sukka", "price": 24.00, "item_desc": "Dry-style roast of lamb with toasted spices and curry leaves. Served with two sides", "avg_prep_time": 20},
    {"category": "Curries", "item_name": "Butter Chicken", "price": 20.00, "item_desc": "Tandoori-grilled chicken simmered in the classic creamy tomato-butter sauce. Served with two sides", "avg_prep_time": 20},
    {"category": "Curries", "item_name": "Butter Lamb", "price": 22.00, "item_desc": "Tandoori-grilled lamb simmered in the classic creamy tomato-butter sauce. Served with two sides", "avg_prep_time": 22},
    {"category": "Curries", "item_name": "Butter Prawn", "price": 23.00, "item_desc": "Tandoori-grilled prawns simmered in the classic creamy tomato-butter sauce. Served with two sides", "avg_prep_time": 18},
    {"category": "Curries", "item_name": "Chettinad Chicken Curry", "price": 18.00, "item_desc": "Traditional Chettinad-style curry with a bold blend of roasted spices in a tomato-onion gravy. Served with two sides", "avg_prep_time": 20},
    {"category": "Curries", "item_name": "Chettinad Lamb Curry", "price": 20.00, "item_desc": "Traditional Chettinad-style curry with a bold blend of roasted spices in a tomato-onion gravy. Served with two sides", "avg_prep_time": 22},
    {"category": "Curries", "item_name": "Chettinad Beef Curry", "price": 20.00, "item_desc": "Traditional Chettinad-style curry with a bold blend of roasted spices in a tomato-onion gravy. Served with two sides", "avg_prep_time": 22},
    {"category": "Curries", "item_name": "Chettinad Prawn Curry", "price": 20.00, "item_desc": "Traditional Chettinad-style curry with a bold blend of roasted spices in a tomato-onion gravy. Served with two sides", "avg_prep_time": 18},
    {"category": "Curries", "item_name": "Malabar Fish Curry", "price": 20.00, "item_desc": "Coastal-style curry of fish in a tangy tamarind and coconut-based gravy. Served with two sides", "avg_prep_time": 18},
    {"category": "Curries", "item_name": "Prawn Pepper Masala", "price": 22.00, "item_desc": "Succulent prawns cooked with cracked black pepper, onions, and garlic in a robust spicy sauce. Served with two sides", "avg_prep_time": 18},
    
    # Kothu Parotta
    {"category": "Kothu Parotta", "item_name": "Vegetable Kothu Parotta", "price": 15.00, "item_desc": "Shredded South Indian parotta bread stir-fried with vegetables, plus spices and curry sauce", "avg_prep_time": 12},
    {"category": "Kothu Parotta", "item_name": "Egg Kothu Parotta", "price": 16.00, "item_desc": "Shredded South Indian parotta bread stir-fried with egg, plus spices and curry sauce", "avg_prep_time": 12},
    {"category": "Kothu Parotta", "item_name": "Chicken Kothu Parotta", "price": 17.00, "item_desc": "Shredded South Indian parotta bread stir-fried with chicken, plus spices and curry sauce", "avg_prep_time": 14},
    {"category": "Kothu Parotta", "item_name": "Lamb Kothu Parotta", "price": 17.00, "item_desc": "Shredded South Indian parotta bread stir-fried with lamb, plus spices and curry sauce", "avg_prep_time": 14},
    {"category": "Kothu Parotta", "item_name": "Beef Kothu Parotta", "price": 17.00, "item_desc": "Shredded South Indian parotta bread stir-fried with beef, plus spices and curry sauce", "avg_prep_time": 14},
    
    # Parotta Dishes
    {"category": "Parotta Dishes", "item_name": "Meat Parotta", "price": 18.00, "avg_prep_time": 15},
    {"category": "Parotta Dishes", "item_name": "Egg Parotta", "price": 16.00, "avg_prep_time": 12},
    {"category": "Parotta Dishes", "item_name": "2 Parotta with Veg Gravy", "price": 10.00, "avg_prep_time": 10},
    {"category": "Parotta Dishes", "item_name": "2 Parotta with Chicken Gravy", "price": 10.00, "avg_prep_time": 10},
    
    # Sides
    {"category": "Sides", "item_name": "Parotta", "price": 3.50, "avg_prep_time": 8},
    {"category": "Sides", "item_name": "Plain Naan", "price": 3.50, "avg_prep_time": 5},
    {"category": "Sides", "item_name": "Garlic Naan", "price": 4.50, "avg_prep_time": 6},
    {"category": "Sides", "item_name": "Chutney (2oz)", "price": 0.50, "item_desc": "Coconut or tomato chutney", "avg_prep_time": 1},
    {"category": "Sides", "item_name": "Chutney (4oz)", "price": 3.00, "item_desc": "Coconut or tomato chutney", "avg_prep_time": 1},
    {"category": "Sides", "item_name": "Raita (2oz)", "price": 0.50, "avg_prep_time": 2},
    {"category": "Sides", "item_name": "Raita (4oz)", "price": 4.00, "avg_prep_time": 2},
    {"category": "Sides", "item_name": "Pickle (2oz)", "price": 1.00, "avg_prep_time": 1},
    {"category": "Sides", "item_name": "Pickle (4oz)", "price": 4.00, "avg_prep_time": 1},
    {"category": "Sides", "item_name": "Sambar (4oz)", "price": 0.50, "item_desc": "Lentil soup", "avg_prep_time": 3},
    {"category": "Sides", "item_name": "Salna (4oz)", "price": 4.00, "item_desc": "Spicy gravy", "avg_prep_time": 3},
    
    # Biryani
    {"category": "Biryani", "item_name": "Chennai Street Style Biryani - Kushka (plain)", "price": 15.00, "item_desc": "Bold, spicy biryani made with fragrant basmati rice", "avg_prep_time": 25},
    {"category": "Biryani", "item_name": "Chennai Street Style Biryani - Vegetable", "price": 16.00, "item_desc": "Bold, spicy biryani made with fragrant basmati rice and vegetables", "avg_prep_time": 25},
    {"category": "Biryani", "item_name": "Chennai Street Style Biryani - Egg", "price": 16.00, "item_desc": "Bold, spicy biryani made with fragrant basmati rice and egg", "avg_prep_time": 25},
    {"category": "Biryani", "item_name": "Chennai Street Style Biryani - Chicken", "price": 16.00, "item_desc": "Bold, spicy biryani made with fragrant basmati rice and chicken", "avg_prep_time": 25},
    {"category": "Biryani", "item_name": "Chennai Street Style Biryani - Lamb", "price": 17.00, "item_desc": "Bold, spicy biryani made with fragrant basmati rice and lamb", "avg_prep_time": 25},
    {"category": "Biryani", "item_name": "Chennai Street Style Biryani - Beef", "price": 17.00, "item_desc": "Bold, spicy biryani made with fragrant basmati rice and beef", "avg_prep_time": 25},
    {"category": "Biryani", "item_name": "Chennai Street Style Biryani - Goat", "price": 17.00, "item_desc": "Bold, spicy biryani made with fragrant basmati rice and goat", "avg_prep_time": 25},
    {"category": "Biryani", "item_name": "Chennai Street Style Biryani - Prawn", "price": 18.00, "item_desc": "Bold, spicy biryani made with fragrant basmati rice and prawn", "avg_prep_time": 25},
    
    # Beverages - Cafe
    {"category": "Beverages", "item_name": "Masala Chai (spiced tea)", "price": 4.50, "avg_prep_time": 3},
    {"category": "Beverages", "item_name": "Coffee", "price": 4.50, "avg_prep_time": 3},
    {"category": "Beverages", "item_name": "Indian-Style Cold Coffee", "price": 8.00, "avg_prep_time": 4},
    {"category": "Beverages", "item_name": "Lassi - Mango", "price": 6.00, "avg_prep_time": 3},
    {"category": "Beverages", "item_name": "Lassi - Sweet", "price": 6.00, "avg_prep_time": 3},
    {"category": "Beverages", "item_name": "Lassi - Salted", "price": 6.00, "avg_prep_time": 3},
    {"category": "Beverages", "item_name": "Lassi - Buttermilk", "price": 7.00, "avg_prep_time": 3},
    {"category": "Beverages", "item_name": "Pop (Soft Drinks)", "price": 2.50, "item_desc": "Coke, Diet Coke, Ginger Ale, Orange Crush, Iced Tea, Root Beer, Sprite, or Club Soda", "avg_prep_time": 1},
    {"category": "Beverages", "item_name": "Coconut Water", "price": 5.00, "avg_prep_time": 1},
    
    # Specialty Shakes
    {"category": "Specialty Shakes", "item_name": "Chocolate Shake", "price": 7.00, "avg_prep_time": 4},
    {"category": "Specialty Shakes", "item_name": "Vanilla Shake", "price": 7.00, "avg_prep_time": 4},
    {"category": "Specialty Shakes", "item_name": "Strawberry Shake", "price": 7.00, "avg_prep_time": 4},
    {"category": "Specialty Shakes", "item_name": "Mango Shake", "price": 7.00, "avg_prep_time": 4},
    {"category": "Specialty Shakes", "item_name": "Oreo Shake", "price": 9.00, "avg_prep_time": 5},
    {"category": "Specialty Shakes", "item_name": "KitKat Shake", "price": 9.00, "avg_prep_time": 5},
    {"category": "Specialty Shakes", "item_name": "HOD's Exclusive Mango Shake", "price": 10.00, "item_desc": "Signature deluxe mango shake", "avg_prep_time": 5},
    {"category": "Specialty Shakes", "item_name": "Caramel Shake", "price": 8.00, "avg_prep_time": 4},
    {"category": "Specialty Shakes", "item_name": "Gulab Jamun Shake", "price": 10.00, "item_desc": "Blended with the classic Indian sweet", "avg_prep_time": 5},
    {"category": "Specialty Shakes", "item_name": "Rasmalai Shake", "price": 10.00, "item_desc": "Inspired by the Indian dessert with cardamom & saffron", "avg_prep_time": 5},
    {"category": "Specialty Shakes", "item_name": "Red Velvet Shake", "price": 10.00, "avg_prep_time": 5},
]

def main():
    """Main function to seed pilot restaurant data."""
    print("=" * 60)
    print("Seeding Pilot Restaurant Data")
    print("=" * 60)
    
    connection = get_connection()
    
    restaurants = [
        {
            "name": "Amici Italian Grill & Lounge",
            "address": "500 Country Hills Blvd NE #313, Calgary, AB T3K 5K3",
            "phone_number": "+14032265345",
            "twilio_phone_number": "+14032265345",
            "menu": amici_menu
        },
        {
            "name": "Biryani Lounge Restaurant and Bar",
            "address": "1184 Denman St, Vancouver, BC V6G 2M9",
            "phone_number": "+16046099999",
            "twilio_phone_number": "+16046099999",
            "menu": biryani_menu
        },
        {
            "name": "Coco Rico Cafe",
            "address": "1290 Robson St, Vancouver, BC V6E 2B1",
            "phone_number": "+16046870424",
            "twilio_phone_number": "+16046870424",
            "menu": coco_rico_menu
        },
        {
            "name": "House of Dosas",
            "address": "1391 Kingsway, Vancouver, BC V5V 3E3",
            "phone_number": "+16048751283",
            "twilio_phone_number": "+16048751283",
            "menu": house_of_dosas_menu
        }
    ]
    
    try:
        for restaurant_data in restaurants:
            print(f"\n[INFO] Processing: {restaurant_data['name']}")
            print("-" * 60)
            
            # Add restaurant
            restaurant_id = add_restaurant(connection, restaurant_data)
            
            # Add menu items
            print(f"  Adding {len(restaurant_data['menu'])} menu items...")
            add_menu_items(connection, restaurant_id, restaurant_data['menu'])
        
        print("\n" + "=" * 60)
        print("[SUCCESS] All pilot restaurants and menus seeded successfully!")
        print("=" * 60)
        print("\nTwilio Numbers for testing:")
        for r in restaurants:
            print(f"  - {r['name']}: {r['twilio_phone_number']}")
        
    except Error as e:
        print(f"\n[ERROR] Error seeding data: {e}")
        connection.rollback()
    finally:
        if connection.is_connected():
            connection.close()
            print("\nDatabase connection closed")

if __name__ == "__main__":
    main()

