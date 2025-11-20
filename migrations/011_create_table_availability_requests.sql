-- Migration: Create Table_Availability_Requests table
-- Description: Stores table availability requests

CREATE TABLE IF NOT EXISTS Table_Availability_Requests (
    id INT AUTO_INCREMENT PRIMARY KEY,
    restaurant_id INT NOT NULL,
    start_date_time DATETIME NOT NULL,
    party_size INT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (restaurant_id) REFERENCES Restaurants(id) ON DELETE CASCADE ON UPDATE CASCADE,
    INDEX idx_restaurant_id (restaurant_id),
    INDEX idx_start_date_time (start_date_time),
    INDEX idx_created_at (created_at),
    INDEX idx_restaurant_datetime (restaurant_id, start_date_time)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

