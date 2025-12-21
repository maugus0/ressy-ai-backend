-- Migration: Create User_Restaurant_Metadata table
-- Description: Maps users to restaurants they are associated with (e.g., created via dashboard)
-- This allows tracking which restaurants a user "belongs to" without limiting them to one restaurant

CREATE TABLE IF NOT EXISTS User_Restaurant_Metadata (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    restaurant_id INT NOT NULL,
    source VARCHAR(50) NOT NULL DEFAULT 'dashboard' COMMENT 'How the association was created: dashboard, reservation, call',
    notes TEXT COMMENT 'Optional notes about the user-restaurant relationship',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES Users(id) ON DELETE CASCADE ON UPDATE CASCADE,
    FOREIGN KEY (restaurant_id) REFERENCES Restaurants(id) ON DELETE CASCADE ON UPDATE CASCADE,
    UNIQUE KEY unique_user_restaurant (user_id, restaurant_id),
    INDEX idx_user_id (user_id),
    INDEX idx_restaurant_id (restaurant_id),
    INDEX idx_source (source),
    INDEX idx_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

