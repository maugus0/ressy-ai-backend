"""
Seed script for Frying Pan waitlist menu with customization options.

Usage:
  python scripts/seed_frying_pan_menu.py --restaurant-id 1
"""

from __future__ import annotations

import argparse
import os
from typing import Any, Dict, List, Optional

import mysql.connector
from dotenv import load_dotenv


def _db_config() -> Dict[str, Any]:
    load_dotenv()
    return {
        "host": os.getenv("DB_HOST", os.getenv("MYSQL_HOST", "localhost")),
        "database": os.getenv("DB_NAME", os.getenv("MYSQL_DATABASE", "ressy")),
        "user": os.getenv("DB_USERNAME", os.getenv("MYSQL_USER", "root")),
        "password": os.getenv("DB_PASSWORD", os.getenv("MYSQL_PASSWORD", "root")),
        "port": int(os.getenv("DB_PORT", os.getenv("MYSQL_PORT", 3306))),
    }


def _fetch_one(cursor, query: str, params: tuple) -> Optional[Dict[str, Any]]:
    cursor.execute(query, params)
    return cursor.fetchone()


def _ensure_menu_item(cursor, restaurant_id: int, item: Dict[str, Any]) -> int:
    row = _fetch_one(
        cursor,
        "SELECT id FROM Menus WHERE restaurant_id = %s AND item_name = %s LIMIT 1",
        (restaurant_id, item["item_name"]),
    )
    if row:
        cursor.execute(
            """
            UPDATE Menus
            SET category = %s,
                sub_category = %s,
                item_desc = %s,
                price = %s,
                avg_prep_time = %s,
                is_available = %s,
                is_special = %s
            WHERE id = %s
            """,
            (
                item.get("category"),
                item.get("sub_category"),
                item.get("item_desc"),
                item.get("price"),
                item.get("avg_prep_time"),
                item.get("is_available", True),
                item.get("is_special", False),
                row["id"],
            ),
        )
        return int(row["id"])
    cursor.execute(
        """
        INSERT INTO Menus (
            restaurant_id, category, sub_category, item_name, item_desc, price, avg_prep_time,
            is_available, is_special, created_at, updated_at
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
        """,
        (
            restaurant_id,
            item.get("category"),
            item.get("sub_category"),
            item["item_name"],
            item.get("item_desc"),
            item.get("price"),
            item.get("avg_prep_time"),
            item.get("is_available", True),
            item.get("is_special", False),
        ),
    )
    return int(cursor.lastrowid)


def _ensure_option_group(cursor, restaurant_id: int, group: Dict[str, Any]) -> int:
    row = _fetch_one(
        cursor,
        "SELECT id FROM Menu_Option_Groups WHERE restaurant_id = %s AND name = %s LIMIT 1",
        (restaurant_id, group["name"]),
    )
    if row:
        cursor.execute(
            """
            UPDATE Menu_Option_Groups
            SET description = %s,
                selection_type = %s,
                min_select = %s,
                max_select = %s,
                free_allowance = %s,
                allows_quantity = %s,
                max_quantity_per_option = %s,
                prompt_style = %s,
                is_required = %s,
                is_available = %s,
                sort_order = %s
            WHERE id = %s
            """,
            (
                group.get("description"),
                group.get("selection_type", "multiple"),
                group.get("min_select", 0),
                group.get("max_select"),
                group.get("free_allowance", 0),
                group.get("allows_quantity", False),
                group.get("max_quantity_per_option"),
                group.get("prompt_style", "ASK_IF_MENTIONED"),
                group.get("is_required", False),
                group.get("is_available", True),
                group.get("sort_order", 0),
                row["id"],
            ),
        )
        return int(row["id"])
    cursor.execute(
        """
        INSERT INTO Menu_Option_Groups (
            restaurant_id, name, description, selection_type, min_select, max_select,
            free_allowance, allows_quantity, max_quantity_per_option, prompt_style,
            is_required, is_available, sort_order, created_at, updated_at
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
        """,
        (
            restaurant_id,
            group["name"],
            group.get("description"),
            group.get("selection_type", "multiple"),
            group.get("min_select", 0),
            group.get("max_select"),
            group.get("free_allowance", 0),
            group.get("allows_quantity", False),
            group.get("max_quantity_per_option"),
            group.get("prompt_style", "ASK_IF_MENTIONED"),
            group.get("is_required", False),
            group.get("is_available", True),
            group.get("sort_order", 0),
        ),
    )
    return int(cursor.lastrowid)


def _ensure_option_value(cursor, group_id: int, value: Dict[str, Any]) -> int:
    row = _fetch_one(
        cursor,
        "SELECT id FROM Menu_Option_Values WHERE group_id = %s AND name = %s LIMIT 1",
        (group_id, value["name"]),
    )
    if row:
        cursor.execute(
            """
            UPDATE Menu_Option_Values
            SET price_delta = %s,
                is_default = %s,
                is_available = %s,
                sort_order = %s
            WHERE id = %s
            """,
            (
                value.get("price_delta", 0),
                value.get("is_default", False),
                value.get("is_available", True),
                value.get("sort_order", 0),
                row["id"],
            ),
        )
        return int(row["id"])
    cursor.execute(
        """
        INSERT INTO Menu_Option_Values (
            group_id, name, price_delta, is_default, is_available, sort_order, created_at, updated_at
        )
        VALUES (%s, %s, %s, %s, %s, %s, NOW(), NOW())
        """,
        (
            group_id,
            value["name"],
            value.get("price_delta", 0),
            value.get("is_default", False),
            value.get("is_available", True),
            value.get("sort_order", 0),
        ),
    )
    return int(cursor.lastrowid)


def _attach_group_to_item(cursor, menu_item_id: int, group_id: int, overrides: Optional[Dict[str, Any]] = None) -> None:
    overrides = overrides or {}
    cursor.execute(
        """
        INSERT INTO Menu_Item_Option_Groups (
            menu_item_id,
            group_id,
            min_select_override,
            max_select_override,
            free_allowance_override,
            allows_quantity_override,
            max_quantity_per_option_override,
            is_required_override,
            sort_order,
            created_at,
            updated_at
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
        ON DUPLICATE KEY UPDATE
            min_select_override = VALUES(min_select_override),
            max_select_override = VALUES(max_select_override),
            free_allowance_override = VALUES(free_allowance_override),
            allows_quantity_override = VALUES(allows_quantity_override),
            max_quantity_per_option_override = VALUES(max_quantity_per_option_override),
            is_required_override = VALUES(is_required_override),
            sort_order = VALUES(sort_order),
            updated_at = NOW()
        """,
        (
            menu_item_id,
            group_id,
            overrides.get("min_select_override"),
            overrides.get("max_select_override"),
            overrides.get("free_allowance_override"),
            overrides.get("allows_quantity_override"),
            overrides.get("max_quantity_per_option_override"),
            overrides.get("is_required_override"),
            overrides.get("sort_order", 0),
        ),
    )


def _menu_items() -> List[Dict[str, Any]]:
    return [
        {
            "category": "Chicken Sandwiches",
            "sub_category": "White Meat (Chicken Breast)",
            "item_name": "OG Hot Chicken",
            "price": 15.5,
            "item_desc": "Nashville st hot chicken breast with frying pan hot dust, spicy mayo, cabbage slaw, pickles",
        },
        {
            "category": "Chicken Sandwiches",
            "sub_category": "White Meat (Chicken Breast)",
            "item_name": "Hot & Sweet Honey Garlic",
            "price": 17.5,
            "item_desc": "Chicken breast, honey garlic sauce, spicy mayo, marble cheese, cabbage slaw, pickles",
        },
        {
            "category": "Chicken Sandwiches",
            "sub_category": "White Meat (Chicken Breast)",
            "item_name": "Korean Mozza Yang-Nyeom",
            "price": 17.9,
            "item_desc": "Chicken breast, Korean yang-nyeom sauce, house mayo, grilled mozza, lettuce, pickles",
        },
        {
            "category": "Chicken Sandwiches",
            "sub_category": "White Meat (Chicken Breast)",
            "item_name": "Waffle Sando",
            "price": 17.0,
            "item_desc": "Nashville st hot chicken breast with frying pan hot dust, marble cheese, powdered sugar, house-made maple butter syrup",
        },
        {
            "category": "Chicken Sandwiches",
            "sub_category": "Dark Meat (Chicken Thigh)",
            "item_name": "Hot Crunch",
            "price": 14.5,
            "item_desc": "Chicken thigh, house mayo, cabbage slaw, pickles",
        },
        {
            "category": "Chicken Sandwiches",
            "sub_category": "Dark Meat (Chicken Thigh)",
            "item_name": "Double Crunch",
            "price": 16.9,
            "item_desc": "2 pieces chicken thighs, house mayo, cabbage slaw, pickles",
        },
        {
            "category": "Chicken Sandwiches",
            "sub_category": "Dark Meat (Chicken Thigh)",
            "item_name": "K-Mix Double Decker",
            "price": 18.5,
            "item_desc": "2 pieces chicken thighs sauced with sweet soy and yang-nyeom, house mayo, marble cheese, lettuce, pickles",
        },
        {
            "category": "Fries",
            "sub_category": None,
            "item_name": "Dirty Chicken",
            "price": 18.5,
            "item_desc": "Waffle fries, tenders with hot dust, marble cheese, green onion, slaw, pickles, sweet soy sauce, spicy mayo",
        },
        {
            "category": "Fries",
            "sub_category": None,
            "item_name": "Smoked Beef",
            "price": 17.9,
            "item_desc": "Waffle fries, beef bulgogi, marble cheese, green onion, sour cream, sweet soy sauce, house mayo",
        },
        {
            "category": "Fries",
            "sub_category": None,
            "item_name": "Pulled Chicken",
            "price": 16.9,
            "item_desc": "Waffle fries, pulled chicken, green onion, marble cheese, sour cream, sweet soy sauce, spicy mayo",
        },
        {
            "category": "Fries",
            "sub_category": None,
            "item_name": "Fried Tofu",
            "price": 17.5,
            "item_desc": "Waffle fries, fried tofu with hot dust, marble cheese, green onion, slaw, pickles, sweet soy sauce, spicy mayo",
        },
        {
            "category": "Fries",
            "sub_category": None,
            "item_name": "Bacon Cheese",
            "price": 14.5,
            "item_desc": "Waffle fries, bacon crumble, marble cheese, jalapeno cheese sauce, green onion",
        },
        {
            "category": "Fries",
            "sub_category": None,
            "item_name": "Waffle Fries",
            "price": 6.5,
            "item_desc": "Served with house mayo and ketchup",
        },
        {
            "category": "Fries",
            "sub_category": None,
            "item_name": "Yam Fries",
            "price": 7.5,
            "item_desc": "Served with house mayo and ketchup",
        },
    ]


def _option_groups() -> List[Dict[str, Any]]:
    return [
        {
            "name": "Spice Level",
            "description": "Choose your heat level",
            "selection_type": "single",
            "min_select": 0,
            "max_select": 1,
            "free_allowance": 0,
            "allows_quantity": False,
            "prompt_style": "ASK_ALWAYS",
            "is_required": False,
            "sort_order": 1,
            "values": [
                {"name": "No Heat", "price_delta": 0, "is_default": True, "sort_order": 0},
                {"name": "Mild Hot", "price_delta": 0, "sort_order": 1},
                {"name": "Medium Hot", "price_delta": 0, "sort_order": 2},
                {"name": "Extra Hot", "price_delta": 0, "sort_order": 3},
                {"name": "911", "price_delta": 0.5, "sort_order": 4},
            ],
        },
        {
            "name": "Sandwich Add-ons",
            "description": "Add extra items to your sandwich",
            "selection_type": "multiple",
            "min_select": 0,
            "max_select": None,
            "free_allowance": 0,
            "allows_quantity": False,
            "prompt_style": "ASK_IF_MENTIONED",
            "is_required": False,
            "sort_order": 2,
            "values": [
                {"name": "Egg", "price_delta": 2.5, "sort_order": 0},
                {"name": "Cheese", "price_delta": 1.5, "sort_order": 1},
                {"name": "Egg + Cheese", "price_delta": 3.5, "sort_order": 2},
                {"name": "Pickled Jalapeno", "price_delta": 1.0, "sort_order": 3},
                {"name": "Corn Slaw", "price_delta": 3.5, "sort_order": 4},
                {"name": "Grilled Mozza", "price_delta": 3.0, "sort_order": 5},
                {"name": "Bacon (2 slices)", "price_delta": 3.0, "sort_order": 6},
                {"name": "Hash Brown", "price_delta": 2.0, "sort_order": 7},
            ],
        },
        {
            "name": "Make It Combo",
            "description": "Served with house mayo and ketchup",
            "selection_type": "single",
            "min_select": 0,
            "max_select": 1,
            "free_allowance": 0,
            "allows_quantity": False,
            "prompt_style": "ASK_ALWAYS",
            "is_required": False,
            "sort_order": 3,
            "values": [
                {"name": "Waffle Fries", "price_delta": 4.5, "sort_order": 0},
                {"name": "Yam Fries", "price_delta": 5.5, "sort_order": 1},
                {"name": "Fries + Pop (Waffle Fries)", "price_delta": 6.0, "sort_order": 2},
                {"name": "Fries + Pop (Yam Fries)", "price_delta": 7.0, "sort_order": 3},
                {"name": "Fries + Corn Slaw (Waffle Fries)", "price_delta": 6.5, "sort_order": 4},
                {"name": "Fries + Corn Slaw (Yam Fries)", "price_delta": 7.5, "sort_order": 5},
            ],
        },
        {
            "name": "Fries Add-ons",
            "description": "Add extra toppings to fries",
            "selection_type": "multiple",
            "min_select": 0,
            "max_select": None,
            "free_allowance": 0,
            "allows_quantity": False,
            "prompt_style": "ASK_IF_MENTIONED",
            "is_required": False,
            "sort_order": 4,
            "values": [
                {"name": "Egg", "price_delta": 2.5, "sort_order": 0},
                {"name": "Pickles", "price_delta": 1.0, "sort_order": 1},
                {"name": "Pickled Jalapeno", "price_delta": 1.0, "sort_order": 2},
                {"name": "Extra Cheese", "price_delta": 1.5, "sort_order": 3},
                {"name": "Bacon Crumble", "price_delta": 3.0, "sort_order": 4},
                {"name": "Sour Cream", "price_delta": 1.5, "sort_order": 5},
            ],
        },
        {
            "name": "House-made Dips (2oz)",
            "description": "Optional dipping sauces",
            "selection_type": "multiple",
            "min_select": 0,
            "max_select": None,
            "free_allowance": 0,
            "allows_quantity": False,
            "prompt_style": "ASK_IF_MENTIONED",
            "is_required": False,
            "sort_order": 5,
            "values": [
                {"name": "Spicy Mayo", "price_delta": 1.5, "sort_order": 0},
                {"name": "House Mayo", "price_delta": 1.5, "sort_order": 1},
                {"name": "911 Spicy Mayo", "price_delta": 2.0, "sort_order": 2},
                {"name": "Korean Yang-Nyeom", "price_delta": 2.0, "sort_order": 3},
                {"name": "Sweet Soy", "price_delta": 1.5, "sort_order": 4},
                {"name": "Honey Mustard", "price_delta": 1.5, "sort_order": 5},
                {"name": "Jalapeno Cheese (3oz)", "price_delta": 3.0, "sort_order": 6},
            ],
        },
    ]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--restaurant-id", type=int, required=True, help="Restaurant ID to seed menu for")
    args = parser.parse_args()

    conn = mysql.connector.connect(**_db_config())
    try:
        cursor = conn.cursor(dictionary=True)

        item_rows = _menu_items()
        option_groups = _option_groups()

        menu_ids: Dict[str, int] = {}
        for item in item_rows:
            menu_id = _ensure_menu_item(cursor, args.restaurant_id, item)
            menu_ids[item["item_name"]] = menu_id

        group_ids: Dict[str, int] = {}
        for group in option_groups:
            group_id = _ensure_option_group(cursor, args.restaurant_id, group)
            group_ids[group["name"]] = group_id
            for value in group.get("values", []):
                _ensure_option_value(cursor, group_id, value)

        chicken_sandwich_items = [
            "OG Hot Chicken",
            "Hot & Sweet Honey Garlic",
            "Korean Mozza Yang-Nyeom",
            "Waffle Sando",
            "Hot Crunch",
            "Double Crunch",
            "K-Mix Double Decker",
        ]
        fries_items = [
            "Dirty Chicken",
            "Smoked Beef",
            "Pulled Chicken",
            "Fried Tofu",
            "Bacon Cheese",
            "Waffle Fries",
            "Yam Fries",
        ]

        for item_name in chicken_sandwich_items:
            menu_id = menu_ids[item_name]
            _attach_group_to_item(cursor, menu_id, group_ids["Spice Level"])
            _attach_group_to_item(cursor, menu_id, group_ids["Sandwich Add-ons"])
            _attach_group_to_item(cursor, menu_id, group_ids["Make It Combo"])
            _attach_group_to_item(cursor, menu_id, group_ids["House-made Dips (2oz)"])

        for item_name in fries_items:
            menu_id = menu_ids[item_name]
            _attach_group_to_item(cursor, menu_id, group_ids["Spice Level"])
            _attach_group_to_item(cursor, menu_id, group_ids["Fries Add-ons"])
            _attach_group_to_item(cursor, menu_id, group_ids["House-made Dips (2oz)"])

        conn.commit()
        print("Seed completed.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
