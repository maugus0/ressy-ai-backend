-- Migration: Create Menus table
-- Description: Stores menu items for restaurants

CREATE TABLE IF NOT EXISTS Menus (
    id INT AUTO_INCREMENT PRIMARY KEY,
    restaurant_id INT NOT NULL,
    category VARCHAR(100),
    sub_category VARCHAR(100),
    item_name VARCHAR(255) NOT NULL,
    item_desc TEXT COMMENT 'Optional item description',
    price DECIMAL(10, 2) NOT NULL,
    avg_prep_time INT COMMENT 'Average preparation time in minutes',
    suggested_items JSON COMMENT 'Array of suggested item IDs',
    is_available BOOLEAN DEFAULT TRUE,
    is_special BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (restaurant_id) REFERENCES Restaurants(id) ON DELETE CASCADE ON UPDATE CASCADE,
    INDEX idx_restaurant_id (restaurant_id),
    INDEX idx_category (category),
    INDEX idx_sub_category (sub_category),
    INDEX idx_item_name (item_name),
    INDEX idx_is_available (is_available),
    INDEX idx_is_special (is_special),
    INDEX idx_created_at (created_at),
    INDEX idx_restaurant_category (restaurant_id, category)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

