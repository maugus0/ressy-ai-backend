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
            print(f"✓ Restaurant '{restaurant_data['name']}' already exists with id: {restaurant_id}")
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
        print(f"✓ Added restaurant '{restaurant_data['name']}' with id: {restaurant_id}")
        
        cursor.close()
        return restaurant_id
        
    except Error as e:
        print(f"✗ Error adding restaurant {restaurant_data['name']}: {e}")
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
                    print(f"  ✗ Error adding menu item '{item['item_name']}': {e}")
        
        connection.commit()
        cursor.close()
        print(f"  ✓ Added {added_count} menu items (skipped {skipped_count} duplicates)")
        
    except Error as e:
        print(f"✗ Error adding menu items: {e}")
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

# Restaurant 3: Coco Rico Cafe (limited menu data provided)
coco_rico_menu = [
    # Note: Full menu not provided, adding placeholder items based on cafe style
    {"category": "Beverages", "item_name": "Coffee", "price": 4.50, "avg_prep_time": 3},
    {"category": "Beverages", "item_name": "Espresso", "price": 3.50, "avg_prep_time": 2},
    {"category": "Beverages", "item_name": "Cappuccino", "price": 5.00, "avg_prep_time": 4},
    {"category": "Beverages", "item_name": "Latte", "price": 5.50, "avg_prep_time": 4},
    {"category": "Desserts", "item_name": "Pastries", "price": 6.00, "avg_prep_time": 2},
    {"category": "Desserts", "item_name": "Cakes", "price": 8.00, "avg_prep_time": 2},
]

# Restaurant 4: House of Dosas (limited menu data provided)
house_of_dosas_menu = [
    # Note: Full menu not provided, adding common dosa items
    {"category": "Dosas", "item_name": "Plain Dosa", "price": 8.00, "avg_prep_time": 10},
    {"category": "Dosas", "item_name": "Masala Dosa", "price": 10.00, "avg_prep_time": 12},
    {"category": "Dosas", "item_name": "Onion Dosa", "price": 9.00, "avg_prep_time": 11},
    {"category": "Dosas", "item_name": "Rava Dosa", "price": 11.00, "avg_prep_time": 12},
    {"category": "Dosas", "item_name": "Paper Dosa", "price": 9.50, "avg_prep_time": 10},
    {"category": "Dosas", "item_name": "Ghee Dosa", "price": 12.00, "avg_prep_time": 11},
    {"category": "Dosas", "item_name": "Butter Dosa", "price": 11.50, "avg_prep_time": 11},
    {"category": "Dosas", "item_name": "Mysore Masala Dosa", "price": 12.00, "avg_prep_time": 13},
    {"category": "Dosas", "item_name": "Uttapam", "price": 10.00, "avg_prep_time": 12},
    {"category": "Dosas", "item_name": "Idli", "price": 7.00, "avg_prep_time": 8},
    {"category": "Dosas", "item_name": "Vada", "price": 6.00, "avg_prep_time": 8},
    {"category": "Beverages", "item_name": "Chai", "price": 3.50, "avg_prep_time": 3},
    {"category": "Beverages", "item_name": "Coffee", "price": 3.50, "avg_prep_time": 3},
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
            print(f"\n📋 Processing: {restaurant_data['name']}")
            print("-" * 60)
            
            # Add restaurant
            restaurant_id = add_restaurant(connection, restaurant_data)
            
            # Add menu items
            print(f"  Adding {len(restaurant_data['menu'])} menu items...")
            add_menu_items(connection, restaurant_id, restaurant_data['menu'])
        
        print("\n" + "=" * 60)
        print("✓ All pilot restaurants and menus seeded successfully!")
        print("=" * 60)
        print("\nTwilio Numbers for testing:")
        for r in restaurants:
            print(f"  • {r['name']}: {r['twilio_phone_number']}")
        
    except Error as e:
        print(f"\n✗ Error seeding data: {e}")
        connection.rollback()
    finally:
        if connection.is_connected():
            connection.close()
            print("\nDatabase connection closed")

if __name__ == "__main__":
    main()

