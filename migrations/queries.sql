-- SQL Queries for Multitenant WebSocket Operations

-- 1. Get Restaurant by Twilio Phone Number
-- Used to identify which restaurant a call belongs to
SELECT 
    id,
    name,
    address,
    phone_number,
    twilio_phone_number,
    twilio_details,
    deepgram_details,
    open_table_details,
    forward_minutes,
    backward_minutes,
    is_credit_card_required_for_reservation,
    created_at,
    updated_at
FROM Restaurants
WHERE twilio_phone_number = ?;

-- 2. Get Available Menu Items for a Restaurant
-- Only fetches items where is_available = TRUE
SELECT 
    id,
    restaurant_id,
    category,
    sub_category,
    item_name,
    item_desc,
    price,
    avg_prep_time,
    suggested_items,
    is_available,
    is_special,
    created_at,
    updated_at
FROM Menus
WHERE restaurant_id = ? 
  AND is_available = TRUE
ORDER BY category, sub_category, item_name;

-- 3. Get FAQs for a Restaurant
SELECT 
    id,
    restaurant_id,
    question,
    answer,
    created_at,
    updated_at
FROM FAQs
WHERE restaurant_id = ?
ORDER BY id;

-- 4. Insert or Update User
-- Used to store/update user information extracted from conversation
INSERT INTO Users (name, phone_number, email, address, is_spam, credit_card, created_at, updated_at)
VALUES (?, ?, ?, ?, ?, ?, NOW(), NOW())
ON DUPLICATE KEY UPDATE
    name = VALUES(name),
    email = VALUES(email),
    address = VALUES(address),
    is_spam = VALUES(is_spam),
    credit_card = VALUES(credit_card),
    updated_at = NOW();

-- Alternative: Insert User if not exists (by phone_number or email)
INSERT INTO Users (name, phone_number, email, address, is_spam, credit_card, created_at, updated_at)
SELECT ?, ?, ?, ?, ?, ?, NOW(), NOW()
WHERE NOT EXISTS (
    SELECT 1 FROM Users 
    WHERE (phone_number = ? AND phone_number IS NOT NULL)
       OR (email = ? AND email IS NOT NULL)
);

-- 5. Create Order
-- Used to store order information extracted from conversation
INSERT INTO Orders (user_id, status, total_amount, order_details, customization, created_at, updated_at)
VALUES (?, ?, ?, ?, ?, NOW(), NOW());

-- 6. Create Order Details
-- Used to store individual menu items in an order
INSERT INTO Order_Details (order_id, menu_item_id, created_at, updated_at)
VALUES (?, ?, NOW(), NOW());

-- 7. Get User ID by Phone Number or Email
-- Used to find existing user when creating orders
SELECT id 
FROM Users 
WHERE (phone_number = ? AND phone_number IS NOT NULL)
   OR (email = ? AND email IS NOT NULL)
LIMIT 1;

-- 8. Create Transcript
-- Used to store complete call transcript
INSERT INTO Transcripts (user_id, order_id, call_log, created_at, updated_at)
VALUES (?, ?, ?, NOW(), NOW());

-- 9. Get Last Inserted Order ID
-- Used after creating an order to get the order_id for order_details
SELECT LAST_INSERT_ID() AS order_id;

-- 10. Get Menu Item by Name (for order details)
-- Used to find menu_item_id when user mentions item names
SELECT id, restaurant_id, item_name, price
FROM Menus
WHERE restaurant_id = ?
  AND LOWER(item_name) LIKE LOWER(?)
  AND is_available = TRUE
LIMIT 1;

